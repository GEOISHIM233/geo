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
import subprocess
import asyncio
import traceback
from threading import Thread
from datetime import datetime
import random
import time
import aiohttp
import discord
from discord import Spotify
from discord.ext import commands, tasks
from core import Context
from core.Cog import Cog
from core.zyrox import zyrox
from utils.Tools import *
from utils.config import *
from utils.emoji import SUCCESS, ERROR, TICK, CROSS, REACTION_TEST_EMOJIS
from utils.sync_emojis import run_sync
import jishaku
import cogs

os.environ["JISHAKU_NO_DM_TRACEBACK"] = "False"
os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TOKEN")

# --- Configuration ---
# IMPORTANT: Replace these with your actual channel IDs.
SERVER_COUNT_CHANNEL_ID = 1419729255977189467  # Replace with your server count channel ID
USER_COUNT_CHANNEL_ID = 1419729283861184632   # Replace with your user count channel ID
LOG_CHANNEL_ID = 1396794297386532978          # Replace with the channel ID for join/leave logs

client = zyrox()
tree = client.tree

# --- Background Task for Stats ---
async def update_stats():
    """A background task to update server and user stats in channel names."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            servers = len(client.guilds)
            users = sum(guild.member_count for guild in client.guilds if guild.member_count is not None)

            server_channel = client.get_channel(SERVER_COUNT_CHANNEL_ID)
            user_channel = client.get_channel(USER_COUNT_CHANNEL_ID)

            if server_channel:
                await server_channel.edit(name=f"Servers: {servers}")
            if user_channel:
                await user_channel.edit(name=f"Users: {users}")
        except Exception as e:
            print(f"Error updating stats: {e}")
        await asyncio.sleep(600)  # Update every 10 minutes

# --- Event Handlers ---
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

    # Sync application emojis on startup
    await run_sync(TOKEN)

async def sync_commands():
    try:
        synced = await client.tree.sync()
        all_commands = list(client.commands)
        print(f"Synced Total {len(all_commands)} Client Commands and {len(synced)} Slash Commands")
    except Exception as e:
        print(f"Error syncing command tree: {e}")

client.loop.create_task(sync_commands())
client.loop.create_task(update_stats())

@client.event
async def on_guild_join(guild: discord.Guild):
    # Log when the bot joins a server
    log_channel = client.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"Bezms Bot has been added to the server: **{guild.name}** (ID: `{guild.id}`)")

@client.event
async def on_command_completion(context: commands.Context) -> None:
    if context.author.id in OWNER_IDS:
        return

    full_command_name = context.command.qualified_name
    split = full_command_name.split("\n")
    executed_command = str(split[0])

    webhook_url = CMD_WEBHOOK_URL
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(webhook_url, session=session)
        embed_color = 0xFF0000
        embed = discord.Embed(color=embed_color)
        avatar_url = context.author.display_avatar.url
        embed.set_author(name=f"Cmd Executed: {executed_command}", icon_url=avatar_url)
        embed.set_thumbnail(url=avatar_url)
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
            print(f"Failed to send command log to webhook: {e}")

@client.event
async def on_guild_remove(guild: discord.Guild):
    # Log when the bot leaves a server
    log_channel = client.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"Bezms Bot has been removed from the server: **{guild.name}** (ID: `{guild.id}`)")

if __name__ == "__main__":
    try:
        client.run(TOKEN)
    except discord.LoginFailure:
        print("Invalid token. Please check your TOKEN environment variable.")
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
