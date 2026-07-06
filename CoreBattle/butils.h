#ifndef BUTILS_H
#define BUTILS_H

#include <stdbool.h> 
#include <stdio.h> 

#define MAX_SIZE 3

typedef struct BattleBall{
    char name[100];
    int atk;
    int hp;
    int id; 
    int ablityid;
    bool Is_Shiny; 
    bool stunned;
    bool canattack;

} BattleBall; 

typedef struct Player{
    char name[100];
    BattleBall balls[MAX_SIZE];
    int winball;
    int AblityUsed;

} Player;

typedef enum BattleEns{
    NONE,
    ATTACKED,
    BALL_DEAD,
} BattleEns;

typedef enum global_enums{
    NOTHING,
    FIGHT_START,
    FIGHT_ENDED,

} global_enums;

typedef struct BallState{
    BattleBall *ball;
    BattleEns events; 
    bool Dead_by_ablity;
    //int Total_DMG_Done;
    //int Total_DMG_recivied;
} BallState;

typedef struct BattleState{
     BallState *ballstate1;
     BallState *ballstate2;
     global_enums gb;
     int total_turns; 

} BattleState;

#endif
