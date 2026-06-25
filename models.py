from dataclasses import dataclass, field

import discord


@dataclass
class BattleBall:
    name: str
    owner: str
    health: int
    attack: int
    health_bonus: int
    attack_bonus: int
    emoji: str = ""
    instance_id: str = ""
    special_emoji: str = ""
    favorite: bool = False
    dead: bool = False


@dataclass
class BattleInstance:
    p1_balls: list = field(default_factory=list)
    p2_balls: list = field(default_factory=list)
    winner: str = ""
    turns: int = 0


@dataclass
class GuildBattle:
    interaction: discord.Interaction
    author: discord.Member
    opponent: discord.Member
    battle: BattleInstance = field(default_factory=BattleInstance)
    author_ready: bool = False
    opponent_ready: bool = False
    battle_message: discord.Message | None = None
    amount_required: int = 3
    allow_duplicates: bool = True
    allow_buffs: bool = True
    author_confirmed: bool = False
    opponent_confirmed: bool = False
    created_at: float = field(default_factory=lambda: __import__("time").time())

    def get_user_balls(self, user: discord.User | discord.Member) -> list:
        return self.battle.p1_balls if user == self.author else self.battle.p2_balls

    def is_user_ready(self, user: discord.User | discord.Member) -> bool:
        return self.author_ready if user == self.author else self.opponent_ready

    def set_user_ready(self, user: discord.User | discord.Member, ready: bool) -> None:
        if user == self.author:
            self.author_ready = ready
        else:
            self.opponent_ready = ready

    def has_required_amount(self, user: discord.User | discord.Member) -> bool:
        return len(self.get_user_balls(user)) == self.amount_required

    def both_have_required_amount(self) -> bool:
        return (
            len(self.battle.p1_balls) == self.amount_required
            and len(self.battle.p2_balls) == self.amount_required
        )


battles: list[GuildBattle] = []


def fetch_battle(user: discord.User | discord.Member, guild_id: int | None = None) -> GuildBattle | None:
    """
    Fetches a battle based on the user provided.

    Parameters
    ----------
    user: discord.User | discord.Member
        The user you want to fetch the battle from.
    guild_id: int | None
        The guild where the battle should be searched.
    """
    found_battle = None

    for battle in battles:
        if guild_id is not None and battle.interaction.guild_id != guild_id:
            continue

        if user not in (battle.author, battle.opponent):
            continue

        found_battle = battle
        break

    return found_battle


def fetch_battle_by_interaction(interaction: discord.Interaction) -> GuildBattle | None:
    for battle in battles:
        if battle.interaction == interaction:
            return battle

    return None
