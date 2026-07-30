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

      # Send warning for large deletions
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
