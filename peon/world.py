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

    def get_next_highest_solid_block(self, x, y, z):
        for y in xrange(y, -1, -1):
            _type = self.get_id(x, y, z)
            if ItemTypes.is_solid(_type):
                return (x, y, z), _type
