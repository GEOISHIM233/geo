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

    def is_admin(self, interaction: discord.Interaction) -> bool:
        """Check if user is admin"""
        return interaction.user.guild_permissions.administrator

    @app_commands.command(name="myhits", description="Check hits on all configured websites")
    @app_commands.describe(username="Username to check (defaults to your Discord name)")
    async def myhits(self, interaction: discord.Interaction, username: Optional[str] = None):
        """Check all configured websites for a username"""
        await interaction.response.defer()
        
        if username is None:
            username = interaction.user.name
        
        websites = load_websites()
        
        if not websites:
            embed = discord.Embed(
                title="No Websites Configured",
                description="No websites have been added yet. Use `/addsite` to add one.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        embed = discord.Embed(
            title=f"Website Hits for **{username}**",
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
                        value=f"**{hit_count:,}** hits",
                        inline=False
                    )
                except ValueError:
                    embed.add_field(
                        name=site_name,
                        value=f"**{hits}** (non-numeric)",
                        inline=False
                    )
            else:
                embed.add_field(
                    name=site_name,
                    value="❌ Error fetching data",
                    inline=False
                )
        
        embed.set_footer(text=f"Total Hits: {total_hits:,}" if results else "No data available")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="addsite", description="Add a website to track")
    @app_commands.describe(
        name="Site name (e.g., 'Beamse')",
        url_template="URL with {user} placeholder (e.g., 'https://app.beamse.pro/api/user/{user}')",
        parser_type="Parser type: 'json' or 'regex'",
        parser_value="JSON path (e.g., 'hits') or regex pattern (e.g., 'Total: (\\d+)')"
    )
    async def addsite(
        self,
        interaction: discord.Interaction,
        name: str,
        url_template: str,
        parser_type: str,
        parser_value: str
    ):
        """Add a website to track (Admin only)"""
        if not self.is_admin(interaction):
            embed = discord.Embed(
                title="Permission Denied",
                description="Only administrators can add websites.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if parser_type not in ["json", "regex"]:
            embed = discord.Embed(
                title="Invalid Parser Type",
                description="Parser type must be 'json' or 'regex'.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if "{user}" not in url_template:
            embed = discord.Embed(
                title="Invalid URL Template",
                description="URL must contain `{user}` as a placeholder.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        websites = load_websites()
        websites[name] = {
            "url_template": url_template,
            "parser_type": parser_type,
            "parser_value": parser_value
        }
        save_websites(websites)
        
        embed = discord.Embed(
            title="Website Added",
            description=f"**{name}** has been added to tracking.",
            color=discord.Color.green()
        )
        embed.add_field(name="URL Template", value=url_template, inline=False)
        embed.add_field(name="Parser Type", value=parser_type, inline=False)
        embed.add_field(name="Parser Value", value=parser_value, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="removesite", description="Remove a tracked website")
    @app_commands.describe(name="Site name to remove")
    async def removesite(self, interaction: discord.Interaction, name: str):
        """Remove a website from tracking (Admin only)"""
        if not self.is_admin(interaction):
            embed = discord.Embed(
                title="Permission Denied",
                description="Only administrators can remove websites.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        websites = load_websites()
        
        if name not in websites:
            embed = discord.Embed(
                title="Site Not Found",
                description=f"**{name}** is not in the tracking list.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        del websites[name]
        save_websites(websites)
        
        embed = discord.Embed(
            title="Website Removed",
            description=f"**{name}** has been removed from tracking.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="listsites", description="List all configured websites")
    async def listsites(self, interaction: discord.Interaction):
        """Show all configured websites"""
        await interaction.response.defer()
        
        websites = load_websites()
        
        if not websites:
            embed = discord.Embed(
                title="No Websites Configured",
                description="No websites have been added yet. Use `/addsite` to add one.",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=embed)
        
        embed = discord.Embed(
            title="Configured Websites",
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
    async def testuser(self, interaction: discord.Interaction, site: str, username: str):
        """Test a specific website for a user"""
        await interaction.response.defer()
        
        websites = load_websites()
        
        if site not in websites:
            embed = discord.Embed(
                title="Site Not Found",
                description=f"**{site}** is not in the tracking list.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        config = websites[site]
        embed = discord.Embed(
            title=f"Testing {site}",
            description=f"Username: **{username}**",
            color=discord.Color.blue()
        )
        
        hits = await fetch_hits(
            config["url_template"],
            username,
            config["parser_type"],
            config["parser_value"]
        )
        
        if hits:
            embed.add_field(name="Result", value=f"✅ **{hits}** hits", inline=False)
            embed.color = discord.Color.green()
        else:
            embed.add_field(
                name="Result",
                value="❌ Could not fetch data. Check if the username exists on this site.",
                inline=False
            )
            embed.color = discord.Color.red()
        
        embed.add_field(name="URL Tested", value=config["url_template"].replace("{user}", username), inline=False)
        await interaction.followup.send(embed=embed)


import asyncio

async def setup(bot: commands.Bot):
    await bot.add_cog(WebsiteTracker(bot))

