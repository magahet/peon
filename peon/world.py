from types import (MobTypes, ItemTypes)
import smpmap


class World(smpmap.World):
    def __init__(self):
        self.columns = {}
        self.entities = {}

    def iter_entities(self, types=None):
        if isinstance(types, list):
            type_ids = [t if isinstance(t, int)
                        else MobTypes.get_id(t)
                        for t in types]
        for entity in self.entities.values():
            if types is None or entity._type in type_ids:
                yield entity

    def is_solid_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return None if _type is None else ItemTypes.is_solid(_type)

    def get_next_highest_solid_block(self, x, y, z):
        for y in xrange(int(y), -1, -1):
            if self.is_solid_block(x, y, z):
                return (x, y, z)
