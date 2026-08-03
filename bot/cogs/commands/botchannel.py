"""
bot/cogs/commands/botchannel.py

Bot Command Channel system:
 - >botchannel set <#channel>  : restrict bot commands to one channel (owner-only)
 - >botchannel remove          : lift the restriction, commands work everywhere (owner-only)
 - >botchannel status          : show the current restriction for this server

A global check blocks every command from running anywhere except:
 - the configured channel for that server,
 - DMs (always allowed),
 - servers that have no restriction configured,
 - the bot owner (always allowed, so they can never lock themselves out),
 - the `botchannel` command group itself (so it can always be managed/viewed).

Storage: SQLite at db/botchannel.db. A guild_id -> channel_id map is cached in
memory on load so the global check (which runs on every single command) never
has to hit the database.
"""

import discord
from discord.ext import commands
import sqlite3
import os
import asyncio

DB_DIR = os.path.join("db")
DB_PATH = os.path.join(DB_DIR, "botchannel.db")

# Commands that are always allowed to run, regardless of the channel restriction.
# This guarantees the bot channel system can always be managed/inspected.
EXEMPT_COMMAND_ROOTS = {"botchannel"}


def _get_connection() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_channel (
            guild_id   INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    return conn


class BotChannel(commands.Cog):
    """Restricts command usage to a single designated channel per server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel_cache: dict[int, int] = {}
        self._load_cache()

        # Register the global check. Stored as a bound method reference so it
        # can be cleanly removed again in cog_unload.
        self.bot.add_check(self.global_channel_check)

    def cog_unload(self):
        self.bot.remove_check(self.global_channel_check)

    # ------------------------------------------------------------------ #
    # INTERNAL HELPERS
    # ------------------------------------------------------------------ #
    def _load_cache(self):
        """Load every guild's configured channel into memory on startup."""
        conn = _get_connection()
        try:
            rows = conn.execute("SELECT guild_id, channel_id FROM bot_channel").fetchall()
            self.channel_cache = {guild_id: channel_id for guild_id, channel_id in rows}
        finally:
            conn.close()

    async def _set_channel(self, guild_id: int, channel_id: int):
        def _write():
            conn = _get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO bot_channel (guild_id, channel_id)
                    VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
                    """,
                    (guild_id, channel_id),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_write)
        self.channel_cache[guild_id] = channel_id

    async def _remove_channel(self, guild_id: int):
        def _write():
            conn = _get_connection()
            try:
                conn.execute("DELETE FROM bot_channel WHERE guild_id = ?", (guild_id,))
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_write)
        self.channel_cache.pop(guild_id, None)

    # ------------------------------------------------------------------ #
    # GLOBAL CHECK
    # ------------------------------------------------------------------ #
    async def global_channel_check(self, ctx: commands.Context) -> bool:
        """Blocks command execution outside the configured bot channel."""
        # Always allow in DMs.
        if ctx.guild is None:
            return True

        # Always allow the bot owner, so a bad config can never lock them out.
        if await self.bot.is_owner(ctx.author):
            return True

        # Always allow managing/inspecting the bot channel system itself.
        root_command = ctx.command.root_parent.name if ctx.command.root_parent else ctx.command.name
        if root_command in EXEMPT_COMMAND_ROOTS:
            return True

        configured_channel_id = self.channel_cache.get(ctx.guild.id)

        # No restriction configured for this server -> allow everywhere.
        if configured_channel_id is None:
            return True

        if ctx.channel.id == configured_channel_id:
            return True

        # Wrong channel — block, and let the user know where to go.
        channel = ctx.guild.get_channel(configured_channel_id)
        if channel:
            try:
                await ctx.send(
                    f"❌ Commands can only be used in {channel.mention}.",
                    delete_after=6,
                )
            except discord.HTTPException:
                pass
        return False

    # ------------------------------------------------------------------ #
    # COMMANDS
    # ------------------------------------------------------------------ #
    @commands.group(name="botchannel", invoke_without_command=True)
    async def botchannel(self, ctx: commands.Context):
        """Base command for the bot command channel system. Subcommands: set, remove, status."""
        await ctx.send_help(ctx.command)

    @botchannel.command(name="set")
    @commands.is_owner()
    async def botchannel_set(self, ctx: commands.Context, channel: discord.TextChannel):
        """Restrict bot commands to a single channel. Owner-only."""
        await self._set_channel(ctx.guild.id, channel.id)
        await ctx.send(f"✅ Bot commands are now restricted to {channel.mention}.")

    @botchannel.command(name="remove")
    @commands.is_owner()
    async def botchannel_remove(self, ctx: commands.Context):
        """Remove the channel restriction so commands work everywhere. Owner-only."""
        if ctx.guild.id not in self.channel_cache:
            return await ctx.send("There is no bot channel restriction configured for this server.")
        await self._remove_channel(ctx.guild.id)
        await ctx.send("✅ Bot channel restriction removed. Commands now work in every channel.")

    @botchannel.command(name="status")
    async def botchannel_status(self, ctx: commands.Context):
        """Show the current bot channel configuration for this server."""
        channel_id = self.channel_cache.get(ctx.guild.id)

        embed = discord.Embed(title="Bot Channel Status", color=discord.Color.blurple())
        if channel_id is None:
            embed.description = "No restriction is configured — commands work in **every channel**."
        else:
            channel = ctx.guild.get_channel(channel_id)
            embed.description = (
                f"Commands are restricted to {channel.mention if channel else f'`{channel_id}` (channel not found)'}."
            )
        await ctx.send(embed=embed)

    @botchannel_set.error
    async def botchannel_set_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.ChannelNotFound):
            await ctx.send("I couldn't find that channel.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `>botchannel set #channel`")
        elif isinstance(error, commands.NotOwner):
            await ctx.send("Only the bot owner can use this command.")

    @botchannel_remove.error
    async def botchannel_remove_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.NotOwner):
            await ctx.send("Only the bot owner can use this command.")


async def setup(bot: commands.Bot):
    await bot.add_cog(BotChannel(bot))
