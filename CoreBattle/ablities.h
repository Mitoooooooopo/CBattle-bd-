#ifndef ABLITIES_H
#define ABLITIES_H  

#include "butils.h"

enum BattleSequance {
    ON_TURN,
    ON_ENTER,
    ON_DEATH,
    ON_LIMITED_TURNS
};

typedef bool(*BallAblity)(BattleBall *attacker, BattleBall *attacked, int turn, BattleState *state, BallState *self_ball);

typedef struct Ablity{
        char abname[100];
        char discription[200];
        BallAblity activate; 
        enum BattleSequance bs;

} Ablity;

typedef struct AblityDatabase{
        Ablity *ablity;
        int id;
} AblityDatabase;

extern AblityDatabase abilitydatabase[3];

#endif
