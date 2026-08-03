import asyncio
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Optional

import aiohttp
import aiosqlite
import discord
from discord import Embed
from discord.ext import commands, tasks
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "db"
BOT_DB = DB_DIR / "bot.db"
LEAVE_DB = DB_DIR / "leave.db"
TICKETS_DB = DB_DIR / "tickets.db"
TIKTOK_DB = DB_DIR / "tiktok.db"
BOTCHANNEL_DB = DB_DIR / "botchannel.db"
ROLEPERMS_DB = DB_DIR / "roleperms.db"

DEFAULT_PREFIX = os.getenv("BOT_PREFIX", ">").strip() or ">"
BOT_NAME = os.getenv("BOT_NAME", "Bezms Bot")
OWNER_IDS = [int(x.strip()) for x in os.getenv("OWNER_IDS", "").split(",") if x.strip().isdigit()]
API_ENABLED = os.getenv("API_ENABLED", "false").lower() in ("true", "1", "yes")
API_PORT = int(os.getenv("API_PORT", "8000"))

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix=lambda bot, msg: get_prefix(bot, msg), intents=intents, help_command=None, case_insensitive=True)

ALL_MOD_COMMANDS = {
    "ping",
    "purge",
    "lockall",
    "unlockall",
    "hideall",
    "unhideall",
    "give",
    "nuke",
    "slowmode",
    "unslowmode",
    "gtfo",
    "kick",
    "ban",
    "mute",
    "unmute",
    "warn",
    "ticket_close",
}

ROLE_COMMAND_MAP = {
    "admin": ALL_MOD_COMMANDS,
    "administrator": ALL_MOD_COMMANDS,
    "owner": ALL_MOD_COMMANDS,
    "mod": {"kick", "ban", "mute", "warn", "purge", "lockall", "unlockall", "hideall", "unhideall", "slowmode", "unslowmode", "ticket_close"},
    "moderator": {"kick", "ban", "mute", "warn", "purge", "lockall", "unlockall", "hideall", "unhideall", "slowmode", "unslowmode", "ticket_close"},
    "staff": {"kick", "ban", "mute", "warn", "purge", "lockall", "unlockall", "hideall", "unhideall", "slowmode", "unslowmode", "ticket_close"},
    "helper": {"mute", "warn", "slowmode", "unslowmode", "purge"},
    "support": {"mute", "warn", "slowmode", "unslowmode", "purge"},
    "trial": {"purge", "slowmode", "unslowmode"},
    "junior": {"purge", "slowmode", "unslowmode"},
}

WELCOME_DEFAULT_MESSAGE = "{user} left {server}. We now have {member_count} members."
TIKTOK_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def get_prefix(bot: commands.Bot, message: discord.Message):
    if not message.guild:
        return commands.when_mentioned_or(DEFAULT_PREFIX)(bot, message)
    prefix = await fetch_prefix(message.guild.id)
    return commands.when_mentioned_or(prefix)(bot, message)


async def execute_sql(db_path: Path, query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False):
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cursor = await db.execute(query, params)
        if fetchone:
            row = await cursor.fetchone()
            await db.commit()
            return row
        if fetchall:
            rows = await cursor.fetchall()
            await db.commit()
            return rows
        await db.commit()
        return cursor.lastrowid


async def ensure_database_files():
    DB_DIR.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(BOT_DB) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS bot_prefixes(guild_id INTEGER PRIMARY KEY, prefix TEXT NOT NULL)"
        )
        await db.commit()

    async with aiosqlite.connect(LEAVE_DB) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS leave_config(guild_id INTEGER PRIMARY KEY, channel_id INTEGER, mode TEXT, message TEXT, autodelete INTEGER DEFAULT 0, embed INTEGER DEFAULT 0)"
        )
        await db.commit()

    async with aiosqlite.connect(TICKETS_DB) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS ticket_config(guild_id INTEGER PRIMARY KEY, category_id INTEGER, role_id INTEGER)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS ticket_open(guild_id INTEGER, user_id INTEGER, channel_id INTEGER, open INTEGER DEFAULT 1, created_at INTEGER)"
        )
        await db.commit()

    async with aiosqlite.connect(TIKTOK_DB) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS tiktok_config(guild_id INTEGER PRIMARY KEY, channel_id INTEGER, username TEXT, role_id INTEGER, interval INTEGER DEFAULT 5, last_video_id TEXT, enabled INTEGER DEFAULT 1, last_checked INTEGER DEFAULT 0)"
        )
        await db.commit()

    async with aiosqlite.connect(BOTCHANNEL_DB) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS bot_channel(guild_id INTEGER PRIMARY KEY, channel_id INTEGER)"
        )
        await db.commit()

    async with aiosqlite.connect(ROLEPERMS_DB) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS role_permissions(guild_id INTEGER, role_name TEXT, command TEXT, custom INTEGER DEFAULT 0, PRIMARY KEY(guild_id, role_name, command))"
        )
        await db.commit()


async def fetch_prefix(guild_id: int) -> str:
    row = await execute_sql(BOT_DB, "SELECT prefix FROM bot_prefixes WHERE guild_id = ?", (guild_id,), fetchone=True)
    return row[0] if row else DEFAULT_PREFIX


async def set_prefix(guild_id: int, prefix: str):
    await execute_sql(
        BOT_DB,
        "INSERT OR REPLACE INTO bot_prefixes(guild_id, prefix) VALUES(?, ?)",
        (guild_id, prefix),
    )


async def get_bot_channel(guild_id: int) -> Optional[int]:
    row = await execute_sql(BOTCHANNEL_DB, "SELECT channel_id FROM bot_channel WHERE guild_id = ?", (guild_id,), fetchone=True)
    return row[0] if row else None


async def set_bot_channel(guild_id: int, channel_id: int):
    await execute_sql(
        BOTCHANNEL_DB,
        "INSERT OR REPLACE INTO bot_channel(guild_id, channel_id) VALUES(?, ?)",
        (guild_id, channel_id),
    )


async def remove_bot_channel(guild_id: int):
    await execute_sql(BOTCHANNEL_DB, "DELETE FROM bot_channel WHERE guild_id = ?", (guild_id,))


async def get_leave_config(guild_id: int):
    return await execute_sql(
        LEAVE_DB,
        "SELECT channel_id, mode, message, autodelete, embed FROM leave_config WHERE guild_id = ?",
        (guild_id,),
        fetchone=True,
    )


async def update_leave_config(guild_id: int, channel_id: int, mode: str, message: str, autodelete: int, embed: bool):
    await execute_sql(
        LEAVE_DB,
        "INSERT OR REPLACE INTO leave_config(guild_id, channel_id, mode, message, autodelete, embed) VALUES(?, ?, ?, ?, ?, ?)",
        (guild_id, channel_id, mode, message, autodelete, int(embed)),
    )


async def update_leave_message(guild_id: int, message: str):
    current = await get_leave_config(guild_id)
    if current:
        channel_id, mode, _, autodelete, embed_flag = current
        await update_leave_config(guild_id, channel_id, mode, message, autodelete, bool(embed_flag))
    else:
        await update_leave_config(guild_id, 0, "simple", message, 0, False)


async def update_leave_autodelete(guild_id: int, autodelete: int):
    current = await get_leave_config(guild_id)
    if not current:
        await update_leave_config(guild_id, 0, "simple", WELCOME_DEFAULT_MESSAGE, autodelete, False)
        return
    channel_id, mode, message, _, embed_flag = current
    await update_leave_config(guild_id, channel_id, mode, message, autodelete, bool(embed_flag))


async def reset_leave_config(guild_id: int):
    await execute_sql(LEAVE_DB, "DELETE FROM leave_config WHERE guild_id = ?", (guild_id,))


async def get_ticket_config(guild_id: int):
    return await execute_sql(
        TICKETS_DB,
        "SELECT category_id, role_id FROM ticket_config WHERE guild_id = ?",
        (guild_id,),
        fetchone=True,
    )


async def set_ticket_config(guild_id: int, category_id: int, role_id: int):
    await execute_sql(
        TICKETS_DB,
        "INSERT OR REPLACE INTO ticket_config(guild_id, category_id, role_id) VALUES(?, ?, ?)",
        (guild_id, category_id, role_id),
    )


async def add_open_ticket(guild_id: int, user_id: int, channel_id: int):
    await execute_sql(
        TICKETS_DB,
        "INSERT INTO ticket_open(guild_id, user_id, channel_id, open, created_at) VALUES(?, ?, ?, 1, ?)",
        (guild_id, user_id, channel_id, int(time.time())),
    )


async def get_open_ticket_count(guild_id: int, user_id: int) -> int:
    row = await execute_sql(
        TICKETS_DB,
        "SELECT COUNT(*) FROM ticket_open WHERE guild_id = ? AND user_id = ? AND open = 1",
        (guild_id, user_id),
        fetchone=True,
    )
    return int(row[0]) if row else 0


async def get_ticket_by_channel(guild_id: int, channel_id: int):
    return await execute_sql(
        TICKETS_DB,
        "SELECT user_id FROM ticket_open WHERE guild_id = ? AND channel_id = ? AND open = 1",
        (guild_id, channel_id),
        fetchone=True,
    )


async def close_ticket_record(guild_id: int, channel_id: int):
    await execute_sql(
        TICKETS_DB,
        "UPDATE ticket_open SET open = 0 WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id),
    )


async def get_tiktok_config(guild_id: int):
    return await execute_sql(
        TIKTOK_DB,
        "SELECT channel_id, username, role_id, interval, last_video_id, enabled, last_checked FROM tiktok_config WHERE guild_id = ?",
        (guild_id,),
        fetchone=True,
    )


async def upsert_tiktok_config(guild_id: int, channel_id: int = 0, username: str = "", role_id: int = 0, interval: int = 5, last_video_id: str = "", enabled: int = 1, last_checked: int = 0):
    await execute_sql(
        TIKTOK_DB,
        "INSERT OR REPLACE INTO tiktok_config(guild_id, channel_id, username, role_id, interval, last_video_id, enabled, last_checked) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
        (guild_id, channel_id, username, role_id, interval, last_video_id, enabled, last_checked),
    )


async def set_tiktok_channel(guild_id: int, channel_id: int):
    config = await get_tiktok_config(guild_id)
    if config:
        _, username, role_id, interval, last_video_id, enabled, last_checked = config
        await upsert_tiktok_config(guild_id, channel_id, username or "", role_id or 0, interval or 5, last_video_id or "", enabled or 1, last_checked or 0)
        return
    await upsert_tiktok_config(guild_id, channel_id=channel_id)


async def set_tiktok_username(guild_id: int, username: str):
    config = await get_tiktok_config(guild_id)
    if config:
        channel_id, _, role_id, interval, last_video_id, enabled, last_checked = config
        await upsert_tiktok_config(guild_id, channel_id, username, role_id or 0, interval or 5, last_video_id or "", enabled or 1, last_checked or 0)
        return
    await upsert_tiktok_config(guild_id, username=username)


async def set_tiktok_role(guild_id: int, role_id: int):
    config = await get_tiktok_config(guild_id)
    if config:
        channel_id, username, _, interval, last_video_id, enabled, last_checked = config
        await upsert_tiktok_config(guild_id, channel_id, username or "", role_id, interval or 5, last_video_id or "", enabled or 1, last_checked or 0)
        return
    await upsert_tiktok_config(guild_id, role_id=role_id)


async def set_tiktok_interval(guild_id: int, interval: int):
    config = await get_tiktok_config(guild_id)
    if config:
        channel_id, username, role_id, _, last_video_id, enabled, last_checked = config
        await upsert_tiktok_config(guild_id, channel_id, username or "", role_id or 0, interval, last_video_id or "", enabled or 1, last_checked or 0)
        return
    await upsert_tiktok_config(guild_id, interval=interval)


async def set_tiktok_enabled(guild_id: int, enabled: bool):
    config = await get_tiktok_config(guild_id)
    if config:
        channel_id, username, role_id, interval, last_video_id, _, _ = config
        await upsert_tiktok_config(guild_id, channel_id, username or "", role_id or 0, interval or 5, last_video_id or "", 1 if enabled else 0, int(time.time()) if not enabled else 0)
        return
    await upsert_tiktok_config(guild_id, enabled=0 if not enabled else 1)


async def set_tiktok_last_video(guild_id: int, video_id: str):
    config = await get_tiktok_config(guild_id)
    if config:
        channel_id, username, role_id, interval, _, enabled, last_checked = config
        await upsert_tiktok_config(guild_id, channel_id, username or "", role_id or 0, interval or 5, video_id, enabled or 1, int(time.time()))
        return
    await upsert_tiktok_config(guild_id, last_video_id=video_id, last_checked=int(time.time()))


async def get_all_tiktok_configs():
    return await execute_sql(
        TIKTOK_DB,
        "SELECT guild_id, channel_id, username, role_id, interval, last_video_id, enabled, last_checked FROM tiktok_config",
        fetchall=True,
    )


async def upsert_role_permission(guild_id: int, role_name: str, command: str, custom: int = 1):
    await execute_sql(
        ROLEPERMS_DB,
        "INSERT OR REPLACE INTO role_permissions(guild_id, role_name, command, custom) VALUES(?, ?, ?, ?)",
        (guild_id, role_name.lower(), command, custom),
    )


async def remove_role_permission_db(guild_id: int, role_name: str, command: str):
    await execute_sql(
        ROLEPERMS_DB,
        "DELETE FROM role_permissions WHERE guild_id = ? AND role_name = ? AND command = ?",
        (guild_id, role_name.lower(), command),
    )


async def get_role_permissions_db(guild_id: int):
    return await execute_sql(
        ROLEPERMS_DB,
        "SELECT role_name, command, custom FROM role_permissions WHERE guild_id = ?",
        (guild_id,),
        fetchall=True,
    )


async def normalize_command_name(value: str) -> str:
    return value.lower().replace(" ", "_").replace("-", "_")


async def user_has_command_permission(member: discord.Member, command_name: str) -> bool:
    if member.guild is None:
        return False
    if member.guild_permissions.administrator or member.id in OWNER_IDS:
        return True

    command_name = await normalize_command_name(command_name)
    config = await get_role_permissions_db(member.guild.id)
    role_names = {role.name.lower() for role in member.roles if role.name}

    for role_name, command, _custom in config:
        if command == command_name and role_name in role_names:
            return True
    return False


async def refresh_role_permissions(guild: discord.Guild) -> int:
    existing = await get_role_permissions_db(guild.id)
    existing_set = {f"{role_name}:{permission}" for role_name, permission, _ in existing}
    total = 0
    for role in guild.roles:
        name_lower = role.name.lower()
        for key, commands_set in ROLE_COMMAND_MAP.items():
            if key in name_lower:
                for command in commands_set:
                    entry = f"{role.name.lower()}:{command}"
                    if entry not in existing_set:
                        await upsert_role_permission(guild.id, role.name, command, custom=0)
                        total += 1
    return total


async def format_leave_message(member: discord.Member, message_template: str) -> str:
    return (
        message_template
        .replace("{user}", member.mention)
        .replace("{server}", member.guild.name)
        .replace("{member_count}", str(member.guild.member_count))
    )


class ConfirmationView(commands.View):
    def __init__(self, author: discord.Member, action: str):
        super().__init__(timeout=30)
        self.author = author
        self.action = action
        self.confirmed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command author can confirm this action.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.confirmed = True
        self.stop()
        await interaction.response.edit_message(content=f"{self.action} confirmed.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(content="Action cancelled.", view=None)


class LeaveSetupView(commands.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=120)
        self.author = author
        self.selected_channel: Optional[discord.TextChannel] = None
        self.mode = "simple"
        self.message = WELCOME_DEFAULT_MESSAGE

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command author can configure the leave system.", ephemeral=True)
            return False
        return True

    @discord.ui.channel_select(placeholder="Select a goodbye channel", channel_types=[discord.ChannelType.text], min_values=1, max_values=1)
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.selected_channel = select.values[0]
        await interaction.response.send_message(
            f"Selected channel {self.selected_channel.mention}. Choose a mode and click Save.", ephemeral=True
        )

    @discord.ui.button(label="Simple Mode", style=discord.ButtonStyle.primary)
    async def simple_mode(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.mode = "simple"
        await interaction.response.send_message("Leave mode set to simple.", ephemeral=True)

    @discord.ui.button(label="Embed Mode", style=discord.ButtonStyle.success)
    async def embed_mode(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.mode = "embed"
        await interaction.response.send_message("Leave mode set to embed.", ephemeral=True)

    @discord.ui.button(label="Save", style=discord.ButtonStyle.secondary)
    async def save(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self.selected_channel:
            await interaction.response.send_message("Please select a channel first.", ephemeral=True)
            return
        await update_leave_config(
            interaction.guild.id,
            self.selected_channel.id,
            self.mode,
            self.message,
            0,
            self.mode == "embed",
        )
        self.stop()
        await interaction.response.edit_message(
            content=f"Leave system configured in {self.selected_channel.mention} using {self.mode} mode.",
            embed=None,
            view=None,
        )


class TicketSetupView(commands.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=120)
        self.author = author
        self.selected_category: Optional[discord.CategoryChannel] = None
        self.selected_role: Optional[discord.Role] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command author can configure the ticket system.", ephemeral=True)
            return False
        return True

    @discord.ui.channel_select(placeholder="Select a ticket category", channel_types=[discord.ChannelType.category], min_values=1, max_values=1)
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.selected_category = select.values[0]
        await interaction.response.send_message(
            f"Selected category {self.selected_category.name}.", ephemeral=True
        )

    @discord.ui.role_select(placeholder="Select a support role", min_values=1, max_values=1)
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        self.selected_role = select.values[0]
        await interaction.response.send_message(
            f"Selected support role {self.selected_role.mention}.", ephemeral=True
        )

    @discord.ui.button(label="Save", style=discord.ButtonStyle.success)
    async def save(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self.selected_category or not self.selected_role:
            await interaction.response.send_message("Please select both a category and a support role.", ephemeral=True)
            return
        await set_ticket_config(interaction.guild.id, self.selected_category.id, self.selected_role.id)
        self.stop()
        await interaction.response.edit_message(
            content=f"Ticket setup saved. Category: {self.selected_category.name}, Support role: {self.selected_role.name}.",
            view=None,
        )


class TikTokSetupView(commands.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=120)
        self.author = author
        self.selected_channel: Optional[discord.TextChannel] = None
        self.selected_role: Optional[discord.Role] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command author can configure TikTok notifications.", ephemeral=True)
            return False
        return True

    @discord.ui.channel_select(placeholder="Select a TikTok notification channel", channel_types=[discord.ChannelType.text], min_values=1, max_values=1)
    async def channel_select(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        self.selected_channel = select.values[0]
        await interaction.response.send_message(
            f"Notification channel set to {self.selected_channel.mention}.", ephemeral=True
        )

    @discord.ui.role_select(placeholder="Select a mention role for new videos", min_values=1, max_values=1)
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        self.selected_role = select.values[0]
        await interaction.response.send_message(
            f"Mention role set to {self.selected_role.mention}.", ephemeral=True
        )

    @discord.ui.button(label="Save", style=discord.ButtonStyle.success)
    async def save(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self.selected_channel or not self.selected_role:
            await interaction.response.send_message("Please select both channel and role.", ephemeral=True)
            return
        await set_tiktok_channel(interaction.guild.id, self.selected_channel.id)
        await set_tiktok_role(interaction.guild.id, self.selected_role.id)
        self.stop()
        await interaction.response.edit_message(
            content=f"TikTok notifications will post in {self.selected_channel.mention} and mention {self.selected_role.mention}. Use `>tiktok username <username>` next.",
            view=None,
        )


class TicketPanelView(commands.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_panel_create")
    async def create(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Ticket creation must happen in a server.", ephemeral=True)
            return
        channel = await create_ticket_for_member(interaction.guild, interaction.user)
        if channel:
            await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("Unable to create a ticket. Check the ticket setup.", ephemeral=True)


def admin_only():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id in OWNER_IDS:
            return True
        if ctx.guild is None:
            raise commands.MissingPermissions(["administrator"])
        if ctx.author.guild_permissions.administrator:
            return True
        raise commands.MissingPermissions(["administrator"])
    return commands.check(predicate)


def permission_required(command_name: str):
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.CheckFailure("This command can only be used in a server.")
        if ctx.author.id in OWNER_IDS or ctx.author.guild_permissions.administrator:
            return True
        allowed = await user_has_command_permission(ctx.author, command_name)
        if allowed:
            return True
        raise commands.MissingPermissions([command_name])
    return commands.check(predicate)


@bot.check
async def enforce_bot_channel(ctx: commands.Context) -> bool:
    if ctx.guild is None:
        return True
    channel_id = await get_bot_channel(ctx.guild.id)
    if channel_id is None:
        return True
    if ctx.channel.id == channel_id:
        return True
    raise commands.CheckFailure(
        f"All bot commands are restricted to <#{channel_id}> in this server. Use DMs or the configured channel."
    )


@bot.event
async def on_ready():
    print(f"{BOT_NAME} is online — logged in as {bot.user}.")
    if API_ENABLED:
        print(f"API server enabled on port {API_PORT}.")
    if not tiktok_watcher.is_running():
        tiktok_watcher.start()


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, (commands.MissingPermissions, commands.CheckFailure)):
        await ctx.reply(str(error), mention_author=False)
        return
    await ctx.reply(f"An error occurred: {error}", mention_author=False)
    raise error


@bot.event
async def on_member_remove(member: discord.Member):
    config = await get_leave_config(member.guild.id)
    if not config:
        return
    channel_id, mode, message, autodelete, embed_flag = config
    channel = member.guild.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return
    text = await format_leave_message(member, message or WELCOME_DEFAULT_MESSAGE)
    if embed_flag:
        embed = Embed(title="Member Left", description=text, color=discord.Color.red())
        leave_message = await channel.send(embed=embed)
    else:
        leave_message = await channel.send(text)
    if autodelete and autodelete > 0:
        await asyncio.sleep(autodelete)
        await leave_message.delete()


@bot.command(name="help")
async def help_command(ctx: commands.Context):
    prefix = await fetch_prefix(ctx.guild.id) if ctx.guild else DEFAULT_PREFIX
    embed = Embed(
        title="Bezms Bot Help",
        description=(
            f"Prefix: `{prefix}` | Server: Bezms | Bot: {BOT_NAME}\n"
            "Use commands in the configured bot channel or in DMs."
        ),
        color=discord.Color.red(),
    )
    embed.add_field(
        name="Moderation",
        value=(
            "`ping`, `purge <amount>`, `lockall`, `unlockall`, `hideall`, `unhideall`, `give @user @role`, `nuke`, "
            "`slowmode <seconds>`, `unslowmode`, `gtfo @user <reason>`"
        ),
        inline=False,
    )
    embed.add_field(
        name="Leave System",
        value="`leave setup`, `leave reset`, `leave test`, `leave config`, `leave edit <message>`, `leave autodelete <seconds>`",
        inline=False,
    )
    embed.add_field(
        name="Ticket System",
        value="`ticket setup`, `ticket panel`, `ticket create`, `ticket close`",
        inline=False,
    )
    embed.add_field(
        name="TikTok Notifications",
        value="`tiktok setup`, `tiktok channel #channel`, `tiktok username <username>`, `tiktok role @role`, `tiktok interval <minutes>`, `tiktok test`, `tiktok status`, `tiktok disable`",
        inline=False,
    )
    embed.add_field(
        name="Bot Channel",
        value="`botchannel set #channel`, `botchannel remove`, `botchannel status`",
        inline=False,
    )
    embed.add_field(
        name="Role Permissions",
        value="`roleperms refresh`, `roleperms add <role> <command>`, `roleperms remove <role> <command>`, `roleperms list`",
        inline=False,
    )
    embed.add_field(name="Prefix", value="`prefix <new>`", inline=False)
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    await ctx.reply(f"Pong! Latency: {round(bot.latency * 1000)}ms", mention_author=False)


@bot.command(name="purge")
@permission_required("purge")
async def purge(ctx: commands.Context, amount: int = 10000):
    amount = max(1, min(amount, 10000))
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Deleted {max(0, len(deleted) - 1)} messages.", delete_after=10)


@bot.command(name="lockall")
@permission_required("lockall")
async def lockall(ctx: commands.Context):
    view = ConfirmationView(ctx.author, "Lock all channels")
    message = await ctx.send("Are you sure you want to lock all text channels?", view=view)
    await view.wait()
    if not view.confirmed:
        await message.edit(content="Lock operation cancelled.", view=None)
        return
    for channel in ctx.guild.text_channels:
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("All text channels are locked.")


@bot.command(name="unlockall")
@permission_required("unlockall")
async def unlockall(ctx: commands.Context):
    view = ConfirmationView(ctx.author, "Unlock all channels")
    message = await ctx.send("Are you sure you want to unlock all text channels?", view=view)
    await view.wait()
    if not view.confirmed:
        await message.edit(content="Unlock operation cancelled.", view=None)
        return
    for channel in ctx.guild.text_channels:
        await channel.set_permissions(ctx.guild.default_role, send_messages=None)
    await ctx.send("All text channels are unlocked.")


@bot.command(name="hideall")
@permission_required("hideall")
async def hideall(ctx: commands.Context):
    view = ConfirmationView(ctx.author, "Hide all channels")
    message = await ctx.send("Are you sure you want to hide all text channels from everyone?", view=view)
    await view.wait()
    if not view.confirmed:
        await message.edit(content="Hide operation cancelled.", view=None)
        return
    for channel in ctx.guild.text_channels:
        await channel.set_permissions(ctx.guild.default_role, view_channel=False)
    await ctx.send("All text channels have been hidden.")


@bot.command(name="unhideall")
@permission_required("unhideall")
async def unhideall(ctx: commands.Context):
    view = ConfirmationView(ctx.author, "Unhide all channels")
    message = await ctx.send("Are you sure you want to unhide all text channels for everyone?", view=view)
    await view.wait()
    if not view.confirmed:
        await message.edit(content="Unhide operation cancelled.", view=None)
        return
    for channel in ctx.guild.text_channels:
        await channel.set_permissions(ctx.guild.default_role, view_channel=None)
    await ctx.send("All text channels are visible again.")


@bot.command(name="give")
@permission_required("give")
async def give(ctx: commands.Context, member: discord.Member, role: discord.Role):
    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"Removed {role.name} from {member.mention}.")
    else:
        await member.add_roles(role)
        await ctx.send(f"Assigned {role.name} to {member.mention}.")


@bot.command(name="nuke")
@permission_required("nuke")
async def nuke(ctx: commands.Context):
    channel = ctx.channel
    await ctx.send("Nuking this channel in 3 seconds...", delete_after=3)
    new_channel = await channel.clone(name=channel.name)
    await channel.delete()
    await new_channel.send("Channel has been nuked and recreated.")


@bot.command(name="slowmode")
@permission_required("slowmode")
async def slowmode(ctx: commands.Context, seconds: int):
    seconds = max(0, min(seconds, 120))
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"Slowmode set to {seconds} seconds.")


@bot.command(name="unslowmode")
@permission_required("unslowmode")
async def unslowmode(ctx: commands.Context):
    await ctx.channel.edit(slowmode_delay=0)
    await ctx.send("Slowmode disabled.")


@bot.command(name="gtfo")
@permission_required("gtfo")
async def gtfo(ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "No reason provided"):
    if member.guild_permissions.administrator or member.guild_permissions.manage_messages or member.guild_permissions.ban_members:
        await member.ban(reason=reason)
        action = "banned"
    else:
        await member.kick(reason=reason)
        action = "kicked"
    embed = Embed(
        title="GTFO",
        description=f"{member.mention} has been {action}.",
        color=discord.Color.red(),
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    await ctx.send(embed=embed)


@bot.command(name="kick")
@permission_required("kick")
async def kick(ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"Kicked {member.mention}. Reason: {reason}")


@bot.command(name="ban")
@permission_required("ban")
async def ban(ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "No reason provided"):
    await member.ban(reason=reason)
    await ctx.send(f"Banned {member.mention}. Reason: {reason}")


async def ensure_muted_role(guild: discord.Guild) -> discord.Role:
    muted = discord.utils.get(guild.roles, name="Muted")
    if muted is None:
        muted = await guild.create_role(name="Muted", permissions=discord.Permissions(send_messages=False), reason="Created Muted role for bot")
    for channel in guild.text_channels:
        await channel.set_permissions(muted, send_messages=False, add_reactions=False)
    for voice in guild.voice_channels:
        await voice.set_permissions(muted, speak=False, connect=False)
    return muted


@bot.command(name="mute")
@permission_required("mute")
async def mute(ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "No reason provided"):
    muted_role = await ensure_muted_role(ctx.guild)
    await member.add_roles(muted_role, reason=reason)
    await ctx.send(f"{member.mention} has been muted. Reason: {reason}")


@bot.command(name="unmute")
@permission_required("mute")
async def unmute(ctx: commands.Context, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if muted_role is None or muted_role not in member.roles:
        await ctx.send(f"{member.mention} is not muted.")
        return
    await member.remove_roles(muted_role)
    await ctx.send(f"{member.mention} has been unmuted.")


@bot.command(name="warn")
@permission_required("warn")
async def warn(ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "No reason provided"):
    try:
        await member.send(f"You have been warned in {ctx.guild.name}. Reason: {reason}")
    except discord.HTTPException:
        pass
    await ctx.send(f"{member.mention} has been warned. Reason: {reason}")


@bot.group(name="leave", invoke_without_command=True)
@admin_only()
async def leave(ctx: commands.Context):
    await ctx.send("Available leave commands: setup, reset, test, config, edit, autodelete")


@leave.command(name="setup")
@admin_only()
async def leave_setup(ctx: commands.Context):
    view = LeaveSetupView(ctx.author)
    await ctx.send(
        "Configure the leave system below. Select a channel and choose simple or embed mode, then click Save.",
        view=view,
    )


@leave.command(name="reset")
@admin_only()
async def leave_reset(ctx: commands.Context):
    await reset_leave_config(ctx.guild.id)
    await ctx.send("Leave system configuration has been reset.")


@leave.command(name="test")
@admin_only()
async def leave_test(ctx: commands.Context):
    config = await get_leave_config(ctx.guild.id)
    if not config:
        await ctx.send("Leave system is not configured yet.")
        return
    channel_id, mode, message, autodelete, embed_flag = config
    channel = ctx.guild.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        await ctx.send("Configured leave channel could not be found.")
        return
    sample = message or WELCOME_DEFAULT_MESSAGE
    text = sample.replace("{user}", ctx.author.mention).replace("{server}", ctx.guild.name).replace("{member_count}", str(ctx.guild.member_count))
    if embed_flag:
        await channel.send(embed=Embed(title="Goodbye Test", description=text, color=discord.Color.red()))
    else:
        await channel.send(text)
    await ctx.send(f"Sent a test leave message to {channel.mention}.")


@leave.command(name="config")
@admin_only()
async def leave_config(ctx: commands.Context):
    config = await get_leave_config(ctx.guild.id)
    if not config:
        await ctx.send("Leave system is not configured.")
        return
    channel_id, mode, message, autodelete, embed_flag = config
    channel = ctx.guild.get_channel(channel_id)
    embed = Embed(title="Leave System Configuration", color=discord.Color.red())
    embed.add_field(name="Channel", value=channel.mention if channel else "Not found", inline=False)
    embed.add_field(name="Mode", value=mode or "simple", inline=False)
    embed.add_field(name="Embed", value="Yes" if embed_flag else "No", inline=False)
    embed.add_field(name="Autodelete", value=f"{autodelete}s" if autodelete else "Disabled", inline=False)
    embed.add_field(name="Message", value=message or WELCOME_DEFAULT_MESSAGE, inline=False)
    await ctx.send(embed=embed)


@leave.command(name="edit")
@admin_only()
async def leave_edit(ctx: commands.Context, *, message: str):
    await update_leave_message(ctx.guild.id, message)
    await ctx.send("Leave message updated.")


@leave.command(name="autodelete")
@admin_only()
async def leave_autodelete(ctx: commands.Context, seconds: int):
    seconds = max(0, seconds)
    await update_leave_autodelete(ctx.guild.id, seconds)
    await ctx.send(f"Leave messages will now be deleted after {seconds}s." if seconds else "Leave autodelete disabled.")


async def create_ticket_for_member(guild: discord.Guild, member: discord.Member) -> Optional[discord.TextChannel]:
    config = await get_ticket_config(guild.id)
    if not config:
        return None
    category_id, role_id = config
    category = guild.get_channel(category_id)
    support_role = guild.get_role(role_id)
    if not isinstance(category, discord.CategoryChannel) or support_role is None:
        return None
    count = await get_open_ticket_count(guild.id, member.id)
    if count >= 3:
        return None
    safe_name = re.sub(r"[^a-z0-9-]", "", member.name.lower())[:80]
    ticket_name = f"ticket-{safe_name}"
    existing_names = {c.name for c in category.channels}
    suffix = 1
    while ticket_name in existing_names:
        ticket_name = f"ticket-{safe_name}-{suffix}"
        suffix += 1
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }
    channel = await category.create_text_channel(ticket_name, overwrites=overwrites, reason="Ticket created")
    await add_open_ticket(guild.id, member.id, channel.id)
    await channel.send(f"Welcome {member.mention}! Our support team will be with you shortly.")
    return channel


@bot.group(name="ticket", invoke_without_command=True)
async def ticket(ctx: commands.Context):
    await ctx.send("Available ticket commands: setup, panel, create, close")


@ticket.command(name="setup")
@admin_only()
async def ticket_setup(ctx: commands.Context):
    view = TicketSetupView(ctx.author)
    await ctx.send("Use the menu below to configure ticket setup.", view=view)


@ticket.command(name="panel")
@admin_only()
async def ticket_panel(ctx: commands.Context):
    config = await get_ticket_config(ctx.guild.id)
    if not config:
        await ctx.send("Ticket system is not configured. Run `>ticket setup` first.")
        return
    embed = Embed(
        title="Support Ticket Panel",
        description="Click the button below to create a new ticket. A member of the support team will assist you.",
        color=discord.Color.red(),
    )
    await ctx.send(embed=embed, view=TicketPanelView())


@ticket.command(name="create")
async def ticket_create(ctx: commands.Context):
    if ctx.guild is None:
        await ctx.send("Tickets can only be created inside a server.")
        return
    channel = await create_ticket_for_member(ctx.guild, ctx.author)
    if channel:
        await ctx.send(f"Ticket created: {channel.mention}")
    else:
        await ctx.send("Unable to create a ticket right now. Ensure the ticket system is configured and you have fewer than 3 open tickets.")


@ticket.command(name="close")
@permission_required("ticket_close")
async def ticket_close(ctx: commands.Context):
    config = await get_ticket_config(ctx.guild.id)
    if not config:
        await ctx.send("Ticket system is not configured.")
        return
    ticket_row = await get_ticket_by_channel(ctx.guild.id, ctx.channel.id)
    if not ticket_row:
        await ctx.send("This command may only be used inside an open ticket channel.")
        return
    await close_ticket_record(ctx.guild.id, ctx.channel.id)
    await ctx.send("Closing this ticket in 5 seconds...")
    await asyncio.sleep(5)
    await ctx.channel.delete()


@bot.group(name="tiktok", invoke_without_command=True)
@admin_only()
async def tiktok(ctx: commands.Context):
    await ctx.send("Use TikTok setup commands: setup, channel, username, role, interval, test, status, disable")


@tiktok.command(name="setup")
@admin_only()
async def tiktok_setup(ctx: commands.Context):
    view = TikTokSetupView(ctx.author)
    await ctx.send("Set up TikTok notifications using the controls below.", view=view)


@tiktok.command(name="channel")
@admin_only()
async def tiktok_channel(ctx: commands.Context, channel: discord.TextChannel):
    await set_tiktok_channel(ctx.guild.id, channel.id)
    await ctx.send(f"TikTok notifications will post in {channel.mention}.")


@tiktok.command(name="username")
@admin_only()
async def tiktok_username(ctx: commands.Context, username: str):
    await set_tiktok_username(ctx.guild.id, username)
    await ctx.send(f"Watching TikTok username `{username}`.")


@tiktok.command(name="role")
@admin_only()
async def tiktok_role(ctx: commands.Context, role: discord.Role):
    await set_tiktok_role(ctx.guild.id, role.id)
    await ctx.send(f"Will ping {role.mention} for new TikTok uploads.")


@tiktok.command(name="interval")
@admin_only()
async def tiktok_interval(ctx: commands.Context, minutes: int):
    minutes = max(1, minutes)
    await set_tiktok_interval(ctx.guild.id, minutes)
    await ctx.send(f"TikTok check interval set to {minutes} minutes.")


@tiktok.command(name="test")
@admin_only()
async def tiktok_test(ctx: commands.Context):
    config = await get_tiktok_config(ctx.guild.id)
    if not config:
        await ctx.send("TikTok monitoring is not configured yet.")
        return
    channel_id, username, role_id, interval, last_video_id, enabled, _ = config
    channel = ctx.guild.get_channel(channel_id)
    role = ctx.guild.get_role(role_id)
    if not isinstance(channel, discord.TextChannel):
        await ctx.send("TikTok notification channel is not set or cannot be found.")
        return
    mention_text = f"{role.mention} " if role else ""
    await channel.send(f"{mention_text}TikTok test notification for `{username or 'username not set'}`.")
    await ctx.send("Sent a TikTok test message.")


@tiktok.command(name="status")
@admin_only()
async def tiktok_status(ctx: commands.Context):
    config = await get_tiktok_config(ctx.guild.id)
    if not config:
        await ctx.send("TikTok monitoring is not configured.")
        return
    channel_id, username, role_id, interval, last_video_id, enabled, last_checked = config
    channel = ctx.guild.get_channel(channel_id)
    role = ctx.guild.get_role(role_id)
    embed = Embed(title="TikTok Configuration", color=discord.Color.red())
    embed.add_field(name="Channel", value=channel.mention if channel else "Not set", inline=False)
    embed.add_field(name="Username", value=username or "Not set", inline=False)
    embed.add_field(name="Mention Role", value=role.mention if role else "Not set", inline=False)
    embed.add_field(name="Interval", value=f"{interval} minutes", inline=False)
    embed.add_field(name="Enabled", value="Yes" if enabled else "No", inline=False)
    embed.add_field(name="Last Video ID", value=last_video_id or "None", inline=False)
    await ctx.send(embed=embed)


@tiktok.command(name="disable")
@admin_only()
async def tiktok_disable(ctx: commands.Context):
    await set_tiktok_enabled(ctx.guild.id, False)
    await ctx.send("TikTok monitoring has been disabled.")


@bot.group(name="botchannel", invoke_without_command=True)
@admin_only()
async def botchannel(ctx: commands.Context):
    await ctx.send("Use `botchannel set #channel`, `botchannel remove`, or `botchannel status`.")


@botchannel.command(name="set")
@admin_only()
async def botchannel_set(ctx: commands.Context, channel: discord.TextChannel):
    await set_bot_channel(ctx.guild.id, channel.id)
    await ctx.send(f"Bot commands are now restricted to {channel.mention}.")


@botchannel.command(name="remove")
@admin_only()
async def botchannel_remove(ctx: commands.Context):
    await remove_bot_channel(ctx.guild.id)
    await ctx.send("Bot channel restriction has been removed.")


@botchannel.command(name="status")
@admin_only()
async def botchannel_status(ctx: commands.Context):
    channel_id = await get_bot_channel(ctx.guild.id)
    if channel_id:
        await ctx.send(f"Bot commands are restricted to <#{channel_id}>.")
    else:
        await ctx.send("No bot channel restriction is configured.")


@bot.group(name="roleperms", invoke_without_command=True)
@admin_only()
async def roleperms(ctx: commands.Context):
    await ctx.send("Use `roleperms refresh`, `roleperms add <role> <command>`, `roleperms remove <role> <command>`, or `roleperms list`.")


@roleperms.command(name="refresh")
@admin_only()
async def roleperms_refresh(ctx: commands.Context):
    count = await refresh_role_permissions(ctx.guild)
    await ctx.send(f"Refreshed role-based command permissions and added {count} entries.")


@roleperms.command(name="add")
@admin_only()
async def roleperms_add(ctx: commands.Context, role: discord.Role, command: str):
    normalized = await normalize_command_name(command)
    if normalized not in ALL_MOD_COMMANDS and normalized != "ticket_close":
        await ctx.send(f"Unknown command permission: {command}.")
        return
    await upsert_role_permission(ctx.guild.id, role.name, normalized, custom=1)
    await ctx.send(f"Granted {role.name} permission to run `{normalized}`.")


@roleperms.command(name="remove")
@admin_only()
async def roleperms_remove(ctx: commands.Context, role: discord.Role, command: str):
    normalized = await normalize_command_name(command)
    await remove_role_permission_db(ctx.guild.id, role.name, normalized)
    await ctx.send(f"Removed permission `{normalized}` from {role.name}.")


@roleperms.command(name="list")
@admin_only()
async def roleperms_list(ctx: commands.Context):
    rows = await get_role_permissions_db(ctx.guild.id)
    if not rows:
        await ctx.send("No custom role permissions found.")
        return
    embed = Embed(title="Role Permission List", color=discord.Color.red())
    permissions = {}
    for role_name, command, _custom in rows:
        permissions.setdefault(role_name, []).append(command)
    for role_name, commands_list in permissions.items():
        embed.add_field(name=role_name, value=", ".join(sorted(set(commands_list))), inline=False)
    await ctx.send(embed=embed)


def start_api():
    app = FastAPI()

    @app.get("/status")
    async def status():
        return JSONResponse(
            content={
                "status": "online",
                "bot": BOT_NAME,
                "prefix": DEFAULT_PREFIX,
                "guilds": len(bot.guilds),
                "timestamp": int(time.time()),
            }
        )

    @app.get("/health")
    async def health():
        return JSONResponse(content={"status": "healthy"})

    uvicorn.run(app, host="0.0.0.0", port=API_PORT, log_level="warning")


@tasks.loop(minutes=1)
async def tiktok_watcher():
    configs = await get_all_tiktok_configs()
    async with aiohttp.ClientSession(headers={"User-Agent": TIKTOK_USER_AGENT}) as session:
        for guild_id, channel_id, username, role_id, interval, last_video_id, enabled, last_checked in configs:
            if not enabled or not username or not channel_id:
                continue
            now_ts = int(time.time())
            if last_checked and now_ts - last_checked < interval * 60:
                continue
            guild = bot.get_guild(guild_id)
            if not guild:
                continue
            channel = guild.get_channel(channel_id)
            role = guild.get_role(role_id) if role_id else None
            if not isinstance(channel, discord.TextChannel):
                continue
            new_video = await fetch_latest_tiktok_video(session, username)
            await execute_sql(TIKTOK_DB, "UPDATE tiktok_config SET last_checked = ? WHERE guild_id = ?", (now_ts, guild_id))
            if not new_video:
                continue
            if new_video["id"] == last_video_id:
                continue
            await set_tiktok_last_video(guild_id, new_video["id"])
            mention = f"{role.mention} " if role else ""
            await channel.send(
                f"{mention}New TikTok video detected for @{username}!\n{new_video['title']}\n{new_video['url']}"
            )


async def fetch_latest_tiktok_video(session: aiohttp.ClientSession, username: str) -> Optional[dict]:
    url = f"https://www.tiktok.com/@{username}"
    try:
        async with session.get(url, timeout=30) as response:
            html = await response.text()
    except Exception:
        return None
    match = re.search(r'<script id="SIGI_STATE" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        match = re.search(r'window\["SIGI_STATE"\] = (\{.*?\});', html, re.S)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    items = payload.get("ItemModule") or {}
    if not items:
        return None
    latest = max(items.values(), key=lambda item: int(item.get("createTime", 0)))
    return {
        "id": latest.get("id"),
        "title": latest.get("desc", "New TikTok upload"),
        "url": f"https://www.tiktok.com/@{username}/video/{latest.get('id')}",
    }


async def main():
    await ensure_database_files()
    if API_ENABLED:
        thread = threading.Thread(target=start_api, daemon=True)
        thread.start()
    await bot.start(os.getenv("TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
