import time
from scipy.spatial.distance import euclidean
from fastmc.proto import (Slot, Position)
import numpy as np
from math import floor
import threading
import types
import itertools
import logging


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
        self._health = None
        self._food = None
        self._food_saturation = 0
        self._xp_bar = -1
        self._xp_level = -1
        self._xp_total = -1
        self._available_enchantments = {}
        self._open_window_id = 0
        self._held_slot_num = 0
        self._held_slot_cycle = itertools.cycle(range(10))
        self._cursor_slot = Slot(-1, None, None, None)
        self.windows = {}
        self.world = world
        self.on_ground = True
        self._is_moving = threading.Event()
        self._move_lock = threading.Lock()
        self.move_corrected_by_server = threading.Event()
        self._action_lock = threading.Lock()
        self._auto_actions = {
            'defend': threading.Event(),
            'eat': threading.Event(),
            'hunt': threading.Event(),
        }
        self.auto_defend_mob_types = types.HOSTILE_MOBS
        self._auto_eat = threading.Event()
        self._auto_eat_level = 18
        self.auto_hunt_settings = {}
        self._threads = {}
        self._thread_funcs = {
            'falling': self._do_falling,
            'auto_defend': self._do_auto_defend,
            'auto_eat': self._do_auto_eat,
            'auto_hunt': self._do_auto_hunt,
        }
        self._active_threads = set(self._thread_funcs.keys())
        self.start_threads()

    def _wait_for(self, what, timeout=10):
        start = time.time()
        with self._recv_condition:
            while not what() and time.time() - start < timeout:
                self._recv_condition.wait(timeout=1)
        return what()

    def start_threads(self):
        for name, func in self._thread_funcs.iteritems():
            thread = threading.Thread(target=func, name=name)
            thread.daemon = True
            thread.start()
            self._threads[name] = thread

    def _do_falling(self):
        while True:
            if self._is_moving.is_set():
                continue
            pos = self.position
            if None in pos:
                continue
            x, y, z = pos
            standing = self.world.is_solid_block(x, y - 1, z)
            if standing is None or standing:
                continue
            next_pos = self.world.get_next_highest_solid_block(x, y, z)
            if next_pos is None:
                continue
            self.on_ground = False
            x, y, z = next_pos
            self.on_ground = self.move_to(x, y + 1, z, speed=13)
            time.sleep(0.1)

    def _do_auto_defend(self):
        auto_defend = self._auto_actions.get('defend')
        while True:
            auto_defend.wait()
            eids_in_range = [e.eid for e in self.iter_entities_in_range(
                self.auto_defend_mob_types)]
            if not eids_in_range:
                time.sleep(0.1)
                continue
            with self._action_lock:
                self.equip_any_item_from_list([
                    'Diamond Sword',
                    'Golden Sword',
                    'Iron Sword',
                    'Stone Sword',
                    'Wooden Sword',
                ])
                for eid in eids_in_range:
                    self._send(self.proto.PlayServerboundUseEntity.id,
                               target=eid,
                               type=1
                               )
            time.sleep(0.1)

    def _do_auto_eat(self):
        auto_eat = self._auto_actions.get('eat')
        self._wait_for(lambda: None not in (self.inventory, self._food))
        while True:
            auto_eat.wait()
            if self._food < self._auto_eat_level:
                if not self.eat(self._auto_eat_level):
                    log.warn('Hungry, but no food!')
            time.sleep(10)

    def _do_auto_hunt(self):
        auto_hunt = self._auto_actions.get('hunt')
        self._wait_for(
            lambda: None not in (self.inventory, self._food, self._health))
        while True:
            auto_hunt.wait()
            self.hunt(**self.auto_hunt_settings)
            time.sleep(1)

    def _send(self, packet_id, **kwargs):
        self._send_queue.put((packet_id, kwargs))

    def __repr__(self):
        return 'Player(x={}, y={}, z={})'.format(self.x, self.y, self.z)

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

    def navigate_to(self, x, y, z, speed=10, space=0, timeout=10):
        x0, y0, z0 = self.get_position(floor=True)
        x, y, z = floor(x), floor(y), floor(z)
        log.debug('navigating from %s to %s.', str((x0, y0, z0)), str((x, y, z)))
        if (x0, y0, z0) == (x, y, z):
            return True
        path = self.world.find_path(x0, y0, z0, x, y, z, space=space, timeout=timeout)
        if not path:
            return False
        return self.follow_path(path)

    def follow_path(self, path, speed=10):
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
        with self._move_lock:
            self.x += dx
            self.y += dy
            self.z += dz

    def teleport(self, x, y, z, yaw, pitch):
        self._move_lock.acquire()
        self.x = x
        self.y = y
        self.z = z
        self.yaw = yaw
        self.pitch = pitch
        self._move_lock.release()

    def iter_entities_in_range(self, types=None, reach=4):
        for entity in self.world.iter_entities(types=types):
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

    def enable_auto_action(self, name):
        auto_action = self._auto_actions.get(name)
        if auto_action is None:
            return False
        auto_action.set()
        return True

    def disable_auto_action(self, name):
        auto_action = self._auto_actions.get(name)
        if auto_action is None:
            return False
        auto_action.clear()
        return True

    def set_auto_defend_mob_types(self, mob_types):
        self.auto_defend_mob_types = mob_types

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

    def eat(self, target=20):
        if self._food >= target:
            return True
        with self._action_lock:
            if not self.equip_any_item_from_list(types.FOOD):
                return False
            log.info('Eating: %s', self.held_item.name)
            while self.held_item is not None and self._food < target:
                count = self.held_item.count
                self._send(self.proto.PlayServerboundBlockPlacement.id,
                           location=Position(-1, 255, -1),
                           direction=-1,
                           held_item=self.held_item,
                           cursor_x=-1,
                           cursor_y=-1,
                           cursor_z=-1)
                self._wait_for(
                    lambda: (
                        self.held_item is None or
                        self.held_item.count < count
                    )
                )
            self._send(self.proto.PlayServerboundPlayerDigging.id,
                       status=5,
                       location=Position(0, 0, 0),
                       face=127)
        return self._food >= target

    def hunt(self, home=None, mob_types=None, space=3, speed=10, _range=50):
        if not self._health or self._health <= 10:
            log.warn('health unknown or too low: %s', self._health)
            return False
        home = self.get_position(floor=True) if home is None else home
        if not self.navigate_to(*home, timeout=30):
            log.warn('failed nav to home')
            return False
        self.enable_auto_action('defend')
        if mob_types is None:
            mob_types = types.HOSTILE_MOBS
        for entity in self.iter_entities_in_range(mob_types, reach=_range):
            log.info("hunting entity: %s", str(entity))
            x0, y0, z0 = self.get_position(floor=True)
            x, y, z = entity.get_position(floor=True)
            path = self.world.find_path(x0, y0, z0, x, y, z, space=space, timeout=30)
            if path:
                break
        else:
            return False
        self.follow_path(path)
        self.attack_entity(entity)
        self.navigate_to(*path[-1])
        path.reverse()
        path.append(home)
        self.follow_path(path)
        return self.navigate_to(*home, timeout=30)

    def attack_entity(self, entity, space=3, timeout=6):
        on_kill_list = entity._type in self.auto_defend_mob_types
        if not on_kill_list:
            self.auto_defend_mob_types.add(entity._type)
        start = time.time()
        while self._health > 10 and entity.eid in self.world.entities:
            x, y, z = entity.get_position(floor=True)
            if not self.navigate_to(x, y, z, space=space, timeout=2):
                break
            elif time.time() - start > timeout:
                break
            time.sleep(0.1)
        if not on_kill_list:
            self.auto_defend_mob_types.remove(entity._type)
