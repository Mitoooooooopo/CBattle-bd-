import logging
from typing import List, Optional, Dict, TYPE_CHECKING
from dataclasses import dataclass
import discord
from discord import app_commands
from discord.ext import commands

from bd_models.models import BallInstance, Player
from ballsdex.core.utils.transformers import BallInstanceTransform, BallEnabledTransform
from ballsdex.settings import settings 
from .utils import BattleBall, BattlingUser
from ballsdex.packages.battle.display import fill_battle_embed_fields
from ballsdex.packages.battle.battle_core import run_battle

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot 


battle_tracker = {}
MAX_SIZE = 0

@dataclass
class BattleSession:
    p1: BattlingUser
    p2: BattlingUser
    message: discord.Message | None = None
    
class BattleStartView(discord.ui.View): 
   def __init__(self, user: discord.Member, opponent: discord.Member, accepted: bool): 
     super().__init__(timeout=60)
     self.user = user
     self.opponent = opponent
     self.accepted = accepted
          
   @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="Accept_button") 
   async def accept(self, interaction: discord.Interaction, button: discord.ui.Button): 
     if interaction.user.id != self.opponent.id:
         await interaction.response.send_message("its Not your battle bro", ephemeral=True)
         return
     await interaction.response.send_message("You accepted the Battle its locked", ephemeral=True) 
     self.accepted = True
     self.stop()

   @discord.ui.button(label="Reject/Cancel", style=discord.ButtonStyle.red, custom_id="Reject_button") 
   async def reject(self, interaction: discord.Interaction, button: discord.ui.Button): 
      if interaction.user.id not in (self.user.id, self.opponent.id):
          await interaction.response.send_message(
              "It's not your battle bro",
              ephemeral=True
          )
          return
          
      await interaction.response.send_message("You rejected the Battle", ephemeral=True) 
      for button in self.children:
          button.disabled = True
      self.accepted = False
      self.stop()
   

class Battle(commands.GroupCog, name="battle"):
   def __init__(self, bot: "BallsDexBot"):
     self.bot = bot 

   async def create_battle(self, p1, p2):
    BEmbed = discord.Embed(
        title="battle",
        description="use /battle add to add balls",
        color=discord.Color.green()
    ) 

    fill_battle_embed_fields(embed=BEmbed, bot=self.bot, battler1=p1, battler2=p2, compact=False)
    return BEmbed

   @app_commands.command(name="begin")
   async def battle_begin(self, interaction: discord.Interaction, opponent: discord.Member):
    """ 
    start a battle

    Parameters 
    -----

    opponent: discord.Member
      The Player You wana fight 
    """ 

    await interaction.response.defer()
    
    if opponent.id == interaction.user.id:
       await interaction.followup.send("You cant fight against yourself") 
       return

    if opponent.bot:
       await interaction.followup.send("You cant fight against bots") 
       return 

    user_obj = interaction.user  

    player1, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)
    player2, _ = await Player.objects.aget_or_create(discord_id=opponent.id)

    await interaction.followup.send(f" hey {opponent.mention} you have been invited for battle") 
   
    BattleInviteEmbed = discord.Embed(
     title=(f"{user_obj.display_name} has invited {opponent.display_name} to battle"),
     description="press accept to fight or reject to cancel",
     color=discord.Color.green()
    
    ) 

    BattleInviteView = BattleStartView(user=user_obj, opponent=opponent, accepted=None)

    message = await interaction.followup.send(embed=BattleInviteEmbed, view=BattleInviteView, wait=True) 
    
    await BattleInviteView.wait()

    if BattleInviteView.accepted is None:
       BattleInviteEmbed.title="TimedOut"
       BattleInviteEmbed.color=discord.Color.red() 
    elif BattleInviteView.accepted == False:
        BattleInviteEmbed.title="BattleCanceled"
        BattleInviteEmbed.color=discord.Color.red() 
    else:
        await message.delete()
        session = BattleSession(
            p1=BattlingUser(user=user_obj),
            p2=BattlingUser(user=opponent)
        )
        battle_tracker[user_obj.id] = session
        battle_tracker[opponent.id] = session
        BEmbed = await self.create_battle(session.p1, session.p2)
        session.message = await interaction.channel.send(embed=BEmbed)
        return
    await message.edit(embed=BattleInviteEmbed, view=None) 

   @app_commands.command(name="add") 
   async def battle_add(self, interaction: discord.Interaction, ball: BallInstanceTransform):
    """
    add a countryball to your deck

    Parameters
    -----
    ball: BallInstanceTransform
      the ball you want to add
    """  

    user_obj = interaction.user 

    battle = battle_tracker.get(interaction.user.id)
    
    if battle is None:
        await interaction.response.send_message("its either not your battle or you dond have valid battle session", ephemeral=True)
        return 

    P1, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id) 

    ball = await BallInstance.objects.select_related("ball").aget(id=ball.id)

    b1 = BattleBall(
        name=ball.ball.country,
        atk=ball.attack,
        hp=ball.health,
        ballid=ball.ball_id,
        emoji=ball.ball.emoji_id
    )  

    if interaction.user.id == battle.p1.user.id:
        battle.p1.proposal.append(b1)
    else: 
        battle.p2.proposal.append(b1) 

    BEmbed = discord.Embed(title="battle", description="use /battle add to add balls", color=discord.Color.green())
    fill_battle_embed_fields(embed=BEmbed, bot=self.bot, battler1=battle.p1, battler2=battle.p2, compact=False)
    await battle.message.edit(embed=BEmbed) 

    await interaction.followup("Ball has been added", ephemeral=True) 
    
    if len(battle.p1.proposal) == MAX_SIZE and len(battle.p2.proposal) == MAX_SIZE:
        await interaction.channel.send("Both teams are full! Battle starting...")
        await self.start_fight(battle)  # fills C structs, calls Fight(), posts results
            
    



    
   
    

    

    
       
       

    
