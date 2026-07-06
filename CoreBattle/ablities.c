#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <stdbool.h>
#include <stdio.h>  
#include "ablities.h"

bool None(BattleBall *attacker, BattleBall *attacked, int turn, BattleState *state, BallState *self_ball) {
	// just filler func
}
bool Dubai_style(BattleBall *attacker, BattleBall *attacked, int turn, BattleState *state, BallState *self_ball) {
  
  if (state->gb == FIGHT_START) {
  	if (attacked->atk < attacker->atk) {
  		attacker->canattack = false; 
  		return true;
  	} 
  	else {
  		return false;
  	}
  } 
}

bool Never_try_to_invade(BattleBall *attacker, BattleBall *attacked, int turn, BattleState *state, BallState *self_ball) {
  
  if (self_ball->events == BALL_DEAD) {
		attacked->hp -= 1000;  
		if(attacked->hp <= 0) {
			self_ball->Dead_by_ablity = true;
		}
		return true;
  } 
  else {
	 return false;
  }
  
} 

Ablity nv = {
	.abname = "none",
	.discription = "used as placeholder", 
	.bs = ON_DEATH,
	.activate = None
};

Ablity ab = {
	.abname = "Dubai_style",
	.discription = "uae blocked all incoming attacks in dubai style",
	.bs = ON_TURN,
	.activate = Dubai_style
}; 

Ablity bb = {
	.abname = "Never_try_to_invade_me",
	.discription = "Russia dead leaving a nuclear bomb -1000 dmg",
	.bs = ON_DEATH,
	.activate = Never_try_to_invade
};

AblityDatabase abilitydatabase[3] = {
    {&nv, 0},
	{&ab, 1},
	{&bb, 2},
};
