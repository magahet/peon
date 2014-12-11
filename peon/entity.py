from types import (MobTypes, ObjectTypes)
import numpy as np
import utils


class BaseEntity(object):
    '''Prototype class with position methods'''

    def __init__(self, eid, x, y, z, pitch, yaw):
        self.eid = eid
        self.x = x
        self.y = y
        self.z = z
        self.pitch = pitch
        self.yaw = yaw

    @property
    def position(self):
        return (self.x, self.y, self.z)

    def get_position(self, dx=0, dy=0, dz=0, floor=False):
        if self.x is None:
            return (None, None, None)
        position = np.add((self.x, self.y, self.z), (dx, dy, dz))
        if floor:
            return tuple([int(i) for i in np.floor(position)])
        else:
            return tuple(position)

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


class Object(BaseEntity):
    '''Represents objects/dropped items'''

    def __init__(self, eid, _type, x, y, z, pitch, yaw, data):
        self._type = _type if isinstance(_type, int) else ObjectTypes.get_id(_type)
        self.data = data
        self.metadata = {}
        super(Object, self).__init__(eid, x, y, z, pitch, yaw)

    def __repr__(self):
        return 'Object(eid={}, _type={}, xyx={})'.format(
            self.eid, ObjectTypes.get_name(self._type),
            self.get_position(floor=True))


class PlayerEntity(BaseEntity):
    '''Represents other players'''

    def __init__(self, eid, uuid, name, x, y, z, yaw, pitch, current_item,
                 metadata):
        self.uuid = uuid
        self.name = name
        self.current_item = current_item
        self.metadata = metadata
        self.name = None
        super(PlayerEntity, self).__init__(eid, x, y, z, pitch, yaw)

    def __repr__(self):
        return 'PlayerEntity(eid={}, name={}, xyz={})'.format(
            self.eid, self.name, self.get_position(floor=True))


class Entity(BaseEntity):
    '''Represents mobs'''

    def __init__(self, eid, _type, x, y, z, pitch, head_pitch, yaw,
                 velocity_x, velocity_y, velocity_z, metadata):
        self._type = _type if isinstance(_type, int) else MobTypes.get_id(_type)
        self.head_pitch = head_pitch
        self.velocity_x = velocity_x
        self.velocity_y = velocity_y
        self.velocity_z = velocity_z
        self.metadata = metadata
        super(Entity, self).__init__(eid, x, y, z, pitch, yaw)

    def __repr__(self):
        return 'Entity(eid={}, _type={}, xyz={})'.format(
            self.eid, MobTypes.get_name(self._type), self.get_position(floor=True))


class BlockEntity(object):
    def __init__(self, location, data):
        self.location = location
        self.data = utils.unpack_nbt(data[1])
        self._type = self.data.get('id')

    def __repr__(self):
        return 'BlockEntity(location={}, type={}, data={})'.format(
            self.location, self._type, self.data)

    def __contains__(self, other):
        return other in self.data.keys()

    def get(self, key):
        return self.data.get(key)

    def keys(self):
        return self.data.keys()

    def iteritems(self):
        for key in self.data.keys():
            yield (key, self.data.get(key))

    def items(self):
        return [t for t in self.iteritems]
