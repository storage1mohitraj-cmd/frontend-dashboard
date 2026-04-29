import discord
from discord.ext import commands
import logging

try:
    from api_manager import make_request
except ImportError:
    make_request = None
    logging.warning("api_manager could not be imported. AI responses will be disabled.")

logger = logging.getLogger(__name__)

class AIChat(commands.Cog):
    """Cog for AI chat functionality on mentions, replies, and DMs."""
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Send a greeting when joining a new server."""
        # Find a suitable channel
        chat_channel = None
        
        # Priority 1: Substring match for common channel names
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                channel_name = channel.name.lower()
                if any(word in channel_name for word in ["chat", "general", "main", "welcome"]):
                    chat_channel = channel
                    break
                    
        # Priority 2: Use the system channel if we have permission
        if not chat_channel and guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            chat_channel = guild.system_channel
            
        # Priority 3: Fallback to the very first channel we have permission to type in
        if not chat_channel:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    chat_channel = channel
                    break
                    
        if chat_channel:
            try:
                embed = discord.Embed(
                    title="👋 Hello there!",
                    description=(
                        f"I'm **{self.bot.user.name}**, your friendly AI assistant!\n\n"
                        "💬 **How to talk to me:**\n"
                        "• Tag me in a message (e.g., `@Molly how do I...`)\n"
                        "• Reply to any of my messages\n"
                        "• Send me a Direct Message (DM)"
                    ),
                    color=discord.Color.blue()
                )
                await chat_channel.send(embed=embed)
                logger.info(f"[AIChat] Sent welcome message to {guild.name} in {chat_channel.name}")
            except Exception as e:
                logger.error(f"[AIChat] Failed to send welcome message to {guild.name}: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for mentions, replies, and DMs to interact with AI."""
        # Ignore bots (including ourselves)
        if message.author.bot:
            return
            
        # Determine if we should respond
        should_respond = False
        
        # 1. Is it a DM?
        if not message.guild:
            should_respond = True
            
        # 2. Did they mention the bot directly?
        elif self.bot.user in message.mentions:
            should_respond = True
            
        # 3. Did they reply to the bot?
        elif message.reference:
            # First try the cached message
            if message.reference.cached_message:
                if message.reference.cached_message.author == self.bot.user:
                    should_respond = True
            else:
                # If we don't have it cached, we need to fetch it to check author
                try:
                    channel = self.bot.get_channel(message.reference.channel_id)
                    if channel:
                        replied_message = await channel.fetch_message(message.reference.message_id)
                        if replied_message.author == self.bot.user:
                            should_respond = True
                except (discord.NotFound, discord.HTTPException):
                    pass

        if should_respond and make_request:
            # Strip bot mention from the prompt if it's there
            content = message.content
            if self.bot.user in message.mentions:
                # Remove the <@ID> or <@!ID> tag from the message
                content = content.replace(f'<@{self.bot.user.id}>', '').replace(f'<@!{self.bot.user.id}>', '').strip()

            if not content:
                # If they just tagged the bot with no text, send a greeting
                content = "Hello! How can I help you?"

            try:
                # Indicate typing
                async with message.channel.typing():
                    # Build history
                    messages_list = [
                        {"role": "system", "content": f"You are a helpful and friendly Discord bot named {self.bot.user.name}. Be conversational and concise."}
                    ]

                    # If it's a reply, add the bot's previous message for context
                    if message.reference:
                        try:
                            replied_msg = message.reference.cached_message
                            if not replied_msg:
                                channel = self.bot.get_channel(message.reference.channel_id)
                                if channel:
                                    replied_msg = await channel.fetch_message(message.reference.message_id)
                                
                            if replied_msg and replied_msg.content:
                                messages_list.append({"role": "assistant", "content": replied_msg.content})
                        except Exception as e:
                            logger.debug(f"[AIChat] Failed to fetch replied message for context: {e}")

                    messages_list.append({"role": "user", "content": content})

                    response = await make_request(messages=messages_list)

                    if response and response.strip():
                        # Discord messages max length is 2000 chars
                        if len(response) > 2000:
                            response = response[:1996] + "..."
                        
                        await message.reply(response, mention_author=False)
                    else:
                        await message.reply("I'm sorry, I couldn't formulate a response right now.", mention_author=False)

            except Exception as e:
                logger.error(f"[AIChat] Error generating response: {e}", exc_info=True)
                await message.reply("I encountered an error trying to process your request. Please try again later.", mention_author=False)

async def setup(bot):
    await bot.add_cog(AIChat(bot))
