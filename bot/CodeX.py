import discord
from discord.ext import commands
from discord.ui import Button, View, ChannelSelect
import os
import asyncio
import aiosqlite
import sys

# ─── CREATE DB FOLDER ────────────────────────────────────────────────
os.makedirs('db', exist_ok=True)

# ─── BOT SETUP ──────────────────────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='>', intents=intents, help_command=None)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ No TOKEN found!")
    sys.exit(1)

# ─── DATABASE SETUP ─────────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect('db/bot.db') as db:
        await db.execute('CREATE TABLE IF NOT EXISTS prefixes (guild_id TEXT PRIMARY KEY, prefix TEXT DEFAULT ">")')
        await db.commit()
    async with aiosqlite.connect('db/leave.db') as db:
        await db.execute('CREATE TABLE IF NOT EXISTS leave_config (guild_id TEXT PRIMARY KEY, channel_id TEXT, enabled INTEGER DEFAULT 1)')
        await db.commit()
    print("✅ Database initialized.")

# ─── LEAVE SETUP VIEW ──────────────────────────────────────────────
class LeaveSetupView(View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        select = ChannelSelect(
            placeholder="Select a goodbye channel",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            custom_id="leave_channel"
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ Not your setup.", ephemeral=True)
        channel = interaction.data["values"][0]
        async with aiosqlite.connect('db/leave.db') as db:
            await db.execute('INSERT OR REPLACE INTO leave_config (guild_id, channel_id) VALUES (?, ?)', (str(self.ctx.guild.id), channel))
            await db.commit()
        embed = discord.Embed(title="✅ Leave System Setup Complete", description=f"Goodbye messages will be sent to <#{channel}>", color=0x00FF00)
        await interaction.response.edit_message(embed=embed, view=None)

# ─── HELP COMMAND ──────────────────────────────────────────────────
@bot.command(name='help')
async def help_cmd(ctx):
    embed = discord.Embed(title="📋 Bezms Bot Commands", description="Server Prefix: >\nTotal Commands: 15+", color=0x00FF00)
    embed.add_field(name="🛡️ SECURITY", value="antinuke, antiraid, automod", inline=False)
    embed.add_field(name="🔨 MODERATION", value="purge, lockall, unlockall, hideall, unhideall, give, nuke, slowmode", inline=False)
    embed.add_field(name="👋 LEAVE", value="leave_setup", inline=False)
    embed.add_field(name="🎫 TICKET", value="ticket_setup", inline=False)
    embed.add_field(name="🔧 BOT CHANNEL", value="botchannel_set, botchannel_remove, botchannel_status", inline=False)
    embed.add_field(name="💀 GTFO", value="gtfo @user reason", inline=False)
    embed.set_footer(text="Bezms Bot • Support: https://discord.gg/9nKHrnWZqV")
    await ctx.send(embed=embed)

# ─── LEAVE SETUP ──────────────────────────────────────────────────
@bot.command(name='leave_setup')
@commands.has_permissions(administrator=True)
async def leave_setup(ctx):
    embed = discord.Embed(title="🛠️ Leave System Setup", description="Select a channel from the dropdown below.", color=0x00FF00)
    view = LeaveSetupView(ctx)
    await ctx.send(embed=embed, view=view)

# ─── TICKET SETUP ──────────────────────────────────────────────────
@bot.command(name='ticket_setup')
@commands.has_permissions(administrator=True)
async def ticket_setup(ctx):
    category = discord.utils.get(ctx.guild.categories, name="TICKETS")
    if not category:
        category = await ctx.guild.create_category("TICKETS")
    role = discord.utils.get(ctx.guild.roles, name="Support Team")
    if not role:
        role = await ctx.guild.create_role(name="Support Team", color=0x00FF00)
    async with aiosqlite.connect('db/tickets.db') as db:
        await db.execute('CREATE TABLE IF NOT EXISTS ticket_config (guild_id TEXT PRIMARY KEY, category_id TEXT, support_role_id TEXT)')
        await db.execute('INSERT OR REPLACE INTO ticket_config VALUES (?, ?, ?)', (str(ctx.guild.id), str(category.id), str(role.id)))
        await db.commit()
    embed = discord.Embed(title="✅ Ticket System Setup Complete", description=f"Category: {category.name}\nSupport Role: {role.mention}", color=0x00FF00)
    await ctx.send(embed=embed)

# ─── BOTCHANNEL ────────────────────────────────────────────────────
@bot.command(name='botchannel_set')
@commands.is_owner()
async def botchannel_set(ctx, channel: discord.TextChannel):
    async with aiosqlite.connect('db/botchannel.db') as db:
        await db.execute('CREATE TABLE IF NOT EXISTS botchannel (guild_id TEXT PRIMARY KEY, channel_id TEXT)')
        await db.execute('INSERT OR REPLACE INTO botchannel VALUES (?, ?)', (str(ctx.guild.id), str(channel.id)))
        await db.commit()
    await ctx.send(f"✅ Bot commands restricted to {channel.mention}")

@bot.command(name='botchannel_remove')
@commands.is_owner()
async def botchannel_remove(ctx):
    async with aiosqlite.connect('db/botchannel.db') as db:
        await db.execute('DELETE FROM botchannel WHERE guild_id = ?', (str(ctx.guild.id),))
        await db.commit()
    await ctx.send("✅ Bot channel restriction removed.")

@bot.command(name='botchannel_status')
@commands.is_owner()
async def botchannel_status(ctx):
    async with aiosqlite.connect('db/botchannel.db') as db:
        async with db.execute('SELECT channel_id FROM botchannel WHERE guild_id = ?', (str(ctx.guild.id),)) as cursor:
            row = await cursor.fetchone()
            if row:
                await ctx.send(f"ℹ️ Bot channel: <#{row[0]}>")
            else:
                await ctx.send("ℹ️ No bot channel set.")

# ─── PURGE ─────────────────────────────────────────────────────────
@bot.command(name='purge')
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int = 10):
    if amount > 100: amount = 100
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"✅ Deleted {len(deleted)-1} messages.", delete_after=5)

# ─── GTFO ──────────────────────────────────────────────────────────
@bot.command(name='gtfo')
@commands.has_permissions(kick_members=True)
async def gtfo(ctx, member: discord.Member, *, reason: str = "No reason"):
    if ctx.author.top_role <= member.top_role:
        return await ctx.send("❌ You can't kick someone with higher/equal role.")
    embed = discord.Embed(title="🚀 GTFO!", description=f"**{member.display_name}** has been removed.", color=0xFF0000)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    if member.guild_permissions.administrator or member.guild_permissions.kick_members or member.guild_permissions.ban_members:
        try:
            await member.ban(reason=reason)
            embed.description = f"**{member.display_name}** has been **BANNED**."
        except:
            return await ctx.send("❌ Failed to ban.")
    else:
        try:
            await member.kick(reason=reason)
            embed.description = f"**{member.display_name}** has been **KICKED**."
        except:
            return await ctx.send("❌ Failed to kick.")
    await ctx.send(embed=embed)

# ─── LEAVE EVENT ──────────────────────────────────────────────────
@bot.event
async def on_member_remove(member):
    async with aiosqlite.connect('db/leave.db') as db:
        async with db.execute('SELECT channel_id FROM leave_config WHERE guild_id = ? AND enabled = 1', (str(member.guild.id),)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return
            channel = member.guild.get_channel(int(row[0]))
            if not channel:
                return
            embed = discord.Embed(title="👋 Goodbye!", description=f"**{member.display_name}** has left the server.", color=0xFF4444)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Member Count: {member.guild.member_count}")
            await channel.send(embed=embed)

# ─── START ──────────────────────────────────────────────────────────
async def main():
    await init_db()
    try:
        await bot.start(TOKEN)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
