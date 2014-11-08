import time
from scipy.spatial.distance import euclidean
from fastmc.proto import Slot
import numpy as np


class Player(object):

    def __init__(self, world):
        self.x = None
        self.y = None
        self.z = None
        self.yaw = None
        self.pitch = None
        self._health = 0
        self._food = 0
        self._food_saturation = 0
        self._xp_bar = -1
        self._xp_level = -1
        self._xp_total = -1
        self._available_enchantments = {}
        self._open_window_id = 0
        self._held_slot_num = 0
        self._cursor_slot = Slot(-1, None, None, None)
        self.windows = {}
        self.world = world
        self.on_ground = True

    def __repr__(self):
        return 'Player(x={}, y={}, z={})'.format(self.x, self.y, self.z)

    @property
    def position(self):
        return (self.x, self.y, self.z)

    def get_position(self, dx=0, dy=0, dz=0, floor=False):
        position = np.add((self.x, self.y, self.z), (dx, dy, dz))
        if floor:
            return tuple([int(i) for i in np.floor(position)])
        else:
            return tuple(position)

    @property
    def held_item(self):
        inventory = self.inventory
        if inventory is not None:
            held = inventory.get_held()
        return held[self._held_slot_num]

    @property
    def inventory(self):
        return self.windows.get(0)

    def move_to(self, x, y, z, speed=10):
        def abs_min(n, delta):
            if n < 0:
                return max(n, -delta)
            else:
                return min(n, delta)

        x += 0.5
        z += 0.5
        dt = 0.1
        delta = speed * dt
        while euclidean((x, y, z), self.get_position()) > 0.1:
            dx = x - self.x
            dy = y - self.y
            dz = z - self.z
            self.move(abs_min(dx, delta), abs_min(dy, delta), abs_min(dz, delta))
            time.sleep(dt)

    def move(self, dx=0, dy=0, dz=0):
        self.x += dx
        self.y += dy
        self.z += dz

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
