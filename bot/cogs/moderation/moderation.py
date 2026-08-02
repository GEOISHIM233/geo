import discord
from discord.ext import commands
from discord.ui import Button, View
from utils.emoji import TICK, CROSS, ZWARNING
from utils.Tools import *
from core import Context

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF0000

    # ----- PURGE -----
    @commands.command(name="purge", aliases=["clean"])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: Context, amount: int = None):
        if amount is None:
            amount = 10000
        if amount < 1:
            embed = discord.Embed(title="❌ Invalid", description="At least 1 message.", color=self.color)
            return await ctx.send(embed=embed)
        if amount > 10000:
            embed = discord.Embed(title="❌ Too Many", description="Max 10,000.", color=self.color)
            return await ctx.send(embed=embed)

        warning = None
        if amount >= 1000:
            warning = await ctx.send(f"⚠️ Deleting **{amount}** messages...")

        deleted = await ctx.channel.purge(limit=amount + 1)
        if warning:
            await warning.delete()

        embed = discord.Embed(title="✅ Cleared", description=f"Deleted **{len(deleted)-1}** messages.", color=discord.Color.green())
        await ctx.send(embed=embed, delete_after=5)

    @purge.error
    async def purge_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ Permission", description="You need **Manage Messages**.", color=self.color)
            await ctx.send(embed=embed)

    # ----- LOCKALL -----
    @commands.hybrid_command(name="lockall", help="Lock all channels.")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def lockall(self, ctx):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(embed=discord.Embed(title="⛔ Denied", description="Your role must be above mine.", color=self.color))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji=TICK)
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji=CROSS)

        async def confirm(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.edit_message(content="Missing `manage roles`.", embed=None, view=None)
            count = 0
            for ch in interaction.guild.channels:
                try:
                    await ch.set_permissions(ctx.guild.default_role, overwrite=discord.PermissionOverwrite(send_messages=False, read_messages=True))
                    count += 1
                except:
                    pass
            await interaction.response.edit_message(content=f"{TICK} Locked {count} channels.", embed=None, view=None)

        async def cancel(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)

        button.callback = confirm
        button1.callback = cancel
        view = View()
        view.add_item(button)
        view.add_item(button1)

        embed = discord.Embed(color=self.color, description=f"**Lock all channels in {ctx.guild.name}?**")
        embed.set_footer(text="30 seconds to decide.")
        await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)

    # ----- UNLOCKALL -----
    @commands.hybrid_command(name="unlockall", help="Unlock all channels.")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def unlockall(self, ctx):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(embed=discord.Embed(title="⛔ Denied", description="Your role must be above mine.", color=self.color))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji=TICK)
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji=CROSS)

        async def confirm(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_roles:
                return await interaction.response.edit_message(content="Missing `manage roles`.", embed=None, view=None)
            count = 0
            for ch in interaction.guild.channels:
                try:
                    await ch.set_permissions(ctx.guild.default_role, overwrite=discord.PermissionOverwrite(send_messages=True, read_messages=True))
                    count += 1
                except:
                    pass
            await interaction.response.edit_message(content=f"{TICK} Unlocked {count} channels.", embed=None, view=None)

        async def cancel(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)

        button.callback = confirm
        button1.callback = cancel
        view = View()
        view.add_item(button)
        view.add_item(button1)

        embed = discord.Embed(color=self.color, description=f"**Unlock all channels in {ctx.guild.name}?**")
        embed.set_footer(text="30 seconds to decide.")
        await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)

    # ----- HIDEALL -----
    @commands.hybrid_command(name="hideall", help="Hide all channels.")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def hideall(self, ctx):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(embed=discord.Embed(title="⛔ Denied", description="Your role must be above mine.", color=self.color))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji=TICK)
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji=CROSS)

        async def confirm(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_channels:
                return await interaction.response.edit_message(content="Missing `manage channels`.", embed=None, view=None)
            count = 0
            for ch in interaction.guild.channels:
                try:
                    await ch.set_permissions(ctx.guild.default_role, view_channel=False)
                    count += 1
                except:
                    pass
            await interaction.response.edit_message(content=f"{TICK} Hidden {count} channels.", embed=None, view=None)

        async def cancel(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)

        button.callback = confirm
        button1.callback = cancel
        view = View()
        view.add_item(button)
        view.add_item(button1)

        embed = discord.Embed(color=self.color, description=f"**Hide all channels in {ctx.guild.name}?**")
        embed.set_footer(text="30 seconds to decide.")
        await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)

    # ----- UNHIDEALL -----
    @commands.hybrid_command(name="unhideall", help="Unhide all channels.")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def unhideall(self, ctx):
        if not (ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position):
            return await ctx.send(embed=discord.Embed(title="⛔ Denied", description="Your role must be above mine.", color=self.color))

        button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji=TICK)
        button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji=CROSS)

        async def confirm(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            if not interaction.guild.me.guild_permissions.manage_channels:
                return await interaction.response.edit_message(content="Missing `manage channels`.", embed=None, view=None)
            count = 0
            for ch in interaction.guild.channels:
                try:
                    await ch.set_permissions(ctx.guild.default_role, view_channel=True)
                    count += 1
                except:
                    pass
            await interaction.response.edit_message(content=f"{TICK} Unhidden {count} channels.", embed=None, view=None)

        async def cancel(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)

        button.callback = confirm
        button1.callback = cancel
        view = View()
        view.add_item(button)
        view.add_item(button1)

        embed = discord.Embed(color=self.color, description=f"**Unhide all channels in {ctx.guild.name}?**")
        embed.set_footer(text="30 seconds to decide.")
        await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)

    # ----- GIVE -----
    @commands.hybrid_command(name="give", help="Give or remove a role.", usage="give <user> <role>", aliases=["addrole"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def give(self, ctx, member: discord.Member, *, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=discord.Embed(color=self.color, description="I can't manage roles higher/equal to mine."))
        if ctx.author != ctx.guild.owner and ctx.author.top_role <= member.top_role:
            return await ctx.send(embed=discord.Embed(color=self.color, description="You can't manage this user."))
        try:
            if role not in member.roles:
                await member.add_roles(role)
                embed = discord.Embed(color=discord.Color.green(), description=f"✅ Added {role.name} to {member.mention}.")
            else:
                await member.remove_roles(role)
                embed = discord.Embed(color=discord.Color.green(), description=f"✅ Removed {role.name} from {member.mention}.")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(embed=discord.Embed(color=self.color, description=f"❌ Failed: {e}"))

    # ----- NUKE -----
    @commands.hybrid_command(name="nuke", help="Nuke this channel.")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def nuke(self, ctx):
        button = Button(label="💥 Confirm", style=discord.ButtonStyle.danger)
        button1 = Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def confirm(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            channel = interaction.channel
            new = await channel.clone()
            await new.edit(position=channel.position)
            await channel.delete()
            embed = discord.Embed(title="💥 Nuked!", description=f"Channel nuked by {ctx.author.mention}", color=discord.Color.red())
            await new.send(embed=embed)

        async def cancel(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)

        button.callback = confirm
        button1.callback = cancel
        view = View()
        view.add_item(button)
        view.add_item(button1)

        embed = discord.Embed(color=self.color, description="**Nuke this channel?**")
        embed.set_footer(text="30 seconds to decide.")
        await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)

    # ----- SLOWMODE -----
    @commands.hybrid_command(name="slowmode", help="Set slowmode (max 120s).", aliases=["slow"])
    @commands.has_permissions(manage_messages=True)
    async def slowmode(self, ctx, seconds: int = 0):
        if seconds > 120:
            return await ctx.send(embed=discord.Embed(color=self.color, description="Max 120 seconds."))
        await ctx.channel.edit(slowmode_delay=seconds)
        embed = discord.Embed(color=discord.Color.green(), description=f"Slowmode set to {seconds}s." if seconds > 0 else "Slowmode disabled.")
        await ctx.send(embed=embed)

    # ----- UNSLOWMODE -----
    @commands.hybrid_command(name="unslowmode", help="Disable slowmode.", aliases=["unslow"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def unslowmode(self, ctx):
        await ctx.channel.edit(slowmode_delay=0)
        await ctx.send(embed=discord.Embed(color=discord.Color.green(), description="Slowmode disabled."))

async def setup(bot):
    await bot.add_cog(Moderation(bot))
