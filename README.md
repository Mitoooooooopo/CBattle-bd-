 

# CBattle 
it's a Battle system for ballsdex made in C Currently it's not recommended to use it on any production bots 
this is just a small prototype it's unpolished and have some edge cases 


# How it works 
basically python acts Like UX python fetch ball data grabs values (hp atk and name) Then pass that to
C side, C perfom the battle with that values then sends results into txt python get's and sends The 
txt to discord 

# How to install 
assuming you know how to install basic package in Ballsdex 3xx

On your config/extra.toml add 

```
[[ballsdex.packages]]
location = "https://github.com/Mitoooooooopo/CBattle-bd-.git#main"
path = "cbattle"
enabled = true
```
restart your bot and if everything succeed you should see the battle commands 

# Updating

if any updates come to the core battle engine you can simply just copy the updated battlev1.0.so and replace yours with updated ver
(ony applicable to core engine any updates with python code have to be updated in normal way)

# Abilities 

The Battle Engine support minimal abilities the only drawback is you have to know how to write basic C 


## adding new abliity

To Add a new ablity you just have to open ablities.c create the ablity function a instamce and add it to ablitydatabase defined

here

```
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
```

Here Dubai_style is a bool function that takes exactly 5 parameters

attacker - the main ball who is attacking

attacked - the opponent ball

turn - the amount of turns

state - the battle state

self_ball - the current balls state(attacker)

here  if (state->gb == FIGHT_START)  means when the states gb get set to fight start logic goes

if attackers atk is above the opponent set attackers canattack to false
we are using pointers so it change the orginal balls artibutes

attacker->canattack = false;                                         
this will make attacker immune to damages
then 
return true;
returns bool true indicating ablity worked

else we set it to return false aka ablity didnt worked

You can take a look at butils.h and second defined ablity to understand more about the structure

next after writing your ability is define it

```
Ablity ds = {
	.name = dubai_style,
	.discription = "Uae dodged all attacks in dubai style",
	// The discription is what shown when the ability activates
	.bs = ON_TURN,
	// when the ability have to trigger
	.activate = Dubai_style 
	// pointes to your ablity function
}

```

Creates a ablity 

next would be to register it

in same file there is 

```
AblityDatabase abilitydatabase[3] = {
    {&nv, 0},
    {&ab, 1},
    {&bb, 2},
};

```

you have to add your ablity here  since our ablity name is ds

```
AblityDatabase abilitydatabase[4] = { // since a new entry is added the number goes from 3 to 4
    {&nv, 0},
    {&ab, 1},
    {&bb, 2},
    {&ds, 3}, // add your ability entry here 
};

```
note that the ab and bb are just templates you can obviously remove them or rename them

then we open ablities.h 

and edit

```

extern AblityDatabase abilitydatabase[3];
```

to 

```
extern AblityDatabase abilitydatabase[4];
```
now your ability is succesfully registered Next We have to connect Ball With the ability

start your bots admin panel edit the capacity_json of the ball whom you want to give the ability

in capacity_json remove the {} bracket and just add the ability id 

here i want uae to have the ability ds so i edit uae's capacity_json from {} to 3 
Its recommended to put -1 if a ball dond have ability defined

after this you have to compile the modified code to a .so please see below

now try the battle and see if your ability works

Hope You Understand if you have any trouble getting it work or understanding please dm me on the discord

# Compiling the code to shared library

If you have made any changes in the c code or added a ability you have to compile it for use
you need to have gcc installed 

```
gcc -shared -fPIC main.c ablities.c -o battlev1.0.so
```

this command creates a .so file called battlev1.0.so 

replace the existing .so in extension folder with your compiled one

thats it your modified code or new ability  will take effect

its necessary to do this every time you make a change in c code or add a new ability

## the project is in early stage and may have problems feel free to report or contribute









