import logging
from typing import List, Optional, Dict, TYPE_CHECKING 
from dataclasses import dataclass
from pathlib import Path
import ctypes
import discord
from discord import app_commands
from discord.ext import commands

from bd_models.models import BallInstance
from ballsdex.core.utils.transformers import BallInstanceTransform, BallEnabledTransform
from ballsdex.settings import settings

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot 

LIB_PATH = Path(__file__).parent / "battle.so"

MAX_SIZE = 3

@dataclass
class TempBattleBall:
    name: str
    atk: int
    hp: int
    ballid: int 

@dataclass
class TempBattlePlayer:
    name: str
    balls: list[TempBattleBall] 

    
lib = ctypes.CDLL(str(LIB_PATH)) 

class BattleBall(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 100),
        ("atk", ctypes.c_int),
        ("hp", ctypes.c_int),
        ("id", ctypes.c_int),
        ("IsCurrent", ctypes.c_bool),
        ("stunned", ctypes.c_bool),
        ("freezed", ctypes.c_bool),
    ] 
    
class Player(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 100),
        ("balls", BattleBall * MAX_SIZE),
        ("winball", ctypes.c_int),
        ("AblityUsed", ctypes.c_int),
    ] 


lib.Fight.argtypes = [
    ctypes.POINTER(Player),
    ctypes.POINTER(Player),
    ctypes.c_char_p,
]
lib.Fight.restype = None 

def build_ctypes_player(balls: list[BattleBall], owner_name: str) -> Player:
    p = Player()
    p.name = owner_name.encode()[:99]

    for i, ball in enumerate(balls):
        total_atk = ball.attack + ball.attack_bonus
        total_hp = ball.health + ball.health_bonus

        p.balls[i].name = ball.name.encode()[:99]
        p.balls[i].atk = total_atk
        p.balls[i].hp = total_hp
        p.balls[i].id = 0 
        p.balls[i].IsCurrent = (i == 0)
        p.balls[i].stunned = False
        p.balls[i].freezed = False

    return p 
        
#async def run_battle(battle: BattleSession):
    #temp1 = TempBattlePlayer(
        #name=battle.p1.user.name,
       # balls=[TempBattleBall(b.name, b.atk, b.hp, b.ballid) for b in battle.p1.proposal]
   # )
   # temp2 = TempBattlePlayer(
       # name=battle.p2.user.name,
  #      balls=[TempBattleBall(b.name, b.atk, b.hp, b.ballid) for b in battle.p2.proposal]
  #  )

  #  user1 = build_ctypes_player(temp1)
  #  user2 = build_ctypes_player(temp2) 

  #  log_name = f"battle_{battle.p1.user.id}_{battle.p2.user.id}.txt"
    
 #   lib.Fight(
    #    ctypes.byref(user1),
   #     ctypes.byref(user2),
    #    log_name.encode()
  #  ) 

  #  with open(log_name, "r", encoding="utf-8") as f:
       # battle_log = f.read() 

  #  await interaction.followup.send(
     #   file=discord.File(log_name)
    #)



