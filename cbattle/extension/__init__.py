from typing import TYPE_CHECKING
  
if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot
 
 
async def setup(bot: "BallsDexBot"):
    from .cog import Battle
    await bot.add_cog(Battle(bot))
