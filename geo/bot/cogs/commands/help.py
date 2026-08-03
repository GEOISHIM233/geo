# ╔══════════════════════════════════════════════════════════════════╗
# ║                     BeZmerz Help System                            ║
# ║            © 2025 BeZmerz — All Rights Reserved                  ║
# ╚══════════════════════════════════════════════════════════════════╝

import discord
from discord.ext import commands
from discord.ui import Button, View
from core.zyrox import zyrox
from core.Cog import Cog
from utils.Tools import getConfig
from utils.cv2 import CV2, CV2Embed
from typing import Optional

class HelpSystem(Cog):
    """Enhanced Help System for BeZmerz"""
    
    def __init__(self, bot: zyrox):
        self.bot = bot
        self.config = {}
    
    async def load_config(self):
        """Load configuration"""
        self.config = await getConfig()
    
    def get_command_signature(self, command: commands.Command):
        """Get formatted command signature"""
        parent = command.full_parent_name
        alias = command.name if not command.aliases else command.aliases[0]
        if parent:
            alias = f"{parent} {alias}"
        return f"{self.config.get('BOT_PREFIX', '>')}{alias}"
    
    def create_help_embed(self, ctx: commands.Context, category: Optional[str] = None):
        """Create help embed for a specific category"""
        
        embed = CV2Embed(
            title="📚 BeZmerz Help Center",
            description="**Your ultimate multipurpose Discord companion**\n\n💡 **Tip:** Use the buttons below to navigate different command categories!",
            color=0x2E86DE
        )
        
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild and ctx.guild.icon else "https://via.placeholder.com/100")
        embed.set_footer(text=f"Requested by {ctx.author.display_name} | Type >help <command> for details")
        
        if category:
            embed.title = f"📚 {category} Commands"
            embed.description = f"**Commands in {category} category**\n\n💡 Use the buttons to switch categories"
        
        return embed
    
    def create_command_list(self, commands_list, category: str):
        """Create formatted command list"""
        command_groups = {}
        
        for cmd in commands_list:
            if cmd.hidden:
                continue
                
            cmd_category = getattr(cmd.cog, 'qualified_name', 'Uncategorized') if cmd.cog else 'Uncategorized'
            
            if cmd_category not in command_groups:
                command_groups[cmd_category] = []
            
            command_groups[cmd_category].append(cmd)
        
        return command_groups
    
    @commands.command(name="help", aliases=["h", "?"])
    async def help_command(self, ctx: commands.Context, command_name: Optional[str] = None):
        """Main help command"""
        
        if command_name:
            # Specific command help
            command = self.bot.get_command(command_name)
            
            if not command:
                # Try to find similar commands
                all_commands = list(self.bot.commands)
                similar = []
                for cmd in all_commands:
                    if command_name.lower() in cmd.name.lower() or any(command_name.lower() in alias.lower() for alias in cmd.aliases):
                        similar.append(cmd)
                
                if similar:
                    embed = CV2Embed(
                        title="❓ Command Not Found",
                        description=f"Command `{command_name}` not found. Did you mean:",
                        color=0xE74C3C
                    )
                    
                    for cmd in similar[:5]:
                        embed.add_field(
                            name=f"`{self.get_command_signature(cmd)}`",
                            value=cmd.short_doc or "No description available",
                            inline=False
                        )
                    
                    embed.set_footer(text="Use >help to see all commands")
                    return await ctx.reply(embed=embed)
                else:
                    return await ctx.reply(f"❌ Command `{command_name}` not found!")
            
            # Command found - show detailed help
            embed = CV2Embed(
                title=f"📖 {command.name.capitalize()} Command",
                description=command.help or "No description available",
                color=0x3498DB
            )
            
            embed.add_field(name="📋 Usage", value=f"`{self.get_command_signature(command)}`", inline=False)
            
            if command.aliases:
                embed.add_field(name="🔗 Aliases", value=", ".join(f"`{alias}`" for alias in command.aliases), inline=False)
            
            if command.cooldown:
                embed.add_field(name="⏱️ Cooldown", value=f"{command.cooldown.rate} uses per {command.cooldown.per} seconds", inline=False)
            
            embed.set_footer(text=f"Category: {getattr(command.cog, 'qualified_name', 'Uncategorized')}")
            
            return await ctx.reply(embed=embed)
        
        # Main help menu
        await self.show_main_help(ctx)
    
    async def show_main_help(self, ctx: commands.Context):
        """Show main help menu with categories"""
        
        # Create command groups
        command_groups = self.create_command_list(list(self.bot.commands), "All")
        
        # Sort categories
        categories = sorted(command_groups.keys())
        
        # Create embed
        embed = self.create_help_embed(ctx)
        
        # Add command categories
        for category in categories[:10]:  # Show first 10 categories
            commands_in_cat = command_groups[category]
            cmd_count = len(commands_in_cat)
            
            # Get first few commands
            cmd_examples = []
            for cmd in commands_in_cat[:3]:
                cmd_examples.append(f"`{self.get_command_signature(cmd)}`")
            
            example_text = "\n".join(cmd_examples) if cmd_examples else "No commands available"
            
            embed.add_field(
                name=f"📁 {category} ({cmd_count} commands)",
                value=f"{example_text}",
                inline=False
            )
        
        # Add footer with total commands
        total_commands = sum(len(cmds) for cmds in command_groups.values())
        embed.set_footer(text=f"BeZmerz v2.0 | {total_commands} total commands | Type >help <command> for details")
        
        # Create buttons for navigation
        view = View(timeout=300)
        
        # Category buttons
        for i, category in enumerate(categories[:5]):
            view.add_item(Button(
                label=category[:8],
                style=discord.ButtonStyle.primary,
                custom_id=f"help_cat_{i}"
            ))
        
        # Help buttons
        view.add_item(Button(
            label="🔍 Search",
            style=discord.ButtonStyle.secondary,
            custom_id="help_search"
        ))
        
        view.add_item(Button(
            label="📖 Docs",
            style=discord.ButtonStyle.link,
            url="https://docs.bezmerz.com"
        ))
        
        msg = await ctx.reply(embed=embed, view=view)
        
        # TODO: Add button interactions
        # self.bot.loop.create_task(self.handle_help_interactions(msg, view, command_groups))
    
    @commands.Cog.listener()
    async def on_button_click(self, interaction: discord.Interaction):
        """Handle help menu button clicks"""
        if not interaction.data:
            return
        
        custom_id = interaction.data.get('custom_id', '')
        
        if custom_id.startswith('help_'):
            await interaction.response.defer()
            # Handle help interactions

async def setup(bot: zyrox):
    await bot.add_cog(HelpSystem(bot))
