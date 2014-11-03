from entity import MobTypes


class World(object):
    def __init__(self):
        self.entities = {}
        self.chunks = {}

    def iter_entities(self, _type=None):
        _type = _type if isinstance(_type, int) else MobTypes.get_id(_type)
        for entity in self.entities.values():
            if _type is None or entity._type == _type:
                yield entity
