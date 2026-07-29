import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any

class WebsiteTracker(commands.Cog):
    """Tracks website hit counts for users across multiple configured sites."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.websites_file = Path("bot/data/websites.json")
        self.websites_file.parent.mkdir(parents=True, exist_ok=True)
        self.websites = self._load_websites()
        self.timeout = aiohttp.ClientTimeout(total=10)
    
    def _load_websites(self) -> Dict[str, Dict[str, str]]:
        """Load websites from JSON file."""
        if self.websites_file.exists():
            try:
                with open(self.websites_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_websites(self) -> None:
        """Save websites to JSON file."""
        with open(self.websites_file, 'w') as f:
            json.dump(self.websites, f, indent=2)
    
    def _get_json_value(self, data: Any, path: str) -> Optional[int]:
        """Extract value from nested JSON using dot notation (e.g., 'data.hits' or 'user.stats.total')."""
        try:
            keys = path.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
            return int(value) if value is not None else None
        except (ValueError, TypeError, AttributeError):
            return None
    
    async def _fetch_hits(self, site_name: str, username: str) -> Optional[int]:
        """Fetch hit count from a website."""
        if site_name not in self.websites:
            return None
        
        site = self.websites[site_name]
        url = site['url'].replace('{user}', username)
        parser_type = site['parser_type']
        parser_value = site['parser_value']
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    
                    if parser_type == 'json':
                        data = await resp.json()
                        return self._get_json_value(data, parser_value)
                    
                    elif parser_type == 'regex':
                        text = await resp.text()
                        match = re.search(parser_value, text)
                        if match and match.groups():
                            try:
                                return int(match.group(1))
                            except (ValueError, IndexError):
                                return None
                        return None
        
        except asyncio.TimeoutError:
            return None
        except aiohttp.ClientError:
            return None
        except Exception:
            return None
    
    @app_commands.command(name="myhits", description="Check total hits across all tracked websites")
    @app_commands.describe(username="Username to check (defaults to your Discord name)")
    async def myhits(self, interaction: discord.Interaction, username: Optional[str] = None) -> None:
        """Check all configured websites for hit counts."""
        await interaction.response.defer()
        
        if not username:
            username = interaction.user.name
        
        if not self.websites:
            await interaction.followup.send("❌ No websites configured yet. Use `/addsite` to add one.")
            return
        
        results = {}
        total = 0
        
        for site_name in self.websites:
            hits = await self._fetch_hits(site_name, username)
            if hits is not None:
                results[site_name] = hits
                total += hits
        
        if not results:
            await interaction.followup.send(
                f"❌ No hit data found for `{username}` on any configured sites."
            )
            return
        
        embed = discord.Embed(
            title=f"📊 Hit Count for {username}",
            color=discord.Color.blue()
        )
        
        for site_name, hits in results.items():
            embed.add_field(name=site_name, value=f"`{hits:,}` hits", inline=False)
        
        embed.add_field(name="📈 Total", value=f"`{total:,}` hits", inline=False)
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="addsite", description="Add a website to track hit counts")
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
    ) -> None:
        """Add a website to track."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can add websites.",
                ephemeral=True
            )
            return
        
        if parser_type.lower() not in ['json', 'regex']:
            await interaction.response.send_message(
                "❌ Parser type must be 'json' or 'regex'.",
                ephemeral=True
            )
            return
        
        if '{user}' not in url_template:
            await interaction.response.send_message(
                "❌ URL must contain `{user}` placeholder.",
                ephemeral=True
            )
            return
        
        self.websites[name] = {
            'url': url_template,
            'parser_type': parser_type.lower(),
            'parser_value': parser_value
        }
        self._save_websites()
        
        await interaction.response.send_message(
            f"✅ Website `{name}` added successfully!",
            ephemeral=True
        )
    
    @app_commands.command(name="removesite", description="Remove a tracked website")
    @app_commands.describe(name="Site name to remove")
    async def removesite(self, interaction: discord.Interaction, name: str) -> None:
        """Remove a website from tracking."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can remove websites.",
                ephemeral=True
            )
            return
        
        if name not in self.websites:
            await interaction.response.send_message(
                f"❌ Website `{name}` not found.",
                ephemeral=True
            )
            return
        
        del self.websites[name]
        self._save_websites()
        
        await interaction.response.send_message(
            f"✅ Website `{name}` removed successfully!",
            ephemeral=True
        )
    
    @app_commands.command(name="listsites", description="List all configured websites")
    async def listsites(self, interaction: discord.Interaction) -> None:
        """Show all configured websites."""
        if not self.websites:
            await interaction.response.send_message("📭 No websites configured yet.")
            return
        
        embed = discord.Embed(
            title="📍 Tracked Websites",
            color=discord.Color.green(),
            description=f"Total: {len(self.websites)} site(s)"
        )
        
        for site_name, site_config in self.websites.items():
            value = (
                f"**URL:** `{site_config['url']}`\n"
                f"**Parser:** `{site_config['parser_type']}` → `{site_config['parser_value']}`"
            )
            embed.add_field(name=site_name, value=value, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="testuser", description="Test a specific site for a user")
    @app_commands.describe(site="Website name to test", username="Username to test")
    async def testuser(self, interaction: discord.Interaction, site: str, username: str) -> None:
        """Test a specific website."""
        await interaction.response.defer()
        
        if site not in self.websites:
            await interaction.followup.send(f"❌ Website `{site}` not found.")
            return
        
        hits = await self._fetch_hits(site, username)
        
        if hits is None:
            site_config = self.websites[site]
            url = site_config['url'].replace('{user}', username)
            await interaction.followup.send(
                f"❌ Failed to fetch data for `{username}` from `{site}`.\n"
                f"**URL tested:** `{url}`"
            )
            return
        
        await interaction.followup.send(
            f"✅ `{username}` has **{hits:,}** hits on `{site}`!"
        )

async def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    await bot.add_cog(WebsiteTracker(bot))

