# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                  ║
# ║   ░█▀▀░█▀█░█▀▄░█▀▀░█░█   ░█▀▄░█▀▀░█░█░█▀▀                     ║
# ║   ░█░░░█░█░█░█░█▀▀░▄▀▄   ░█░█░█▀▀░▀▄▀░▀▀█                     ║
# ║   ░▀▀▀░▀▀▀░▀▀░░▀▀▀░▀░▀   ░▀▀░░▀▀▀░░▀░░▀▀▀                     ║
# ║                                                                  ║
# ║            © 2026 Bezms — All Rights Reserved                   ║
# ║                                                                  ║
# ║   discord  ──  https://discord.gg/9nKHrnWZqV                    ║
# ║   website  ──  https://your-website.com                         ║
# ║   github   ──  https://github.com/YOUR_USERNAME                 ║
# ║                                                                  ║
# ╚══════════════════════════════════════════════════════════════════╝

from __future__ import annotations
from discord.ext import commands, tasks
import discord
import aiohttp
import json
import jishaku
import asyncio
import typing
from typing import List
import aiosqlite
import os
import importlib
from utils.config import OWNER_IDS, BotName
from utils import getConfig, updateConfig
from .Context import Context
from colorama import Fore, Style, init
import inspect

init(autoreset=True)

class zyrox(commands.AutoShardedBot):
    def __init__(self, *arg, **kwargs):
        intents = discord.Intents.all()
        intents.presences = True
        intents.members = True
        super().__init__(command_prefix=self.get_prefix,
                         case_insensitive=True,
                         intents=intents,
                         strip_after_prefix=True,
                         owner_ids=OWNER_IDS,
                         allowed_mentions=discord.AllowedMentions(
                             everyone=False, replied_user=False, roles=False),
                         sync_commands_debug=True,
                         sync_commands=True,
                         shard_count=1)
        self.status_index = 0
        self.activity_list = []
        self.status_rotations = []

    async def setup_hook(self):
        await self.load_all_cogs()
        self.status_task.start()

    async def load_all_cogs(self):
        """Recursively load every .py file in the 'cogs' folder as a cog."""
        cogs_dir = os.path.join(os.path.dirname(__file__), "..", "cogs")
        if not os.path.exists(cogs_dir):
            print(Fore.YELLOW + "cogs folder not found!")
            return

        loaded = 0
        for root, dirs, files in os.walk(cogs_dir):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    # Build the module path: cogs.subfolder.filename
                    rel_path = os.path.relpath(root, cogs_dir)
                    if rel_path == ".":
                        module_path = f"cogs.{file[:-3]}"
                    else:
                        module_path = f"cogs.{rel_path.replace(os.sep, '.')}.{file[:-3]}"
                    
                    try:
                        # Load the cog
                        await self.load_extension(module_path)
                        print(Fore.GREEN + Style.BRIGHT + f"Loaded cog: {module_path}")
                        loaded += 1
                    except commands.ExtensionError as e:
                        # If it's a duplicate, skip; otherwise warn
                        if isinstance(e, commands.ExtensionAlreadyLoaded):
                            pass
                        elif "CommandRegistrationError" in str(e):
                            print(Fore.YELLOW + f"Skipped {module_path} (duplicate command)")
                        else:
                            print(Fore.RED + f"Failed to load {module_path}: {e}")
                    except Exception as e:
                        print(Fore.RED + f"Unexpected error loading {module_path}: {e}")

        print(Fore.GREEN + Style.BRIGHT + f"* Loaded {loaded} cog(s) *")

    @tasks.loop(seconds=30)
    async def status_task(self):
        await self.wait_until_ready()
        if not self.guilds:
            return

        guild = self.guilds[0]
        try:
            config = await getConfig(guild.id)
            prefix = config.get("prefix", "!")
        except:
            prefix = "!"

        user_count = sum(g.member_count or 0 for g in self.guilds)
        guild_count = len(self.guilds)

        combined_rotations = [
            (discord.Status.online, discord.ActivityType.playing, f"{prefix}help | Bezms Bot"),
            (discord.Status.idle, discord.ActivityType.watching, f"{user_count} users"),
            (discord.Status.do_not_disturb, discord.ActivityType.listening, "Bezms"),
            (discord.Status.online, discord.ActivityType.playing, f"Protector {BotName}"),
            (discord.Status.idle, discord.ActivityType.competing, "Anti-Nuke Active"),
            (discord.Status.do_not_disturb, discord.ActivityType.watching, f"{guild_count} servers"),
        ]

        current = combined_rotations[self.status_index % len(combined_rotations)]
        status, activity_type, activity_name = current

        await self.change_presence(
            status=status,
            activity=discord.Activity(type=activity_type, name=activity_name)
        )

        self.status_index += 1

    async def send_raw(self, channel_id: int, content: str, **kwargs) -> typing.Optional[discord.Message]:
        await self.http.send_message(channel_id, content, **kwargs)

    async def invoke_help_command(self, ctx: Context) -> None:
        return await ctx.send_help(ctx.command)

    async def fetch_message_by_channel(self, channel: discord.TextChannel, messageID: int) -> typing.Optional[discord.Message]:
        async for msg in channel.history(limit=1, before=discord.Object(messageID + 1), after=discord.Object(messageID - 1)):
            return msg

    async def get_prefix(self, message: discord.Message):
        if message.guild:
            guild_id = message.guild.id
            async with aiosqlite.connect('db/np.db') as db:
                async with db.execute("SELECT id FROM np WHERE id = ?", (message.author.id,)) as cursor:
                    row = await cursor.fetchone()
            data = await getConfig(guild_id)
            prefix = data["prefix"]
            if row:
                return commands.when_mentioned_or(prefix, '')(self, message)
            else:
                return commands.when_mentioned_or(prefix)(self, message)
        else:
            async with aiosqlite.connect('db/np.db') as db:
                async with db.execute("SELECT id FROM np WHERE id = ?", (message.author.id,)) as cursor:
                    row = await cursor.fetchone()
            if row:
                return commands.when_mentioned_or('!', '')(self, message)
            else:
                return commands.when_mentioned_or('!')(self, message)

    async def on_message_edit(self, before, after):
        ctx: Context = await self.get_context(after, cls=Context)
        if before.content != after.content:
            if after.guild is None or after.author.bot:
                return
            if ctx.command is None:
                return
            if type(ctx.channel) == "public_thread":
                return
            await self.invoke(ctx)

def setup_bot():
    intents = discord.Intents.all()
    bot = zyrox(intents=intents)
    return bot
