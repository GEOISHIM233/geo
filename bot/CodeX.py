# ╔══════════════════════════════════════════════════════════════════╗
# ║            © 2026 Bezms — All Rights Reserved                   ║
# ║   discord  ──  https://discord.gg/9nKHrnWZqV                    ║
# ╚══════════════════════════════════════════════════════════════════╝

import os
import asyncio
import traceback
import aiohttp
import discord
from discord.ext import commands
from core import Context
from core.zyrox import zyrox
from utils.Tools import *
from utils.config import *
from utils.emoji import SUCCESS, ERROR, TICK, CROSS
from utils.sync_emojis import run_sync
import jishaku

# --- FastAPI imports ---
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import threading

os.environ["JISHAKU_NO_DM_TRACEBACK"] = "False"
os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TOKEN")
API_ENABLED = os.getenv("API_ENABLED", "false").lower() == "true"
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "")

# --- Configuration (replace with your channel IDs) ---
SERVER_COUNT_CHANNEL_ID = 1419729255977189467
USER_COUNT_CHANNEL_ID = 1419729283861184632
LOG_CHANNEL_ID = 1396794297386532978

client = zyrox()
tree = client.tree

# --- Completely disable Lavalink ---
os.environ["LAVALINK_HOST"] = ""
os.environ["LAVALINK_PORT"] = "0"
print("⚠️ Lavalink disabled. Music commands will not work.")

async def update_stats():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            servers = len(client.guilds)
            users = sum(g.member_count for g in client.guilds if g.member_count)
            server_channel = client.get_channel(SERVER_COUNT_CHANNEL_ID)
            user_channel = client.get_channel(USER_COUNT_CHANNEL_ID)
            if server_channel:
                await server_channel.edit(name=f"Servers: {servers}")
            if user_channel:
                await user_channel.edit(name=f"Users: {users}")
        except Exception as e:
            print(f"Stats error: {e}")
        await asyncio.sleep(600)

async def sync_commands():
    await client.wait_until_ready()
    try:
        synced = await client.tree.sync()
        all_cmds = list(client.commands)
        print(f"✅ Synced {len(all_cmds)} text commands and {len(synced)} slash commands")
        if len(synced) == 0:
            print("⚠️ No slash commands synced – check cogs loading.")
    except Exception as e:
        print(f"❌ Sync error: {e}")

original_setup_hook = client.setup_hook
async def new_setup_hook():
    await original_setup_hook()
    client.loop.create_task(sync_commands())
    client.loop.create_task(update_stats())
client.setup_hook = new_setup_hook

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
    await run_sync(TOKEN)
    try:
        synced = await client.tree.sync()
        print(f"✅ Force sync: {len(synced)} slash commands synced")
    except Exception as e:
        print(f"❌ Force sync failed: {e}")

@client.event
async def on_guild_join(guild: discord.Guild):
    log = client.get_channel(LOG_CHANNEL_ID)
    if log:
        await log.send(f"Added to: **{guild.name}** (`{guild.id}`)")
    try:
        await client.tree.sync()
        print(f"✅ Synced for new guild: {guild.name}")
    except Exception as e:
        print(f"❌ Sync failed for {guild.name}: {e}")

@client.event
async def on_command_completion(ctx: commands.Context):
    if ctx.author.id in OWNER_IDS:
        return
    webhook_url = CMD_WEBHOOK_URL
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(webhook_url, session=session)
        embed = discord.Embed(color=0xFF0000)
        embed.set_author(name=f"Cmd: {ctx.command.qualified_name}", icon_url=ctx.author.display_avatar.url)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(name="User", value=f"{ctx.author} (`{ctx.author.id}`)", inline=False)
        if ctx.guild:
            embed.add_field(name="Server", value=f"{ctx.guild.name} (`{ctx.guild.id}`)", inline=False)
            embed.add_field(name="Channel", value=f"{ctx.channel.mention} (`{ctx.channel.id}`)", inline=False)
        embed.timestamp = discord.utils.utcnow()
        try:
            await webhook.send(embed=embed)
        except:
            pass

@client.event
async def on_guild_remove(guild: discord.Guild):
    log = client.get_channel(LOG_CHANNEL_ID)
    if log:
        await log.send(f"Removed from: **{guild.name}** (`{guild.id}`)")

# --- FastAPI Server ---
if API_ENABLED:
    app = FastAPI(title="Bezms Bot API", version="1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        return {"status": "online", "bot": client.user.name if client.user else "Unknown"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/guilds")
    async def get_guilds(api_key: str = Header(...)):
        if api_key != DASHBOARD_API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")
        if not client.is_ready():
            return {"guilds": []}
        guilds = []
        for g in client.guilds:
            guilds.append({
                "id": str(g.id),
                "name": g.name,
                "icon": g.icon.url if g.icon else None,
                "member_count": g.member_count,
                "owner_id": str(g.owner_id)
            })
        return {"guilds": guilds}

    @app.get("/guild/{guild_id}")
    async def get_guild(guild_id: str, api_key: str = Header(...)):
        if api_key != DASHBOARD_API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")
        guild = client.get_guild(int(guild_id))
        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")
        return {
            "id": str(guild.id),
            "name": guild.name,
            "icon": guild.icon.url if guild.icon else None,
            "member_count": guild.member_count,
            "owner_id": str(guild.owner_id),
            "channels": [{"id": str(c.id), "name": c.name, "type": str(c.type)} for c in guild.channels],
            "roles": [{"id": str(r.id), "name": r.name, "color": r.color.value} for r in guild.roles]
        }

    def run_api():
        port = int(os.environ.get("PORT", 8000))
        uvicorn.run(app, host="0.0.0.0", port=port)

    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    print(f"✅ API server started on port {os.environ.get('PORT', 8000)}")
else:
    print("⚠️ API is disabled (API_ENABLED not set to true)")

if __name__ == "__main__":
    try:
        client.run(TOKEN)
    except discord.LoginFailure:
        print("Invalid token. Check TOKEN env var.")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
