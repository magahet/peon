import os
import json


HOSTILE_MOBS = set(range(48, 65) + range(66, 69))
DANGER_BLOCKS = set([
    'Flowing Lava',
    'Still Lava'
])
LIQUID_BLOCKS = set([
    'Flowing Water',
    'Still Water',
    'Flowing Lava',
    'Still Lava',
])


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


class ItemTypes(object):
    types_by_id = {}
    types_by_name = {}
    blocks_by_id = {}
    blocks_by_name = {}
    solid_types = set([])
    non_climbable_types = set([])
    with open(os.path.join(os.path.dirname(__file__), 'types.json')) as _file:
        types = json.load(_file)
    for _, data in types.iteritems():
        if 'blockID' in data:
            blocks_by_id[data.get('blockID')] = data.get('name')
            blocks_by_name[data.get('name')] = data.get('blockID')
            if data.get('solid', False):
                solid_types.add(data.get('blockID'))
            if not data.get('climbable', True):
                non_climbable_types.add(data.get('blockID'))
        if 'damageValues' not in data:
            types_by_id[(data.get('itemID'), None)] = data.get('name')
            types_by_name[data.get('name')] = (data.get('itemID'), None)
        else:
            item_id = data.get('itemID')
            for damage_value, sub_data in data.get('damageValues', {}).iteritems():
                types_by_id[(item_id, int(damage_value))] = sub_data.get('name')
                types_by_name[sub_data.get('name')] = (item_id, int(damage_value))

    @classmethod
    def get_id(cls, name_query):
        return cls.types_by_name.get(name_query)

    @classmethod
    def get_name(cls, id_query, damage_query=None):
        return cls.types_by_id.get((id_query, damage_query),
                                   cls.types_by_id.get((id_query, None)))

    @classmethod
    def is_solid(cls, block_id):
        return block_id in cls.solid_types

    @classmethod
    def is_safe_non_solid(cls, block_id):
        return all([
            block_id not in cls.solid_types,
            cls.blocks_by_name.get(block_id, '') not in DANGER_BLOCKS,
        ])

    @classmethod
    def is_breathable(cls, block_id):
        return all([
            block_id not in cls.solid_types,
            cls.blocks_by_name.get(block_id, '') not in LIQUID_BLOCKS,
        ])

    @classmethod
    def is_climbable(cls, block_id):
        return all([
            cls.is_solid(block_id),
            block_id not in cls.non_climbable_types
        ])
