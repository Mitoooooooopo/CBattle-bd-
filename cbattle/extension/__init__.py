from typing import TYPE_CHECKING
  
if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot
 
 
async def setup(bot: "BallsDexBot"):
    from .cog import BattleCog
    await bot.add_cog(BattleCog(bot))
