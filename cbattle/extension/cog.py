import logging
import random
import time
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

import asyncio

from bd_models.models import BallInstance, Player
from settings.models import settings

from ballsdex.core.utils.transformers import (
    BallInstanceTransform,
    SpecialEnabledTransform,
)

from .models import BattleBall, BattleInstance, GuildBattle, battles, fetch_battle
from .views import BattleSetupView, ReadyView
from .battle_core import build_ctypes_player, lib

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.battle")

# Configuration constants
SPECIAL_BUFFS = {
    "✨": (2000, 2000), # Shiny buffs
    "🔮": (5000, 5000), # Mythical buffs
} # Special buffs
# HP, ATK
MAXSTATS = [15000, 15000] # Max stats a card is limited to (before buffs)
# HP, ATK
BATTLE_TIMEOUT = "15m" # How long until a battle plan times out
# TIME

def parse_duration(duration: str) -> int:
    units = {
        "s": 1,
        "m": 60,
        "h": 3600,
    }
    duration = duration.strip().lower()
    unit = duration[-1]
    if unit not in units:
        raise ValueError("Duration must end with s, m, or h.")
    return int(duration[:-1]) * units[unit]


def format_duration(duration: str) -> str:
    units = {
        "s": ("second", "seconds"),
        "m": ("minute", "minutes"),
        "h": ("hour", "hours"),
    }
    duration = duration.strip().lower()
    unit = duration[-1]
    amount = int(duration[:-1])
    singular, plural = units[unit]
    return f"{amount} {singular if amount == 1 else plural}"


BATTLE_TIMEOUT_SECONDS = parse_duration(BATTLE_TIMEOUT)
BATTLE_TIMEOUT_TEXT = format_duration(BATTLE_TIMEOUT)

def get_damage(ball):
    return int(ball.attack * random.uniform(0.8, 1.2))


def attack(current_ball, enemy):
    attack_dealt = get_damage(current_ball)
    enemy.health -= attack_dealt

    if enemy.health <= 0:
        enemy.health = 0
        enemy.dead = True
    return attack_dealt


def get_active_ball(balls):
    return next((ball for ball in balls if not ball.dead), None)


def ball_description(countryball, bot) -> str:
    if not hasattr(countryball, "description"):
        return ""
    return countryball.description(short=True, include_emoji=True, bot=bot)


def get_special_buffs(countryball, bot) -> tuple[int, int]:
    if not getattr(countryball, "special_id", None):
        return 0, 0

    description = ball_description(countryball, bot)
    return next(
        (buffs for emoji, buffs in SPECIAL_BUFFS.items() if emoji in description),
        (0, 0),
    )


def get_special_emoji(countryball) -> str:
    special = countryball.specialcard
    return str(getattr(special, "emoji", "") or "")


def get_ball_instance_id(countryball) -> str:
    value = getattr(countryball, "pk", None) or getattr(countryball, "id", "")
    return f"{int(value):0X}" if value else ""


def format_ball_name(ball: BattleBall) -> str:
    parts = [str(ball.emoji)]
    if ball.favorite:
        parts.append(settings.favorited_collectible_emoji)
    if ball.special_emoji:
        parts.append(str(ball.special_emoji))
    if ball.instance_id:
        parts.append(f"#{ball.instance_id}")
    parts.append(ball.name)
    return " ".join(part for part in parts if part)


async def prune_unowned_balls(guild_battle: GuildBattle) -> bool:
    async def prune_player_balls(balls: list[BattleBall], user: discord.Member) -> bool:
        valid_balls = []

        for ball in balls:
            if not ball.instance_id:
                continue

            try:
                ball_pk = int(ball.instance_id, 16)
            except ValueError:
                continue

            if await BallInstance.objects.filter(
                pk=ball_pk,
                player__discord_id=user.id,
                deleted=False,
            ).aexists():
                valid_balls.append(ball)

        if len(valid_balls) == len(balls):
            return False

        balls[:] = valid_balls
        return True

    author_pruned = await prune_player_balls(guild_battle.battle.p1_balls, guild_battle.author)
    opponent_pruned = await prune_player_balls(guild_battle.battle.p2_balls, guild_battle.opponent)
    return author_pruned or opponent_pruned


import ctypes

def gen_battle(battle: BattleInstance) -> str: 
    hi = "hello"
    hi2 = "welcome"
    user1 = build_ctypes_player(battle.p1_balls, hi)
    user2 = build_ctypes_player(battle.p2_balls,  hi2)

    log_filename = f"battle_{id(battle)}.txt"

    result = lib.Fight(
        ctypes.byref(user1),
        ctypes.byref(user2),
        log_filename.encode()
    )

    return log_filename 

        
def gen_deck(balls, strikethrough=False) -> str:
    """Generates a text representation of a player's deck."""
    if not balls:
        return "*Empty*"

    if strikethrough:
        deck = "\n".join(
            [
                f"- ~~{format_ball_name(ball)} ATK:{ball.attack_bonus:+}% HP:{ball.health_bonus:+}%~~"
                for ball in balls
            ]
        )
    else:
        deck = "\n".join(
            [
                f"- {format_ball_name(ball)} ATK:{ball.attack_bonus:+}% HP:{ball.health_bonus:+}%"
                for ball in balls
            ]
        )

    if len(deck) > 1024:
        return deck[0:951] + f'\n<truncated due to discord limits, rest of your {settings.plural_collectible_name} are still here>'
    return deck

async def get_battle_embed(guild_battle: "GuildBattle") -> discord.Embed:
    """Creates the appropriate embed for the current battle state."""
    bot = guild_battle.interaction.client
    add_mention = "`/battle add`"
    remove_mention = "`/battle remove`"

    try:
        for cmd in await bot.tree.fetch_commands():
            if cmd.name == "battle":
                for sub in cmd.options:
                    if sub.name == "add":
                        add_mention = f"</{cmd.name} {sub.name}:{cmd.id}>"
                    elif sub.name == "remove":
                        remove_mention = f"</{cmd.name} {sub.name}:{cmd.id}>"
                break
    except Exception as e:
        log.error(f"Failed to fetch command mentions: {e}")

    if guild_battle.author_confirmed or guild_battle.opponent_confirmed:
        embed = discord.Embed(
            title=f"{settings.plural_collectible_name.title()} Battle Plan",
            description="Both users have locked their propositions! Now confirm to begin the battle.",
            color=discord.Color(0xfee65c),
        )
        author_emoji = "✅" if guild_battle.author_confirmed else "🔒"
        opponent_emoji = "✅" if guild_battle.opponent_confirmed else "🔒"

        embed.add_field(
            name=f"{author_emoji} {guild_battle.author.name}",
            value=gen_deck(guild_battle.battle.p1_balls),
            inline=True,
        )
        embed.add_field(
            name=f"{opponent_emoji} {guild_battle.opponent.name}",
            value=gen_deck(guild_battle.battle.p2_balls),
            inline=True,
        )
    elif guild_battle.author_ready and guild_battle.opponent_ready:
        embed = discord.Embed(
            title=f"{settings.plural_collectible_name.title()} Battle Plan",
            description="Both users have locked their propositions! Now confirm to begin the battle.",
            color=discord.Color(0xfee65c),
        )
        embed.add_field(
            name=f"🔒 {guild_battle.author.name}",
            value=gen_deck(guild_battle.battle.p1_balls),
            inline=True,
        )
        embed.add_field(
            name=f"🔒 {guild_battle.opponent.name}",
            value=gen_deck(guild_battle.battle.p2_balls),
            inline=True,
        )
    else:
        embed = discord.Embed(
            title=f"{settings.plural_collectible_name.title()} Battle Plan",
            description=(
                f"Add or remove {settings.plural_collectible_name} you want to propose to the other player using the "
                f"{add_mention} and {remove_mention} commands.\n"
                "Once you're finished, click the lock button to confirm your proposal.\n"
                f"*You have {BATTLE_TIMEOUT_TEXT} before this interaction ends.*\n"
                f"**Settings**:\n"
                f"- Duplicates: {'Allowed' if guild_battle.allow_duplicates else 'Not allowed'}\n"
                f"- Buffs: {'Allowed' if guild_battle.allow_buffs else 'Not allowed'}\n"
                f"- Amount: {guild_battle.amount_required}"
            ),
            color=discord.Color.blurple(),
        )
        author_emoji = "🔒" if guild_battle.author_ready else ""
        opponent_emoji = "🔒" if guild_battle.opponent_ready else ""

        embed.add_field(
            name=f"{author_emoji} {guild_battle.author.name}",
            value=gen_deck(guild_battle.battle.p1_balls),
            inline=True,
        )
        embed.add_field(
            name=f"{opponent_emoji} {guild_battle.opponent.name}",
            value=gen_deck(guild_battle.battle.p2_balls),
            inline=True,
        )

    embed.set_footer(text="This message is updated every 15 seconds, but you can keep on editing your battle proposal.")
    return embed



class Battle(commands.GroupCog):
    """
    Battle your countryballs!
    """

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot
        asyncio.create_task(self._battle_expiration_checker())


    async def _battle_expiration_checker(self):
        """Checks for expired battles every minute."""
        while True:
            try:
                await asyncio.sleep(60)
                current_time = time.time()
                expired_battles = []

                for battle in battles[:]:
                    if current_time - battle.created_at > BATTLE_TIMEOUT_SECONDS:
                        expired_battles.append(battle)

                for battle in expired_battles:
                    try:
                        if battle.battle_message:
                            embed = discord.Embed(
                                title=f"{settings.plural_collectible_name.title()} Battle Plan",
                                description="The battle timed out",
                                color=discord.Color(0x992e22),
                            )
                            embed.add_field(
                                name=f"{battle.author.name}'s deck:",
                                value=gen_deck(battle.battle.p1_balls, strikethrough=bool(battle.battle.p1_balls)),
                                inline=True,
                            )
                            embed.add_field(
                                name=f"{battle.opponent.name}'s deck:",
                                value=gen_deck(battle.battle.p2_balls, strikethrough=bool(battle.battle.p2_balls)),
                                inline=True,
                            )
                            embed.set_footer(text="This message is updated every 15 seconds, but you can keep on editing your battle proposal.")


                            if battle.author_ready and battle.opponent_ready:
                                timeout_view = ReadyView(battle)
                                for item in timeout_view.children:
                                    item.disabled = True
                            else:
                                timeout_view = BattleSetupView(battle.interaction, battle.author, battle.opponent)
                                for item in timeout_view.children:
                                    item.disabled = True


                            try:
                                await battle.battle_message.edit(
                                    embed=embed,
                                    view=timeout_view
                                )
                            except discord.NotFound:
                                pass
                            except discord.HTTPException:
                                log.error("Could not update expired battle message; will retry.")
                                continue

                        if battle in battles:
                            battles.remove(battle)
                        battle.battle_message = None

                    except Exception as e:
                        log.error(f"Error handling expired battle: {e}")
                        if battle in battles:
                            battles.remove(battle)
                        battle.battle_message = None

            except Exception as e:
                log.error(f"Battle expiration checker error: {e}")
                await asyncio.sleep(60)


    @app_commands.command()
    async def start(self, interaction: discord.Interaction, user: discord.Member, duplicates: bool = True, buffs: bool = True, amount: int = 3):
        """
        Begin a battle with the chosen user.

        Parameters
        ----------
        user: discord.Member
            The user you want to battle with
        duplicates: bool
            Whether or not you want to allow duplicates in your battle
        buffs: bool
            Whether or not you want to allow buffs in your battle
        amount: int
            The amount of countryballs needed for the battle. Minimum is 3, maximum is 10
        """ 
        await interaction.response.defer(ephemeral=True)
        
        if user.bot:
            await interaction.followup.send(
                "You can't battle against bots.", ephemeral=True,
            )
            return

        if user.id == interaction.user.id:
            await interaction.followup.send(
                "You can't battle against yourself.", ephemeral=True,
            )
            return

        player1, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
        player2, _ = await Player.objects.aget_or_create(discord_id=user.id)

        if await player1.is_blocked(player2):
            await interaction.followup.send(
                "You cannot begin a battle with a user that you have blocked.", ephemeral=True
            )
            return

        if await player2.is_blocked(player1):
            await interaction.followup.send(
                "You cannot begin a battle with a user that has blocked you.", ephemeral=True
            )
            return

        if player2.discord_id in self.bot.blacklist:
            await interaction.followup.send(
                "You cannot begin a battle with a blacklisted user.", ephemeral=True
            )
            return

        if amount < 3 or amount > 10:
            await interaction.followup.send(
                f"Amount must be between 3 and 10 {settings.plural_collectible_name}!", ephemeral=True,
            )
            return

        battle_self = fetch_battle(interaction.user, interaction.guild_id)
        battle_user = fetch_battle(user, interaction.guild_id)

        if battle_self and battle_self == battle_user:
            await interaction.followup.send(
                "You are already in a battle with this player", ephemeral=True,
            )
            return

        if battle_self:
            await interaction.followup.send(
                "You are already in a battle.", ephemeral=True,
            )
            return

        if battle_user:
            await interaction.followups.send(
                "This user is already in a battle.", ephemeral=True,
            )
            return

        guild_battle = GuildBattle(interaction, interaction.user, user, amount_required=amount, allow_duplicates=duplicates, allow_buffs=buffs)

        embed = await get_battle_embed(guild_battle)

        view = BattleSetupView(interaction, interaction.user, user)

        try:
            battle_message = await interaction.channel.send(
                f"Hey, {user.mention}, {interaction.user.name} is proposing a battle with you!",
                embed=embed,
                view=view,
            )
        except discord.HTTPException:
            try:
                await interaction.delete_original_response()
            except discord.HTTPException:
                pass
            return

        battles.append(guild_battle)
        guild_battle.battle_message = battle_message

        await interaction.edit_original_response(content="battle started!")

        asyncio.create_task(self._update_battle_message(guild_battle))

    async def _update_battle_message(self, guild_battle):
        """Updates the battle message every 15 seconds to keep it alive."""
        while guild_battle in battles and guild_battle.battle_message:
            try:
                await asyncio.sleep(15)
                if guild_battle in battles and guild_battle.battle_message:
                    embed = await get_battle_embed(guild_battle)
                    await guild_battle.battle_message.edit(embed=embed)
            except (discord.NotFound, discord.Forbidden):
                break
            except discord.HTTPException:
                continue
            except Exception as e:
                log.error(f"Error updating battle message: {e}")
                break

    def build_battle_ball(self, interaction: discord.Interaction, countryball, guild_battle: GuildBattle) -> BattleBall:
        health = min(countryball.health, MAXSTATS[0])
        attack = min(countryball.attack, MAXSTATS[1])

        if guild_battle.allow_buffs:
            health_buff, attack_buff = get_special_buffs(countryball, self.bot)
            health += health_buff
            attack += attack_buff

        return BattleBall(
            countryball.ball.country,
            interaction.user.name,
            health,
            attack,
            countryball.health_bonus,
            countryball.attack_bonus,
            self.bot.get_emoji(countryball.ball.emoji_id),
            get_ball_instance_id(countryball),
            get_special_emoji(countryball),
            countryball.favorite,
        )

    async def add_balls(self, interaction: discord.Interaction, countryballs):
        guild_battle = fetch_battle(interaction.user, interaction.guild_id)

        if guild_battle is None:
            await interaction.response.send_message(
                "You aren't a part of a battle!", ephemeral=True
            )
            return

        if interaction.guild_id != guild_battle.interaction.guild_id:
            await interaction.response.send_message(
                "You must be in the same server as your battle to use commands.", ephemeral=True
            )
            return

        if guild_battle.is_user_ready(interaction.user):
            await interaction.response.send_message(
                f"You cannot change your {settings.plural_collectible_name} as you are already ready.", ephemeral=True
            )
            return

        user_balls = guild_battle.get_user_balls(interaction.user)
        for countryball in countryballs:
            ball_name = countryball.ball.country

            if not guild_battle.allow_duplicates:
                if any(b.name == ball_name for b in user_balls):
                    yield True
                    continue

            ball = self.build_battle_ball(interaction, countryball, guild_battle)

            if ball in user_balls:
                yield True
                continue

            user_balls.append(ball)
            yield False

    async def remove_balls(self, interaction: discord.Interaction, countryballs):
        guild_battle = fetch_battle(interaction.user, interaction.guild_id)

        if guild_battle is None:
            await interaction.response.send_message(
                "You aren't a part of a battle!", ephemeral=True
            )
            return

        if interaction.guild_id != guild_battle.interaction.guild_id:
            await interaction.response.send_message(
                "You must be in the same server as your battle to use commands.", ephemeral=True
            )
            return

        if guild_battle.is_user_ready(interaction.user):
            await interaction.response.send_message(
                f"You cannot change your {settings.plural_collectible_name} as you are already ready.", ephemeral=True
            )
            return

        user_balls = guild_battle.get_user_balls(interaction.user)
        for countryball in countryballs:
            ball = self.build_battle_ball(interaction, countryball, guild_battle)

            if ball not in user_balls:
                yield True
                continue

            user_balls.remove(ball)
            yield False

    @app_commands.command()
    async def add(
        self, interaction: discord.Interaction, countryball: BallInstanceTransform, special: SpecialEnabledTransform | None = None
    ):
        """
        Adds a countryball to the battle plan.

        Parameters
        ----------
        countryball: Ball
            The countryball you want to add to your proposal
        """
        countryball = await BallInstance.objects.prefetch_related("ball", "special").aget(id=countryball.id)

        guild_battle = fetch_battle(interaction.user, interaction.guild_id)
        if guild_battle:
            user_balls = guild_battle.get_user_balls(interaction.user)
            if len(user_balls) >= guild_battle.amount_required:
                await interaction.response.send_message(
                    f"You cannot have more than {guild_battle.amount_required} {settings.plural_collectible_name} in your battle plan.",
                    ephemeral=True,
                )
                return

            health = min(countryball.health, MAXSTATS[0])
            attack = min(countryball.attack, MAXSTATS[1])

            if guild_battle.allow_buffs:
                health_buff, attack_buff = get_special_buffs(countryball, self.bot)
                health += health_buff
                attack += attack_buff

            if health < 1 or attack < 1:
                await interaction.response.send_message(
                    f"You cannot add a dead {settings.collectible_name}.", ephemeral=True
                )
                return

        async for dupe in self.add_balls(interaction, [countryball]):
            if dupe:
                await interaction.response.send_message(
                    f"You already have this {settings.collectible_name} in your proposal.", ephemeral=True
                )
                return

        await interaction.response.send_message(
            f"{countryball.ball.country} added.",
            ephemeral=True,
        )

    @app_commands.command()
    async def remove(
        self, interaction: discord.Interaction, countryball: BallInstanceTransform, special: SpecialEnabledTransform | None = None
    ):
        """
        Remove a countryball from what you proposed in the ongoing battle plan.

        Parameters
        ----------
        countryball: Ball
            The countryball you want to remove from your proposal
        """
        countryball = await BallInstance.objects.prefetch_related("ball", "special").aget(id=countryball.id)

        async for not_in_battle in self.remove_balls(interaction, [countryball]):
            if not_in_battle:
                await interaction.response.send_message(
                    f"You cannot remove a {settings.collectible_name} that is not in your deck!", ephemeral=True
                )
                return

        await interaction.response.send_message(
            f"{countryball.ball.country} removed.",
            ephemeral=True,
        )
