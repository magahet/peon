Peon
====

Peon is a minecraft bot written in python. It acts as a replacement for the minecraft client and allows for automation of tasks in the minecraft world. The bot can hunt, mine, gather, defend, eat, etc. He has efficient path finding both for movement and digging.

This version of peon uses fastmc and works with Mincraft 1.8.


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

## Auto Actions

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

Example config:

```
- name: hunt
  mob_types: ['Sheep', 'Zombie']   # list of mobs to hunt
  _range: 20                       # how far from home to hunt
```


### Gather

He will search for objects of a given type and go collect them.

Example config:

```
- name: gather
  args:                     # gather takes one argument, a list of items to gather
    - ['Stone', 'Sand']     # list of items to gather
  _range: 20                # how far from home to search
```


### Mine

Finds, digs to, and mines given block types. He has perfect knowledge of the world, so he digs straight to the resources. There's no searching involved.

Example config:

```
- name: mine
  block_types:
    - Diamond Ore
    - Gold Ore
    - Iron Ore
```


# TODO

So, so much. It would be great to get all the previous peon functionality going again. However, we all have real lives and there are only so many hours in a day. Here are some big items I'm working to get going again:

- clearing land
- exploring/searching for world features or biomes
- farming
- trading
- building
