import logging
from typing import List, Optional, Dict, TYPE_CHECKING
from dataclasses import dataclass, field

import discord
from discord import app_commands
from discord.ext import commands

from bd_models.models import BallInstance
from ballsdex.core.utils.transformers import BallInstanceTransform
from ballsdex.settings import settings

from .battle_core import build_ctypes_player, run_fight_async

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("extra.cbattle.cbattle.extension")

@dataclass
class BattleSetup:
    interaction: discord.Interaction
    author: discord.Member
    opponent: discord.Member
    author_balls: List[BallInstance] = field(default_factory=list)
    opponent_balls: List[BallInstance] = field(default_factory=list)
    author_ready: bool = False
    opponent_ready: bool = False


class BattleCog(commands.GroupCog, name="battle"):
    """Battle system for countryballs"""

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        self.battle_setups: Dict[int, BattleSetup] = {}  

    def _get_battle_setup(self, interaction: discord.Interaction) -> Optional[BattleSetup]:
        """Get battle setup for this guild"""
        return self.battle_setups.get(interaction.guild_id)

    def _is_user_in_setup(self, user: discord.Member, setup: BattleSetup) -> bool:
        """Check if user is part of the battle setup"""
        return user in (setup.author, setup.opponent)

    def _create_setup_embed(self, setup: BattleSetup) -> discord.Embed:
        """Create embed for battle setup"""
        embed = discord.Embed(
            title="Battle Setup",
            description=(
                "Use `/battle add` and `/battle remove` to build your deck (max 3 balls). "
                "Click Ready when finished."
            ),
            color=discord.Color.blurple()
        )

        author_emoji = "✅" if setup.author_ready else ""
        author_deck = self._format_deck(setup.author_balls)
        embed.add_field(
            name=f"{author_emoji} {setup.author.display_name}'s Deck ({len(setup.author_balls)}/3)",
            value=author_deck,
            inline=True
        )

        opponent_emoji = "✅" if setup.opponent_ready else ""
        opponent_deck = self._format_deck(setup.opponent_balls)
        embed.add_field(
            name=f"{opponent_emoji} {setup.opponent.display_name}'s Deck ({len(setup.opponent_balls)}/3)",
            value=opponent_deck,
            inline=True
        )

        return embed

    def _format_deck(self, balls: List[BallInstance]) -> str:
        """Format ball list for embed"""
        if not balls:
            return "Empty deck"

        deck_lines = []
        for ball in balls:
            emoji = self.bot.get_emoji(ball.countryball.emoji_id) or "⚽"
            deck_lines.append(
                f"{emoji} **{ball.countryball.country}**\n"
                f"   HP: {ball.health} | ATK: {ball.attack}"
            )

        return "\n".join(deck_lines)

    @app_commands.command(name="begin")
    async def battle_begin(self, interaction: discord.Interaction, opponent: discord.Member):
        """
        Start setting up a battle with another player

        Parameters
        ----------
        opponent: discord.Member
            The player you want to battle
        """
        await interaction.response.defer()
        
        if opponent.bot:
            await interaction.followup.send("You can't battle bots!", ephemeral=True)
            return

        if opponent.id == interaction.user.id:
            await interaction.followup.send("You can't battle yourself!", ephemeral=True)
            return

        if interaction.guild_id in self.battle_setups:
            existing = self.battle_setups[interaction.guild_id]
            await interaction.followup.send(
                f"There's already a battle setup between {existing.author.mention} "
                f"and {existing.opponent.mention}!",
                ephemeral=True
            )
            return

        setup = BattleSetup(
            interaction=interaction,
            author=interaction.user,
            opponent=opponent
        )
        self.battle_setups[interaction.guild_id] = setup

        embed = self._create_setup_embed(setup)
        view = BattleSetupView(self, setup)

        await interaction.followup.send(
            f"{opponent.mention}, {interaction.user.mention} wants to battle you!",
            embed=embed,
            view=view
        )

    @app_commands.command(name="add")
    async def battle_add(self, interaction: discord.Interaction, ball: BallInstanceTransform):
        """
        Add a ball to your battle deck

        Parameters
        ----------
        ball: BallInstanceTransform
            The ball you want to add to your deck
        """
        await interaction.response.defer(ephemeral=True)
        
        setup = self._get_battle_setup(interaction)
        if not setup:
            await interaction.followup.send(
                "No battle setup found! Use `/battle begin` first.", ephemeral=True
            )
            return

        if not self._is_user_in_setup(interaction.user, setup):
            await interaction.followup.send("You're not part of this battle!", ephemeral=True)
            return

        if (interaction.user == setup.author and setup.author_ready) or \
           (interaction.user == setup.opponent and setup.opponent_ready):
            await interaction.followup.send(
                "You can't modify your deck after clicking Ready!", ephemeral=True
            )
            return

        user_balls = setup.author_balls if interaction.user == setup.author else setup.opponent_balls

        if len(user_balls) >= 3:
            await interaction.followup.send("Your deck is full! (Max 3 balls)", ephemeral=True)
            return

        if ball in user_balls:
            await interaction.followup.send("This ball is already in your deck!", ephemeral=True)
            return

        user_balls.append(ball)

        embed = self._create_setup_embed(setup)
        await setup.interaction.edit_original_response(embed=embed)

        await interaction.followup.send(
            f"Added **{ball.countryball.country}** to your deck!",
            ephemeral=True
        )

    @app_commands.command(name="remove")
    async def battle_remove(self, interaction: discord.Interaction, ball: BallInstanceTransform):
        """
        Remove a ball from your battle deck

        Parameters
        ----------
        ball: BallInstanceTransform
            The ball you want to remove from your deck
        """

        await interaction.response.defer(ephemeral=True)
        
        setup = self._get_battle_setup(interaction)
        if not setup:
            await interaction.followup.send("No battle setup found!", ephemeral=True)
            return

        if not self._is_user_in_setup(interaction.user, setup):
            await interaction.followup.send("You're not part of this battle!", ephemeral=True)
            return

        if (interaction.user == setup.author and setup.author_ready) or \
           (interaction.user == setup.opponent and setup.opponent_ready):
            await interaction.followup.send(
                "You can't modify your deck after clicking Ready!", ephemeral=True
            )
            return

        user_balls = setup.author_balls if interaction.user == setup.author else setup.opponent_balls

        if ball not in user_balls:
            await interaction.followup.send("This ball is not in your deck!", ephemeral=True)
            return

        user_balls.remove(ball)

        embed = self._create_setup_embed(setup)
        await setup.interaction.edit_original_response(embed=embed)

        await interaction.followup.send(
            f"Removed **{ball.countryball.country}** from your deck!",
            ephemeral=True
        )


class BattleSetupView(discord.ui.View):

    def __init__(self, cog: BattleCog, setup: BattleSetup):
        super().__init__(timeout=300)
        self.cog = cog
        self.setup = setup

    @discord.ui.button(label="Ready", style=discord.ButtonStyle.success, emoji="✅")
    async def ready_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark player as ready"""
        await interaction.response.defer(ephemeral=True)
        
        if not self.cog._is_user_in_setup(interaction.user, self.setup):
            await interaction.followup("You're not part of this battle!", ephemeral=True)
            return

        user_balls = (
            self.setup.author_balls if interaction.user == self.setup.author
            else self.setup.opponent_balls
        )
        if not user_balls:
            await interaction.followup.send("You need at least 1 ball in your deck!", ephemeral=True)
            return

        if interaction.user == self.setup.author:
            self.setup.author_ready = True
        else:
            self.setup.opponent_ready = True
        await interaction.followup.send("You Accepted", ephemeral=True)

        if self.setup.author_ready and self.setup.opponent_ready: 
            await self._start_battle(interaction)
        else:
            embed = self.cog._create_setup_embed(self.setup)
            await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel / reject battle setup"""
        await interaction.response.defer(ephemeral=True)
        
        if not self.cog._is_user_in_setup(interaction.user, self.setup):
            await interaction.followup.send("You're not part of this battle!", ephemeral=True)
            return

        self.cog.battle_setups.pop(interaction.guild_id, None)

        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            title="Battle Cancelled",
            description="The battle setup has been cancelled.",
            color=discord.Color.red()
        )

        await interaction.edit_original_response(embed=embed, view=self)

    async def _start_battle(self, interaction: discord.Interaction):
        """Build ctypes players, run the C fight function, show result text"""
        p1 = build_ctypes_player(self.setup.author_balls, self.setup.author.display_name)
        p2 = build_ctypes_player(self.setup.opponent_balls, self.setup.opponent.display_name)

        logi = await run_fight_async(p1, p2)
        
        self.cog.battle_setups.pop(interaction.guild_id, None)

        for item in self.children:
            item.disabled = True

        try:
            await interaction.edit_original_response(
                content="Fight Finished!",
                attachments=[discord.File(logi)],
                view=self,
            )
        finally:
            logi.unlink(missing_ok=True) # delete the file from your pc 

