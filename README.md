Peon
====

**WARNING: Peon currently supports minecraft 1.2.5 packet protocol.**

This is fairly old, so practical use will require updates be made. Please submit a pull request if you do this. I'd love to revive peon to it's former glory.**



Description
-----------

Peon is a minecraft bot writen in python. It acts as a replacement for the minecraft client and allows for automation of tasks in the minecraft world.



Componants
----------

## mc.py

mc.py defines the minecraft packet protocol. It provides handlers for the various server packets received and provides methods for sending client packets for all the actions available in the game.

## peon.py

peon.py is the bot code. It coordinates the 

## scrap.py

scrap.py contains higher level tasks including teraforming, farming, crafting, etc. It also is home to experimental code.



Usage
-----
    $ ./peon.py -h
    Usage: peon.py [options]

    Options:
      -h, --help            show this help message and exit
      -s SERVER, --server=SERVER
                            server
      -P PORT, --port=PORT  port
      -u USER, --user=USER  user to login as
      -p PASSWORD, --pass=PASSWORD
                            password
      -b BBOX, --bbox=BBOX  digging bbox
      -r BASE, --return-base=BASE
                            base to return to for better tools
      -v, --verbose         Increase verbosity (specify multiple times for more)
