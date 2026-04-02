import discord
from discord.ext import commands

class SupportOperations(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def show_support_menu(self, interaction: discord.Interaction):
        support_menu_embed = discord.Embed(
            title="🎯 Support Operations",
            description=(
                "Please select an operation:\n\n"
                "**Available Operations**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "📝 **Request Support**\n"
                "└ Get help and support\n\n"
                "ℹ️ **About Project**\n"
                "└ Project information\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.blue()
        )

        view = SupportView(self, user_id=interaction.user.id)
        
        try:
            await interaction.response.edit_message(embed=support_menu_embed, view=view)
        except discord.errors.InteractionResponded:
            await interaction.message.edit(embed=support_menu_embed, view=view)

    async def show_support_info(self, interaction: discord.Interaction):
        support_embed = discord.Embed(
            title="🤖 Bot Support Information",
            description=(
                "If you need help with the bot or are experiencing any issues, "
                "please feel free to ask on our [Discord](https://discord.com/users/850786361572720661)\n\n"
                "**Additional resources:**\n"
                "**GitHub Repository:** [Whiteout Project](https://github.com/Magnus-zzz/Whiteout-Survival--Discord-bot)\n"
                "**Issues & Bug Reports:** [GitHub Issues](https://github.com/Magnus-zzz/Whiteout-Survival--Discord-bot/issues)\n\n"
            
                "You can report bugs, request features, or contribute to the project "
                "through our Discord or GitHub repository.\n\n"
                "For technical support, please make sure to provide "
                "detailed information about your problem."
                     
                "--BY MAGNUS" 
            ),
            color=discord.Color.blue()
        )
        
        try:
            await interaction.response.send_message(embed=support_embed, ephemeral=True)
            try:
                await interaction.user.send(embed=support_embed)
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Could not send DM because your DMs are closed!",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error sending support info: {e}")

class SupportView(discord.ui.View):
    def __init__(self, cog, user_id=None):
        super().__init__()
        self.cog = cog
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.user_id and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This menu is not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(
        label="Request Support",
        emoji="📝",
        style=discord.ButtonStyle.primary,
        custom_id="request_support"
    )
    async def support_request_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_support_info(interaction)

    @discord.ui.button(
        label="About Project",
        emoji="ℹ️",
        style=discord.ButtonStyle.primary,
        custom_id="about_project"
    )
    async def about_project_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        about_embed = discord.Embed(
            title="ℹ️ About Whiteout Project",
            description=(
                "**Open Source Bot**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "This is an open source Discord bot for Whiteout Survival.\n"
                "**Repository:** [GitHub](https://github.com/Magnus-zzz/Whiteout-Survival--Discord-bot)\n"
                
                "**Features**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "• Alliance member management\n"
                "• Gift code operations\n"
                "• Automated member tracking\n"
                "• Bear trap notifications\n"
                "• ID channel verification\n"
                "• and more...\n\n"
                "**Contributing**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "Contributions are welcome! Please check our GitHub repository "
                "to report issues, suggest features, or submit pull requests."
            ),
            color=discord.Color.green()
        )

        about_embed.set_footer(text="Whiteout Survival | Magnus", icon_url="https://cdn.discordapp.com/attachments/1435569370389807144/1445459239131680859/images_7_1.png")
        
        try:
            await interaction.response.send_message(embed=about_embed, ephemeral=True)
            try:
                await interaction.user.send(embed=about_embed)
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Could not send DM because your DMs are closed!",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error sending project info: {e}")

    @discord.ui.button(
        label="Main Menu",
        emoji="🏠",
        style=discord.ButtonStyle.secondary,
        custom_id="main_menu"
    )
    async def main_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        alliance_cog = self.cog.bot.get_cog("Alliance")
        if alliance_cog:
            try:
                await interaction.message.edit(content=None, embed=None, view=None)
                await alliance_cog.show_main_menu(interaction)
            except discord.errors.InteractionResponded:
                await interaction.message.edit(content=None, embed=None, view=None)
                await alliance_cog.show_main_menu(interaction)

async def setup(bot):
    await bot.add_cog(SupportOperations(bot))