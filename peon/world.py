from scipy.spatial.distance import euclidean
from math import floor
import smpmap
import astar
from types import (MobTypes, ItemTypes, ObjectTypes)
from window import Slot


class World(smpmap.World):
    def __init__(self):
        self.columns = {}
        self.entities = {}
        self.objects = {}
        self.dimmension = 0

    def iter_entities(self, types=None):
        if isinstance(types, list):
            types = [t if isinstance(t, int)
                     else MobTypes.get_id(t)
                     for t in types]
        for entity in self.entities.values():
            if types is None or entity._type in types:
                yield entity

    def iter_objects(self, types=None, items=None):
        if isinstance(types, list):
            types = [t if isinstance(t, int)
                     else ObjectTypes.get_id(t)
                     for t in types]
        if isinstance(items, list):
            items = [i if isinstance(i, basestring)
                     else ItemTypes.get_name(*i)
                     for i in items]
        for obj in self.objects.values():
            if types is None or obj._type in types:
                if ObjectTypes.get_name(obj._type) == 'Item Stack':
                    slot = Slot(obj.metadata.get(10, (None, None))[1])
                    if items is None or slot.name in items:
                        yield obj
                else:
                    yield obj

    def is_solid_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return None if _type is None else ItemTypes.is_solid(_type)

    def is_climbable_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return None if _type is None else ItemTypes.is_climbable(_type)

    def is_breathable_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return None if _type is None else ItemTypes.is_breathable(_type)

    def is_safe_non_solid_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return None if _type is None else ItemTypes.is_safe_non_solid(_type)

    def get_next_highest_solid_block(self, x, y, z):
        for y in xrange(int(y), -1, -1):
            if self.is_solid_block(x, y, z):
                return (x, y, z)

    @staticmethod
    def iter_adjacent(x, y, z):
        for dx in xrange(-1, 2):
            for dy in xrange(-1, 2):
                for dz in xrange(-1, 2):
                    if dx != 0 or dz != 0:
                        yield (x + dx, y + dy, z + dz)

    def iter_moveable_adjacent(self, x0, y0, z0):
        for x, y, z in self.iter_adjacent(x0, y0, z0):
            if self.is_moveable(x0, y0, z0, x, y, z):
                yield (x, y, z)

    def is_moveable(self, x0, y0, z0, x, y, z, with_floor=True):
        # check target spot
        if with_floor:
            if not self.is_standable(x, y, z):
                return False
        else:
            if not self.is_passable(x, y, z):
                return False

        if y > y0:
            return self.is_moveable(x0, y, z0, x, y, z)
        elif y < y0:
            return self.is_moveable(x0, y0, z0, x, y0, z, with_floor=False)

        # check if horizontal x z movement
        if x0 == x or z0 == z:
            return True

        # check diagonal x z movement
        return all([
            self.is_safe_non_solid_block(x0, y, z),
            self.is_safe_non_solid_block(x, y, z0),
        ])

    def is_standable(self, x, y, z):
        return all([
            self.is_breathable_block(x, y + 1, z),
            self.is_safe_non_solid_block(x, y + 1, z),
            self.is_safe_non_solid_block(x, y, z),
            self.is_climbable_block(x, y - 1, z),
        ])

    def is_passable(self, x, y, z):
        return all([
            self.is_safe_non_solid_block(x, y + 1, z),
            self.is_safe_non_solid_block(x, y, z),
        ])

    def find_path(self, x0, y0, z0, x, y, z, space=0, timeout=10, debug=None):

        def iter_moveable_adjacent(pos):
            return self.iter_moveable_adjacent(*pos)

        return astar.astar(
            (floor(x0), floor(y0), floor(z0)),              # start_pos
            iter_moveable_adjacent,                         # neighbors
            lambda p: euclidean(p, (x, y, z)) <= space,     # at_goal
            0,                                              # start_g
            lambda p1, p2: euclidean(p1, p2),               # cost
            lambda p: euclidean(p, (x, y, z)),              # heuristic
            timeout,                                        # timeout
            debug                                           # debug
        )
