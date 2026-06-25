#ifndef MAIN_H
#define MAIN_H 

#include <stdbool.h>

#define MAX_SIZE 3

typedef struct BattleBall{
    char name[100];
    int atk;
    int hp;
    int id;
    bool IsCurrent;
    bool stunned;
    bool freezed;

} BattleBall;

typedef struct Player{
    char name[100];
    BattleBall balls[MAX_SIZE];
    int winball;
    int AblityUsed;

} Player; 

#endif
