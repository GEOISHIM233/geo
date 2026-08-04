import discord
from discord.ext import commands
from discord.ui import Select, View
import aiosqlite
import asyncio
from typing import Optional
from contextlib import suppress

class LeaveSetupView(discord.ui.View):
    class LeaveChannelSelect(discord.ui.ChannelSelect):
        def __init__(self, parent_view: "LeaveSetupView"):
            super().__init__(placeholder="Select a goodbye channel", channel_types=[discord.ChannelType.text], min_values=1, max_values=1)
            self.parent_view = parent_view

        async def callback(self, interaction: discord.Interaction):
            self.parent_view.selected_channel = self.values[0]
            await interaction.response.send_message(
                f"Selected {self.parent_view.selected_channel.mention} for goodbye messages.", ephemeral=True
            )

    def __init__(self, cog, author: discord.Member):
        super().__init__(timeout=120)
        self.cog = cog
        self.author = author
        self.selected_channel: Optional[discord.TextChannel] = None
        self.mode = "simple"
        self.add_item(self.LeaveChannelSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command author can configure the leave system.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Simple Mode", style=discord.ButtonStyle.secondary)
    async def simple_mode(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.mode = "simple"
        await interaction.response.send_message("Leave messages will use simple mode.", ephemeral=True)

    @discord.ui.button(label="Embed Mode", style=discord.ButtonStyle.success)
    async def embed_mode(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.mode = "embed"
        await interaction.response.send_message("Leave messages will use embed mode.", ephemeral=True)

    @discord.ui.button(label="Save", style=discord.ButtonStyle.primary)
    async def save(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not self.selected_channel:
            await interaction.response.send_message("Please choose a channel before saving.", ephemeral=True)
            return
        await self.cog.update_leave_config(
            self.author.guild.id,
            self.selected_channel.id,
            self.mode,
            None,
            0,
            self.mode == "embed",
        )
        self.stop()
        await interaction.response.edit_message(content=f"Leave system configured in {self.selected_channel.mention} using {self.mode} mode.", embed=None, view=None)


class LeaveSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/leave.db"
        self.color = 0xFF4444

    async def ensure_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS leave_config (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    enabled INTEGER DEFAULT 1,
                    mode TEXT DEFAULT 'simple',
                    message TEXT,
                    autodelete INTEGER DEFAULT 0,
                    embed INTEGER DEFAULT 0
                )
            ''')
            await db.commit()

    async def get_config(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT channel_id, enabled, mode, message, autodelete, embed FROM leave_config WHERE guild_id = ?', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                return row if row else (None, 1, "simple", None, 0, 0)

    async def set_config(self, guild_id, channel_id=None, enabled=None, mode=None, message=None, autodelete=None, embed=None):
        current = await self.get_config(guild_id)
        async with aiosqlite.connect(self.db_path) as db:
            if current:
                await db.execute('''
                    INSERT INTO leave_config (guild_id, channel_id, enabled, mode, message, autodelete, embed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id, enabled = excluded.enabled, mode = excluded.mode, message = excluded.message, autodelete = excluded.autodelete, embed = excluded.embed
                ''', (
                    guild_id,
                    channel_id if channel_id is not None else current[0],
                    enabled if enabled is not None else current[1],
                    mode if mode is not None else current[2],
                    message if message is not None else current[3],
                    autodelete if autodelete is not None else current[4],
                    1 if (embed if embed is not None else current[5]) else 0,
                ))
            else:
                await db.execute('''
                    INSERT INTO leave_config (guild_id, channel_id, enabled, mode, message, autodelete, embed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    guild_id,
                    channel_id or 0,
                    enabled if enabled is not None else 1,
                    mode or "simple",
                    message or "{user} left {server}.",
                    autodelete if autodelete is not None else 0,
                    1 if embed else 0,
                ))
            await db.commit()

    async def format_message(self, member: discord.Member, message: str):
        if not message:
            return f"**{member.display_name}** has left {member.guild.name}."
        return (
            message.replace("{user}", member.mention)
            .replace("{server}", member.guild.name)
            .replace("{member_count}", str(member.guild.member_count))
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        channel_id, enabled, mode, msg, autodelete, embed_flag = await self.get_config(guild.id)
        if not enabled or not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        text = await self.format_message(member, msg or "{user} left {server}. We now have {member_count} members.")
        if embed_flag:
            embed = discord.Embed(title="👋 Goodbye!", description=text, color=self.color)
            embed.set_footer(text="Bezms Bot")
            await channel.send(embed=embed)
            message = await channel.send(embed=embed)
        else:
            message = await channel.send(text)

        if autodelete and autodelete > 0:
            await asyncio.sleep(autodelete)
            with suppress(discord.NotFound):
                await message.delete()

    @commands.group(name='leave', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def leave(self, ctx):
        embed = discord.Embed(
            title="📋 Leave System",
            description="Use `>leave setup` to configure goodbye messages.",
            color=self.color,
        )
        embed.add_field(name=">leave setup", value="Interactive setup wizard for goodbye messages", inline=False)
        embed.add_field(name=">leave reset", value="Reset all leave configuration", inline=False)
        embed.add_field(name=">leave test", value="Send a test goodbye message", inline=False)
        embed.add_field(name=">leave config", value="Show current leave configuration", inline=False)
        embed.add_field(name=">leave edit <message>", value="Edit the goodbye message using {user}, {server}, {member_count}", inline=False)
        embed.add_field(name=">leave autodelete <seconds>", value="Automatically delete goodbye messages after a time", inline=False)
        embed.set_footer(text="Bezms Bot")
        await ctx.send(embed=embed)

    @leave.command(name='setup')
    @commands.has_permissions(administrator=True)
    async def leave_setup(self, ctx):
        await self.ensure_db()
        if not ctx.guild:
            return await ctx.send("This command must be used in a server.")
        view = LeaveSetupView(self, ctx.author)
        await ctx.send(
            "Select a goodbye channel and mode, then click Save.",
            view=view,
        )

    @leave.command(name='reset')
    @commands.has_permissions(administrator=True)
    async def leave_reset(self, ctx):
        await self.ensure_db()
        await self.set_config(ctx.guild.id, channel_id=0, enabled=0, mode="simple", message="{user} left {server}.", autodelete=0, embed=0)
        await ctx.send("✅ Leave system configuration has been reset.")

    @leave.command(name='test')
    @commands.has_permissions(administrator=True)
    async def leave_test(self, ctx):
        await self.ensure_db()
        channel_id, enabled, mode, message, autodelete, embed_flag = await self.get_config(ctx.guild.id)
        if not enabled or not channel_id:
            return await ctx.send("Leave system is not configured yet.")

        channel = ctx.guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("Configured goodbye channel could not be found.")

        text = await self.format_message(ctx.author, message or "{user} left {server}. We now have {member_count} members.")
        if embed_flag:
            embed = discord.Embed(title="Goodbye Test", description=text, color=self.color)
            embed.set_footer(text="Bezms Bot")
            await channel.send(embed=embed)
        else:
            await channel.send(text)
        await ctx.send(f"Sent a test goodbye message to {channel.mention}.")

    @leave.command(name='config')
    @commands.has_permissions(administrator=True)
    async def leave_config(self, ctx):
        await self.ensure_db()
        channel_id, enabled, mode, message, autodelete, embed_flag = await self.get_config(ctx.guild.id)
        embed = discord.Embed(title="Leave System Configuration", color=self.color)
        embed.add_field(name="Channel", value=f"<#{channel_id}>" if channel_id else "Not set", inline=False)
        embed.add_field(name="Enabled", value="✅" if enabled else "❌", inline=False)
        embed.add_field(name="Mode", value=mode or "simple", inline=False)
        embed.add_field(name="Embed", value="Yes" if embed_flag else "No", inline=False)
        embed.add_field(name="Autodelete", value=f"{autodelete}s" if autodelete else "Disabled", inline=False)
        embed.add_field(name="Message", value=message or "{user} left {server}.", inline=False)
        embed.set_footer(text="Bezms Bot")
        await ctx.send(embed=embed)

    @leave.command(name='edit')
    @commands.has_permissions(administrator=True)
    async def leave_edit(self, ctx, *, message: str):
        await self.ensure_db()
        await self.set_config(ctx.guild.id, message=message)
        await ctx.send("✅ Leave message updated.")

    @leave.command(name='autodelete')
    @commands.has_permissions(administrator=True)
    async def leave_autodelete(self, ctx, seconds: int):
        seconds = max(0, seconds)
        await self.ensure_db()
        await self.set_config(ctx.guild.id, autodelete=seconds)
        await ctx.send(f"✅ Leave messages will be deleted after {seconds}s." if seconds else "Leave autodelete disabled.")

    async def update_leave_config(self, guild_id: int, channel_id: int, mode: str, message: str, autodelete: int, embed: bool):
        await self.set_config(guild_id, channel_id=channel_id, mode=mode, message=message, autodelete=autodelete, embed=embed)

    @commands.command(name='gtfo', aliases=['yeet'])
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def gtfo(self, ctx, member: discord.Member, *, reason: str = "No reason"):
        if ctx.author.top_role <= member.top_role:
            return await ctx.send("⛔ You can't kick someone with higher/equal role.", delete_after=10)
        if ctx.guild.me.top_role <= member.top_role:
            return await ctx.send("⚠️ I can't kick that user.", delete_after=10)

        if member.guild_permissions.kick_members or member.guild_permissions.ban_members:
            try:
                await member.ban(reason=f"{ctx.author}: {reason}")
                result = f"🔨 **Banned** {member.mention} (had mod perms)."
            except:
                result = "❌ Failed to ban."
        else:
            try:
                await member.kick(reason=f"{ctx.author}: {reason}")
                result = f"👢 **Kicked** {member.mention}."
            except:
                result = "❌ Failed to kick."

        embed = discord.Embed(title="🚀 GTFO!", description=result, color=0xFF0000)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LeaveSystem(bot))
