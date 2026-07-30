# ╔══════════════════════════════════════════════════════════════════╗
# ║            © 2026 Bezms — All Rights Reserved                   ║
# ║   discord  ──  https://discord.gg/9nKHrnWZqV                    ║
# ╚══════════════════════════════════════════════════════════════════╝

import discord
from utils.emoji import CROSS, DENIED, TICK, ZWARNING
import asyncio
import datetime
import re
import typing
import typing as t
from typing import *
from utils.Tools import *
from core import Cog, zyrox, Context
from discord.ext.commands import Converter
from discord.ext import commands, tasks
from discord.ui import Button, View
from typing import Union, Optional
from utils import Paginator, DescriptionEmbedPaginator, FieldPagePaginator, TextPaginator
from typing import Union, Optional
from io import BytesIO
import requests
import aiohttp
import time
from datetime import datetime, timezone, timedelta
import sqlite3
from typing import *
from discord.utils import utcnow
from collections import Counter



time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "s": 1, "m": 60, "d": 86400}


def convert(argument):
  args = argument.lower()
  matches = re.findall(time_regex, args)
  time = 0
  for key, value in matches:
    try:
      time += time_dict[value] * float(key)
    except KeyError:
      raise commands.BadArgument(
        f"{value} is an invalid time key! h|m|s|d are valid arguments")
    except ValueError:
      raise commands.BadArgument(f"{key} is not a number!")
  return round(time)

async def do_removal(ctx, limit, predicate, *, before=None, after=None):
    if limit > 2000:
        return await ctx.error(f"Too many messages to search given ({limit}/2000)")

    if before is None:
        before = ctx.message
    else:
        before = discord.Object(id=before)

    if after is not None:
        after = discord.Object(id=after)

    try:
        deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
    except discord.Forbidden as e:
        return await ctx.error("I do not have permissions to delete messages.")
    except discord.HTTPException as e:
        return await ctx.error(f"Error: {e} (try a smaller search?)")

    spammers = Counter(m.author.display_name for m in deleted)
    deleted = len(deleted)
    messages = [f'{TICK}> | {deleted} message{" was" if deleted == 1 else "s were"} removed.']
    if deleted:
        messages.append("")
        spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
        messages.extend(f"**{name}**: {count}" for name, count in spammers)

    to_send = "\n".join(messages)

    if len(to_send) > 2000:
        await ctx.send(f"{TICK}> | Successfully removed {deleted} messages.", delete_after=7)
    else:
        await ctx.send(to_send, delete_after=7)


class Moderation(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.color = 0xFF0000
    self.sniped = {}

  def convert(self, time):
    pos = ["s", "m", "h", "d"]

    time_dict = {"s": 1, "m": 60, "h": 3600, "d": 3600 * 24}
    unit = time[-1]
    if unit not in pos:
      return -1
    try:
      val = int(time[:-1])
    except:
      return -2
    return val * time_dict[unit]

  @commands.command(name="wipe", aliases=["purge", "clean"])
  @commands.has_permissions(manage_messages=True)
  async def wipe(self, ctx: Context, amount: int = None):
      """
      Deletes messages. Usage: !wipe [amount] – if no amount, deletes up to 10000.
      """
      if amount is None:
          amount = 10000
      if amount < 1:
          embed = discord.Embed(
              title="❌ Invalid Number",
              description="You must delete at least 1 message.",
              color=self.color
          )
          return await ctx.send(embed=embed)
      if amount > 10000:
          embed = discord.Embed(
              title="❌ Too Many Messages",
              description="You can only delete up to 10,000 messages at a time.",
              color=self.color
          )
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

      embed = discord.Embed(
          title="✅ Messages Cleared",
          description=f"Successfully deleted **{len(deleted) - 1}** messages.",
          color=discord.Color.green()
      )
      await ctx.send(embed=embed, delete_after=5)

  @wipe.error
  async def wipe_error(self, ctx: Context, error):
      if isinstance(error, commands.MissingPermissions):
          embed = discord.Embed(
              title="❌ Permission Denied",
              description="You need the **Manage Messages** permission to use this command.",
              color=self.color
          )
          await ctx.send(embed=embed)
      elif isinstance(error, commands.BadArgument):
          embed = discord.Embed(
              title="❌ Invalid Input",
              description="Please provide a valid number. Example: `!wipe 50`\nOr just type `!wipe` to clear everything.",
              color=self.color
          )
          await ctx.send(embed=embed)

  # ================================================================
  # YOUR OTHER MODERATION COMMANDS (lockall, unlockall, hideall, give, etc.)
  # Add them below exactly as you had them.
  # ================================================================

async def setup(bot):
    await bot.add_cog(Moderation(bot))
