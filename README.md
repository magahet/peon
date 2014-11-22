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
client = peon.Client()
client.connect('myminecraftserver.org', 'peon', 'mypassword', auth=False)
bot = client.bot
```
 
Authentication flag determines if bot will authenticate with central minecraft servers. If you're playing on an offline mode server, this can be set to False.

## Some available attributes
```
# inventory
bot.inventory

# world
bot.world

# entities
bot.world.entities

# other players
bot.world.players

# objects (items, projectiles, etc)
bot.world.players

# method to get nearby entities
[e for e in bot.player.iter_entities_in_range(_type='Sheep', reach=4)]
```

## Auto Actions

Peon performs the following actions automatically and without blocking the main process.

### Fall

If he's not actively moving and not on the ground, peon will auto update his position downward.

### Eat

If his hunger reaches a set threshold, he will look for food in his inventory and eat it.

### Defend

If hostile mobs enter a 4m radius, he will grab a sword from his inventory (if available) and kill the mob.

### Hunt

He will search the area for certain mob types, navigate to, and kill them.

### Gather

He will search for objects of a given type and go collect them.


## Using Auto Actions

Each auto action can be enabled/disabled and can run concurrently. Peon will used action and inventory locks to ensure he doesn't try to run in two directions at the same time.

Here's an example. Read through peon/robot.py for more info.

```
bot.enable_auto_action('hunt')
bot.set_auto_action_settings('hunt', mob_types=['Sheep'])
```

# TODO

So, so much. It would be great to get all the previous peon functionality going again. However, we all have real lives and there are only so many hours in a day. Here are some big items I'm working to get going again:

- enchanting
- clearing land
- exploring/searching for world features or biomes
- farming
- trading
- mining
