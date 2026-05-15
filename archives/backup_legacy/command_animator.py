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


def command_animation(func):
    """
    Decorator to add animation to any command function.
    """
    @functools.wraps(func)
    async def wrapper(first_arg, *args: Any, **kwargs: Any) -> Any:
        # Detect if this is a cog method (first_arg is self) or standalone command (first_arg is interaction)
        # Note: in py-cord slash commands, first_arg might be ApplicationContext
        interaction = None
        if hasattr(discord, 'ApplicationContext') and isinstance(first_arg, discord.ApplicationContext):
            interaction = first_arg
            actual_args = args
        elif isinstance(first_arg, discord.Interaction):
            interaction = first_arg
            actual_args = args
        elif len(args) > 0:
            if hasattr(discord, 'ApplicationContext') and isinstance(args[0], discord.ApplicationContext):
                interaction = args[0]
                actual_args = args[1:]
            elif isinstance(args[0], discord.Interaction):
                interaction = args[0]
                actual_args = args[1:]
        
        if not interaction:
             # Fallback: just call the function
             return await func(first_arg, *args, **kwargs)
        
        try:
            # Try to defer and show animation
            try:
                # py-cord ApplicationContext has .interaction and .response
                if hasattr(interaction, 'response'):
                    if not interaction.response.is_done():
                        # Determine if ephemeral based on context if possible, otherwise default to False
                        # Or just defer without arguments which shows "thinking..."
                        await interaction.response.defer()
                
                # Show thinking animation
                await _thinking_animation.show_thinking(interaction)
                animation_shown = True
            except Exception as e:
                print(f"Animation error: {e}")
                animation_shown = False
            
            # Run original function
            if interaction == first_arg:
                # Standalone
                result = await func(interaction, *actual_args, **kwargs)
            else:
                # Cog method
                result = await func(first_arg, interaction, *actual_args, **kwargs)
            
            # Stop animation
            if animation_shown:
                try:
                    await _thinking_animation.stop_thinking(interaction, delete_message=True)
                except:
                    pass
                    
            return result
            
        except Exception as e:
            try:
                await _thinking_animation.stop_thinking(interaction, delete_message=True)
            except:
                pass
            raise
    
    return wrapper

# Global instance
animator = CommandAnimator()

__all__ = ['animator', 'CommandAnimator', 'command_animation']
