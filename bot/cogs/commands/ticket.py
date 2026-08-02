import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import sqlite3
import os
from datetime import datetime


class TicketSystem(commands.Cog):
    """Complete ticket support system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF0000
        self.db_path = "db/tickets.db"
        self._init_db()

    def _init_db(self):
        """Initialize the database."""
        if not os.path.exists('db'):
            os.makedirs('db')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Guild config table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_guilds (
                guild_id INTEGER PRIMARY KEY,
                tickets_category_id INTEGER,
                support_role_id INTEGER,
                panel_channel_id INTEGER,
                panel_message_id INTEGER
            )
        ''')
        
        # Open tickets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS open_tickets (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER,
                creator_id INTEGER,
                created_at TEXT,
                FOREIGN KEY (guild_id) REFERENCES ticket_guilds(guild_id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def get_db_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ============================================================
    # TICKET SETUP
    # ============================================================
    @commands.hybrid_group(name='ticket', description='Ticket system commands.')
    @commands.guild_only()
    async def ticket(self, ctx):
        """Ticket system main group."""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🎫 Ticket System",
                description="Manage your support tickets.",
                color=self.color
            )
            embed.add_field(name=">ticket setup", value="Setup ticket system (creates category & role)", inline=False)
            embed.add_field(name=">ticket panel", value="Send ticket creation panel", inline=False)
            embed.add_field(name=">ticket close", value="Close the current ticket", inline=False)
            embed.set_footer(text="Use >ticket <subcommand> to manage tickets")
            await ctx.send(embed=embed)

    @ticket.command(name='setup', description='Setup the ticket system.')
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx):
        """Setup ticket system - creates TICKETS category and Support Team role."""
        guild = ctx.guild
        conn = self.get_db_connection()
        cursor = conn.cursor()

        # Create TICKETS category
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True, manage_messages=True)
            }
            tickets_category = await guild.create_category("TICKETS", overwrites=overwrites)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to create category: {str(e)}",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Create Support Team role
        try:
            support_role = await guild.create_role(
                name="Support Team",
                color=discord.Color.blue(),
                reason="Ticket System Support Role"
            )
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to create role: {str(e)}",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Save to database
        cursor.execute(
            'INSERT OR REPLACE INTO ticket_guilds (guild_id, tickets_category_id, support_role_id) VALUES (?, ?, ?)',
            (guild.id, tickets_category.id, support_role.id)
        )
        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="✅ Ticket System Setup Complete",
            description=f"**TICKETS Category:** {tickets_category.mention}\n**Support Team Role:** {support_role.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Next Steps", value="Use `>ticket panel` to send the ticket creation panel.", inline=False)
        await ctx.send(embed=embed)

    @ticket.command(name='panel', description='Send the ticket creation panel.')
    @commands.has_permissions(administrator=True)
    async def ticket_panel(self, ctx):
        """Send ticket creation panel with button."""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT tickets_category_id, support_role_id FROM ticket_guilds WHERE guild_id = ?', (ctx.guild.id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            embed = discord.Embed(
                title="❌ Not Setup",
                description="Run `>ticket setup` first.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Create panel
        embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Click the button below to create a support ticket.\n\nOur team will respond as soon as possible!",
            color=self.color
        )
        embed.set_footer(text="Ticket System")

        class TicketButton(View):
            def __init__(self, cog):
                super().__init__(timeout=None)
                self.cog = cog

            @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.blurple, emoji="🎫", custom_id="create_ticket_btn")
            async def create_ticket(self, interaction: discord.Interaction, button: Button):
                await self.cog.create_ticket(interaction)

        view = TicketButton(self)
        await ctx.send(embed=embed, view=view)

    async def create_ticket(self, interaction: discord.Interaction):
        """Create a new ticket for the user."""
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        user = interaction.user
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT tickets_category_id, support_role_id FROM ticket_guilds WHERE guild_id = ?', (guild.id,))
        result = cursor.fetchone()

        if not result:
            await interaction.followup.send("❌ Ticket system not setup.", ephemeral=True)
            conn.close()
            return

        tickets_category_id, support_role_id = result[0], result[1]
        tickets_category = guild.get_channel(tickets_category_id)
        support_role = guild.get_role(support_role_id)

        if not tickets_category or not support_role:
            await interaction.followup.send("❌ Ticket category or support role not found.", ephemeral=True)
            conn.close()
            return

        # Get ticket count for user
        cursor.execute('SELECT COUNT(*) as count FROM open_tickets WHERE guild_id = ? AND creator_id = ?', 
                      (guild.id, user.id))
        ticket_count = cursor.fetchone()['count']

        if ticket_count >= 3:
            await interaction.followup.send("❌ You already have 3 open tickets. Close one first.", ephemeral=True)
            conn.close()
            return

        # Create ticket channel
        ticket_number = cursor.execute('SELECT COUNT(*) as count FROM open_tickets WHERE guild_id = ?', 
                                      (guild.id,)).fetchone()['count'] + 1

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True, manage_messages=True)
        }

        try:
            ticket_channel = await tickets_category.create_text_channel(
                name=f"ticket-{ticket_number:04d}",
                overwrites=overwrites,
                topic=f"Ticket created by {user} | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create ticket: {str(e)}", ephemeral=True)
            conn.close()
            return

        # Save to database
        cursor.execute(
            'INSERT INTO open_tickets (channel_id, guild_id, creator_id, created_at) VALUES (?, ?, ?, ?)',
            (ticket_channel.id, guild.id, user.id, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        # Send welcome message
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_number:04d}",
            description=f"Welcome {user.mention}!\n\nOur support team will be with you shortly. Please describe your issue.",
            color=self.color
        )
        embed.set_footer(text="React with ❌ to close this ticket")

        class TicketActions(View):
            def __init__(self, cog):
                super().__init__(timeout=None)
                self.cog = cog

            @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="❌", custom_id="close_ticket_btn")
            async def close_ticket(self, interaction: discord.Interaction, button: Button):
                await self.cog.close_ticket(interaction)

        view = TicketActions(self)
        msg = await ticket_channel.send(embed=embed, view=view)

        await interaction.followup.send(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

    async def close_ticket(self, interaction: discord.Interaction):
        """Close a ticket and delete it after 5 seconds."""
        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT creator_id FROM open_tickets WHERE channel_id = ?', (channel.id,))
        result = cursor.fetchone()

        if not result:
            await interaction.followup.send("❌ This is not a ticket channel.", ephemeral=True)
            conn.close()
            return

        creator_id = result['creator_id']

        # Check permissions
        if interaction.user.id != creator_id and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ You can't close this ticket.", ephemeral=True)
            conn.close()
            return

        # Remove from database
        cursor.execute('DELETE FROM open_tickets WHERE channel_id = ?', (channel.id,))
        conn.commit()
        conn.close()

        # Send closing message
        embed = discord.Embed(
            title="🎫 Ticket Closed",
            description=f"This ticket will be deleted in 5 seconds...",
            color=discord.Color.orange()
        )
        await channel.send(embed=embed)

        # Wait 5 seconds then delete
        import asyncio
        await asyncio.sleep(5)

        try:
            await channel.delete(reason=f"Ticket closed by {interaction.user}")
        except:
            pass

    @ticket.command(name='close', description='Close the current ticket.')
    @commands.has_permissions(administrator=True)
    async def ticket_close(self, ctx):
        """Close the current ticket channel."""
        channel = ctx.channel
        conn = self.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT creator_id FROM open_tickets WHERE channel_id = ?', (channel.id,))
        result = cursor.fetchone()

        if not result:
            embed = discord.Embed(
                title="❌ Not a Ticket",
                description="This is not a ticket channel.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Remove from database
        cursor.execute('DELETE FROM open_tickets WHERE channel_id = ?', (channel.id,))
        conn.commit()
        conn.close()

        # Send closing message
        embed = discord.Embed(
            title="🎫 Ticket Closed",
            description="This ticket will be deleted in 5 seconds...",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

        # Wait 5 seconds then delete
        import asyncio
        await asyncio.sleep(5)

        try:
            await channel.delete(reason=f"Ticket closed by {ctx.author}")
        except:
            pass


async def setup(bot):
    await bot.add_cog(TicketSystem(bot))

