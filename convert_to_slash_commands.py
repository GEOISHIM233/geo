#!/usr/bin/env python3
"""
Converts prefix commands (@commands.command()) to slash commands (@app_commands.command())
Run: python convert_to_slash_commands.py
"""

import os
import re
from pathlib import Path

def convert_file(filepath: Path) -> bool:
    """Convert a single Python file from prefix to slash commands."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # Skip if already converted
        if '@app_commands.command' in content:
            print(f"⏭️  Skipping {filepath.name} (already uses app_commands)")
            return False
        
        # Skip if no commands
        if '@commands.command' not in content:
            print(f"⏭️  Skipping {filepath.name} (no prefix commands found)")
            return False
        
        # Add app_commands import if missing
        if 'from discord import app_commands' not in content and 'import app_commands' not in content:
            import_insert = "from discord import app_commands\n"
            # Find a good place to insert (after other discord imports)
            if 'from discord' in content:
                last_discord_import = max([m.end() for m in re.finditer(r'from discord.*\n', content)])
                content = content[:last_discord_import] + import_insert + content[last_discord_import:]
            else:
                content = import_insert + content
        
        # Convert @commands.command() to @app_commands.command()
        content = re.sub(r'@commands\.command\(\s*\)', '@app_commands.command()', content)
        
        # Convert async def command_name(self, ctx) to async def command_name(self, interaction: discord.Interaction)
        content = re.sub(
            r'async def (\w+)\(self, ctx\):',
            r'async def \1(self, interaction: discord.Interaction):',
            content
        )
        
        # Convert ctx.send() to interaction.response.send_message()
        content = re.sub(
            r'await ctx\.send\(',
            r'await interaction.response.send_message(',
            content
        )
        
        # Convert ctx.author to interaction.user
        content = re.sub(r'\bctx\.author\b', 'interaction.user', content)
        
        # Convert ctx.guild to interaction.guild
        content = re.sub(r'\bctx\.guild\b', 'interaction.guild', content)
        
        # Convert ctx.channel to interaction.channel
        content = re.sub(r'\bctx\.channel\b', 'interaction.channel', content)
        
        # Convert ctx.message to interaction.message
        content = re.sub(r'\bctx\.message\b', 'interaction.message', content)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Converted {filepath.name}")
            return True
        else:
            print(f"⏭️  No changes needed for {filepath.name}")
            return False
    
    except Exception as e:
        print(f"❌ Error converting {filepath.name}: {e}")
        return False

def main():
    """Convert all Python files in bot/cogs directory."""
    cogs_dir = Path('bot/cogs')
    
    if not cogs_dir.exists():
        print(f"❌ Directory {cogs_dir} not found")
        return
    
    converted = 0
    skipped = 0
    
    # Find all Python files recursively
    for py_file in cogs_dir.rglob('*.py'):
        if convert_file(py_file):
            converted += 1
        else:
            skipped += 1
    
    print(f"\n{'='*50}")
    print(f"📊 Summary: {converted} converted, {skipped} skipped")
    print(f"{'='*50}")
    
    if converted > 0:
        print("\n⚠️  Manual review recommended:")
        print("  - Check for ctx.defer() → use interaction.response.defer()")
        print("  - Check for ctx.edit() → use interaction.response.edit_message()")
        print("  - Add @app_commands.describe() decorators for parameter descriptions")

if __name__ == '__main__':
    main()

