import discord
import asyncio
from thinking_animation import ThinkingAnimation
from typing import Any
import functools

# Global animation instance
_thinking_animation = ThinkingAnimation()


class CommandAnimator:
    """Manages animations for any command"""
    
    def __init__(self):
        self.active_animations = {}  # Track running animations
    
    async def show_loading(self, interaction: discord.Interaction, message: str = "Loading..."):
        """Show a loading animation for a command"""
        try:
            await _thinking_animation.show_thinking(interaction)
            return _thinking_animation.animation_message
        except Exception as e:
            print(f"Error showing loading animation: {e}")
            return None
    
    async def stop_loading(self, interaction: discord.Interaction, delete: bool = False):
        """Stop the loading animation"""
        try:
            await _thinking_animation.stop_thinking(interaction, delete_message=delete)
        except Exception as e:
            print(f"Error stopping loading animation: {e}")
    
    async def animate_command(self, interaction: discord.Interaction, coro):
        """
        Wrapper to run a command with loading animation.
        
        Usage:
            result = await animator.animate_command(interaction, fetch_some_data())
        """
        try:
            # Show loading animation
            await self.show_loading(interaction)
            
            # Run the actual command
            result = await coro
            
            # Stop animation
            await self.stop_loading(interaction, delete=True)
            
            return result
        except Exception as e:
            await self.stop_loading(interaction, delete=True)
            raise


# Global instance for use throughout the app
animator = CommandAnimator()


def command_animation(func):
    """
    Decorator to add animation to any command function.
    
    Usage:
        @bot.tree.command(name="mycommand")
        @command_animation
        async def mycommand(interaction: discord.Interaction):
            # Your command code here
            await interaction.followup.send("Done!")
    """
    @functools.wraps(func)
    async def wrapper(first_arg, /, *args: Any, **kwargs: Any) -> Any:
        # Detect if this is a cog method (first_arg is self) or standalone command (first_arg is interaction)
        if isinstance(first_arg, discord.Interaction):
            # Standalone command: first_arg is the interaction
            interaction = first_arg
            cog_self = None
        else:
            # Cog method: first_arg is self, second arg (args[0]) is the interaction
            cog_self = first_arg
            interaction = args[0]
            args = args[1:]  # Remove interaction from args since we extracted it
        
        try:
            # Try to defer and show animation
            try:
                await interaction.response.defer(thinking=True)
                await _thinking_animation.show_thinking(interaction)
                animation_shown = True
            except discord.errors.NotFound as e:
                # Interaction expired (404 error code 10062: Unknown interaction)
                # This happens when the interaction token expired before we could defer
                # Skip animation and run command normally
                print(f"⚠️ Interaction expired before defer: {e}")
                animation_shown = False
            
            # Run the actual command
            if cog_self is not None:
                # Call as cog method: func(self, interaction, *args, **kwargs)
                result = await func(cog_self, interaction, *args, **kwargs)
            else:
                # Call as standalone: func(interaction, *args, **kwargs)
                result = await func(interaction, *args, **kwargs)
            
            # Stop animation if it was shown
            if animation_shown:
                await _thinking_animation.stop_thinking(interaction, delete_message=True)
            
            return result
        except Exception as e:
            try:
                await _thinking_animation.stop_thinking(interaction, delete_message=True)
            except:
                pass
            raise
    
    return wrapper
