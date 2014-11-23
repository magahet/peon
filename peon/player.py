import time
from scipy.spatial.distance import euclidean
from fastmc.proto import Slot
import numpy as np
import math
from math import floor
import threading
import itertools
import logging
from fastmc.proto import Position


log = logging.getLogger(__name__)


class Player(object):

    def __init__(self, proto, send_queue, recv_condition, world):
        self.proto = proto
        self._send_queue = send_queue
        self._recv_condition = recv_condition
        self.x = None
        self.y = None
        self.z = None
        self.yaw = None
        self.pitch = None
        self.health = None
        self.food = None
        self.food_saturation = 0
        self._xp_bar = -1
        self._xp_total = -1
        self.xp_level = -1
        self._available_enchantments = {}
        self._open_window_id = 0
        self._held_slot_num = 0
        self._held_slot_cycle = itertools.cycle(range(10))
        self._cursor_slot = Slot(-1, None, None, None)
        self.windows = {}
        self.world = world
        self.on_ground = True
        self._is_moving = threading.Event()
        self._position_update_lock = threading.Lock()
        self.move_corrected_by_server = threading.Event()

    def _wait_for(self, what, timeout=10):
        if what():
            return True
        start = time.time()
        with self._recv_condition:
            while not what() and time.time() - start < timeout:
                self._recv_condition.wait(timeout=0.1)
        return what()

    def _send(self, packet_id, **kwargs):
        self._send_queue.put((packet_id, kwargs))

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

    @property
    def held_item(self):
        inventory = self.inventory
        if inventory is None:
            return None
        held = inventory.held
        return held[self._held_slot_num]

    @property
    def inventory(self):
        return self.windows.get(0)

    @property
    def open_window(self):
        return self.windows.get(self._open_window_id)

    def navigate_to(self, x, y, z, speed=10, space=0, timeout=10):
        x0, y0, z0 = self.get_position(floor=True)
        x, y, z = floor(x), floor(y), floor(z)
        log.debug('navigating from %s to %s.', str((x0, y0, z0)), str((x, y, z)))
        if euclidean((x0, y0, z0), (x, y, z)) <= space:
            return True
        path = self.world.find_path(x0, y0, z0, x, y, z, space=space, timeout=timeout)
        if not path:
            return False
        return self.follow_path(path)

    def follow_path(self, path, speed=10):
        log.debug('following path: %s', str(path))
        for x, y, z in path:
            if not self.move_to(x, y, z, speed=speed, center=True):
                log.error("can't move to: %s", str((x, y, z)))
                return False
        return True

    def move_to(self, x, y, z, speed=10, center=False):
        def abs_min(n, delta):
            if n < 0:
                return max(n, -delta)
            else:
                return min(n, delta)

        if center:
            x = floor(x) + 0.5
            z = floor(z) + 0.5

        dt = 0.1
        delta = speed * dt
        self._is_moving.set()
        self.move_corrected_by_server.clear()
        while euclidean((x, y, z), self.get_position()) > 0.1:
            if self.move_corrected_by_server.is_set():
                self.move_corrected_by_server.clear()
                self._is_moving.clear()
                return False
            dx = x - self.x
            dy = y - self.y
            dz = z - self.z
            self.move(abs_min(dx, delta), abs_min(dy, delta), abs_min(dz, delta))
            time.sleep(dt)
        self._is_moving.clear()
        return True

    def move(self, dx=0, dy=0, dz=0):

        def calc_yaw(x0, z0, x, z):
            l = x - x0
            w = z - z0
            c = math.sqrt(l * l + w * w)
            if c == 0:
                return 0
            alpha1 = -math.asin(l / c) / math.pi * 180
            alpha2 = math.acos(w / c) / math.pi * 180
            if alpha2 > 90:
                return 180 - alpha1
            else:
                return alpha1

        with self._position_update_lock:
            self.yaw = calc_yaw(self.x, self.z, self.x + dx, self.z + dz)
            self.x += dx
            self.y += dy
            self.z += dz
            log.debug('moved to: %s', str(self.position))

    def teleport(self, x, y, z, yaw, pitch):
        self._position_update_lock.acquire()
        self.x = x
        self.y = y
        self.z = z
        self.yaw = yaw
        self.pitch = pitch
        self._position_update_lock.release()

    def iter_entities_in_range(self, types=None, reach=4):
        for entity in self.world.iter_entities(types=types):
            if euclidean((self.x, self.y, self.z),
                         (entity.x, entity.y, entity.z)) <= reach:
                yield entity

    def iter_objects_in_range(self, types=None, items=None, reach=10):
        for entity in self.world.iter_objects(types=types, items=items):
            if euclidean((self.x, self.y, self.z),
                         (entity.x, entity.y, entity.z)) <= reach:
                yield entity

    def get_closest_entity(self, types=None, limit=None):
        closest_entity, dist = None, None
        for entity in self.world.iter_entities(types=types):
            cur_dist = euclidean(self.position, (entity.x, entity.y, entity.z))
            if closest_entity is None or (cur_dist < limit and cur_dist < dist):
                closest_entity = entity
                dist = cur_dist
        return (closest_entity, dist)

    def equip_any_item_from_list(self, item_types):
        for _type in item_types:
            if self.equip_item(_type):
                return True
        return False

    def equip_item(self, item):
        if item == self.held_item:  # item already in hand
            return True
        elif item in self.inventory.held:  # item in held_items
            self.change_held_item(self.inventory.held.index(item))
        elif item in self.inventory:
            held_slot = self._held_slot_cycle.next()
            inventory_held_slot = self.inventory.count - 1 - held_slot
            if not self.inventory.swap_slots(inventory_held_slot,
                                             self.inventory.index(item)):
                return False
            held_index = self.inventory.held.index(item)
            if held_index is None:
                return False
            self.change_held_item(held_index)
        else:
            return False
        return self._wait_for(lambda: item == self.held_item)

    def change_held_item(self, slot_num):
        self._send(self.proto.PlayServerboundHeldItemChange.id,
                   slot=slot_num)

    def click_inventory_block(self, x, y, z):
        if self._open_window_id != 0:
            return False
        self._send(self.proto.PlayServerboundBlockPlacement.id,
                   location=Position(x, y, z),
                   direction=0,
                   held_item=None,
                   cursor_x=0,
                   cursor_y=0,
                   cursor_z=0)
        return (
            self._wait_for(lambda: self._open_window_id != 0) and
            self._wait_for(lambda: len(self.open_window.slots) > 0)
        )

    def close_window(self):
        self._send(self.proto.PlayServerboundCloseWindow.id,
                   window_id=self._open_window_id)
        for _id in self.windows.keys():
            if _id != 0:
                del self.windows[_id]
        self._open_window_id = 0
