import discord
from discord.ext import commands
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

# ─── HELP COMMAND ──────────────────────────────────────────────────
@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title="📋 Bezms Bot Commands",
        description="Here are all the commands you can use:",
        color=0x00FF00
    )
    embed.add_field(name=">help", value="Show this help menu", inline=False)
    embed.add_field(name=">ping", value="Check bot latency", inline=False)
    embed.add_field(name=">purge <amount>", value="Delete messages (max 10000)", inline=False)
    embed.add_field(name=">lockall", value="Lock all channels (Admin only)", inline=False)
    embed.add_field(name=">unlockall", value="Unlock all channels (Admin only)", inline=False)
    embed.add_field(name=">hideall", value="Hide all channels (Admin only)", inline=False)
    embed.add_field(name=">unhideall", value="Unhide all channels (Admin only)", inline=False)
    embed.add_field(name=">give @user @role", value="Give or remove a role", inline=False)
    embed.add_field(name=">nuke", value="Nuke a channel (delete and recreate)", inline=False)
    embed.add_field(name=">slowmode <seconds>", value="Set slowmode (max 120s)", inline=False)
    embed.add_field(name=">unslowmode", value="Disable slowmode", inline=False)
    embed.add_field(name=">gtfo @user <reason>", value="Kick/ban a bad user", inline=False)
    embed.add_field(name=">leave setup", value="Setup goodbye messages", inline=False)
    embed.add_field(name=">ticket setup", value="Setup ticket system", inline=False)
    embed.add_field(name=">botchannel set #channel", value="Set bot command channel", inline=False)
    embed.add_field(name=">prefix <new>", value="Change bot prefix", inline=False)
    embed.set_footer(text="Bezms Bot • Support: https://discord.gg/9nKHrnWZqV")
    embed.timestamp = discord.utils.utcnow()
    await ctx.send(embed=embed)

# ─── PING COMMAND ──────────────────────────────────────────────────
@bot.command(name='ping')
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

# ─── PURGE COMMAND ─────────────────────────────────────────────────
@bot.command(name='purge', aliases=['clean'])
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int = None):
    if amount is None:
        amount = 10000
    if amount < 1:
        return await ctx.send("❌ Must delete at least 1 message.")
    if amount > 10000:
        return await ctx.send("❌ Max 10000 messages.")
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"✅ Deleted {len(deleted)-1} messages.", delete_after=5)

# ─── LOCKALL ──────────────────────────────────────────────────────
@bot.command(name='lockall')
@commands.has_permissions(administrator=True)
async def lockall(ctx):
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ You need Administrator permission.")
    count = 0
    for ch in ctx.guild.channels:
        try:
            await ch.set_permissions(ctx.guild.default_role, send_messages=False)
            count += 1
        except:
            pass
    await ctx.send(f"🔒 Locked {count} channels.")

# ─── UNLOCKALL ────────────────────────────────────────────────────
@bot.command(name='unlockall')
@commands.has_permissions(administrator=True)
async def unlockall(ctx):
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ You need Administrator permission.")
    count = 0
    for ch in ctx.guild.channels:
        try:
            await ch.set_permissions(ctx.guild.default_role, send_messages=True)
            count += 1
        except:
            pass
    await ctx.send(f"🔓 Unlocked {count} channels.")

# ─── HIDEALL ──────────────────────────────────────────────────────
@bot.command(name='hideall')
@commands.has_permissions(administrator=True)
async def hideall(ctx):
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ You need Administrator permission.")
    count = 0
    for ch in ctx.guild.channels:
        try:
            await ch.set_permissions(ctx.guild.default_role, view_channel=False)
            count += 1
        except:
            pass
    await ctx.send(f"🙈 Hidden {count} channels.")

# ─── UNHIDEALL ────────────────────────────────────────────────────
@bot.command(name='unhideall')
@commands.has_permissions(administrator=True)
async def unhideall(ctx):
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ You need Administrator permission.")
    count = 0
    for ch in ctx.guild.channels:
        try:
            await ch.set_permissions(ctx.guild.default_role, view_channel=True)
            count += 1
        except:
            pass
    await ctx.send(f"👀 Unhidden {count} channels.")

# ─── GIVE ─────────────────────────────────────────────────────────
@bot.command(name='give', aliases=['addrole'])
@commands.has_permissions(manage_roles=True)
async def give(ctx, member: discord.Member, *, role: discord.Role):
    if role >= ctx.guild.me.top_role:
        return await ctx.send("❌ I can't manage that role.")
    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed {role.name} from {member.mention}")
    else:
        await member.add_roles(role)
        await ctx.send(f"✅ Added {role.name} to {member.mention}")

# ─── NUKE ──────────────────────────────────────────────────────────
@bot.command(name='nuke')
@commands.has_permissions(manage_channels=True)
async def nuke(ctx):
    channel = ctx.channel
    new = await channel.clone()
    await new.edit(position=channel.position)
    await channel.delete()
    await new.send(f"💥 Channel nuked by {ctx.author.mention}")

# ─── SLOWMODE ─────────────────────────────────────────────────────
@bot.command(name='slowmode', aliases=['slow'])
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int = 0):
    if seconds < 0 or seconds > 120:
        return await ctx.send("❌ Slowmode must be 0-120 seconds.")
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"⏱️ Slowmode set to {seconds}s" if seconds > 0 else "⏱️ Slowmode disabled.")

# ─── UNSLOWMODE ───────────────────────────────────────────────────
@bot.command(name='unslowmode', aliases=['unslow'])
@commands.has_permissions(manage_channels=True)
async def unslowmode(ctx):
    await ctx.channel.edit(slowmode_delay=0)
    await ctx.send("⏱️ Slowmode disabled.")

# ─── GTFO ─────────────────────────────────────────────────────────
@bot.command(name='gtfo', aliases=['yeet'])
@commands.has_permissions(kick_members=True)
async def gtfo(ctx, member: discord.Member, *, reason: str = "No reason"):
    if ctx.author.top_role <= member.top_role:
        return await ctx.send("❌ You can't kick someone with higher/equal role.")
    if member.guild_permissions.kick_members or member.guild_permissions.ban_members:
        try:
            await member.ban(reason=reason)
            await ctx.send(f"🔨 Banned {member.mention} (had mod perms). Reason: {reason}")
        except:
            await ctx.send("❌ Failed to ban.")
    else:
        try:
            await member.kick(reason=reason)
            await ctx.send(f"👢 Kicked {member.mention}. Reason: {reason}")
        except:
            await ctx.send("❌ Failed to kick.")

# ─── PREFIX ───────────────────────────────────────────────────────
@bot.command(name='prefix')
@commands.has_permissions(administrator=True)
async def set_prefix(ctx, new_prefix: str):
    async with aiosqlite.connect('db/bot.db') as db:
        await db.execute('INSERT OR REPLACE INTO prefixes (guild_id, prefix) VALUES (?, ?)', (ctx.guild.id, new_prefix))
        await db.commit()
    await ctx.send(f"✅ Prefix changed to `{new_prefix}`")

async def get_prefix(bot, message):
    if not message.guild:
        return '>'
    async with aiosqlite.connect('db/bot.db') as db:
        async with db.execute('SELECT prefix FROM prefixes WHERE guild_id = ?', (message.guild.id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else '>'

bot.get_prefix = get_prefix

# ─── LEAVE SYSTEM (Basic) ─────────────────────────────────────────
leave_channel_cache = {}

@bot.command(name='leave_setup')
@commands.has_permissions(administrator=True)
async def leave_setup(ctx):
    leave_channel_cache[ctx.guild.id] = ctx.channel.id
    await ctx.send(f"✅ Goodbye messages will be sent to {ctx.channel.mention}")

@bot.event
async def on_member_remove(member):
    if member.guild.id in leave_channel_cache:
        channel = member.guild.get_channel(leave_channel_cache[member.guild.id])
        if channel:
            embed = discord.Embed(
                title="👋 Goodbye!",
                description=f"**{member.display_name}** has left the server.",
                color=0xFF4444
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

# ─── START BOT ─────────────────────────────────────────────────────
async def main():
    await init_db()
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        print("Bot stopped.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
