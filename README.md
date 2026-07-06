 

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
path = "cbattle"
enabled = true
```
restart your bot and if everything succeed you should see the battle commands 

# Abilities 

The Battle Engine support minimal abilities the only drawback is you have to know how to write basic C 








