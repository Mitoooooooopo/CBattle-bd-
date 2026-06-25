#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <stdio.h> 
#include "main.h"

// int turn = 1; 

FILE *open_log(const char *filename) {
    return fopen(filename, "w");
}

Player user1 = {
	.name = "Ai1",
	.balls = {0},
	.winball = 0,
	.AblityUsed = 0
};


Player user2 = {
	.name = "Ai2",
	.balls = {0},
	.winball = 0,
	.AblityUsed = 0
};  

int dmgc(BattleBall *attacker) {
	int damage = attacker->atk;
	int atk_decider =  75 + (rand() % 16); 
	int final_calc = damage * atk_decider / 100; 
	
	return final_calc;
	
}
int PlayerAttackPhase(BattleBall *attacker, BattleBall *attacked, FILE *logger) {
	int final_damage = dmgc(attacker);
	int dmgdone = attacked->hp -= final_damage; 
	fprintf(logger, "%s did %d damage to %s\n", attacker->name, final_damage, attacked->name); 

	return final_damage;
}
void Fight(Player *user1, Player *user2, const char *Filename) {
       BattleBall *p1 = user1->balls; 
       BattleBall *p2 = user2->balls; 
       int turn =  1;

      FILE *logfile = open_log(Filename); // starts the log txt
      
      for (int i = 0; i < MAX_SIZE; i++) {
       while(p1[i].hp > 0 && p2[i].hp > 0) {
            fprintf(logfile, "Turn: %d\n", turn);
			int dodmg = PlayerAttackPhase(&p1[i], &p2[i], logfile);  
			if (p2[i].hp <= 0) {
                turn++; 
                user1->winball++;
			    fprintf(logfile, "%s fainted! %s wins!\n", p2[i].name, p1[i].name);  
			    break;
			} 
			int dodmg2 = PlayerAttackPhase(&p2[i], &p1[i], logfile); 
			if (p1[i].hp <= 0) {
                turn++; 
                user2->winball++;
				fprintf(logfile, "%s fainted! %s wins!\n", p1[i].name, p2[i].name);  
				break;
			}  
			turn++;  
	   }  
	  } 
	  if(user1->winball > user2->winball) {
	  	printf(logfile, "user1 won\n");
	  } 
	  else {
	  	fprintf(logfile, "user2 won\n"); 
	  } 
	  fclose(logfile); // close it here
} 

int main() {
    srand(time(NULL)); 
	Player *p = &user1;
	Player *o = &user2; 
	char hi[100] = "hello.txt"; // get overwritten by python th9
	Fight(p, o, hi); 
	
}
