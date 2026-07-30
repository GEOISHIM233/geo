# ╔══════════════════════════════════════════════════════════════════╗
# ║            © 2026 Bezms — All Rights Reserved                   ║
# ║   discord  ──  https://discord.gg/9nKHrnWZqV                    ║
# ╚══════════════════════════════════════════════════════════════════╝

import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
import re
from typing import Optional

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
    """Parse JSON path like 'data.hits' or 'user.stats.total' with support for numeric indices"""
    keys = path.split(".")
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list):
            try:
                idx = int(key)
                obj = obj[idx]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return obj

def parse_regex(text: str, pattern: str):
    """Extract value using regex with one capture group"""
    try:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None

async def fetch_hits(url_template: str, username: str, parser_type: str, parser_value: str) -> Optional[str]:
    """Fetch hit count from a website with 10-second timeout"""
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
                        if value is not None:
                            return str(int(value))  # Ensure it's an integer
                        return None
                    except Exception:
                        return None
                
                elif parser_type == "regex":
                    text = await resp.text()
                    value = parse_regex(text, parser_value)
                    if value:
                        try:
                            return str(int(value))  # Ensure it's an integer
                        except ValueError:
                            return None
                    return None
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None
    
    return None

class WebsiteTracker(commands.Cog):
    """Track website hit counts for users"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_admin(self, ctx: commands.Context) -> bool:
        """Check if user is admin"""
        return ctx.author.guild_permissions.administrator

    @commands.command(name="myhits", help="Check hits on all configured websites")
    async def myhits(self, ctx: commands.Context, *, username: Optional[str] = None):
        """Check all configured websites for a username
        
        Usage: >myhits [username]
        Defaults to your Discord display name if no username provided.
        """
        async with ctx.typing():
            if username is None:
                username = ctx.author.display_name
            
            websites = load_websites()
            
            if not websites:
                embed = discord.Embed(
                    title="No Websites Configured",
                    description="No websites have been added yet. Use `>addsite` to add one.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
            
            embed = discord.Embed(
                title=f"Website Hits for **{username}**",
                color=discord.Color.blue()
            )
            
            total_hits = 0
            found_any = False
            
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
                        found_any = True
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
            
            embed.set_footer(text=f"Total Hits: {total_hits:,}" if found_any else "No data available")
            await ctx.send(embed=embed)

    @commands.command(name="addsite", help="Add a website to track (Admin only)")
    async def addsite(self, ctx: commands.Context, name: str, url_template: str, parser_type: str, *, parser_value: str):
        """Add a website to track
        
        Usage: >addsite <name> <url_template> <parser_type> <parser_value>
        
        Example (JSON): >addsite Beamse https://app.beamse.pro/api/user/{user} json data.hits
        Example (Regex): >addsite Example https://example.com/user/{user} regex "Total Hits: (\\d+)"
        """
        if not self.is_admin(ctx):
            embed = discord.Embed(
                title="Permission Denied",
                description="Only administrators can add websites.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if parser_type.lower() not in ["json", "regex"]:
            embed = discord.Embed(
                title="Invalid Parser Type",
                description="Parser type must be `json` or `regex`.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if "{user}" not in url_template:
            embed = discord.Embed(
                title="Invalid URL Template",
                description="URL must contain `{user}` as a placeholder.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        websites = load_websites()
        websites[name] = {
            "url_template": url_template,
            "parser_type": parser_type.lower(),
            "parser_value": parser_value
        }
        save_websites(websites)
        
        embed = discord.Embed(
            title="✅ Website Added",
            description=f"**{name}** has been added to tracking.",
            color=discord.Color.green()
        )
        embed.add_field(name="URL Template", value=f"`{url_template}`", inline=False)
        embed.add_field(name="Parser Type", value=f"`{parser_type.lower()}`", inline=False)
        embed.add_field(name="Parser Value", value=f"`{parser_value}`", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="removesite", help="Remove a tracked website (Admin only)")
    async def removesite(self, ctx: commands.Context, *, name: str):
        """Remove a website from tracking
        
        Usage: >removesite <name>
        """
        if not self.is_admin(ctx):
            embed = discord.Embed(
                title="Permission Denied",
                description="Only administrators can remove websites.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        websites = load_websites()
        
        if name not in websites:
            embed = discord.Embed(
                title="Site Not Found",
                description=f"**{name}** is not in the tracking list.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        del websites[name]
        save_websites(websites)
        
        embed = discord.Embed(
            title="✅ Website Removed",
            description=f"**{name}** has been removed from tracking.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="listsites", help="List all configured websites")
    async def listsites(self, ctx: commands.Context):
        """Show all configured websites
        
        Usage: >listsites
        """
        async with ctx.typing():
            websites = load_websites()
            
            if not websites:
                embed = discord.Embed(
                    title="No Websites Configured",
                    description="No websites have been added yet. Use `>addsite` to add one.",
                    color=discord.Color.orange()
                )
                return await ctx.send(embed=embed)
            
            embed = discord.Embed(
                title="Configured Websites",
                color=discord.Color.blue()
            )
            
            for site_name, config in websites.items():
                value = (
                    f"**URL:** `{config['url_template']}`\n"
                    f"**Parser:** `{config['parser_type']}` → `{config['parser_value']}`"
                )
                embed.add_field(name=site_name, value=value, inline=False)
            
            embed.set_footer(text=f"Total: {len(websites)} site(s)")
            await ctx.send(embed=embed)

    @commands.command(name="testuser", help="Test a specific site for a username (Admin only)")
    async def testuser(self, ctx: commands.Context, site: str, *, username: str):
        """Test a specific website for a user
        
        Usage: >testuser <site> <username>
        """
        if not self.is_admin(ctx):
            embed = discord.Embed(
                title="Permission Denied",
                description="Only administrators can test sites.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        async with ctx.typing():
            websites = load_websites()
            
            if site not in websites:
                embed = discord.Embed(
                    title="Site Not Found",
                    description=f"**{site}** is not in the tracking list.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
            
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
            
            embed.add_field(
                name="URL Tested",
                value=f"`{config['url_template'].replace('{user}', username)}`",
                inline=False
            )
            await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Load the WebsiteTracker cog"""
    await bot.add_cog(WebsiteTracker(bot))

