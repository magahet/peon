Peon
====

Peon is a minecraft bot writen in python. It acts as a replacement for the minecraft client and allows for automation of tasks in the minecraft world.

This version of peon uses fastmc and works with Mincraft 1.8. It's functional for the most part, though many of the advanced features of the older peon haven't been implemented yet, such as enchanting, path finding, movement, and terraforming.

What is implemented is much of the base player and world modeling, so the bot is aware of entities, blocks, his personal inventory, and health/hunger state.


Small Tutorial
==============

## Get fastmc for protocol handling
```
git clone https://github.com/dividuum/fastmc.git
cd fastmc
python setup.py install
```

## Get peon
```
git clone https://github.com/magahet/peon.git
cd peon
```
   

## Starting peon
```
ipython
import peon
bot = peon.Client()
bot.connect('myminecraftserver.org', 'peon', 'mypassword', auth=False)
```
 
Authentication flag determines if bot will authenticate with central minecraft servers. If you're playing on an offline mode server, this can be set to False.

## Some available attributes
```
# inventory
bot.player.inventory

# world
bot.world

# entities
bot.world.entities

# method to get nearby entities
bot.player.iter\_entities\_in\_range(\_type='Sheep', reach=4)
```


## Examples of slightly more complex actions

Take a look at afk-bot.py and shear-bot.py. These each utilize peon for some simple, but helpful tasks.


# TODO

So, so much. It would be great to get all the previous peon functionality going again. However, we all have real lives and there are only so many hours in a day.
