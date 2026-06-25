import logging
from typing import List, Optional, Dict, TYPE_CHECKING
import discord
from discord import app_commands
from discord.ext import commands

from bd_models.models import BallInstance, Player
from ballsdex.core.utils.transformers import BallInstanceTransform, BallEnabledTransform
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

class BattleUi:
    def __init__(self, p1: discord.Member, p2: discord.Member):
        self.p1 = p1
        self.p2 = p2

        self.embed = self.BattleEmbed()

        self.p1_balls = []
        self.p2_balls = []

    def BattleEmbed(self):
        battle_e = discord.Embed(
            title="CBDv1 Battle System",
            description="A demo battle system. Use /battle add to add balls.",
            color=discord.Color.green()
        )

        battle_e.add_field(
            name=self.p1.display_name,
            value="\n",
            inline=True
        )

        battle_e.add_field(
            name=self.p2.display_name,
            value="\n",
            inline=True
        )

        return battle_e      
        
    def refreshembed(self):
        self.embed = self.BattleEmbed()
