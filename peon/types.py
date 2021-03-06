import os
import json


HOSTILE_MOBS = set(range(48, 65) + range(66, 69) + [93])
DANGER_BLOCKS = set([
    'Flowing Lava',
    'Still Lava'
    'Fire'
])
UNBREAKABLE_BLOCKS = set([
    'Bedrock',
])
LIQUID_BLOCKS = set([
    'Flowing Water',
    'Still Water',
    'Flowing Lava',
    'Still Lava',
])
FALLING_BLOCKS = set([
    'Sand',
    'Red Sand',
    'Gravel',
])
ORE = set([
    'Coal Ore',
    'Iron Ore',
    'Redstone Ore',
    'Lapis Lazuli Ore',
    'Gold Ore',
    'Diamond Ore',
    'Emerald Ore',
    'Nether Quartz Ore',
])
FOOD = set([
    'Cooked Porkchop',
    'Steak',
    'Cooked Mutton',
    'Cooked Salmon',
    'Baked Potato',
    'Cooked Chicken',
    'Cooked Rabbit',
    'Rabbit Stew',
    'Mushroom Stew',
    'Bread',
    'Cooked Fish',
    'Carrot',
    'Apple',
    'Melon',
    'Cookie',
])
ARMOR_MATERIAL = set([
    'Diamond',
    'Golden',
    'Iron',
    'Chain',
])
ARMOR = {
    5: 'Helmet',
    6: 'Chestplate',
    7: 'Leggings',
    8: 'Boots',
}
ENCHANT_ITEMS = set([
    'Diamond Helmet',
    'Diamond Chestplate',
    'Diamond Leggings',
    'Diamond Boots',
    'Diamond Sword',
    'Diamond Pickaxe',
    'Diamond Shovel',
    'Diamond Axe',
    'Diamond Hoe',
    'Bow',
    'Fishing Rod',
])
HARVESTABLE_BLOCKS = set([
    ('Wheat', 7),
    ('Carrot Crops', 7),
    ('Potato Crops', 7),
    ('Beetroot Crops', 7),
    ('Melon', 0),
    ('Pumpkin', 0),
])
DOORS = set([
    'Oak Door',
    'Spruce Door',
    'Birch Door',
    'Jungle Door',
    'Acacia Door',
    'Dark Oak Door',
    'Iron Door',
])
WOOD = set([
    'Wood',
    'Wood2',
])
TREES = set([
    'Oak Wood',
    'Spruce Wood',
    'Birch Wood',
    'Jungle Wood',
    'Acacia Wood',
    'Dark Oak Wood',
])
HALF_SLABS = set([44, 182, 126])
TRAP_DOORS = set([96, 167])


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
        return 'Unknown'


class ItemTypes(object):
    types_by_id = {}
    types_by_name = {}
    blocks_by_id = {}
    blocks_by_name = {}
    block_height = {}
    non_solid_types = set([])
    non_climbable_types = set([])
    doors = set([])
    with open(os.path.join(os.path.dirname(__file__), 'types.json')) as _file:
        types = json.load(_file)
    for _, data in types.iteritems():
        if 'blockID' in data:
            _id = data.get('blockID')
            name = data.get('name')
            blocks_by_id[_id] = name
            if name in DOORS:
                doors.add(_id)
            blocks_by_name[name] = _id
            if not data.get('solid', False):
                non_solid_types.add(_id)
            if not data.get('climbable', True):
                non_climbable_types.add(_id)
            if 'height' in data:
                block_height[_id] = data.get('height')
        types_by_id[(data.get('itemID'), None)] = data.get('name')
        types_by_name[data.get('name')] = (data.get('itemID'), None)
        if 'damageValues' in data:
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
    def get_block_name(cls, id_query):
        return cls.blocks_by_id.get(id_query)

    @classmethod
    def get_block_height(cls, id_query, damage_query=None):
        if id_query in HALF_SLABS and damage_query < 8:
            return 0.5
        elif id_query in TRAP_DOORS and damage_query >> 3 == 0:
            return 0.1875
        return cls.block_height.get(id_query, 1.0)

    @classmethod
    def get_block_id(cls, name_query):
        return cls.blocks_by_name.get(name_query)

    @classmethod
    def is_solid(cls, block_id):
        return block_id not in cls.non_solid_types

    @classmethod
    def is_door(cls, block_id):
        return block_id in cls.doors

    @classmethod
    def is_trap_door(cls, block_id):
        return block_id in TRAP_DOORS

    @classmethod
    def is_unbreakable(cls, block_id):
        name = cls.get_block_name(block_id)
        return name in UNBREAKABLE_BLOCKS

    @classmethod
    def is_liquid(cls, block_id):
        name = cls.get_block_name(block_id)
        return name in LIQUID_BLOCKS

    @classmethod
    def is_falling(cls, block_id):
        name = cls.get_block_name(block_id)
        return name in FALLING_BLOCKS

    @classmethod
    def is_harvestable(cls, block_id, meta):
        name = cls.get_block_name(block_id)
        if name in ('Pumpkin', 'Melon'):
            return True
        return (name, meta) in HARVESTABLE_BLOCKS

    @classmethod
    def is_safe_non_solid(cls, block_id):
        return (
            block_id in cls.non_solid_types and
            cls.blocks_by_name.get(block_id, '') not in DANGER_BLOCKS
        )

    @classmethod
    def is_breathable(cls, block_id):
        return (
            block_id in cls.non_solid_types and
            cls.get_block_name(block_id) not in LIQUID_BLOCKS
        )

    @classmethod
    def is_water(cls, block_id):
        return cls.get_block_name(block_id) == 'Still Water'

    @classmethod
    def is_climbable(cls, block_id):
        return (
            cls.is_solid(block_id) and
            block_id not in cls.non_climbable_types
        )


class InventoryTypes(object):
    types = {
        None: (
            ([0], "crafting output"),
            (range(1, 5), "crafting input"),
            (range(5, 9), "armor"),
            (range(9, 36), "main inventory"),
            (range(36, 45), "held items"),
        ),
        'minecraft:enchanting_table': (
            ([0], "enchantment slot"),
            ([1], "lapis slot"),
            (range(2, 29), "main inventory"),
            (range(29, 38), "held items"),
        ),
    }

    @classmethod
    def get_slot_description(cls, _type, slot_num):
        for _range, description in cls.types.get(_type, []):
            if slot_num in _range:
                return description


class ObjectTypes(object):
    types = (
        (1, 'Boat'),
        (2, 'Item Stack'),
        (10, 'Minecart'),
        (50, 'Activated TNT'),
        (51, 'EnderCrystal'),
        (60, 'Arrow'),
        (61, 'Snowball'),
        (62, 'Egg'),
        (63, 'FireBall'),
        (64, 'FireCharge'),
        (65, 'Thrown Enderpearl'),
        (66, 'Wither Skull'),
        (70, 'Falling Objects'),
        (71, 'Item frames'),
        (72, 'Eye of Ender'),
        (73, 'Thrown Potion'),
        (74, 'Falling Dragon Egg'),
        (75, 'Thrown Exp Bottle'),
        (76, 'Firework Rocket'),
        (77, 'Leash Knot'),
        (78, 'ArmorStand'),
        (90, 'Fishing Float'),
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
        return 'Unknown'


class Door(object):
    def __init__(self, _id, meta):
        self._id = _id
        self._meta = meta

    def is_open(self):
        return self._meta >> 2 == 0


class TrapDoor(object):
    def __init__(self, _id, meta):
        self._id = _id
        self._meta = meta

    def is_open(self):
        return self._meta >> 2 == 0

    def on_bottom(self):
        return self._meta >> 3 == 0
