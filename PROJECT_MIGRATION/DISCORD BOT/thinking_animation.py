import discord
import json
import os
import asyncio
import random

class ThinkingAnimation:
    def __init__(self):
        self.animation_path = os.path.join('animations', 'thinking_animation.json')
        try:
            with open(self.animation_path, 'r') as f:
                self.animation_data = json.load(f)
        except Exception as e:
            print(f"Error loading thinking animation: {e}")
            self.animation_data = None
        self.animation_message = None  # Track the animation message for deletion
        self._animation_task = None
        self._stop_animation = False

    def generate_binary_frame(self, length=24):
        """Generate binary string with independent bit flips for fast, random changes"""
        # Create initial pattern if not exists
        if not hasattr(self, '_binary_pattern') or len(self._binary_pattern) != length:
            self._binary_pattern = ''.join(random.choice(['0', '1']) for _ in range(length))

        # Flip random bits to create independent changes
        pattern_list = list(self._binary_pattern)
        for i in range(length):
            if random.random() < 0.5:  # 50% chance to flip each bit for faster changes
                pattern_list[i] = '1' if pattern_list[i] == '0' else '0'
        self._binary_pattern = ''.join(pattern_list)
        return self._binary_pattern

    def generate_status_text(self):
        """Generate animated status text with moving dots for animation"""
        base_texts = [
            "Analyzing neural networks",
            "Processing quantum algorithms",
            "Scanning knowledge databases",
            "Computing optimal response",
            "Synthesizing information",
            "Calibrating AI circuits",
            "Loading cognitive modules",
            "Initializing response matrix",
            "Processing user query",
            "Generating intelligent reply"
        ]
        base_text = random.choice(base_texts)
        # Animate dots moving from 1 to 3 dots
        if not hasattr(self, '_dot_count'):
            self._dot_count = 1
            self._dot_direction = 1
        else:
            self._dot_count += self._dot_direction
            if self._dot_count == 3 or self._dot_count == 1:
                self._dot_direction *= -1
        dots = '.' * self._dot_count
        return f"{base_text}{dots}"

    def generate_angel_art(self):
        """Generate angel-themed ASCII art for animation"""
        angel_frames = [
            """
     /\\
    //\\\\
   ///\\\\
  ////\\\\
 /////\\\\
//////\\\\
    ||
    ||
   /  \\
  |    |
   \\  /
    \\/
    """,
            """
     /\\
    //\\\\
   ///\\\\
  ////\\\\
 /////\\\\
//////\\\\
    ||
    ||
   /  \\
  | () |
   \\  /
    \\/
    """,
            """
     /\\
    //\\\\
   ///\\\\
  ////\\\\
 /////\\\\
//////\\\\
    ||
    ||
   /  \\
  | >< |
   \\  /
    \\/
    """
        ]
        return random.choice(angel_frames)

    def generate_animated_title(self):
        """Generate animated title with moving dots"""
        base_title = "🤖 Processing"
        # Animate dots moving from 1 to 3 dots
        if not hasattr(self, '_title_dot_count'):
            self._title_dot_count = 1
            self._title_dot_direction = 1
        else:
            self._title_dot_count += self._title_dot_direction
            if self._title_dot_count == 3 or self._title_dot_count == 1:
                self._title_dot_direction *= -1
        dots = '.' * self._title_dot_count
        return f"{base_title}{dots}"

    async def _animation_loop(self):
        while self.animation_message:
            if self._stop_animation:
                break
            try:
                # Longer binary string with visible changes
                binary_display = self.generate_binary_frame(24)

                thinking_embed = discord.Embed(
                    title=self.generate_animated_title(),
                    description=f"```\n{binary_display}\n```\n*{self.generate_status_text()}*",
                    color=0x9b59b6
                )
                thinking_embed.set_footer(text="Analyzing and processing your request...")
                thinking_embed.set_thumbnail(url="https://i.postimg.cc/fLLWWSKq/ezgif-278f9fa56d75db.gif")
                await self.animation_message.edit(embed=thinking_embed)
                await asyncio.sleep(1.0)  # Slower animation to avoid rate limits
            except discord.HTTPException as e:
                if e.code == 429:  # Rate limit
                    print(f"Animation rate limited: {e}")
                    await asyncio.sleep(5.0)  # Wait longer on rate limit
                    continue  # Try again after wait
                else:
                    # Message was edited or deleted by another process, stop animation
                    print(f"Animation stopped due to message conflict: {e}")
                    break
            except (discord.NotFound, discord.Forbidden) as e:
                # Message was edited or deleted by another process, stop animation
                print(f"Animation stopped due to message conflict: {e}")
                break
            except Exception as e:
                print(f"Error updating thinking animation: {e}")
                break

    async def show_thinking(self, interaction: discord.Interaction):
        """Show the thinking state for a command interaction."""
        try:
            # First defer the interaction if not already deferred
            if not interaction.response.is_done():
                await interaction.response.defer(thinking=True)
            
            # Create an initial thinking embed with random elements
            binary_lines = [
                self.generate_binary_frame(10),
                self.generate_binary_frame(12),
                self.generate_binary_frame(8)
            ]
            binary_display = '\n'.join(binary_lines)

            thinking_embed = discord.Embed(
                title=self.generate_animated_title(),
                description=f"```\n{binary_display}\n```\n*{self.generate_status_text()}*",
                color=0x9b59b6
            )
            thinking_embed.set_footer(text="Analyzing and processing your request...")
            thinking_embed.set_thumbnail(url="https://i.postimg.cc/fLLWWSKq/ezgif-278f9fa56d75db.gif")

            # Send the thinking message and store it for later reference
            try:
                self.animation_message = await interaction.followup.send(embed=thinking_embed)
            except discord.HTTPException as e:
                if e.code == 10062:  # Unknown interaction
                    print(f"Interaction token expired, cannot show thinking animation: {e}")
                    self.animation_message = None
                else:
                    raise
            
            # Start the animation loop
            self._stop_animation = False
            self._animation_task = asyncio.create_task(self._animation_loop())
            
        except Exception as e:
            print(f"Error showing thinking animation: {e}")

    async def stop_thinking(self, interaction: discord.Interaction, delete_message=True):
        """Stop the thinking animation and optionally clear its message"""
        try:
            # Stop the animation task first
            self._stop_animation = True

            # Wait a brief moment for the animation loop to stop
            await asyncio.sleep(0.05)

            if self._animation_task:
                self._animation_task.cancel()
                try:
                    await self._animation_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelled
                self._animation_task = None

            # Then delete the message to make animation disappear
            if delete_message and self.animation_message:
                try:
                    await self.animation_message.delete()
                    self.animation_message = None
                except (discord.NotFound, discord.HTTPException):
                    # Message was already deleted or can't be deleted
                    self.animation_message = None
                    pass
        except Exception as e:
            print(f"Error stopping thinking animation: {e}")

    async def update_thinking(self, interaction: discord.Interaction, message: str = None):
        """Update the thinking animation with a new message or random elements"""
        if not self.animation_message:
            return

        try:
            # Create new embed with updated content
            thinking_embed = discord.Embed(
                title=self.generate_animated_title(),
                description=message if message else f"```\n{self.generate_binary_frame()}\n```\n*{self.generate_status_text()}*",
                color=0x9b59b6
            )
            thinking_embed.set_footer(text="Analyzing and processing your request...")
            thinking_embed.set_thumbnail(url="https://i.postimg.cc/fLLWWSKq/ezgif-278f9fa56d75db.gif")

            # Update the message
            await self.animation_message.edit(embed=thinking_embed)
        except Exception as e:
            print(f"Error updating thinking animation: {e}")
