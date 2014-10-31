from scipy.spatial.distance import euclidean


class Player(object):

    def __init__(self, x, y, z, yaw, pitch, world):
        self.world = world
        self.teleport(x, y, z, yaw, pitch)

    def __repr__(self):
        return 'Player(x={}, y={}, z={})'.format(self.x, self.y, self.z)

    def teleport(self, x, y, z, yaw, pitch):
        self.x = x
        self.y = y
        self.z = z
        self.yaw = yaw
        self.pitch = pitch

    def iter_entities_in_range(self, _type=None, reach=4):
        for entity in self.world.iter_entities(_type=_type):
            if euclidean((self.x, self.y, self.z),
                         (entity.x, entity.y, entity.z)) <= reach:
                yield entity
