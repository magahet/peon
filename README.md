Peon
====

Peon is a minecraft bot written in python. It acts as a replacement for the minecraft client and allows for automation of tasks in the minecraft world. The bot can hunt, mine, gather, defend, eat, etc. He has efficient path finding both for movement and digging.

This version of peon uses fastmc and works with Mincraft 1.8.


# Small Tutorial

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

## Setup server settings
```
cp settings.cfg.example settings.cfg
```

Edit settings.cfg with your servername, username, and password.

## Run autobot

```
./autobot -c example/test.yaml
```

This will log peon in and enable a few sample automated processes. Peon will harvest mature crops within 20m of himself and will gather those crops. He will also defend himself from hostile mobs and eat any available food in his inventory when hungry.


## Make him more interactive

Although autobot.py and the auto action yaml files (described in the next section) allow for many automated tasks, it does not have a comprehensive interface. However, using the python interactive terminal, or IPython (recommended) will make working with peon a lot easier than constantly killing the running autobot.py script. Here is an example session:

```
# launch autobot.py, connect to the world "local" defined in settings.cfg, and run the auto actions defined in examples.follow.yaml
$ ipython -i autobot.py -- -w local -a examples/follow.yaml

14:11 - INFO - root - logging into [localhost:25565] as [peon]
14:11 - INFO - root - actions: [{'player_name': 'magahet', 'name': 'follow'}]
14:11 - INFO - peon.client - logging in
14:11 - INFO - peon.robot - Eating: Cooked Chicken
Bot(xyz=(-379, 70, 288), health=20.0, food=18, xp=66, enabled_auto_actions=['defend', 'escape', 'fall', 'eat'], active_auto_actions=['eat'])

In [2]: bot.stop('follow')
Out[2]: True

In [3]: bot.start('hunt')
Out[3]: True

14:12 - INFO - peon.robot - hunting entity: Entity(eid=249767, _type=Spider, xyz=(-364, 70, 262))

In [6]: bot.inventory
Out[6]: 
Window(id=0, slots=[
...
Slot(item_name="Cobblestone", count=64, damage=0, has_data=False),  # 26 main inventory
Slot(item_name="Granite", count=7, damage=1, has_data=False),  # 27 main inventory
Slot(item_name="Seeds", count=1, damage=0, has_data=False),  # 28 main inventory
Slot(item_name="Sandstone", count=8, damage=0, has_data=False),  # 29 main inventory
Slot(item_name="Diamond", count=47, damage=0, has_data=False),  # 30 main inventory
Slot(item_name="Cobblestone", count=64, damage=0, has_data=False),  # 31 main inventory
Slot(item_name="Cobblestone", count=15, damage=0, has_data=False),  # 32 main inventory
```

The interpreter allows you to manipulate the bot object interactively and allows you to print, list, or get help for attributes and methods. A tutorial on IPython will help with learning how to use these features.


# Auto Actions

Peon is able to perform a number actions automatically, without blocking the main process. Using autobot.py, you can enable these actions and configure their settings with a configuration yaml file. Examples are available in the examples directory. 

The following are some of the actions available. To see the full list look at peon/robots.py. The configuration yaml should be made up of a list of dictionaries describing each action. The name must match the set of actions defined in robots.py. Arguments are those defined by each auto action function and remaining keys are passed to the function as keyword arguments. Look at each function to see the full set of options.


### Fall

If he's not actively moving and not on the ground, peon will auto update his position downward. Fall is automatically enabled.


### Eat

If his hunger reaches a set threshold, he will look for food in his inventory and eat it. Eat is automatically enabled.


### Defend

If hostile mobs enter a 4m radius, he will grab a sword from his inventory, if available, and kill the mob. Peon defends against all hostile mobs by default. Defend is automatically enabled.


### Hunt

He will search the area for certain mob types, navigate to, and kill them.

```yaml
- name: hunt
  mob_types: ['Sheep', 'Zombie']   # list of mobs to hunt
  _range: 20                       # how far from home to hunt
```


### Gather

He will search for objects of a given type and go collect them.

```yaml
- name: gather
  items:                    # list of items to gather
    - Stone
    - Sand
  _range: 20                # how far from home to search
```


### Harvest

He will search for grown crops or other block_types to break and collect. Can be used to cut down trees.

```yaml
- name: harvest
  _range: 20                # how far from home to search
```


### Mine

Finds, digs to, and mines given block types. He has perfect knowledge of the world, so he digs straight to the resources. There's no searching involved.

```yaml
- name: mine
  block_types:
    - Diamond Ore
    - Gold Ore
    - Iron Ore
```


### Enchant

Finds and moves to an enchanting table and enchants whatever is available in his inventory. Continues to enchant as long as his xp level is 30+ and has 3+ lapis in his inventory. This works very well when used with defend (next to xp farm), get_enchantables, and store_enchanted.


### Get

Gets items from a chest at a given position.
```yaml
- name: get
  items:
    - Cooked Chicken
  chest_position: [10, 30, 20]
```


### Get Enchantables

Same as Get, but only gets items that can be enchanted.


### Store

Stores items in a chest at a given position.
```yaml
- name: store
  items:
    - Diamonds
  chest_position: [10, 30, 20]
```

### Store Enchanted

Same as Store, but only stores items that are enchanted.


### Follow

Peon will follow a player until this is disabled.
```yaml
- name: follow
  player_name: magahet
```


# Other Fun Stuff

### Mob Spawner Clusters

Peon keeps track of all the interesting blocks in the world, including mob spawners and end portal blocks. This makes him useful for finding strongholds or good places to build spawner xp farms. In addition, he also has the ability to find clusters of mob spawners. This is done using cluster analysis to find groups of spawners with a centroid 16m or less to each spawner.

```python
bot.world.block_entities
bot.world.get_mob_spawner_clusters()
```


### Excavate

Peon can clear an area of all solid blocks. The function takes two tuples of (x, y, z) and will clear everything within the bounding box defined by those points. This works both on the surface and underground. As with mining and all such digging, peon will not break any blocks that are adjacent to liquid (water and lava) or below a falling block (sand and gravel).

```python
bot.excavate((1, 1, 1), (5, 5, 5))
```

This will clear out everything from 1 to 5 on the x, y, and z axises. You can also specify a list of block types to ignore when excavating:

```python
bot.excavate((1, 1, 1), (5, 5, 5), ignore=['Dirt', 'Grass Block'])
```


### Fill

This is the opposite of excavate. Peon will fill this area with a given block type, starting from the bottom.

```python
bot.fill((1, 1, 1), (5, 5, 5), block_type='Dirt')
```

Excavate and fill work well for clearing/flattening areas of land.

# TODO

So, so much. It would be great to get all the previous peon functionality going again. However, we all have real lives and there are only so many hours in a day. Here are some big items I'm working to get going again:

- clearing land
- farming
- trading
- building

# FAQ

### My bot died. How do I respawn?

autobot.py returns two objects, client and bot. Run this:

```python
client.respawn()
```
