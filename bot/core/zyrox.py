# ╔══════════════════════════════════════════════════════════════════╗
# ║            © 2026 Bezms — All Rights Reserved                   ║
# ║   discord  ──  https://discord.gg/9nKHrnWZqV                    ║
# ╚══════════════════════════════════════════════════════════════════╝

from __future__ import annotations
from discord.ext import commands, tasks
import discord
import aiosqlite
import os
import importlib
from utils.config import OWNER_IDS, BotName
from utils import getConfig
from .Context import Context
from colorama import Fore, Style, init

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
        # REMOVE the duplicate clear command (prevents CommandRegistrationError)
        self.remove_command("clear")
        self.status_index = 0

    async def setup_hook(self):
        # Load cogs by importing the setup function directly
        try:
            import cogs
            if hasattr(cogs, 'setup'):
                await cogs.setup(self)
                print(Fore.GREEN + Style.BRIGHT + "Loaded cogs via setup() successfully!")
            else:
                print(Fore.RED + Style.BRIGHT + "cogs.__init__ has no setup() function!")
        except Exception as e:
            print(Fore.RED + Style.BRIGHT + f"Failed to load cogs: {e}")
        
        print(Fore.GREEN + Style.BRIGHT + "*" * 20)
        self.status_task.start()

    @tasks.loop(seconds=30)
    async def status_task(self):
        await self.wait_until_ready()
        if not self.guilds:
            return
        guild = self.guilds[0]
        try:
            config = await getConfig(guild.id)
            prefix = config.get("prefix", ">")
        except:
            prefix = ">"
        user_count = sum(g.member_count or 0 for g in self.guilds)
        guild_count = len(self.guilds)
        statuses = [
            (discord.Status.online, discord.ActivityType.playing, f"{prefix}help | Bezms Bot"),
            (discord.Status.idle, discord.ActivityType.watching, f"{user_count} users"),
            (discord.Status.do_not_disturb, discord.ActivityType.listening, "Bezms"),
            (discord.Status.online, discord.ActivityType.playing, f"Protector {BotName}"),
            (discord.Status.idle, discord.ActivityType.competing, "Anti-Nuke Active"),
            (discord.Status.do_not_disturb, discord.ActivityType.watching, f"{guild_count} servers"),
        ]
        current = statuses[self.status_index % len(statuses)]
        await self.change_presence(status=current[0], activity=discord.Activity(type=current[1], name=current[2]))
        self.status_index += 1

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
                return commands.when_mentioned_or('>', '')(self, message)
            else:
                return commands.when_mentioned_or('>')(self, message)

    async def on_message_edit(self, before, after):
        ctx: Context = await self.get_context(after, cls=Context)
        if before.content != after.content and not after.author.bot and ctx.command:
            await self.invoke(ctx)

def setup_bot():
    bot = zyrox()
    return bot
