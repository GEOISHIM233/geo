import discord
from discord.ext import commands
from discord.ui import Button, View, ChannelSelect, Select
import os
import asyncio
import aiosqlite
import json
import sys

# ─── CREATE DB FOLDER ────────────────────────────────────────────────
os.makedirs('db', exist_ok=True)

# ─── BOT SETUP ──────────────────────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='>', intents=intents, help_command=None)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ No TOKEN found! Set TOKEN in environment variables.")
    sys.exit(1)

# ─── DATABASE SETUP ─────────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect('db/bot.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS prefixes (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT DEFAULT '>'
            )
        ''')
        await db.commit()
        print("✅ Database initialized.")

async def init_leave_db():
    async with aiosqlite.connect('db/leave.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS leave_config (
                guild_id TEXT PRIMARY KEY,
                channel_id TEXT,
                enabled INTEGER DEFAULT 1,
                message TEXT
            )
        ''')
        await db.commit()

async def init_ticket_db():
    async with aiosqlite.connect('db/tickets.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ticket_config (
                guild_id TEXT PRIMARY KEY,
                category_id TEXT,
                support_role_id TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                author_id TEXT,
                status TEXT DEFAULT 'open'
            )
        ''')
        await db.commit()

async def init_botchannel_db():
    async with aiosqlite.connect('db/botchannel.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS botchannel (
                guild_id TEXT PRIMARY KEY,
                channel_id TEXT
            )
        ''')
        await db.commit()

async def init_tiktok_db():
    async with aiosqlite.connect('db/tiktok.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tiktok (
                guild_id TEXT PRIMARY KEY,
                channel_id TEXT,
                username TEXT,
                role_id TEXT,
                interval INTEGER DEFAULT 5,
                enabled INTEGER DEFAULT 0,
                last_video_id TEXT
            )
        ''')
        await db.commit()

async def init_roleperms_db():
    async with aiosqlite.connect('db/roleperms.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS roleperms (
                guild_id TEXT,
                role_name TEXT,
                command TEXT,
                PRIMARY KEY (guild_id, role_name, command)
            )
        ''')
        await db.commit()

# ─── LEAVE SYSTEM VIEW (FIXED) ─────────────────────────────────────
class LeaveSetupView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.channel_select = ChannelSelect(
            placeholder="Select a goodbye channel",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        self.channel_select.callback = self.on_channel_select
        self.add_item(self.channel_select)

    async def on_channel_select(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ Not your setup.", ephemeral=True)
        channel = self.channel_select.values[0]
        # Save to database
        async with aiosqlite.connect('db/leave.db') as db:
            await db.execute('''
                INSERT OR REPLACE INTO leave_config (guild_id, channel_id, enabled)
                VALUES (?, ?, 1)
            ''', (str(self.ctx.guild.id), str(channel.id)))
            await db.commit()
        embed = discord.Embed(
            title="✅ Leave System Setup Complete",
            description=f"Goodbye messages will be sent to {channel.mention}",
            color=0x00FF00
        )
        await interaction.response.edit_message(embed=embed, view=None)

# ─── HELP COMMAND ──────────────────────────────────────────────────
@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title="📋 Bezms Bot Commands",
        description="Start BeZmerz Today\nType >antinuke enable\nServer Prefix: >\nTotal Commands: 50+",
        color=0x00FF00
    )
    embed.add_field(name="🛡️ SECURITY", value="antinuke, antiraid, verification, whitelist", inline=False)
    embed.add_field(name="🔨 MODERATION", value="ban, kick, mute, unban, purge, role, hide, lock", inline=False)
    embed.add_field(name="⚙️ AUTOMOD", value="automod enable/disable, amwhitelist, amfilter", inline=False)
    embed.add_field(name="👋 LEAVE SYSTEM 🆕", value="leave setup, leave reset, leave test, leave config, leave edit, leave autodelete", inline=False)
    embed.add_field(name="🎫 TICKET SYSTEM 🆕", value="ticket setup, ticket panel, ticket create, ticket close", inline=False)
    embed.add_field(name="🔧 BOT CHANNEL 🆕", value="botchannel set, botchannel remove, botchannel status", inline=False)
    embed.add_field(name="📱 TIKTOK 🆕", value="tiktok setup, tiktok channel, tiktok username, tiktok role, tiktok interval, tiktok test, tiktok status, tiktok disable", inline=False)
    embed.add_field(name="🎭 ROLE PERMS 🆕", value="roleperms refresh, roleperms add, roleperms remove, roleperms list", inline=False)
    embed.add_field(name="💀 GTFO 🆕", value="gtfo @user <reason> – kick/ban bad users", inline=False)
    embed.set_footer(text="Bezms Bot • Support: https://discord.gg/9nKHrnWZqV")
    embed.timestamp = discord.utils.utcnow()
    await ctx.send(embed=embed)

# ─── LEAVE SETUP COMMAND ──────────────────────────────────────────
@bot.command(name='leave_setup')
@commands.has_permissions(administrator=True)
async def leave_setup(ctx):
    embed = discord.Embed(
        title="🛠️ Leave System Setup",
        description="Select a channel for goodbye messages from the dropdown below.",
        color=0x00FF00
    )
    view = LeaveSetupView(ctx)
    await ctx.send(embed=embed, view=view)

# ─── TICKET SETUP ──────────────────────────────────────────────────
@bot.command(name='ticket_setup')
@commands.has_permissions(administrator=True)
async def ticket_setup(ctx):
    await init_ticket_db()
    category = discord.utils.get(ctx.guild.categories, name="TICKETS")
    if not category:
        category = await ctx.guild.create_category("TICKETS")
    role = discord.utils.get(ctx.guild.roles, name="Support Team")
    if not role:
        role = await ctx.guild.create_role(name="Support Team", color=0x00FF00)
    async with aiosqlite.connect('db/tickets.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO ticket_config (guild_id, category_id, support_role_id)
            VALUES (?, ?, ?)
        ''', (str(ctx.guild.id), str(category.id), str(role.id)))
        await db.commit()
    embed = discord.Embed(
        title="✅ Ticket System Setup Complete",
        description=f"Category: {category.name}\nSupport Role: {role.mention}",
        color=0x00FF00
    )
    await ctx.send(embed=embed)

# ─── BOTCHANNEL ────────────────────────────────────────────────────
@bot.command(name='botchannel_set')
@commands.is_owner()
async def botchannel_set(ctx, channel: discord.TextChannel):
    await init_botchannel_db()
    async with aiosqlite.connect('db/botchannel.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO botchannel (guild_id, channel_id)
            VALUES (?, ?)
        ''', (str(ctx.guild.id), str(channel.id)))
        await db.commit()
    await ctx.send(f"✅ Bot commands restricted to {channel.mention}")

@bot.command(name='botchannel_remove')
@commands.is_owner()
async def botchannel_remove(ctx):
    await init_botchannel_db()
    async with aiosqlite.connect('db/botchannel.db') as db:
        await db.execute('DELETE FROM botchannel WHERE guild_id = ?', (str(ctx.guild.id),))
        await db.commit()
    await ctx.send("✅ Bot channel restriction removed.")

@bot.command(name='botchannel_status')
@commands.is_owner()
async def botchannel_status(ctx):
    await init_botchannel_db()
    async with aiosqlite.connect('db/botchannel.db') as db:
        async with db.execute('SELECT channel_id FROM botchannel WHERE guild_id = ?', (str(ctx.guild.id),)) as cursor:
            row = await cursor.fetchone()
            if row:
                channel = ctx.guild.get_channel(int(row[0]))
                await ctx.send(f"ℹ️ Bot channel: {channel.mention if channel else 'Deleted channel'}")
            else:
                await ctx.send("ℹ️ No bot channel set. Commands work everywhere.")

# ─── TIKTOK ────────────────────────────────────────────────────────
@bot.command(name='tiktok_setup')
@commands.has_permissions(administrator=True)
async def tiktok_setup(ctx):
    await init_tiktok_db()
    async with aiosqlite.connect('db/tiktok.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO tiktok (guild_id, channel_id, username, enabled)
            VALUES (?, ?, ?, 1)
        ''', (str(ctx.guild.id), str(ctx.channel.id), 'username_here'))
        await db.commit()
    await ctx.send("✅ TikTok monitoring enabled! Use `>tiktok_username <username>` to set the account.")

# ─── ROLEPERMS ─────────────────────────────────────────────────────
@bot.command(name='roleperms_refresh')
@commands.has_permissions(administrator=True)
async def roleperms_refresh(ctx):
    await init_roleperms_db()
    roles = ctx.guild.roles
    count = 0
    for role in roles:
        name = role.name.lower()
        commands_list = []
        if any(word in name for word in ['admin', 'administrator', 'owner']):
            commands_list = ['*']
        elif any(word in name for word in ['mod', 'moderator', 'staff']):
            commands_list = ['kick', 'ban', 'mute', 'purge', 'lock', 'hide', 'slowmode']
        elif any(word in name for word in ['helper', 'support']):
            commands_list = ['mute', 'purge']
        elif any(word in name for word in ['trial', 'junior']):
            commands_list = ['purge']
        for cmd in commands_list:
            async with aiosqlite.connect('db/roleperms.db') as db:
                await db.execute('''
                    INSERT OR REPLACE INTO roleperms (guild_id, role_name, command)
                    VALUES (?, ?, ?)
                ''', (str(ctx.guild.id), role.name, cmd))
                count += 1
    await ctx.send(f"✅ Refreshed permissions! {count} permissions assigned.")

# ─── GTFO ──────────────────────────────────────────────────────────
@bot.command(name='gtfo')
@commands.has_permissions(kick_members=True)
async def gtfo(ctx, member: discord.Member, *, reason: str = "No reason"):
    if ctx.author.top_role <= member.top_role:
        return await ctx.send("❌ You can't kick someone with higher/equal role.")
    embed = discord.Embed(
        title="🚀 GTFO!",
        description=f"**{member.user.tag}** has been removed.",
        color=0xFF0000
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    if member.guild_permissions.administrator or member.guild_permissions.kick_members or member.guild_permissions.ban_members:
        try:
            await member.ban(reason=reason)
            embed.description = f"**{member.user.tag}** has been **BANNED** (had mod perms)."
        except:
            return await ctx.send("❌ Failed to ban. Check my permissions.")
    else:
        try:
            await member.kick(reason=reason)
            embed.description = f"**{member.user.tag}** has been **KICKED**."
        except:
            return await ctx.send("❌ Failed to kick. Check my permissions.")
    await ctx.send(embed=embed)

# ─── PREFIX ────────────────────────────────────────────────────────
@bot.command(name='prefix')
@commands.has_permissions(administrator=True)
async def set_prefix(ctx, new_prefix: str):
    async with aiosqlite.connect('db/bot.db') as db:
        await db.execute('INSERT OR REPLACE INTO prefixes (guild_id, prefix) VALUES (?, ?)', (str(ctx.guild.id), new_prefix))
        await db.commit()
    await ctx.send(f"✅ Prefix changed to `{new_prefix}`")

async def get_prefix(bot, message):
    if not message.guild:
        return '>'
    async with aiosqlite.connect('db/bot.db') as db:
        async with db.execute('SELECT prefix FROM prefixes WHERE guild_id = ?', (str(message.guild.id),)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else '>'

bot.get_prefix = get_prefix

# ─── LEAVE EVENT ──────────────────────────────────────────────────
@bot.event
async def on_member_remove(member):
    async with aiosqlite.connect('db/leave.db') as db:
        async with db.execute('SELECT channel_id, message FROM leave_config WHERE guild_id = ? AND enabled = 1', (str(member.guild.id),)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return
            channel = member.guild.get_channel(int(row[0]))
            if not channel:
                return
            msg = row[1] or f"**{member.display_name}** has left the server."
            embed = discord.Embed(
                title="👋 Goodbye!",
                description=msg,
                color=0xFF4444
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Member", value=f"{member.mention} ({member})", inline=True)
            embed.add_field(name="Joined", value=member.joined_at.strftime("%Y-%m-%d %H:%M") if member.joined_at else "Unknown", inline=True)
            embed.set_footer(text=f"Member Count: {member.guild.member_count}")
            embed.timestamp = discord.utils.utcnow()
            await channel.send(embed=embed)

# ─── START BOT ─────────────────────────────────────────────────────
async def main():
    await init_db()
    await init_leave_db()
    await init_ticket_db()
    await init_botchannel_db()
    await init_tiktok_db()
    await init_roleperms_db()
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        print("Bot stopped.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
