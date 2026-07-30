# ╔══════════════════════════════════════════════════════════════════╗
# ║            © 2026 Bezms — All Rights Reserved                   ║
# ║   discord  ──  https://discord.gg/9nKHrnWZqV                    ║
# ╚══════════════════════════════════════════════════════════════════╝

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
import re
import asyncio
from typing import Optional
from pathlib import Path

WEBSITES_FILE = "websites.json"

def load_websites():
    """Load websites from JSON file"""
    if os.path.exists(WEBSITES_FILE):
        with open(WEBSITES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_websites(data):
    """Save websites to JSON file"""
    with open(WEBSITES_FILE, "w") as f:
        json.dump(data, f, indent=2)

def parse_json_path(obj, path: str):
    """Parse JSON path like 'data.hits' or 'user.stats.total'"""
    keys = path.split(".")
    for key in keys:
        try:
            # Try to convert to int for list indexing
            index = int(key)
            if isinstance(obj, (list, tuple)):
                obj = obj[index]
            else:
                return None
        except (ValueError, IndexError, TypeError):
            # If not an int, try as dict key
            if isinstance(obj, dict):
                obj = obj.get(key)
            else:
                return None
    return obj

def parse_regex(text: str, pattern: str):
    """Extract value using regex with one capture group"""
    try:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    except:
        pass
    return None

async def fetch_hits(url_template: str, username: str, parser_type: str, parser_value: str) -> Optional[str]:
    """Fetch hit count from a website"""
    url = url_template.replace("{user}", username)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                
                if parser_type == "json":
                    try:
                        data = await resp.json()
                        value = parse_json_path(data, parser_value)
                        return str(value) if value is not None else None
                    except:
                        return None
                
                elif parser_type == "regex":
                    text = await resp.text()
                    value = parse_regex(text, parser_value)
                    return value
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None
    
    return None

class WebsiteTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_admin(self, ctx) -> bool:
        """Check if user is admin (for text commands)"""
        return ctx.author.guild_permissions.administrator

    def is_admin_interaction(self, interaction: discord.Interaction) -> bool:
        """Check if user is admin (for slash commands)"""
        return interaction.user.guild_permissions.administrator

    # ==================== TEXT COMMANDS (PREFIX: >) ====================

    @commands.command(name='myhits', aliases=['hits'])
    async def myhits_text(self, ctx: commands.Context, username: Optional[str] = None):
        """Check hits on all configured websites. Usage: >myhits [username]"""
        if username is None:
            username = ctx.author.display_name
        
        websites = load_websites()
        
        if not websites:
            embed = discord.Embed(
                title="❌ No Sites Configured",
                description="No websites are currently being tracked.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"📊 Hit Counts for {username}",
            color=discord.Color.blue()
        )
        
        total_hits = 0
        hit_found = False
        
        for site_name, config in websites.items():
            hits = await fetch_hits(
                config["url_template"],
                username,
                config["parser_type"],
                config["parser_value"]
            )
            
            if hits:
                try:
                    hit_count = int(hits)
                    total_hits += hit_count
                    hit_found = True
                    formatted_hits = f"{hit_count:,}"
                    embed.add_field(name=site_name, value=formatted_hits, inline=False)
                except ValueError:
                    embed.add_field(name=site_name, value="❌", inline=False)
            else:
                embed.add_field(name=site_name, value="❌", inline=False)
        
        if hit_found:
            embed.add_field(name="Total Hits", value=f"{total_hits:,}", inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name='addsite')
    @commands.has_permissions(administrator=True)
    async def addsite_text(self, ctx: commands.Context, name: str, url_template: str, 
                           parser_type: str, parser_value: str):
        """Add a website to track. Admin only. Usage: >addsite <name> <url_template> <json|regex> <parser_value>"""
        if parser_type.lower() not in ['json', 'regex']:
            embed = discord.Embed(
                title="❌ Invalid Parser Type",
                description="Parser type must be `json` or `regex`.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if '{user}' not in url_template:
            embed = discord.Embed(
                title="❌ Invalid URL Template",
                description="URL template must contain `{user}` placeholder.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        websites = load_websites()
        if name.lower() in [k.lower() for k in websites.keys()]:
            embed = discord.Embed(
                title="❌ Site Already Exists",
                description=f"A site named `{name}` is already configured.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        websites[name] = {
            "url_template": url_template,
            "parser_type": parser_type.lower(),
            "parser_value": parser_value
        }
        save_websites(websites)
        
        embed = discord.Embed(
            title="✅ Site Added",
            description=f"Site `{name}` has been added.",
            color=discord.Color.green()
        )
        embed.add_field(name="URL Template", value=url_template, inline=False)
        embed.add_field(name="Parser Type", value=parser_type.lower(), inline=True)
        embed.add_field(name="Parser Value", value=parser_value, inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='removesite')
    @commands.has_permissions(administrator=True)
    async def removesite_text(self, ctx: commands.Context, name: str):
        """Remove a website. Admin only. Usage: >removesite <name>"""
        websites = load_websites()
        
        if name not in websites:
            embed = discord.Embed(
                title="❌ Site Not Found",
                description=f"No site named `{name}` found.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        del websites[name]
        save_websites(websites)
        
        embed = discord.Embed(
            title="✅ Site Removed",
            description=f"Site `{name}` has been removed.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name='listsites', aliases=['sitelist'])
    async def listsites_text(self, ctx: commands.Context):
        """List all configured websites. Usage: >listsites"""
        websites = load_websites()
        
        if not websites:
            embed = discord.Embed(
                title="📋 Configured Sites",
                description="No websites are currently configured.",
                color=discord.Color.blue()
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title="📋 Configured Sites",
            color=discord.Color.blue()
        )
        
        for site_name, config in websites.items():
            parser_info = f"**Type:** {config['parser_type']}\n**Value:** `{config['parser_value']}`"
            embed.add_field(
                name=site_name,
                value=f"**URL:** `{config['url_template']}`\n{parser_info}",
                inline=False
            )
        
        embed.set_footer(text=f"Total: {len(websites)} site(s)")
        await ctx.send(embed=embed)

    @commands.command(name='testuser')
    @commands.has_permissions(administrator=True)
    async def testuser_text(self, ctx: commands.Context, site: str, username: str):
        """Test a specific site for a username. Admin only. Usage: >testuser <site> <username>"""
        websites = load_websites()
        
        if site not in websites:
            embed = discord.Embed(
                title="❌ Site Not Found",
                description=f"No site named `{site}` found.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        config = websites[site]
        embed = discord.Embed(
            title=f"Testing {site}",
            description=f"Username: `{username}`",
            color=discord.Color.blue()
        )
        
        hits = await fetch_hits(
            config["url_template"],
            username,
            config["parser_type"],
            config["parser_value"]
        )
        
        if hits:
            try:
                hit_count = int(hits)
                embed.add_field(name="Result", value=f"✅ {hit_count:,} hits", inline=False)
                embed.color = discord.Color.green()
            except ValueError:
                embed.add_field(name="Result", value=f"✅ {hits} (non-numeric)", inline=False)
                embed.color = discord.Color.green()
        else:
            embed.add_field(
                name="Result",
                value="❌ Could not fetch data.",
                inline=False
            )
            embed.color = discord.Color.red()
        
        embed.add_field(
            name="Attempted URL",
            value=config["url_template"].replace("{user}", username),
            inline=False
        )
        await ctx.send(embed=embed)

    # ==================== SLASH COMMANDS ====================

    @app_commands.command(name="myhits", description="Check hits on all configured websites")
    @app_commands.describe(username="Username to check (defaults to your Discord name)")
    async def myhits_slash(self, interaction: discord.Interaction, username: Optional[str] = None):
        """Check all configured websites for a username"""
        await interaction.response.defer()
        
        if username is None:
            username = interaction.user.name
        
        websites = load_websites()
        
        if not websites:
            embed = discord.Embed(
                title="❌ No Sites Configured",
                description="No websites have been added yet. Use `/addsite` to add one.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        embed = discord.Embed(
            title=f"📊 Hit Counts for {username}",
            color=discord.Color.blue()
        )
        
        total_hits = 0
        results = []
        
        for site_name, config in websites.items():
            hits = await fetch_hits(
                config["url_template"],
                username,
                config["parser_type"],
                config["parser_value"]
            )
            
            if hits:
                try:
                    hit_count = int(hits)
                    total_hits += hit_count
                    results.append((site_name, hit_count))
                    embed.add_field(
                        name=site_name,
                        value=f"{hit_count:,}",
                        inline=False
                    )
                except ValueError:
                    embed.add_field(
                        name=site_name,
                        value=f"{hits} (non-numeric)",
                        inline=False
                    )
            else:
                embed.add_field(
                    name=site_name,
                    value="❌",
                    inline=False
                )
        
        if results:
            embed.add_field(name="Total Hits", value=f"{total_hits:,}", inline=False)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="addsite", description="Add a website to track")
    @app_commands.describe(
        name="Site name (e.g., 'Beamse')",
        url_template="URL with {user} placeholder (e.g., 'https://app.beamse.pro/api/user/{user}')",
        parser_type="Parser type: 'json' or 'regex'",
        parser_value="JSON path (e.g., 'hits') or regex pattern (e.g., 'Total: (\\d+)')"
    )
    async def addsite_slash(
        self,
        interaction: discord.Interaction,
        name: str,
        url_template: str,
        parser_type: str,
        parser_value: str
    ):
        """Add a website to track (Admin only)"""
        if not self.is_admin_interaction(interaction):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators can add websites.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if parser_type.lower() not in ["json", "regex"]:
            embed = discord.Embed(
                title="❌ Invalid Parser Type",
                description="Parser type must be 'json' or 'regex'.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if "{user}" not in url_template:
            embed = discord.Embed(
                title="❌ Invalid URL Template",
                description="URL must contain `{user}` as a placeholder.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        websites = load_websites()
        if name.lower() in [k.lower() for k in websites.keys()]:
            embed = discord.Embed(
                title="❌ Site Already Exists",
                description=f"A site named `{name}` is already configured.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        websites[name] = {
            "url_template": url_template,
            "parser_type": parser_type.lower(),
            "parser_value": parser_value
        }
        save_websites(websites)
        
        embed = discord.Embed(
            title="✅ Site Added",
            description=f"Site `{name}` has been added.",
            color=discord.Color.green()
        )
        embed.add_field(name="URL Template", value=url_template, inline=False)
        embed.add_field(name="Parser Type", value=parser_type.lower(), inline=True)
        embed.add_field(name="Parser Value", value=parser_value, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="removesite", description="Remove a tracked website")
    @app_commands.describe(name="Site name to remove")
    async def removesite_slash(self, interaction: discord.Interaction, name: str):
        """Remove a website from tracking (Admin only)"""
        if not self.is_admin_interaction(interaction):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only administrators can remove websites.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        websites = load_websites()
        
        if name not in websites:
            embed = discord.Embed(
                title="❌ Site Not Found",
                description=f"No site named `{name}` found.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        del websites[name]
        save_websites(websites)
        
        embed = discord.Embed(
            title="✅ Site Removed",
            description=f"Site `{name}` has been removed.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="listsites", description="List all configured websites")
    async def listsites_slash(self, interaction: discord.Interaction):
        """Show all configured websites"""
        await interaction.response.defer()
        
        websites = load_websites()
        
        if not websites:
            embed = discord.Embed(
                title="📋 Configured Sites",
                description="No websites have been added yet. Use `/addsite` to add one.",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed)
        
        embed = discord.Embed(
            title="📋 Configured Sites",
            color=discord.Color.blue()
        )
        
        for name, config in websites.items():
            value = (
                f"**URL:** `{config['url_template']}`\n"
                f"**Parser:** `{config['parser_type']}` → `{config['parser_value']}`"
            )
            embed.add_field(name=name, value=value, inline=False)
        
        embed.set_footer(text=f"Total: {len(websites)} site(s)")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="testuser", description="Test a specific site for a username")
    @app_commands.describe(site="Site name to test", username="Username to test")
    async def testuser_slash(self, interaction: discord.Interaction, site: str, username: str):
        """Test a specific website for a user"""
        await interaction.response.defer()
        
        websites = load_websites()
        
        if site not in websites:
            embed = discord.Embed(
                title="❌ Site Not Found",
                description=f"No site named `{site}` found.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        config = websites[site]
        embed = discord.Embed(
            title=f"Testing {site}",
            description=f"Username: `{username}`",
            color=discord.Color.blue()
        )
        
        hits = await fetch_hits(
            config["url_template"],
            username,
            config["parser_type"],
            config["parser_value"]
        )
        
        if hits:
            try:
                hit_count = int(hits)
                embed.add_field(name="Result", value=f"✅ {hit_count:,} hits", inline=False)
                embed.color = discord.Color.green()
            except ValueError:
                embed.add_field(name="Result", value=f"✅ {hits} (non-numeric)", inline=False)
                embed.color = discord.Color.green()
        else:
            embed.add_field(
                name="Result",
                value="❌ Could not fetch data. Check if the username exists on this site.",
                inline=False
            )
            embed.color = discord.Color.red()
        
        embed.add_field(
            name="Attempted URL",
            value=config["url_template"].replace("{user}", username),
            inline=False
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(WebsiteTracker(bot))

