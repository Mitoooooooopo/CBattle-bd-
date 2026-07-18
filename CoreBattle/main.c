#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <stdbool.h>
#include <stdio.h> 
#include "butils.h"
#include "ablities.h"

FILE *open_log(const char *filename) {
    return fopen(filename, "w");
}

void staterest(BattleState *state) {
    state->ballstate1->Dead_by_ablity = false;
    state->ballstate2->Dead_by_ablity = false;
    state->gb = NOTHING;
    state->ballstate1->events = NONE;
    state->ballstate2->events = NONE;
}

void Ablity_Finder(BattleBall *player1, BattleBall *player2, int Turn, BattleState *state, FILE *logger) {
  int id = player1->ablityid;
  bool ab;

  BallState *self_state = (player1 == state->ballstate1->ball) ? state->ballstate1 : state->ballstate2;
  
  if(id != -1 && abilitydatabase[id].ablity != NULL) {
  	ab = abilitydatabase[id].ablity->activate(player1, player2, Turn, state, self_state);   	
  	if (!ab) {
  		
  	}
  	else {
  		fprintf(logger, "%s\n", abilitydatabase[id].ablity->discription);
  	}
  	
  }

}

int dmgc(BattleBall *attacker, bool *critical) {
    int damage = attacker->atk;    
    if (rand() % 100 < 10) {
    	damage = damage * 3 / 2; 
    	*critical = true;
    } 

    if(attacker->Is_Shiny == true) {
    	damage = damage * 2;
    }
	
	int atk_decider =  75 + (rand() % 16); 
	int final_calc = damage * atk_decider / 100; 
	return final_calc;
	
}
void PlayerAttackPhase(BattleBall *attacker, BattleBall *attacked, FILE *logger) {
    bool IsCrtical = false; 
    char *critical = "!";
    
	if(attacked->canattack == false) {
        fprintf(logger, "ball was unable do any dmg to attacker\n"); 
		return;
	} 
    int final_damage = dmgc(attacker, &IsCrtical); 
    if(IsCrtical == true) {
        critical = "Its Critical";
    }
	attacked->hp -= final_damage;
	if (attacker->Is_Shiny == true) {
		fprintf(logger, "Shiny Bonus Applied\n");
	}
	fprintf(logger, "%s did %d damage to %s %s\n", attacker->name, final_damage, attacked->name, critical);
	
} 

bool DeathPhase(BattleBall *attacker, BattleBall *attacked, BallState *ded, FILE *logger) {
    if(ded->Dead_by_ablity == true) {
    	fprintf(logger, "%s ball took opponent with him!\n", attacked->name);
    	fprintf(logger, "%s fainted! %s fainted!\n", attacker->name, attacked->name);
    	return true;
    }
    fprintf(logger, "%s fainted! %s wins!\n", attacked->name, attacker->name);
    return false;
}
	
void Fight(Player *user1, Player *user2, const char *Filename) {
       srand(time(NULL));
       
       BattleBall *p1 = user1->balls; 
       BattleBall *p2 = user2->balls;   
       int turn = 1; 

       BallState state1 = { .ball = NULL, .events = NONE, .Dead_by_ablity = false };
       BallState state2 = { .ball = NULL, .events = NONE, .Dead_by_ablity = false };

       BattleState bstate = {
         .ballstate1 = &state1,
         .ballstate2 = &state2,
         .gb = NOTHING,
         .total_turns = 0,
       };

       FILE *logfile = open_log(Filename); // starts the log txt
       
      for (int i = 0; i < MAX_SIZE; i++) {           
           staterest(&bstate);
           bstate.ballstate1->ball = &p1[i];
           bstate.ballstate2->ball = &p2[i];
                     
       while(p1[i].hp > 0 && p2[i].hp > 0) {
            bstate.gb = FIGHT_START;
            fprintf(logfile, "Turn: %d\n", turn); 
            bstate.total_turns = turn;
            
            Ablity_Finder(&p1[i], &p2[i], turn, &bstate, logfile); 
            
			PlayerAttackPhase(&p1[i], &p2[i], logfile);  
			bstate.ballstate1->events = ATTACKED;
			if (p2[i].hp <= 0) {
                turn++; 
                user1->winball++; 
                bstate.ballstate2->events = BALL_DEAD; 
                Ablity_Finder(&p2[i], &p1[i], turn, &bstate, logfile);
                bool abdead1 = DeathPhase(&p1[i], &p2[i], bstate.ballstate2, logfile); 
                if(abdead1 == true) {
                	user1->winball--;
                }
			    break;
			}  

			Ablity_Finder(&p2[i], &p1[i], turn, &bstate, logfile);
			
			PlayerAttackPhase(&p2[i], &p1[i], logfile); 
			bstate.ballstate2->events = ATTACKED;
			if (p1[i].hp <= 0) {
                turn++; 
                user2->winball++;
                bstate.ballstate1->events = BALL_DEAD; 
                Ablity_Finder(&p1[i], &p2[i], turn, &bstate, logfile);
                bool abdead = DeathPhase(&p2[i], &p1[i], bstate.ballstate1, logfile);
                if(abdead == true) {
                	user2->winball--;
                }
				break;
			}  
			turn++; 
	   }  
	  } 	   
	  if(user1->winball == user2->winball) {
	  	fprintf(logfile, "its a tie\n"); 
	  	fclose(logfile); 
	  	return;
	  	
	  }
	  if(user1->winball > user2->winball) {
	  	fprintf(logfile, "%s won\n", user1->name);
	  } 
	  else {
	  	fprintf(logfile, "%s won\n", user2->name);
	  }
	  fclose(logfile); 
}

int main() {
  //main is not needed unless testing	
}
