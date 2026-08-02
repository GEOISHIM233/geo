import discord
from discord.ext import commands
from discord.ui import Select, View
import aiosqlite
import asyncio
import os


class LeaveSystem(commands.Cog):
    """Leave/goodbye system for when members leave the server."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/leave.db"
        self.color = 0xFF4444
        self.bot.loop.create_task(self.ensure_db())

    async def ensure_db(self):
        """Create database if it doesn't exist."""
        if not os.path.exists('db'):
            os.makedirs('db')
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS leave_config (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER,
                    enabled INTEGER DEFAULT 1,
                    message TEXT
                )
            ''')
            await db.commit()

    async def get_config(self, guild_id):
        """Get leave config for a guild."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT channel_id, enabled, message FROM leave_config WHERE guild_id = ?', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                return row if row else (None, 1, None)

    async def set_config(self, guild_id, channel_id=None, enabled=None, message=None):
        """Set leave config for a guild."""
        async with aiosqlite.connect(self.db_path) as db:
            current = await self.get_config(guild_id)
            if current[0] is not None:
                await db.execute('''
                    UPDATE leave_config SET channel_id = ?, enabled = ?, message = ? WHERE guild_id = ?
                ''', (channel_id if channel_id is not None else current[0],
                      enabled if enabled is not None else current[1],
                      message if message is not None else current[2],
                      guild_id))
            else:
                await db.execute('''
                    INSERT INTO leave_config (guild_id, channel_id, enabled, message)
                    VALUES (?, ?, ?, ?)
                ''', (guild_id, channel_id or 0, enabled if enabled is not None else 1, message or ''))
            await db.commit()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Send goodbye message when member leaves."""
        guild = member.guild
        channel_id, enabled, msg = await self.get_config(guild.id)
        
        if not enabled or not channel_id:
            return
        
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        # Build goodbye message
        goodbye_msg = msg.format(user=member.display_name) if msg else f"**{member.display_name}** has left the server."
        
        embed = discord.Embed(
            title="👋 Goodbye!",
            description=goodbye_msg,
            color=self.color
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Member", value=f"{member.mention} ({member})", inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Joined", value=member.joined_at.strftime("%Y-%m-%d %H:%M") if member.joined_at else "Unknown", inline=True)
        embed.set_footer(text=f"Member Count: {len(guild.members)}")
        embed.timestamp = discord.utils.utcnow()
        
        try:
            await channel.send(embed=embed)
        except:
            pass

    @commands.group(name='leave', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def leave(self, ctx):
        """Leave system group command."""
        embed = discord.Embed(
            title="📋 Leave System",
            description="Configure goodbye messages for when members leave.",
            color=self.color
        )
        embed.add_field(name=">leave setup", value="Set the goodbye channel via dropdown", inline=False)
        embed.add_field(name=">leave message <text>", value="Set custom message (use {user} placeholder)", inline=False)
        embed.add_field(name=">leave toggle", value="Enable/disable goodbye messages", inline=False)
        embed.add_field(name=">leave status", value="Show current configuration", inline=False)
        embed.set_footer(text="Use >leave <subcommand> to manage goodbye messages")
        await ctx.send(embed=embed)

    @leave.command(name='setup')
    @commands.has_permissions(administrator=True)
    async def leave_setup(self, ctx):
        """Setup goodbye channel."""
        await self.ensure_db()
        channels = [c for c in ctx.guild.channels if isinstance(c, discord.TextChannel)]
        
        if not channels:
            embed = discord.Embed(title="❌ Error", description="No text channels found in this server.", color=discord.Color.red())
            return await ctx.send(embed=embed)
        
        # Create dropdown
        select = Select(
            placeholder="Select channel for goodbye messages...",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label=ch.name[:100], value=str(ch.id)) for ch in channels[:25]]
        )
        
        async def select_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("❌ Not for you.", ephemeral=True)
            
            await self.set_config(ctx.guild.id, channel_id=int(select.values[0]), enabled=1)
            embed = discord.Embed(
                title="✅ Goodbye Channel Set",
                description=f"Goodbye messages will be sent to <#{select.values[0]}>",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(embed=embed, view=None)
        
        select.callback = select_callback
        
        view = View()
        view.add_item(select)
        embed = discord.Embed(
            title="🛠️ Leave System Setup",
            description="Select a channel where goodbye messages will be sent:",
            color=self.color
        )
        await ctx.send(embed=embed, view=view)

    @leave.command(name='message')
    @commands.has_permissions(administrator=True)
    async def leave_message(self, ctx, *, message: str):
        """Set custom goodbye message."""
        await self.ensure_db()
        await self.set_config(ctx.guild.id, message=message)
        embed = discord.Embed(
            title="✅ Goodbye Message Set",
            description=f"New message: `{message}`\n\nUse `{{user}}` as placeholder for the member's name.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @leave.command(name='toggle')
    @commands.has_permissions(administrator=True)
    async def leave_toggle(self, ctx):
        """Toggle goodbye messages on/off."""
        await self.ensure_db()
        _, enabled, _ = await self.get_config(ctx.guild.id)
        new_state = 0 if enabled else 1
        await self.set_config(ctx.guild.id, enabled=new_state)
        
        status = "**enabled** ✅" if new_state else "**disabled** ❌"
        embed = discord.Embed(
            title="✅ Leave System Toggled",
            description=f"Goodbye messages are now {status}",
            color=discord.Color.green() if new_state else discord.Color.orange()
        )
        await ctx.send(embed=embed)

    @leave.command(name='status')
    @commands.has_permissions(administrator=True)
    async def leave_status(self, ctx):
        """Show leave system status."""
        await self.ensure_db()
        channel_id, enabled, msg = await self.get_config(ctx.guild.id)
        
        if not channel_id or not enabled:
            embed = discord.Embed(
                title="ℹ️ Leave System Status",
                description="**Status:** Disabled ❌\n\nUse `>leave setup` to configure.",
                color=discord.Color.blue()
            )
        else:
            channel = ctx.guild.get_channel(channel_id)
            channel_mention = channel.mention if channel else f"<#{channel_id}> (Deleted)"
            
            embed = discord.Embed(
                title="ℹ️ Leave System Status",
                color=discord.Color.green()
            )
            embed.add_field(name="Status", value="Enabled ✅", inline=False)
            embed.add_field(name="Channel", value=channel_mention, inline=False)
            embed.add_field(name="Custom Message", value=f"`{msg}`" if msg else "Default message", inline=False)
            embed.set_footer(text="Use >leave message to change the message")
        
        await ctx.send(embed=embed)

    @commands.command(name='gtfo', aliases=['yeet'])
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def gtfo(self, ctx, member: discord.Member, *, reason: str = "No reason"):
        """Kick or ban a user (ban if they have mod perms)."""
        if ctx.author.top_role <= member.top_role:
            embed = discord.Embed(
                title="❌ Cannot Remove",
                description="You can't kick someone with higher/equal role.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed, delete_after=10)
        
        if ctx.guild.me.top_role <= member.top_role:
            embed = discord.Embed(
                title="⚠️ Cannot Remove",
                description="I can't kick that user (their role is too high).",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed, delete_after=10)

        if member.guild_permissions.kick_members or member.guild_permissions.ban_members:
            try:
                await member.ban(reason=f"{ctx.author}: {reason}")
                result = f"🔨 **Banned** {member.mention} (had mod permissions)."
            except:
                result = "❌ Failed to ban."
        else:
            try:
                await member.kick(reason=f"{ctx.author}: {reason}")
                result = f"👢 **Kicked** {member.mention}."
            except:
                result = "❌ Failed to kick."

        embed = discord.Embed(
            title="🚀 GTFO!",
            description=result,
            color=0xFF0000
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.timestamp = discord.utils.utcnow()
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(LeaveSystem(bot))

