import threading
import time
import logging
import os
import signal
#import itertools
from contextlib import contextmanager
from player import Player
import types
from fastmc.proto import Position
from utils import LocksWrapper
from scipy.spatial.distance import euclidean


log = logging.getLogger(__name__)


class Robot(Player):

    def __init__(self, proto, send_queue, recv_condition, world):
        super(Robot, self).__init__(proto, send_queue, recv_condition, world)
        self._pre_enabled_auto_actions = ('fall', 'eat', 'defend')
        self._auto_eat_level = 18
        self._enabled_auto_actions = {}
        self._active_auto_actions = {}
        self._locks = {
            'movement': threading.Lock(),
            'inventory': threading.Lock(),
        }
        self._threads = {}
        self._thread_functions = {
            'escape': {
                'function': self.escape,
                'interval': 2,
            },
            'fall': {
                'function': self.fall,
                'locks': ['movement'],
            },
            'defend': {
                'function': self.defend,
                'locks': ['inventory'],
                'kwargs': {
                    'mob_types': types.HOSTILE_MOBS,
                }
            },
            'eat': {
                'function': self.eat,
                'locks': ['inventory'],
                'interval': 30,
            },
            'hunt': {
                'function': self.hunt,
                'locks': ['movement'],
                'interval': 2,
            },
            'gather': {
                'function': self.gather,
                'locks': ['movement'],
                'interval': 5,
                'args': [[]],
            },
            'store': {
                'function': self.store_items,
                'locks': ['movement', 'inventory'],
                'interval': 60,
                'args': [[]],
            },
            'drop': {
                'function': self.drop,
                'locks': ['movement', 'inventory'],
                'interval': 60,
                'args': [[]],
            },
            'harvest': {
                'function': self.harvest,
                'locks': ['movement'],
                'interval': 60,
            },
            'mine': {
                'function': self.mine,
                'locks': ['movement', 'inventory'],
                'interval': 1,
            },
            'enchant': {
                'function': self.enchant,
                'locks': ['movement', 'inventory'],
                'interval': 60,
                'kwargs': {
                    'types': types.ENCHANT_ITEMS
                },
            },
        }
        self.start_threads()
        self.state = ''
        self._last_health = 0
        self.unmineable = set([])

    def __repr__(self):
        template = ('Bot(xyz={}, health={}, food={}, xp={}, '
                    'enabled_auto_actions={}, active_auto_actions={})')
        return template.format(
            self.get_position(floor=True),
            self.health,
            self.food,
            self.xp_level,
            self.enabled_auto_actions,
            self.active_auto_actions,
        )

    @property
    def enabled_auto_actions(self):
        return [n for n, e in self._enabled_auto_actions.iteritems() if e.is_set()]

    @property
    def active_auto_actions(self):
        return [n for n, e in self._active_auto_actions.iteritems() if e.is_set()]

    def set_auto_settings(self, *args, **kwargs):
        name = args[0]
        if name not in self._thread_functions:
            return False
        self._thread_functions[name]['args'] = tuple(args[1:])
        self._thread_functions[name]['kwargs'] = kwargs

    def get_auto_settings(self, name):
        settings = self._thread_functions.get(name, {})
        return (settings.get('args', ()), settings.get('kwargs', {}))

    def start_threads(self):
        for name in self._thread_functions:
            if name not in self._enabled_auto_actions:
                self._enabled_auto_actions[name] = threading.Event()
                self._active_auto_actions[name] = threading.Event()
            if name in self._pre_enabled_auto_actions:
                self.enable_auto_action(name)
            thread = threading.Thread(target=self._do_auto_action, name=name,
                                      args=(name,))
            thread.daemon = True
            thread.start()
            self._threads[name] = thread

    def _do_auto_action(self, name):
        auto_event = self._enabled_auto_actions.get(name)
        self._wait_for(
            lambda: None not in (self.inventory, self.food, self.health))
        settings = self._thread_functions.get(name, {})
        function = settings.get('function')
        locks = settings.get('locks', ())
        lock = LocksWrapper({l: self._locks.get(l) for l in locks})
        interval = settings.get('interval', 0.1)
        while True:
            auto_event.wait()
            with lock:
                args, kwargs = self.get_auto_settings(name)
                self._active_auto_actions[name].set()
                function(*args, **kwargs)
                self._active_auto_actions[name].clear()
            time.sleep(interval)

    def fall(self):
        if self._is_moving.is_set():
            return
        pos = self.position
        if None in pos:
            return
        x, y, z = pos
        standing = self.world.is_solid_block(x, y - 1, z)
        if standing is None or standing:
            return
        next_pos = self.world.get_next_highest_solid_block(x, y, z)
        if next_pos is None:
            return
        self.on_ground = False
        x, y, z = next_pos
        self.on_ground = self.move_to(x, y + 1, z, speed=13)

    def defend(self, mob_types=None):
        if mob_types is None:
            return True
        eids_in_range = [e.eid for e in self.iter_entities_in_range(mob_types)]
        if not eids_in_range:
            return False
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
        return True

    def enable_auto_action(self, name):
        auto_action = self._enabled_auto_actions.get(name)
        if auto_action is None:
            return False
        auto_action.set()
        return True

    def disable_auto_action(self, name):
        auto_action = self._enabled_auto_actions.get(name)
        if auto_action is None:
            return False
        auto_action.clear()
        return True

    @property
    def auto_defend_mob_types(self):
        args, kwargs = self.get_auto_settings('defend')
        return kwargs.get('mob_types', set([]))

    def set_auto_defend_mob_types(self, mob_types):
        self.set_auto_settings('defend', mob_types=mob_types)

    @contextmanager
    def add_mob_types(self, mob_types):
        original_set = self.auto_defend_mob_types.copy()
        self.set_auto_settings('defend',
                               mob_types=original_set.union(mob_types))
        yield
        self.set_auto_settings('defend', mob_types=original_set)

    def eat(self, target=20):
        if self.food >= target:
            return True
        if not self.equip_any_item_from_list(types.FOOD):
            return False
        log.info('Eating: %s', self.held_item.name)
        while self.held_item is not None and self.food < target:
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
        return self.food >= target

    def hunt(self, home=None, mob_types=None, space=3, speed=10, _range=50):
        self.don_armor()
        self.enable_auto_action('defend')
        mob_types = () if mob_types is None else mob_types
        home = self.get_position(floor=True) if home is None else home
        if not self.navigate_to(*home, timeout=30):
            log.warn('failed nav to home')
            return False
        x0, y0, z0 = home
        for entity in self.iter_entities_in_range(mob_types, reach=_range):
            log.info("hunting entity: %s", str(entity))
            x, y, z = entity.get_position(floor=True)
            path = self.world.find_path(x0, y0, z0, x, y, z, space=space,
                                        timeout=10)
            if path:
                break
        else:
            return False
        with self.add_mob_types(mob_types):
            self.follow_path(path)
            self.follow_entity(entity, timeout=3)
            self.navigate_to(*path[-1])
            path.reverse()
            path.append(home)
            return self.follow_path(path)

    def gather(self, items, _range=50):
        x0, y0, z0 = self.get_position(floor=True)
        for _object in self.iter_objects_in_range(items=items, reach=_range):
            log.info("gathering object: %s", str(_object))
            x, y, z = _object.get_position(floor=True)
            path = self.world.find_path(x0, y0, z0, x, y, z, space=1)
            if path:
                break
        else:
            return False
        self.follow_path(path)
        path.reverse()
        path.append((x0, y0, z0))
        return self.follow_path(path)

    def follow_entity(self, entity, space=3, timeout=None):
        start = time.time()
        while entity.eid in self.world.entities:
            x, y, z = entity.get_position(floor=True)
            if not self.navigate_to(x, y, z, space=space, timeout=2):
                break
            elif timeout is not None and time.time() - start > timeout:
                break
            time.sleep(0.1)

    def don_armor(self):
        '''Put on best armor in inventory'''
        for slot_num, armor in types.ARMOR.iteritems():
            slot = self.inventory.slots[slot_num]
            if slot is not None:
                current_material, _, _ = slot.name.partition(' ')
            else:
                current_material = ''
            for material in types.ARMOR_MATERIAL:
                if current_material == material:
                    break
                armor_name = ' '.join([material, armor])
                if armor_name in self.inventory:
                    self.inventory.swap_slots(slot_num,
                                              self.inventory.index(armor_name))

    def move_to_player(self, player_name=None, eid=None, uuid=None):
        player_position = self.world.get_player_position(
            player_name=player_name, eid=eid, uuid=uuid)
        if player_position is not None:
            return self.navigate_to(*player_position, space=3)
        return False

    def find_items(self, items, invert=False):
        if invert:
            return [s.name for s in
                    self.inventory.player_inventory if
                    s is not None and s.name not in items]
        else:
            return [i for i in items if i in
                    self.inventory.player_inventory]
        return []

    def drop(self, items, position=None, invert=False):
        items_to_drop = self.find_items(items, invert=invert)
        if not items_to_drop:
            log.debug('No items to drop')
            return True
        if position is not None and not self.navigate_to(*position):
            log.error('Could not navigate to position: %s', position)
            return False
        log.info('Dropping items: %s', str(items_to_drop))
        for item in items_to_drop:
            tries = 0
            while item in self.inventory.player_inventory and tries < 5:
                num = self.inventory.player_inventory.window_index(item)
                log.debug('Item slot: %s', num)
                if not self.inventory.click(num, button=1, mode=4):
                    return False
                    self.close_window()
                tries += 1
        self.close_window()
        return True

    def get_items(self, items, chest_position=None, dig=False):
        '''Get items from chest at the specified location.'''

        if None not in self.inventory:
            log.error('Inventory is full')
            return False
        if chest_position is None:
            # TODO search for nearby chest
            return False
        if not dig and not self.navigate_to(*chest_position, space=3):
            log.error('Could not navigate to chest: %s', chest_position)
            return False
        elif dig and not self.dig_to(*chest_position, space=3):
            log.error('Could not dig to chest: %s', chest_position)
            return False
        if not self.click_inventory_block(*chest_position):
            log.error('Could not open chest: %s', chest_position)
            return False
        for item in items:
            slot_num = self.open_window.custom_inventory.window_index(item)
            if slot_num is None:
                continue
            self.open_window.shift_click(slot_num)
        self.close_window()
        return True

    def store_items(self, items, chest_position=None, invert=False, dig=False):
        '''Put items from inventory into a chest at the specified location.
        The invert option will change the behavior so that everything except the
        items listed will be stored.'''

        items_to_store = self.find_items(items, invert=invert)
        if not items_to_store:
            log.debug('No items to store')
            return True
        if chest_position is None:
            # TODO search for nearby chest
            return False
        if not dig and not self.navigate_to(*chest_position, space=3):
            log.error('Could not navigate to chest: %s', chest_position)
            return False
        elif dig and not self.dig_to(*chest_position, space=3):
            log.error('Could not dig to chest: %s', chest_position)
            return False
        if not self.click_inventory_block(*chest_position):
            log.error('Could not open chest: %s', chest_position)
            return False
        if None not in self.open_window.custom_inventory:
            log.error('Chest is full: %s', chest_position)
            self.close_window()
            return False
        log.info('Storing items: %s', str(items_to_store))
        for item in items_to_store:
            while (self.open_window is not None and
                   self.open_window.player_inventory is not None and
                   item in self.open_window.player_inventory and
                   None in self.open_window.custom_inventory):
                num = self.open_window.player_inventory.window_index(item)
                log.debug('Item slot: %s', num)
                if not self.open_window.click(num, mode=1):
                    self.close_window()
                    return False
        self.close_window()
        return True

    def escape(self, min_health=10):
        if self.health is None:
            return
        if self.health < min_health:
            log.warn('health too low, escaping: %s', self.health)
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(1)
            os.kill(os.getpid(), signal.SIGKILL)
        if self.health < self._last_health:
            log.warn('health is dropping: %s', self.health)
        self._last_health = self.health

    def farm(self, items, home=None, _range=10):
        return
        '''
        #TODO finish this method
        home = self.get_position(floor=True) if home is None else home
        items_to_plant = self.find_items(items)
        if not items_to_plant:
            log.debug('Nothing to plant')
            return True
        if not self.navigate_to(*home):
            log.error('Could not navigate to home: %s', home)
            return False
        items_cycle = itertools.cycle(items_to_plant)
        for position in self.world.iter_reachable(*home, _range=_range):
            tries = 0
            while (self.equip_item(items_cycle.next()) and
                   tries < len(items_to_plant)):
                tries += 1
            x, y, z = position
            is_farmland = self.world.get_name(x, y - 1, z) == 'Farmland'
            is_empty = self.world.get_name(x, y, z) == 'Air'
            if is_farmland and is_empty:
                self.navigate_to(*position, space=2)
                self._send(self.proto.PlayServerboundBlockPlacement.id,
                           location=Position(x, y - 1, z),
                           direction=1,
                           held_item=self.held_item,
                           cursor_x=0,
                           cursor_y=0,
                           cursor_z=0)
        return True
        '''

    def harvest(self, home=None, _range=10):

        def try_to_harvest(spot):
            if self.world.is_harvestable_block(*spot):
                self.navigate_to(*spot, space=1, timeout=2)
                self.break_block(*spot)
                time.sleep(0.5)

        home = self.get_position(floor=True) if home is None else home
        checked = set([])
        for position in self.world.iter_reachable(*home, _range=_range):
            if position in checked:
                continue
            checked.add(position)
            if self.world.get_name(*position) in ('Pumpkin Stem', 'Melon Stem'):
                for neighbor in self.world.iter_adjacent(*position):
                    if neighbor in checked:
                        continue
                    checked.add(neighbor)
                    try_to_harvest(neighbor)
            else:
                try_to_harvest(position)
        self.navigate_to(*home)

    def mine(self, block_types=None, home=None, num=1, timeout=10):
        #if None not in self.inventory.player_inventory:
            #return False
        x, y, z = self.get_position(floor=True) if home is None else home
        block_types = types.ORE if block_types is None else block_types
        block_iter = self.world.iter_nearest_from_block_types(
            x, y, z, block_types)
        for (x, y, z) in block_iter:
            if (x, y, z) in self.unmineable:
                continue
            log.info('Found %s at: %s', self.world.get_name(x, y, z),
                     str((x, y, z)))
            #timeout = (cityblock(self.get_position(floor=True),
                                 #(x, y, z)) / 2) ** 3 / 600
            if not self.dig_to(x, y, z, timeout=timeout):
                self.unmineable.add((x, y, z))
                continue
            num -= 1
            if num <= 0:
                break
        else:
            # No blocks could be reached
            return False
        time.sleep(0.5)
        return True

    def move_to_block_types(self, block_types):
        x0, y0, z0 = self.position
        for x, y, z in self.world.iter_nearest_from_block_types(x0, y0, z0, block_types):
            if euclidean(self.position, (x, y, z)) <= 4:
                return (x, y, z)
            if self.navigate_to(x, y, z, space=3):
                return (x, y, z)
        log.info('could not get to a: %s', block_types)
        return None

    def enchant(self, types=None, min_level=2, min_xp=30):
        if self.xp_level < min_xp:
            log.debug('xp too low: %d', self.xp_level)
            return False
        if self.inventory.count('Lapis Lazuli') < 3:
            log.info('not enough lapis')
            return False
        if not self.inventory.get_enchantables(types):
            log.info('nothing to enchant')
            return False
        table = self.move_to_block_types(['Enchantment Table'])
        if not table:
            print 'table'
            return False
        if not self.click_inventory_block(*table):
            print 'click'
            return False
        for slot_num in self.open_window.get_enchantables(types):
            while self.open_window.get_slot_count(1) < 3:
                self.open_window.shift_click(
                    self.open_window.index('Lapis Lazuli'))
            self.open_window.swap_slots(0, slot_num)
            if not self._wait_for(lambda: bool(self.open_window.get_property(1))):
                self.open_window.swap_slots(0, slot_num)
                break
            for level in xrange(2, min_level - 1, -1):
                if self.open_window.get_property(level):
                    break
            else:
                self.open_window.swap_slots(0, slot_num)
                break
            self._send(self.proto.PlayServerboundEnchantItem.id,
                       window_id=self.open_window._id,
                       enchantment=2
                       )
            self._wait_for(lambda: self.open_window.get_slot(0).nbt is not None)
            self.open_window.swap_slots(0, slot_num)
            if self.open_window.count('Lapis Lazuli') < 3:
                break
        self.open_window.shift_click(1)
        self.close_window()
