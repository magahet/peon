from types import MobTypes


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
