import discord
from discord.ext import commands
import aiohttp
import json
import re
import os
from typing import Optional

WEBSITES_FILE = "websites.json"

class HitCounter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.websites = self.load_websites()

    def load_websites(self):
        if os.path.exists(WEBSITES_FILE):
            with open(WEBSITES_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_websites(self):
        with open(WEBSITES_FILE, 'w') as f:
            json.dump(self.websites, f, indent=4)

    async def fetch_hits(self, site_name: str, username: str) -> Optional[int]:
        site = self.websites.get(site_name)
        if not site:
            return None
        url = site['url'].format(user=username)
        parser_type = site['parser_type']
        parser_value = site['parser_value']

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        return None
                    if parser_type == 'json':
                        data = await response.json()
                        keys = parser_value.split('.')
                        value = data
                        for key in keys:
                            if isinstance(value, dict):
                                value = value.get(key)
                            elif key.isdigit() and isinstance(value, list):
                                value = value[int(key)]
                            else:
                                return None
                        if isinstance(value, int):
                            return value
                        elif isinstance(value, str) and value.isdigit():
                            return int(value)
                        return None
                    elif parser_type == 'regex':
                        text = await response.text()
                        match = re.search(parser_value, text)
                        if match:
                            try:
                                return int(match.group(1))
                            except (ValueError, IndexError):
                                return None
        except Exception:
            return None

    @commands.command(name='myhits')
    async def myhits(self, ctx: commands.Context, username: Optional[str] = None):
        """Check your total hits across all tracked websites.
        Usage: >myhits [username]  (defaults to your Discord name)
        """
        if not username:
            username = ctx.author.name

        results = {}
        total = 0
        for name in self.websites:
            hits = await self.fetch_hits(name, username)
            if hits is not None:
                results[name] = hits
                total += hits
            else:
                results[name] = "❌"

        if not results:
            embed = discord.Embed(
                title="❌ No websites configured",
                description="Ask an admin to add websites using `>addsite`.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title=f"🔢 Hit Counts for `{username}`",
            color=discord.Color.blue()
        )
        for name, hits in results.items():
            if isinstance(hits, int):
                embed.add_field(name=f"📊 {name}", value=f"{hits:,}", inline=True)
            else:
                embed.add_field(name=f"📊 {name}", value=hits, inline=True)
        embed.add_field(name="📈 Total", value=f"{total:,}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='addsite')
    @commands.has_permissions(administrator=True)
    async def addsite(self, ctx: commands.Context, name: str, url_template: str, parser_type: str, parser_value: str):
        """Add a website to track hits.
        Usage: >addsite <name> <url_template> <parser_type> <parser_value>
        parser_type: json or regex
        Example: >addsite beamse https://app.beamse.pro/api/user/{user} json hits
        """
        if name in self.websites:
            embed = discord.Embed(
                title="⚠️ Already Exists",
                description=f"A site named `{name}` already exists. Use `>removesite` first.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        if "{user}" not in url_template:
            embed = discord.Embed(
                title="❌ Invalid URL Template",
                description="The URL must contain `{user}` as a placeholder.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        if parser_type not in ('json', 'regex'):
            embed = discord.Embed(
                title="❌ Invalid parser type",
                description="Must be `json` or `regex`.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        self.websites[name] = {
            "url": url_template,
            "parser_type": parser_type,
            "parser_value": parser_value
        }
        self.save_websites()

        embed = discord.Embed(
            title="✅ Site Added",
            description=f"Added `{name}` with parser `{parser_type}` and value `{parser_value}`.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name='removesite')
    @commands.has_permissions(administrator=True)
    async def removesite(self, ctx: commands.Context, name: str):
        """Remove a tracked website.
        Usage: >removesite <name>
        """
        if name not in self.websites:
            embed = discord.Embed(
                title="❌ Not Found",
                description=f"No site named `{name}` found.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        del self.websites[name]
        self.save_websites()

        embed = discord.Embed(
            title="✅ Site Removed",
            description=f"Removed `{name}`.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name='listsites')
    async def listsites(self, ctx: commands.Context):
        """List all tracked websites.
        Usage: >listsites
        """
        if not self.websites:
            embed = discord.Embed(
                title="📋 Tracked Websites",
                description="No websites configured.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return

        description = ""
        for name, site in self.websites.items():
            description += f"• **{name}** — `{site['url']}` (parser: {site['parser_type']})\n"
        embed = discord.Embed(
            title="📋 Tracked Websites",
            description=description,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.command(name='testuser')
    @commands.has_permissions(administrator=True)
    async def testuser(self, ctx: commands.Context, site: str, username: str):
        """Test a specific site to see if it returns a hit count.
        Usage: >testuser <site> <username>
        """
        if site not in self.websites:
            embed = discord.Embed(
                title="❌ Site Not Found",
                description=f"No site named `{site}` found.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        hits = await self.fetch_hits(site, username)
        if hits is not None:
            embed = discord.Embed(
                title="✅ Test Successful",
                description=f"Site **{site}** returned **{hits:,}** hits for `{username}`.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Test Failed",
                description=f"Could not fetch hit count for `{username}` from **{site}**.\nCheck the URL and parser configuration.",
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(HitCounter(bot))
