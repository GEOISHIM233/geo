# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                  ║
# ║   ░█▀▀░█▀█░█▀▄░█▀▀░█░█   ░█▀▄░█▀▀░█░█░█▀▀                     ║
# ║   ░█░░░█░█░█░█░█▀▀░▄▀▄   ░█░█░█▀▀░▀▄▀░▀▀█                     ║
# ║   ░▀▀▀░▀▀▀░▀▀░░▀▀▀░▀░▀   ░▀▀░░▀▀▀░░▀░░▀▀▀                     ║
# ║                                                                  ║
# ║            © 2026 Bezms — All Rights Reserved                   ║
# ║                                                                  ║
# ║   discord  ──  https://discord.gg/9nKHrnWZqV                    ║
# ║   youtube  ──  https://youtube.com/@Bezms                       ║
# ║   github   ──  https://github.com/YOUR_USERNAME                 ║
# ║                                                                  ║
# ╚══════════════════════════════════════════════════════════════════╝

import os
import asyncio
import traceback
import aiohttp
import discord
from discord.ext import commands
from core import Context
from core.Cog import Cog
from core.zyrox import zyrox
from utils.Tools import *
from utils.config import *
from utils.emoji import SUCCESS, ERROR, TICK, CROSS
from utils.sync_emojis import run_sync
import jishaku

os.environ["JISHAKU_NO_DM_TRACEBACK"] = "False"
os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TOKEN")

# --- Configuration ---
# Replace these with your actual channel IDs
SERVER_COUNT_CHANNEL_ID = 1419729255977189467
USER_COUNT_CHANNEL_ID = 1419729283861184632
LOG_CHANNEL_ID = 1396794297386532978

client = zyrox()
tree = client.tree

# --- Disable Lavalink if host is empty ---
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "")
if not LAVALINK_HOST:
    os.environ["LAVALINK_HOST"] = ""  # Ensure it's empty
    print("⚠️ Lavalink disabled (host not set). Music commands will not work.")
else:
    print(f"✅ Lavalink configured with host: {LAVALINK_HOST}")

# --- Background Tasks ---
async def update_stats():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            servers = len(client.guilds)
            users = sum(g.member_count for g in client.guilds if g.member_count is not None)
            server_channel = client.get_channel(SERVER_COUNT_CHANNEL_ID)
            user_channel = client.get_channel(USER_COUNT_CHANNEL_ID)
            if server_channel:
                await server_channel.edit(name=f"Servers: {servers}")
            if user_channel:
                await user_channel.edit(name=f"Users: {users}")
        except Exception as e:
            print(f"Error updating stats: {e}")
        await asyncio.sleep(600)

async def sync_commands():
    await client.wait_until_ready()
    try:
        synced = await client.tree.sync()
        all_commands = list(client.commands)
        print(f"✅ Synced Total {len(all_commands)} Client Commands and {len(synced)} Slash Commands")
        if len(synced) == 0:
            print("⚠️ WARNING: 0 slash commands synced! Check if cogs are loading properly.")
    except Exception as e:
        print(f"❌ Error syncing command tree: {e}")

# --- Override setup_hook ---
original_setup_hook = client.setup_hook

async def new_setup_hook():
    await original_setup_hook()
    client.loop.create_task(sync_commands())
    client.loop.create_task(update_stats())

client.setup_hook = new_setup_hook

# --- Events ---
@client.event
async def on_ready():
    await client.wait_until_ready()
    print("""
\033[1;31m
 ██████╗ ██████╗ ██████╗ ███████╗██╗  ██╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝╚██╗██╔╝
██║     ██║   ██║██║  ██║█████╗   ╚███╔╝
██║     ██║   ██║██║  ██║██╔══╝   ██╔██╗
╚██████╗╚██████╔╝██████╔╝███████╗██╔╝ ██╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
\033[0m
""")
    print("Loaded & Online!")
    print(f"Logged in as: {client.user}")
    print(f"Connected to: {len(client.guilds)} guilds")
    print(f"Connected to: {len(client.users)} users")
    print("Bot Name: Bezms Bot")
    print(f"Support Server: https://discord.gg/9nKHrnWZqV")

    await run_sync(TOKEN)

    # Force sync again after ready
    try:
        synced = await client.tree.sync()
        print(f"✅ Force sync: {len(synced)} slash commands synced on ready")
    except Exception as e:
        print(f"❌ Failed to force sync: {e}")

@client.event
async def on_guild_join(guild: discord.Guild):
    log_channel = client.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"Bezms Bot added to: **{guild.name}** (ID: `{guild.id}`)")
    # Sync commands for new guild
    try:
        await client.tree.sync()
        print(f"✅ Slash commands synced for new guild: {guild.name}")
    except Exception as e:
        print(f"❌ Failed to sync for new guild: {e}")

@client.event
async def on_command_completion(context: commands.Context) -> None:
    if context.author.id in OWNER_IDS:
        return
    full_command_name = context.command.qualified_name
    executed_command = full_command_name.split("\n")[0]
    webhook_url = CMD_WEBHOOK_URL
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(webhook_url, session=session)
        embed = discord.Embed(color=0xFF0000)
        embed.set_author(name=f"Cmd Executed: {executed_command}", icon_url=context.author.display_avatar.url)
        embed.set_thumbnail(url=context.author.display_avatar.url)
        if context.guild is not None:
            embed.add_field(name="User", value=f"{context.author.mention} (`{context.author.id}`)", inline=False)
            embed.add_field(name="Server", value=f"{context.guild.name} (`{context.guild.id}`)", inline=False)
            embed.add_field(name="Channel", value=f"{context.channel.mention} (`{context.channel.id}`)", inline=False)
        else:
            embed.add_field(name="User (DM)", value=f"{context.author.mention} (`{context.author.id}`)", inline=False)
        embed.timestamp = discord.utils.utcnow()
        try:
            await webhook.send(embed=embed)
        except Exception as e:
            print(f"Webhook send failed: {e}")

@client.event
async def on_guild_remove(guild: discord.Guild):
    log_channel = client.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"Bezms Bot removed from: **{guild.name}** (ID: `{guild.id}`)")

if __name__ == "__main__":
    try:
        client.run(TOKEN)
    except discord.LoginFailure:
        print("Invalid token. Check your TOKEN environment variable.")
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
