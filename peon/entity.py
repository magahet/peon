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


class Entity(object):

    def __init__(self, eid, _type, x, y, z, pitch, head_pitch, yaw,
                 velocity_x, velocity_y, velocity_z, metadata):
        self.eid = eid
        self._type = _type if isinstance(_type, int) else MobTypes.get_id(_type)
        self.x = x
        self.y = y
        self.z = z
        self.pitch = pitch
        self.head_pitch = head_pitch
        self.yaw = yaw
        self.velocity_x = velocity_x
        self.velocity_y = velocity_y
        self.velocity_z = velocity_z
        self.metadata = metadata

    def __repr__(self):
        return 'Entity(eid={}, _type={}, x={}, y={}, z={})'.format(
            self.eid, MobTypes.get_name(self._type), self.x, self.y, self.z)

    def move(self, dx, dy, dz):
        self.x += dx
        self.y += dy
        self.z += dz

    def look(self, yaw, pitch):
        self.yaw = yaw
        self.pitch = pitch

    def teleport(self, x, y, z, yaw, pitch):
        self.x = x
        self.y = y
        self.z = z
        self.yaw = yaw
        self.pitch = pitch
