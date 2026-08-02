import discord
from discord.ext import commands
from discord.ui import Button, View
from utils.emoji import CROSS, DENIED, TICK, ZWARNING
from utils.Tools import *
from core import Context
import aiohttp
import re
from collections import Counter

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF0000

    # ============================================================
    # PURGE
    # ============================================================
    @commands.command(name="purge", aliases=["clean"])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx: Context, amount: int = None):
        if amount is None:
            amount = 10000
        if amount < 1:
            embed = discord.Embed(title="❌ Invalid Number", description="You must delete at least 1 message.", color=self.color)
            return await ctx.send(embed=embed)
        if amount > 10000:
            embed = discord.Embed(title="❌ Too Many Messages", description="You can only delete up to 10,000 messages at a time.", color=self.color)
            return await ctx.send(embed=embed)

        warning_msg = None
        if amount >= 1000:
            warning_msg = await ctx.send(f"⚠️ Deleting **{amount}** messages... This may take a few seconds.")

        deleted = await ctx.channel.purge(limit=amount + 1)
        if warning_msg:
            try:
                await warning_msg.delete()
            except:
                pass

        embed = discord.Embed(title="✅ Messages Cleared", description=f"Successfully deleted **{len(deleted) - 1}** messages.", color=discord.Color.green())
        await ctx.send(embed=embed, delete_after=5)

    @purge.error
    async def purge_error(self, ctx: Context, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ Permission Denied", description="You need **Manage Messages** permission.", color=self.color)
            await ctx.send(embed=embed)

    # ============================================================
    # LOCKALL
    # ============================================================
    @commands.hybrid_command(name="lockall", help="Locks all channels in the Guild.", usage="lockall")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def lockall(self, ctx):
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji=f"{TICK}>")
            button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji=CROSS)
            
            async def button_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)
                if not interaction.guild.me.guild_permissions.manage_roles:
                    return await interaction.response.edit_message(content="I need `manage roles` permission.", embed=None, view=None)
                a = 0
                for channel in interaction.guild.channels:
                    try:
                        await channel.set_permissions(ctx.guild.default_role, overwrite=discord.PermissionOverwrite(send_messages=False, read_messages=True))
                        a += 1
                    except:
                        pass
                await interaction.response.edit_message(content=f"{TICK}> Successfully locked {a} channels.", embed=None, view=None)
            
            async def button1_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)
                await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)

            button.callback = button_callback
            button1.callback = button1_callback
            view = View()
            view.add_item(button)
            view.add_item(button1)
            
            embed = discord.Embed(color=self.color, description=f'**Do you really want to lock all channels in {ctx.guild.name}?**')
            embed.set_footer(text="You have 30 seconds to decide.")
            await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)
        else:
            embed = discord.Embed(title=f"{ZWARNING} Access Denied", description="Your role must be above my top role.", color=self.color)
            await ctx.send(embed=embed)

    # ============================================================
    # UNLOCKALL
    # ============================================================
    @commands.hybrid_command(name="unlockall", help="Unlocks all channels in the Guild.", usage="unlockall")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def unlockall(self, ctx):
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji=f"{TICK}>")
            button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji=CROSS)
            
            async def button_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)
                if not interaction.guild.me.guild_permissions.manage_roles:
                    return await interaction.response.edit_message(content="I need `manage roles` permission.", embed=None, view=None)
                a = 0
                for channel in interaction.guild.channels:
                    try:
                        await channel.set_permissions(ctx.guild.default_role, overwrite=discord.PermissionOverwrite(send_messages=True, read_messages=True))
                        a += 1
                    except:
                        pass
                await interaction.response.edit_message(content=f"{TICK}> Successfully unlocked {a} channels.", embed=None, view=None)
            
            async def button1_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)
                await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)

            button.callback = button_callback
            button1.callback = button1_callback
            view = View()
            view.add_item(button)
            view.add_item(button1)
            
            embed = discord.Embed(color=self.color, description=f'**Do you really want to unlock all channels in {ctx.guild.name}?**')
            embed.set_footer(text="You have 30 seconds to decide.")
            await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)
        else:
            embed = discord.Embed(title=f"{ZWARNING} Access Denied", description="Your role must be above my top role.", color=self.color)
            await ctx.send(embed=embed)

    # ============================================================
    # HIDEALL
    # ============================================================
    @commands.hybrid_command(name="hideall", help="Hides all channels.", usage="hideall")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def hideall(self, ctx):
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji=f"{TICK}>")
            button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji=CROSS)
            
            async def button_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)
                if not interaction.guild.me.guild_permissions.manage_channels:
                    return await interaction.response.edit_message(content="I need `manage channels` permission.", embed=None, view=None)
                a = 0
                for channel in interaction.guild.channels:
                    try:
                        await channel.set_permissions(ctx.guild.default_role, view_channel=False)
                        a += 1
                    except:
                        pass
                await interaction.response.edit_message(content=f"{TICK}> Successfully hidden {a} channels.", embed=None, view=None)
            
            async def button1_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)
                await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)

            button.callback = button_callback
            button1.callback = button1_callback
            view = View()
            view.add_item(button)
            view.add_item(button1)
            
            embed = discord.Embed(color=self.color, description=f'**Do you really want to hide all channels in {ctx.guild.name}?**')
            embed.set_footer(text="You have 30 seconds to decide.")
            await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)
        else:
            embed = discord.Embed(title=f"{ZWARNING} Access Denied", description="Your role must be above my top role.", color=self.color)
            await ctx.send(embed=embed)

    # ============================================================
    # UNHIDEALL
    # ============================================================
    @commands.hybrid_command(name="unhideall", help="Unhides all channels.", usage="unhideall")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def unhideall(self, ctx):
        if ctx.author == ctx.guild.owner or ctx.author.top_role.position > ctx.guild.me.top_role.position:
            button = Button(label="Confirm", style=discord.ButtonStyle.green, emoji=f"{TICK}>")
            button1 = Button(label="Cancel", style=discord.ButtonStyle.red, emoji=CROSS)
            
            async def button_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)
                if not interaction.guild.me.guild_permissions.manage_channels:
                    return await interaction.response.edit_message(content="I need `manage channels` permission.", embed=None, view=None)
                a = 0
                for channel in interaction.guild.channels:
                    try:
                        await channel.set_permissions(ctx.guild.default_role, view_channel=True)
                        a += 1
                    except:
                        pass
                await interaction.response.edit_message(content=f"{TICK}> Successfully unhidden {a} channels.", embed=None, view=None)
            
            async def button1_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Not for you.", ephemeral=True)
                await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)

            button.callback = button_callback
            button1.callback = button1_callback
            view = View()
            view.add_item(button)
            view.add_item(button1)
            
            embed = discord.Embed(color=self.color, description=f'**Do you really want to unhide all channels in {ctx.guild.name}?**')
            embed.set_footer(text="You have 30 seconds to decide.")
            await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)
        else:
            embed = discord.Embed(title=f"{ZWARNING} Access Denied", description="Your role must be above my top role.", color=self.color)
            await ctx.send(embed=embed)

    # ============================================================
    # GIVE
    # ============================================================
    @commands.hybrid_command(name="give", help="Gives a role to a user.", usage="give <user> <role>", aliases=["addrole"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def give(self, ctx, member: discord.Member, *, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            embed = discord.Embed(color=self.color, description="I can't manage roles higher or equal to mine.")
            return await ctx.send(embed=embed)
        if ctx.author != ctx.guild.owner and ctx.author.top_role <= member.top_role:
            embed = discord.Embed(color=self.color, description="You can't manage roles for someone with higher/equal role.")
            return await ctx.send(embed=embed)
        try:
            if role not in member.roles:
                await member.add_roles(role)
                embed = discord.Embed(color=discord.Color.green(), description=f"✅ Added {role.name} to {member.mention}.")
            else:
                await member.remove_roles(role)
                embed = discord.Embed(color=discord.Color.green(), description=f"✅ Removed {role.name} from {member.mention}.")
            await ctx.send(embed=embed)
        except:
            embed = discord.Embed(color=self.color, description="❌ Failed to manage role.")
            await ctx.send(embed=embed)

    # ============================================================
    # NUKE (Channel)
    # ============================================================
    @commands.hybrid_command(name="nuke", help="Nukes a channel.", usage="nuke")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def nuke(self, ctx):
        button = Button(label="Confirm", style=discord.ButtonStyle.danger, emoji="💥")
        button1 = Button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
        
        async def button_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            channel = interaction.channel
            new_channel = await channel.clone()
            await new_channel.edit(position=channel.position)
            await channel.delete()
            embed = discord.Embed(title="💥 Channel Nuked!", description=f"Channel nuked by {ctx.author.mention}", color=discord.Color.red())
            await new_channel.send(embed=embed)
        
        async def button1_callback(interaction):
            if interaction.user != ctx.author:
                return await interaction.response.send_message("Not for you.", ephemeral=True)
            await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)

        button.callback = button_callback
        button1.callback = button1_callback
        view = View()
        view.add_item(button)
        view.add_item(button1)
        
        embed = discord.Embed(color=self.color, description='**Do you really want to nuke this channel?**')
        embed.set_footer(text="You have 30 seconds to decide.")
        await ctx.reply(embed=embed, view=view, mention_author=False, delete_after=30)

    # ============================================================
    # SLOWMODE
    # ============================================================
    @commands.hybrid_command(name="slowmode", help="Changes slowmode.", usage="slowmode [seconds]", aliases=["slow"])
    @commands.has_permissions(manage_messages=True)
    async def slowmode(self, ctx, seconds: int = 0):
        if seconds > 120:
            embed = discord.Embed(color=self.color, description="Slowmode cannot exceed 2 minutes.")
            return await ctx.send(embed=embed)
        await ctx.channel.edit(slowmode_delay=seconds)
        embed = discord.Embed(color=discord.Color.green(), description=f"Slowmode set to {seconds}s." if seconds > 0 else "Slowmode disabled.")
        await ctx.send(embed=embed)

    # ============================================================
    # UNSLOWMODE
    # ============================================================
    @commands.hybrid_command(name="unslowmode", help="Disables slowmode.", usage="unslowmode", aliases=["unslow"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def unslowmode(self, ctx):
        await ctx.channel.edit(slowmode_delay=0)
        embed = discord.Embed(color=discord.Color.green(), description="Slowmode disabled.")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
