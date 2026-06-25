import io

import discord
from settings.models import settings

from .models import BattleBall, BattleInstance, GuildBattle, battles, fetch_battle_by_interaction


def close_battle(guild_battle: GuildBattle):
    if guild_battle in battles:
        battles.remove(guild_battle)
    guild_battle.battle_message = None


def clone_battle_instance(battle: BattleInstance) -> BattleInstance:
    def clone_ball(ball: BattleBall) -> BattleBall:
        return BattleBall(
            name=ball.name,
            owner=ball.owner,
            health=ball.health,
            attack=ball.attack,
            health_bonus=ball.health_bonus,
            attack_bonus=ball.attack_bonus,
            emoji=ball.emoji,
            instance_id=ball.instance_id,
            special_emoji=ball.special_emoji,
            favorite=ball.favorite,
            dead=ball.dead,
        )

    return BattleInstance(
        p1_balls=[clone_ball(ball) for ball in battle.p1_balls],
        p2_balls=[clone_ball(ball) for ball in battle.p2_balls],
        winner=battle.winner,
        turns=battle.turns,
    )


class ReadyView(discord.ui.View):
    def __init__(self, guild_battle: GuildBattle):
        super().__init__(timeout=None)
        self.guild_battle = guild_battle

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user not in (self.guild_battle.author, self.guild_battle.opponent):
            await interaction.response.send_message("You cannot interact with this battle!", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.success, emoji="✔️", label="")
    async def execute_battle(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .cog import gen_battle, gen_deck, get_battle_embed, prune_unowned_balls

        if self.guild_battle not in battles:
            await interaction.response.send_message("This battle has already concluded or been cancelled.", ephemeral=True)
            return

        if await prune_unowned_balls(self.guild_battle):
            self.guild_battle.author_ready = False
            self.guild_battle.opponent_ready = False
            self.guild_battle.author_confirmed = False
            self.guild_battle.opponent_confirmed = False
            setup_view = BattleSetupView(
                self.guild_battle.interaction,
                self.guild_battle.author,
                self.guild_battle.opponent,
            )
            await interaction.message.edit(
                embed=await get_battle_embed(self.guild_battle),
                view=setup_view,
            )
            await interaction.response.send_message(
                f"One or more {settings.plural_collectible_name} are no longer owned by their player and were removed.",
                ephemeral=True,
            )
            return

        if (interaction.user == self.guild_battle.author and self.guild_battle.author_confirmed) or (
            interaction.user == self.guild_battle.opponent and self.guild_battle.opponent_confirmed
        ):
            await interaction.response.send_message("You have already confirmed! Waiting for the other player.", ephemeral=True)
            return

        author_confirmed = self.guild_battle.author_confirmed or interaction.user == self.guild_battle.author
        opponent_confirmed = self.guild_battle.opponent_confirmed or interaction.user == self.guild_battle.opponent

        if not (author_confirmed and opponent_confirmed):
            previous_author_confirmed = self.guild_battle.author_confirmed
            previous_opponent_confirmed = self.guild_battle.opponent_confirmed
            await interaction.response.defer()
            try:
                self.guild_battle.author_confirmed = author_confirmed
                self.guild_battle.opponent_confirmed = opponent_confirmed
                await interaction.message.edit(embed=await get_battle_embed(self.guild_battle))
            except discord.HTTPException:
                self.guild_battle.author_confirmed = previous_author_confirmed
                self.guild_battle.opponent_confirmed = previous_opponent_confirmed
            return

        simulated_battle = clone_battle_instance(self.guild_battle.battle)
        log_filename = gen_battle(simulated_battle) 
        
        battle_plan_embed = discord.Embed(
            title=f"{settings.plural_collectible_name.title()} Battle Plan",
            description="Battle Plan concluded!",
            color=discord.Color(0x2ecc70),
        )
        battle_plan_embed.add_field(
            name=f"✅ {self.guild_battle.author.name}",
            value=gen_deck(self.guild_battle.battle.p1_balls),
            inline=True,
        )
        battle_plan_embed.add_field(
            name=f"✅ {self.guild_battle.opponent.name}",
            value=gen_deck(self.guild_battle.battle.p2_balls),
            inline=True,
        )
        battle_plan_embed.set_footer(text="This message is updated every 15 seconds, but you can keep on editing your battle proposal.")

        battle_logs_embed = discord.Embed(
            title=f"Battle between {self.guild_battle.author.name} and {self.guild_battle.opponent.name}",
            description=(
                f"Battle settings:\n\n"
                f"Duplicates: {'Allowed' if self.guild_battle.allow_duplicates else 'Not allowed'}\n"
                f"Buffs: {'Allowed' if self.guild_battle.allow_buffs else 'Not allowed'}\n"
                f"Amount: {self.guild_battle.amount_required}"
            ),
            color=discord.Color.blurple(),
        )
        battle_logs_embed.add_field(
            name=f"**{self.guild_battle.author.name}'s deck:**",
            value=gen_deck(simulated_battle.p1_balls),
            inline=True,
        )
        battle_logs_embed.add_field(
            name=f"**{self.guild_battle.opponent.name}'s deck:**",
            value=gen_deck(simulated_battle.p2_balls),
            inline=True,
        )
        battle_logs_embed.add_field(
            name="**Winner:**",
            value="check log",
            inline=False,
        )
        battle_logs_embed.set_footer(text="Battle log is attached.")

        await interaction.response.defer()

        concluded_view = ReadyView(self.guild_battle)
        for item in concluded_view.children:
            item.disabled = True

        try:
            await interaction.message.edit(
                content=f"{self.guild_battle.author.mention} vs {self.guild_battle.opponent.mention}",
                embed=battle_plan_embed,
                view=concluded_view,
            )
        except discord.HTTPException:
            await interaction.followup.send(
                "Could not update the battle message. Please try confirming again.",
                ephemeral=True,
            )
            return

        self.guild_battle.author_confirmed = author_confirmed
        self.guild_battle.opponent_confirmed = opponent_confirmed

        try:
            await interaction.channel.send(
                embed=battle_logs_embed,
                file=discord.File(log_filename, filename="battle-log.txt"),
            )
        except discord.HTTPException:
            await interaction.followup.send(
                "Battle concluded, but I could not send the battle log.",
                ephemeral=True,
            )

        close_battle(self.guild_battle)

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="✖️", label="")
    async def cancel_battle(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .cog import gen_deck

        if interaction.user == self.guild_battle.author:
            author_name = f"🚫 {self.guild_battle.author.name}"
            opponent_name = self.guild_battle.opponent.name
        else:
            author_name = self.guild_battle.author.name
            opponent_name = f"🚫 {self.guild_battle.opponent.name}"

        embed = discord.Embed(
            title=f"{settings.plural_collectible_name.title()} Battle Plan",
            description="**The battle has been cancelled.**",
            color=discord.Color(0xe74d3c),
        )
        embed.add_field(
            name=author_name,
            value=gen_deck(self.guild_battle.battle.p1_balls, strikethrough=bool(self.guild_battle.battle.p1_balls)),
            inline=True,
        )
        embed.add_field(
            name=opponent_name,
            value=gen_deck(self.guild_battle.battle.p2_balls, strikethrough=bool(self.guild_battle.battle.p2_balls)),
            inline=True,
        )
        embed.set_footer(text="This message is updated every 15 seconds, but you can keep on editing your battle proposal.")

        if interaction.message:
            cancel_view = BattleSetupView(self.guild_battle.interaction, self.guild_battle.author, self.guild_battle.opponent)
            for item in cancel_view.children:
                item.disabled = True
            try:
                await interaction.message.edit(
                    content="",
                    embed=embed,
                    view=cancel_view,
                )
            except discord.NotFound:
                pass
            except discord.HTTPException:
                await interaction.response.send_message(
                    "Could not update the battle message. Please try cancelling again.",
                    ephemeral=True,
                )
                return

        close_battle(self.guild_battle)

        try:
            await interaction.response.send_message(
                "Battle has been cancelled.",
                ephemeral=True,
            )
        except discord.errors.InteractionResponded:
            pass

class BattleSetupView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, author: discord.Member, opponent: discord.Member):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.author = author
        self.opponent = opponent

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user not in (self.author, self.opponent):
            await interaction.response.send_message("You cannot interact with this battle!", ephemeral=True)
            return False
        return True

    @discord.ui.button(style=discord.ButtonStyle.primary, emoji="🔒", label="Lock proposal")
    async def ready_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .cog import get_battle_embed, prune_unowned_balls

        guild_battle = fetch_battle_by_interaction(self.interaction)

        if guild_battle is None:
            await interaction.response.send_message("Battle not found!", ephemeral=True)
            return

        if await prune_unowned_balls(guild_battle):
            guild_battle.author_ready = False
            guild_battle.opponent_ready = False
            if guild_battle.battle_message:
                await guild_battle.battle_message.edit(embed=await get_battle_embed(guild_battle))

        if not guild_battle.has_required_amount(interaction.user):
            await interaction.response.send_message(
                f"You need to have exactly {guild_battle.amount_required} {settings.plural_collectible_name} in your proposal to lock it.",
                ephemeral=True,
            )
            return

        if guild_battle.is_user_ready(interaction.user):
            await interaction.response.send_message("You have already locked your proposal!", ephemeral=True)
            return

        author_ready = guild_battle.author_ready or interaction.user == guild_battle.author
        opponent_ready = guild_battle.opponent_ready or interaction.user == guild_battle.opponent

        if author_ready and opponent_ready:
            if not guild_battle.both_have_required_amount():
                await interaction.response.send_message(
                    f"Both users must add exactly {guild_battle.amount_required} {settings.plural_collectible_name}!",
                    ephemeral=True,
                )
                return

            previous_author_ready = guild_battle.author_ready
            previous_opponent_ready = guild_battle.opponent_ready
            await interaction.response.defer()
            try:
                guild_battle.author_ready = author_ready
                guild_battle.opponent_ready = opponent_ready
                new_view = ReadyView(guild_battle)
                embed = await get_battle_embed(guild_battle)
                await interaction.message.edit(
                    content=f"{guild_battle.author.mention} vs {guild_battle.opponent.mention}",
                    embed=embed,
                    view=new_view,
                )
            except discord.HTTPException:
                guild_battle.author_ready = previous_author_ready
                guild_battle.opponent_ready = previous_opponent_ready
        else:
            previous_author_ready = guild_battle.author_ready
            previous_opponent_ready = guild_battle.opponent_ready
            guild_battle.set_user_ready(interaction.user, True)
            try:
                if guild_battle.battle_message:
                    embed = await get_battle_embed(guild_battle)
                    await guild_battle.battle_message.edit(embed=embed)
            except discord.HTTPException:
                guild_battle.author_ready = previous_author_ready
                guild_battle.opponent_ready = previous_opponent_ready
                await interaction.response.defer()
                return

            await interaction.response.send_message(
                "Done! Waiting for the other player to press 'Ready'.",
                ephemeral=True,
            )

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="💨", label="Reset")
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .cog import get_battle_embed

        guild_battle = fetch_battle_by_interaction(self.interaction)

        if guild_battle is None:
            await interaction.response.send_message("Battle not found!", ephemeral=True)
            return

        if guild_battle.is_user_ready(interaction.user):
            await interaction.response.send_message(
                "You have locked your proposal, it cannot be edited! You can click the cancel button to stop the battle instead.",
                ephemeral=True,
            )
            return

        user_balls = guild_battle.get_user_balls(interaction.user)
        old_user_balls = user_balls.copy()
        user_balls.clear()

        if guild_battle.battle_message:
            embed = await get_battle_embed(guild_battle)
            try:
                await guild_battle.battle_message.edit(embed=embed)
            except discord.HTTPException:
                user_balls[:] = old_user_balls
                await interaction.response.defer()
                return

        await interaction.response.send_message(
            "Your countryballs have been reset!",
            ephemeral=True,
        )

    @discord.ui.button(style=discord.ButtonStyle.danger, emoji="✖️", label="Cancel battle")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .cog import gen_deck

        guild_battle = fetch_battle_by_interaction(self.interaction)

        if guild_battle is None:
            await interaction.response.send_message("Battle not found!", ephemeral=True)
            return

        if interaction.user == guild_battle.author:
            author_name = f"🚫 {guild_battle.author.name}"
            opponent_name = guild_battle.opponent.name
        else:
            author_name = guild_battle.author.name
            opponent_name = f"🚫 {guild_battle.opponent.name}"

        embed = discord.Embed(
            title=f"{settings.plural_collectible_name.title()} Battle Plan",
            description="**The battle has been cancelled.**",
            color=discord.Color(0xe74d3c),
        )
        embed.add_field(
            name=author_name,
            value=gen_deck(guild_battle.battle.p1_balls, strikethrough=bool(guild_battle.battle.p1_balls)),
            inline=True,
        )
        embed.add_field(
            name=opponent_name,
            value=gen_deck(guild_battle.battle.p2_balls, strikethrough=bool(guild_battle.battle.p2_balls)),
            inline=True,
        )
        embed.set_footer(text="This message is updated every 15 seconds, but you can keep on editing your battle proposal.")

        if interaction.message:
            cancel_view = BattleSetupView(guild_battle.interaction, guild_battle.author, guild_battle.opponent)
            for item in cancel_view.children:
                item.disabled = True
            try:
                await interaction.message.edit(
                    content="",
                    embed=embed,
                    view=cancel_view,
                )
            except discord.NotFound:
                pass
            except discord.HTTPException:
                await interaction.response.send_message(
                    "Could not update the battle message. Please try cancelling again.",
                    ephemeral=True,
                )
                return

        try:
            await interaction.response.send_message(
                "Battle has been cancelled.",
                ephemeral=True,
            )
        except discord.errors.InteractionResponded:
            pass

        close_battle(guild_battle)
