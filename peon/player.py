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
import types


log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


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
        self._move_lock = threading.RLock()
        self._inventory_lock = threading.RLock()
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
        return self.get_position(floor=True)

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
        x0, y0, z0 = self.position
        distance = euclidean(self.position, (x, y, z))
        if distance <= space:
            return True
        log.debug('navigating from %s to %s.', str((x0, y0, z0)),
                  str((x, y, z)))
        with self._move_lock:
            while distance > space:
                space_b = min(space, 100)
                path = self.world.find_path(x0, y0, z0, x, y, z, space=space_b,
                                            timeout=timeout)
                log.debug('path: %s', str(path))
                if not path:
                    return False
                if not self.follow_path(path):
                    return False
                distance = euclidean(self.position, (x, y, z))
        return True

    def dig_to(self, x, y, z, speed=10, space=0, timeout=10):
        x0, y0, z0 = self.get_position(floor=True)
        x, y, z = floor(x), floor(y), floor(z)
        log.debug('digging from %s to %s.', str((x0, y0, z0)), str((x, y, z)))
        distance = euclidean((x0, y0, z0), (x, y, z))
        if distance <= space:
            return True
        with self._move_lock:
            while distance > space:
                space_b = min(space, 100)
                path = self.world.find_path(x0, y0, z0, x, y, z, space=space_b,
                                            timeout=timeout, digging=True)
                log.debug('path: %s', str(path))
                if not path:
                    return False
                if not self.follow_path(path, digging=True):
                    return False
                distance = euclidean(self.position, (x, y, z))
        return True

    def follow_path(self, path, speed=10, digging=False):
        log.debug('following path: %s', str(path))
        with self._move_lock:
            x0, y0, z0 = self.get_position(floor=True)
            for num, (x, y, z) in enumerate(path):
                if digging:
                    if num > 0:
                        x0, y0, z0 = path[num - 1]
                    break_set = self.world.get_blocks_to_break(
                        x0, y0, z0, x, y, z)
                    if not self.break_all_blocks(break_set):
                        log.info('could not break all the blocks: %s',
                                 str(break_set))
                        return False
                if num > 0:
                    x0, y0, z0 = path[num - 1]
                if not self.world.is_moveable(x0, y0, z0, x, y, z):
                    log.info('position is not moveable: %s',
                             str((x0, y0, z0, x, y, z)))
                    return False
                if not self.move_to(x, y, z, speed=speed, center=True):
                    log.info('could not move to: %s', str((x, y, z)))
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
        with self._move_lock:
            while euclidean((x, y, z), self.get_position()) > 0.1:
                dx = x - self.x
                dy = y - self.y
                dz = z - self.z
                target = (abs_min(
                    dx, delta), abs_min(dy, delta), abs_min(dz, delta))
                self.move(*target)
                time.sleep(dt)
                if self.move_corrected_by_server.is_set():
                    self.move_corrected_by_server.clear()
                    self._is_moving.clear()
                    log.error("can't move from: %s to: %s", str(self.position),
                              str(target))
                    return False
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
        with self._position_update_lock:
            self.x = x
            self.y = y
            self.z = z
            self.yaw = yaw
            self.pitch = pitch

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
        with self._inventory_lock:
            if item == self.held_item:  # item already in hand
                return True
            elif item in self.inventory.held:  # item in held_items
                self.change_held_item(self.inventory.held.index(item,
                                                                relative=True))
            elif item in self.inventory:
                held_slot = self._held_slot_cycle.next()
                inventory_held_slot = len(self.inventory.slots) - 1 - held_slot
                if not self.inventory.swap_slots(inventory_held_slot,
                                                 self.inventory.index(item)):
                    return False
                held_index = self.inventory.held.index(item, relative=True)
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

    def break_block(self, x, y, z):

        def is_changed():
            name = self.world.get_name(x, y, z)
            return name != block_name or name == 'Air'

        x, y, z = int(x), int(y), int(z)  # TODO figure out why this is needed
        log.debug('breaking block: (%d, %d, %d)', x, y, z)
        block_name = self.world.get_name(x, y, z)
        if block_name == 'Air':
            return True
        with self._inventory_lock:
            if (self.world.is_falling_block(x, y, z) or
                    block_name in ('Dirt', 'Grass Block')):
                if not self.equip_any_item_from_list([
                    'Diamond Shovel',
                    'Golden Shovel',
                    'Iron Shovel',
                    'Stone Shovel',
                    'Wooden Shovel',
                ]):
                    log.info('No shovels to use')
            elif block_name in types.WOOD:
                if not self.equip_any_item_from_list([
                    'Diamond Axe',
                    'Golden Axe',
                    'Iron Axe',
                    'Stone Axe',
                    'Wooden Axe',
                ]):
                    log.info('No axes to use')
            else:
                if not self.equip_any_item_from_list([
                    'Diamond Pickaxe',
                    'Golden Pickaxe',
                    'Iron Pickaxe',
                    'Stone Pickaxe',
                    'Wooden Pickaxe',
                ]):
                    log.info('No pickaxes to use')
            self._send(self.proto.PlayServerboundPlayerDigging.id,
                       status=0,
                       location=Position(x, y, z),
                       face=1)
            self._send(self.proto.PlayServerboundPlayerDigging.id,
                       status=2,
                       location=Position(x, y, z),
                       face=1)
            result = self._wait_for(is_changed, timeout=10)
        if not result:
            log.info('could not break block: %s', str((x, y, z)))
        return result

    def break_all_blocks(self, blocks):
        tries = 0
        while blocks and tries < 5:
            tries += 1
            blocks = [b for b in blocks if self.world.is_solid_block(*b)]
            for block in blocks:
                self.break_block(*block)
        return not bool(blocks)

    def place_block(self, x, y, z, block_type):
        def get_direction(p1, p2):
            delta = (p2[i] - p1[i] for i in len(p1))
            direction_map = {
                (0, 1, 0): 0,
                (0, -1, 0): 1,
                (0, 0, 1): 2,
                (0, 0, -1): 3,
                (1, 0, 0): 4,
                (-1, 0, 0): 5,
            }
            return direction_map.get(delta)

        x, y, z = int(x), int(y), int(z)
        log.debug('placing block: (%d, %d, %d)', x, y, z)
        block_name = self.world.get_name(x, y, z)
        if block_name != 'Air':
            return False
        with self._inventory_lock:
            if not self.equip_item(block_type):
                return False
            if self.held_item is None:
                held_item = None
            else:
                held_item = self.held_item.as_fastmc()
            for neighbor in self.world.iter_adjacent(x, y, z, degrees=1):
                if self.world.is_solid_block(*neighbor):
                    break
            else:
                return False
            self._send(self.proto.PlayServerboundBlockPlacement.id,
                       location=Position(x, y, z),
                       direction=get_direction((x, y, z), neighbor),
                       held_item=held_item,
                       cursor_x=64,
                       cursor_y=64,
                       cursor_z=64)
            result = self._wait_for(
                lambda: self.world.get_name(x, y, z) == block_type, timeout=1)
        if not result:
            log.info('could not place block: %s', str((x, y, z)))
        return result
