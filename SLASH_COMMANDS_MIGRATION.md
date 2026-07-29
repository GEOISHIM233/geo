# Converting to Slash Commands (/)

Your bot is now set up to use slash commands (`/`) instead of prefix commands. Here's how to convert all your existing cogs.

## Automatic Conversion

Run the included converter script:
```bash
python convert_to_slash_commands.py
```

This script automatically:
- Changes `@commands.command()` → `@app_commands.command()`
- Converts `async def cmd(self, ctx)` → `async def cmd(self, interaction: discord.Interaction)`
- Replaces `ctx.send()` → `interaction.response.send_message()`
- Updates `ctx.author` → `interaction.user`
- Updates `ctx.guild` → `interaction.guild`
- Updates `ctx.channel` → `interaction.channel`

## Manual Conversion Guide

### 1. Basic Command Conversion

**Before (Prefix Command):**
```python
@commands.command()
async def hello(self, ctx):
    await ctx.send(f"Hello {ctx.author.mention}!")
```

**After (Slash Command):**
```python
@app_commands.command()
async def hello(self, interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello {interaction.user.mention}!")
```

### 2. Add Descriptions for Better UX

```python
@app_commands.command(name="hello", description="Say hello to a user")
@app_commands.describe(name="User to greet")
async def hello(self, interaction: discord.Interaction, name: str):
    await interaction.response.send_message(f"Hello {name}!")
```

### 3. Handle Deferred Responses (for long operations)

**Before:**
```python
@commands.command()
async def slowcmd(self, ctx):
    # Long operation
    await ctx.send("Done!")
```

**After:**
```python
@app_commands.command()
async def slowcmd(self, interaction: discord.Interaction):
    await interaction.response.defer()
    # Long operation
    await interaction.followup.send("Done!")
```

### 4. Common Context → Interaction Replacements

| Old (ctx) | New (interaction) |
|-----------|-------------------|
| `ctx.send()` | `interaction.response.send_message()` |
| `ctx.defer()` | `interaction.response.defer()` |
| `ctx.edit()` | `interaction.response.edit_message()` |
| `ctx.author` | `interaction.user` |
| `ctx.guild` | `interaction.guild` |
| `ctx.channel` | `interaction.channel` |
| `ctx.message` | `interaction.message` |
| `ctx.bot` | `interaction.client` |

### 5. Required Imports

Make sure each cog file has:
```python
from discord.ext import commands
from discord import app_commands
import discord
```

### 6. Permission Checks

**Before:**
```python
@commands.command()
@commands.has_permissions(administrator=True)
async def admin_cmd(self, ctx):
    await ctx.send("Admin command!")
```

**After:**
```python
@app_commands.command()
@app_commands.checks.has_permissions(administrator=True)
async def admin_cmd(self, interaction: discord.Interaction):
    await interaction.response.send_message("Admin command!")
```

## New Website Tracker Cog

A new cog has been added: `bot/cogs/websitetracker.py`

This cog provides:
- `/myhits [username]` – Check total hits across all websites
- `/addsite <name> <url> <parser_type> <parser_value>` – Add a tracked website
- `/removesite <name>` – Remove a website
- `/listsites` – Show all tracked websites
- `/testuser <site> <username>` – Test a specific site

**Configuration Example:**
```
/addsite Beamse https://app.beamse.pro/api/user/{user} json hits
/myhits username
```

Websites are stored in `bot/data/websites.json` and persist between restarts.

## Testing Your Changes

1. Run the converter: `python convert_to_slash_commands.py`
2. Merge the PR and redeploy
3. Invite the bot to a test server (if needed)
4. Type `/` in Discord to see all available commands
5. Check bot logs for any errors

## Troubleshooting

**Commands not appearing in Discord:**
- Make sure all cogs are being loaded (check logs for "Failed to load cogs")
- Run `/` and wait 5-10 seconds for the command list to update
- The bot needs to have `applications.commands` scope

**`aiofiles` module not found:**
- This has been added to requirements.txt
- Redeploy the bot to install the new dependency

**Still seeing prefix command errors:**
- Make sure you didn't miss any `ctx` parameters
- Check that all files are saved and deployed

