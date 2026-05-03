import discord
from discord.ext import commands
from discord import app_commands
import random
from typing import Optional
from datetime import datetime

class TicTacToeButton(discord.ui.Button):
    """A button representing a cell in the Tic-Tac-Toe board."""
    
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        
        # Check if it's the correct player's turn
        if interaction.user.id != view.current_player.id:
            await interaction.response.send_message(
                "Not your turn!",
                ephemeral=True
            )
            return
        
        # Check if cell is already taken
        if view.board[self.y][self.x] is not None:
            await interaction.response.send_message(
                "Cell already taken!",
                ephemeral=True
            )
            return
        
        # Make the move
        view.board[self.y][self.x] = view.current_player
        
        # Update button appearance
        if view.current_player == view.player_x:
            self.style = discord.ButtonStyle.danger
            self.label = ''
            self.emoji = '❌'
        else:
            self.style = discord.ButtonStyle.primary
            self.label = ''
            self.emoji = '⭕'
        
        self.disabled = True
        view.moves_made += 1
        
        # Check for winner
        winner = view.check_winner()
        
        if winner:
            # Game won
            view.game_over = True
            await view.end_game(interaction, winner, is_draw=False)
        elif view.moves_made >= 9:
            # Draw
            view.game_over = True
            await view.end_game(interaction, None, is_draw=True)
        else:
            # Switch turns
            view.current_player = view.player_o if view.current_player == view.player_x else view.player_x
            view.update_embed()
            await interaction.response.edit_message(embed=view.embed, view=view)


class TicTacToeView(discord.ui.View):
    """The game view containing all the buttons and game logic."""
    
    def __init__(self, player_x: discord.User, player_o: discord.User):
        super().__init__(timeout=300)  # 5 minute timeout
        self.player_x = player_x
        self.player_o = player_o
        self.current_player = player_x  # X always goes first
        self.board = [[None, None, None] for _ in range(3)]
        self.moves_made = 0
        self.game_over = False
        self.start_time = datetime.now()
        
        # Create the 3x3 grid of buttons
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))
        
        self.embed = self.create_embed()
    
    def create_embed(self) -> discord.Embed:
        """Create the game embed."""
        turn_symbol = '❌' if self.current_player == self.player_x else '⭕'
        
        embed = discord.Embed(
            title="Tic-Tac-Toe",
            description=f"**{turn_symbol} {self.current_player.mention}'s turn**",
            color=0x5865F2
        )
        
        # Simple player info
        embed.add_field(
            name="Players",
            value=f"❌ {self.player_x.mention}\n⭕ {self.player_o.mention}",
            inline=False
        )
        
        return embed
    
    def update_embed(self):
        """Update the embed with current game state."""
        turn_symbol = '❌' if self.current_player == self.player_x else '⭕'
        
        self.embed.description = f"**{turn_symbol} {self.current_player.mention}'s turn**"
        self.embed.clear_fields()
        
        # Simple player info
        self.embed.add_field(
            name="Players",
            value=f"❌ {self.player_x.mention}\n⭕ {self.player_o.mention}",
            inline=False
        )
    
    def check_winner(self) -> Optional[discord.User]:
        """Check if there's a winner."""
        # Check rows
        for row in self.board:
            if row[0] == row[1] == row[2] and row[0] is not None:
                return row[0]
        
        # Check columns
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] and self.board[0][col] is not None:
                return self.board[0][col]
        
        # Check diagonals
        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] is not None:
            return self.board[0][0]
        
        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] is not None:
            return self.board[0][2]
        
        return None
    
    async def end_game(self, interaction: discord.Interaction, winner: Optional[discord.User], is_draw: bool):
        """End the game and display results."""
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        # Create end game embed
        if is_draw:
            embed = discord.Embed(
                title="Tic-Tac-Toe",
                description=(
                    f"```\n"
                    f"╔══════════════╗\n"
                    f"║   IT'S A     ║\n"
                    f"║     DRAW!    ║\n"
                    f"╚══════════════╝\n"
                    f"```"
                ),
                color=0xFFD700
            )
            embed.add_field(
                name="Players",
                value=f"❌ {self.player_x.mention}\n⭕ {self.player_o.mention}",
                inline=False
            )
        else:
            winner_symbol = '❌' if winner == self.player_x else '⭕'
            winner_name = winner.display_name
            
            embed = discord.Embed(
                title="Tic-Tac-Toe",
                description=(
                    f"```\n"
                    f"╔══════════════╗\n"
                    f"║   {winner_symbol} WINNER!   ║\n"
                    f"╚══════════════╝\n"
                    f"```\n"
                    f"**{winner.mention}** wins the game!"
                ),
                color=0xFF1493 if winner == self.player_x else 0x1E90FF
            )
            embed.add_field(
                name="Players",
                value=f"❌ {self.player_x.mention}\n⭕ {self.player_o.mention}",
                inline=False
            )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """Called when the view times out."""
        # Disable all buttons
        for child in self.children:
            child.disabled = True


class TicTacToe(commands.Cog):
    """A Tic-Tac-Toe game cog for Discord."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="tictactoe", description="Play Tic-Tac-Toe")
    @app_commands.describe(opponent="Choose your opponent")
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.User):
        """Start a new Tic-Tac-Toe game."""
        
        # Validation checks
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("You can't play against yourself!", ephemeral=True)
            return
        
        if opponent.bot:
            await interaction.response.send_message("You can't play against bots!", ephemeral=True)
            return
        
        # Randomly decide who goes first (X)
        if random.choice([True, False]):
            player_x = interaction.user
            player_o = opponent
        else:
            player_x = opponent
            player_o = interaction.user
        
        # Create the game
        view = TicTacToeView(player_x, player_o)
        
        # Send simple game start message
        start_message = f"{player_x.mention} (❌) vs {player_o.mention} (⭕)"
        
        await interaction.response.send_message(
            content=start_message,
            embed=view.embed,
            view=view
        )
    
    @app_commands.command(name="ttt", description="Play Tic-Tac-Toe")
    @app_commands.describe(opponent="Choose your opponent")
    async def ttt(self, interaction: discord.Interaction, opponent: discord.User):
        """Shorthand command for Tic-Tac-Toe."""
        await self.tictactoe(interaction, opponent)


async def setup(bot):
    await bot.add_cog(TicTacToe(bot))
