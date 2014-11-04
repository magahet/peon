import csv
import blocktypes
from cStringIO import StringIO


class MobTypes(object):
    types = (
        (48, 'Mob'),
        (49, 'Monster'),
        (50, 'Creeper'),
        (51, 'Skeleton'),
        (52, 'Spider'),
        (53, 'Giant Zombie'),
        (54, 'Zombie'),
        (55, 'Slime'),
        (56, 'Ghast'),
        (57, 'Zombie Pigman'),
        (58, 'Enderman'),
        (59, 'Cave Spider'),
        (60, 'Silverfish'),
        (61, 'Blaze'),
        (62, 'Magma Cube'),
        (63, 'Ender Dragon'),
        (64, 'Wither'),
        (65, 'Bat'),
        (66, 'Witch'),
        (67, 'Endermite'),
        (68, 'Guardian'),
        (90, 'Pig'),
        (91, 'Sheep'),
        (92, 'Cow'),
        (93, 'Chicken'),
        (94, 'Squid'),
        (95, 'Wolf'),
        (96, 'Mooshroom'),
        (97, 'Snowman'),
        (98, 'Ocelot'),
        (99, 'Iron Golem'),
        (100, 'Horse'),
        (101, 'Rabbit'),
        (120, 'Villager'),
    )

    @classmethod
    def get_id(cls, name_query):
        for _id, name in cls.types:
            if name == name_query:
                return _id

    @classmethod
    def get_name(cls, id_query):
        for _id, name in cls.types:
            if _id == id_query:
                return name


class BlockTypes(object):
    types = []
    for row in csv.reader(StringIO(blocktypes.types), delimiter='\t'):
        types.append(tuple([int(e) if e.isdigit() else e for e in row]))
    types = tuple(types)

    @classmethod
    def get_id(cls, name_query):
        for _id, meta, name, meta_name in cls.types:
            if name == name_query:
                return _id, meta

    @classmethod
    def get_name(cls, id_query, meta_query=0):
        for _id, meta, name, meta_name in cls.types:
            if _id == id_query and meta == meta_query:
                return name
