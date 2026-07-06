import asyncio
import logging
import tempfile
import uuid
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

LIB_PATH = Path(__file__).parent / "battlev1.0.so"

MAX_SIZE = 3

lib = ctypes.CDLL(str(LIB_PATH))


class CBattleBall(ctypes.Structure):
    """C-side struct mirroring the .so's expected layout for one ball."""
    _fields_ = [
        ("name", ctypes.c_char * 100),
        ("atk", ctypes.c_int),
        ("hp", ctypes.c_int),
        ("id", ctypes.c_int),
        ("ablityid", ctypes.c_int),
        ("Is_Shiny", ctypes.c_bool),
        ("stunned", ctypes.c_bool),
        ("canattack", ctypes.c_bool),
    ]


class Player(ctypes.Structure):
    """C-side struct mirroring the .so's expected layout for one player."""
    _fields_ = [
        ("name", ctypes.c_char * 100),
        ("balls", CBattleBall * MAX_SIZE),
        ("winball", ctypes.c_int),
        ("AblityUsed", ctypes.c_int),
    ]


# Fight()'s third argument is NOT an output buffer — it's a filename.
# The C side opens this path itself (open_log) and fprintf's the whole
# battle log into it, then returns void. We must pass a real path string,
# not a pre-allocated ctypes buffer, or open_log gets garbage/empty bytes
# as a "path", fails to open a file, and every subsequent fprintf(logfile, ...)
# writes through a NULL FILE* -> segfault.
lib.Fight.argtypes = [
    ctypes.POINTER(Player),
    ctypes.POINTER(Player),
    ctypes.c_char_p,
]
lib.Fight.restype = None


def build_ctypes_player(balls: List[BallInstance], owner_name: str) -> Player:
    """
    Convert a list of Django BallInstance objects into the ctypes Player
    struct expected by the C battle library.

    Notes on the mapping (confirmed against the actual BallInstance model):
      - ball.attack / ball.health are properties that already include the
        instance's attack_bonus/health_bonus baked in as a percentage —
        do NOT add the bonus again on top.
      - The species name lives at ball.countryball.country, not ball.name.
      - capacity_logic (the ability id) lives on ball.countryball (the
        Ball/species model), not on the instance itself. It's stored as
        a JSONField but holds a plain number — the ability id — so it's
        cast straight to int for the ctypes struct.
      - Shiny handling is intentionally skipped for now (always False);
        to be wired up once the "which Special counts as shiny" question
        is resolved.
    """
    if len(balls) > MAX_SIZE:
        raise ValueError(f"Cannot build a player with more than {MAX_SIZE} balls (got {len(balls)})")

    p = Player()
    p.name = owner_name.encode("utf-8", errors="replace")[:99]

    for i, ball in enumerate(balls):
        species = ball.countryball

        p.balls[i].name = species.country.encode("utf-8", errors="replace")[:99]
        p.balls[i].atk = ball.attack
        p.balls[i].hp = ball.health
        p.balls[i].id = ball.pk
        p.balls[i].ablityid = int(species.capacity_logic)
        p.balls[i].Is_Shiny = False  # placeholder: shiny logic deferred
        p.balls[i].stunned = False
        p.balls[i].canattack = True

    return p


def run_fight(player1: Player, player2: Player) -> str:
    """
    Call the C Fight() function and return the battle log text.

    Fight() writes its entire log to the file at the path given as its
    third argument (via internal fprintf calls) and returns nothing.
    So we:
      1. create a unique temp file path
      2. pass that path (as bytes) to Fight()
      3. read the file back once Fight() returns
      4. clean up the temp file

    NOTE: this is a blocking, synchronous call (~1s observed, plus file
    I/O). Do not call this directly from an async Discord callback — use
    run_fight_async instead, which offloads this to a thread so the bot's
    event loop doesn't freeze while the fight runs.
    """
    tmp_dir = Path(tempfile.gettempdir())
    log_path = tmp_dir / f"battle_{uuid.uuid4().hex}.log"

    lib.Fight(
        ctypes.byref(player1),
        ctypes.byref(player2),
        str(log_path).encode("utf-8"),
    )

    if not log_path.exists():
        raise RuntimeError(
            f"Fight() did not produce a log file at {log_path}. "
            "Check open_log()'s behavior / permissions on that path."
        )

    return log_path

async def run_fight_async(player1: Player, player2: Player) -> str:
    """
    Async-safe wrapper around run_fight(). Runs the blocking ctypes call
    (and file I/O) in the default thread pool executor so the bot's event
    loop keeps handling other interactions while the fight computes.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, run_fight, player1, player2)
