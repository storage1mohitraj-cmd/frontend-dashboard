"""
Registration Admin Cog — Global Admin Commands for Server Registration Approval
Provides /reg-approve, /reg-deny, /reg-pending slash commands for the bot owner.
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import os

logger = logging.getLogger(__name__)

BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))


async def _is_global_admin(interaction: discord.Interaction) -> bool:
    """Check if the interaction user is the global admin (bot owner)."""
    return interaction.user.id == BOT_OWNER_ID


class ApproveView(discord.ui.View):
    """Interactive approve/deny buttons sent in admin DMs."""
    def __init__(self, guild_id: str, guild_name: str, alliance_name: str,
                 submitter_id: str, submitter_name: str, access_code: str):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.alliance_name = alliance_name
        self.submitter_id = submitter_id
        self.submitter_name = submitter_name
        self.access_code = access_code

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success,
                       custom_id="reg_approve_btn")
    async def approve_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the global admin can do this.", ephemeral=True)
            return
        await interaction.response.defer()
        await _do_approve(interaction, self.guild_id, self.guild_name,
                          self.alliance_name, self.submitter_id, self.submitter_name)
        # Disable buttons
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger,
                       custom_id="reg_deny_btn")
    async def deny_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the global admin can do this.", ephemeral=True)
            return
        await interaction.response.defer()
        await _do_deny(interaction, self.guild_id, self.guild_name,
                       self.submitter_id, self.submitter_name)
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)


async def _do_approve(interaction, guild_id: str, guild_name: str,
                      alliance_name: str, submitter_id: str, submitter_name: str):
    try:
        from db.mongo_adapters import PendingConfigAdapter, mongo_enabled
        if not mongo_enabled():
            await interaction.followup.send("❌ Database not available.", ephemeral=True)
            return
        ok = await PendingConfigAdapter.approve_async(int(guild_id), interaction.user.id)
        if ok:
            # Notify submitter
            try:
                user = await interaction.client.fetch_user(int(submitter_id))
                await user.send(
                    f"✅ **Your registration has been approved!**\n\n"
                    f"**Server:** {guild_name}\n"
                    f"**Alliance:** `{alliance_name}`\n\n"
                    f"Your access code is now active. Visit the dashboard and use "
                    f"`/manage` or click **Alliance Monitor / Gift Codes** — then enter "
                    f"the code you set during registration."
                )
            except Exception as dm_err:
                logger.warning(f"Could not DM submitter {submitter_id}: {dm_err}")
            await interaction.followup.send(
                f"✅ **Approved!** Registration for **{guild_name}** is now active.\n"
                f"Alliance `{alliance_name}` has been configured.",
                ephemeral=False
            )
        else:
            await interaction.followup.send(
                f"⚠️ Could not find a pending request for guild `{guild_id}`. "
                f"It may have already been processed.", ephemeral=True
            )
    except Exception as e:
        logger.error(f"Error approving registration for guild {guild_id}: {e}")
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


async def _do_deny(interaction, guild_id: str, guild_name: str,
                   submitter_id: str, submitter_name: str):
    try:
        from db.mongo_adapters import PendingConfigAdapter, mongo_enabled
        if not mongo_enabled():
            await interaction.followup.send("❌ Database not available.", ephemeral=True)
            return
        ok = await PendingConfigAdapter.deny_async(int(guild_id), interaction.user.id)
        if ok:
            # Notify submitter
            try:
                user = await interaction.client.fetch_user(int(submitter_id))
                await user.send(
                    f"❌ **Your registration request was denied.**\n\n"
                    f"**Server:** {guild_name}\n\n"
                    f"Please contact the bot administrator for more details.\n"
                    f"You may submit a new registration request when ready."
                )
            except Exception as dm_err:
                logger.warning(f"Could not DM submitter {submitter_id}: {dm_err}")
            await interaction.followup.send(
                f"❌ **Denied.** Registration for **{guild_name}** has been rejected.",
                ephemeral=False
            )
        else:
            await interaction.followup.send(
                f"⚠️ Could not find a pending request for guild `{guild_id}`.", ephemeral=True
            )
    except Exception as e:
        logger.error(f"Error denying registration for guild {guild_id}: {e}")
        await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


class RegistrationAdmin(commands.Cog):
    """Slash commands for the global admin to approve or deny server registrations."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /reg-pending ──────────────────────────────────────────────────────────
    @app_commands.command(
        name="reg-pending",
        description="[Admin] View all pending server registration requests"
    )
    async def reg_pending(self, interaction: discord.Interaction):
        if not await _is_global_admin(interaction):
            await interaction.response.send_message(
                "❌ This command is restricted to the global administrator.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from db.mongo_adapters import PendingConfigAdapter, mongo_enabled
            if not mongo_enabled():
                await interaction.followup.send("❌ Database not available.", ephemeral=True)
                return

            docs = await PendingConfigAdapter.get_all_pending_async()
            if not docs:
                await interaction.followup.send(
                    "✅ No pending registration requests.", ephemeral=True
                )
                return

            embed = discord.Embed(
                title="📋 Pending Server Registrations",
                description=f"**{len(docs)}** request(s) awaiting review.",
                color=0xf59e0b
            )
            for doc in docs[:10]:  # Show up to 10
                embed.add_field(
                    name=f"🏰 {doc.get('guild_name', 'Unknown Server')}",
                    value=(
                        f"**Guild ID:** `{doc.get('guild_id')}`\n"
                        f"**Alliance:** `{doc.get('alliance_name')}`\n"
                        f"**By:** {doc.get('discord_username')} (`{doc.get('discord_user_id')}`)\n"
                        f"**Submitted:** {doc.get('submitted_at', 'N/A')[:10]}\n"
                        f"Use `/reg-approve {doc.get('guild_id')}` or `/reg-deny {doc.get('guild_id')}`"
                    ),
                    inline=False
                )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error fetching pending registrations: {e}")
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    # ── /reg-approve ──────────────────────────────────────────────────────────
    @app_commands.command(
        name="reg-approve",
        description="[Admin] Approve a pending server registration request"
    )
    @app_commands.describe(guild_id="The Discord server (guild) ID to approve")
    async def reg_approve(self, interaction: discord.Interaction, guild_id: str):
        if not await _is_global_admin(interaction):
            await interaction.response.send_message(
                "❌ This command is restricted to the global administrator.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from db.mongo_adapters import PendingConfigAdapter, mongo_enabled
            if not mongo_enabled():
                await interaction.followup.send("❌ Database not available.", ephemeral=True)
                return

            doc = await PendingConfigAdapter.get_by_guild_async(int(guild_id))
            if not doc or doc.get("status") != "pending":
                await interaction.followup.send(
                    f"⚠️ No pending registration found for guild `{guild_id}`.", ephemeral=True
                )
                return

            await _do_approve(
                interaction, guild_id,
                doc.get("guild_name", guild_id),
                doc.get("alliance_name", ""),
                doc.get("discord_user_id", "0"),
                doc.get("discord_username", "Unknown")
            )
        except Exception as e:
            logger.error(f"Error in reg-approve: {e}")
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    # ── /reg-deny ─────────────────────────────────────────────────────────────
    @app_commands.command(
        name="reg-deny",
        description="[Admin] Deny a pending server registration request"
    )
    @app_commands.describe(guild_id="The Discord server (guild) ID to deny")
    async def reg_deny(self, interaction: discord.Interaction, guild_id: str):
        if not await _is_global_admin(interaction):
            await interaction.response.send_message(
                "❌ This command is restricted to the global administrator.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from db.mongo_adapters import PendingConfigAdapter, mongo_enabled
            if not mongo_enabled():
                await interaction.followup.send("❌ Database not available.", ephemeral=True)
                return

            doc = await PendingConfigAdapter.get_by_guild_async(int(guild_id))
            if not doc or doc.get("status") != "pending":
                await interaction.followup.send(
                    f"⚠️ No pending registration found for guild `{guild_id}`.", ephemeral=True
                )
                return

            await _do_deny(
                interaction, guild_id,
                doc.get("guild_name", guild_id),
                doc.get("discord_user_id", "0"),
                doc.get("discord_username", "Unknown")
            )
        except Exception as e:
            logger.error(f"Error in reg-deny: {e}")
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationAdmin(bot))
    logger.info("✅ RegistrationAdmin cog loaded")
