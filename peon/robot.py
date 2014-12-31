"""Provides a Minecraft bot able to perform complex tasks."""

import threading
import time
import logging
import os
import signal
from contextlib import contextmanager
from player import Player
import types
from fastmc.proto import Position
from scipy.spatial.distance import euclidean
import bb


log = logging.getLogger(__name__)


class Robot(Player):

    """A Minecraft bot able to perform complex tasks."""

    def __init__(self, proto, send_queue, chat_queue, recv_condition, world):
        """Inherit from base player class and start threads for auto actions."""
        super(Robot, self).__init__(proto, send_queue, recv_condition, world)
        self._pre_enabled_auto_actions = ('fall', 'eat', 'defend', 'escape')
        self._auto_eat_level = 18
        self._chat_queue = chat_queue
        self._enabled_auto_actions = {}
        self._active_auto_actions = {}
        self._mission_lock = threading.RLock()
        self._threads = {}
        self._thread_functions = {
            'escape': {
                'function': self.escape,
                'interval': 2,
            },
            'fall': {
                'function': self.fall,
            },
            'defend': {
                'function': self.defend,
            },
            'eat': {
                'function': self.eat,
                'interval': 30,
            },
            'hunt': {
                'function': self.hunt,
                'interval': 2,
            },
            'gather': {
                'function': self.gather,
                'interval': 1,
            },
            'store': {
                'function': self.store_items,
                'interval': 60,
            },
            'store_enchanted': {
                'function': self.store_enchanted_items,
                'interval': 60,
            },
            'get': {
                'function': self.get_items,
                'interval': 60,
            },
            'get_enchantables': {
                'function': self.get_enchantable_items,
                'interval': 60,
            },
            'drop': {
                'function': self.drop,
                'interval': 60,
            },
            'harvest': {
                'function': self.harvest,
                'interval': 60,
            },
            'mine': {
                'function': self.mine,
                'interval': 1,
            },
            'chop': {
                'function': self.chop,
                'interval': 1,
            },
            'enchant': {
                'function': self.enchant,
                'interval': 10,
            },
            'follow': {
                'function': self.move_to_player,
                'interval': 1,
            },
            'listen': {
                'function': self.listen,
                'interval': 1,
            },
        }
        self._start_threads()
        self._last_health = 0
        self.unbreakable = set([])

    def __repr__(self):
        """Create a representation of the robot's current state."""
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
    def state(self):
        template = 'xyz={}, health={}, food={}, xp={}'
        return template.format(
            self.get_position(floor=True),
            int(self.health),
            int(self.food),
            int(self.xp_level)
        )

    @property
    def enabled_auto_actions(self):
        """Get the list of enabled auto actions."""
        return [n for n, e in self._enabled_auto_actions.iteritems() if e.is_set()]

    @property
    def active_auto_actions(self):
        """Get the list of currently running auto actions."""
        return [n for n, e in
                self._active_auto_actions.iteritems() if
                e.is_set()]

    def set_auto_settings(self, *args, **kwargs):
        """Set the arguments and keyword arguments for an auto action.

        Arguments:
            first -- the name of the auto action to update (e.g. hunt)
            *args[1:] -- the arguments that should be passed to the function

        Keyword Arguments:
            *kwargs -- The set of keyword arguments to pass to the function
        """
        name = args[0]
        if name not in self._thread_functions:
            return False
        self._thread_functions[name]['args'] = tuple(args[1:])
        self._thread_functions[name]['kwargs'] = kwargs

    def get_auto_settings(self, name):
        """Get the currently set settings for auto actions."""
        settings = self._thread_functions.get(name, {})
        return (settings.get('args', ()), settings.get('kwargs', {}))

    def _start_threads(self):
        """Start auto action threads."""
        for name in self._thread_functions:
            if name not in self._enabled_auto_actions:
                self._enabled_auto_actions[name] = threading.Event()
                self._active_auto_actions[name] = threading.Event()
            if name in self._pre_enabled_auto_actions:
                self.start(name)
            thread = threading.Thread(target=self._do_auto_action, name=name,
                                      args=(name,))
            thread.daemon = True
            thread.start()
            self._threads[name] = thread

    def _do_auto_action(self, name):
        """Run the function assigned to an auto action on an interval."""
        auto_event = self._enabled_auto_actions.get(name)
        self._wait_for(
            lambda: None not in (self.inventory, self.food, self.health))
        settings = self._thread_functions.get(name, {})
        function = settings.get('function')
        interval = settings.get('interval', 0.1)
        while True:
            auto_event.wait()
            args, kwargs = self.get_auto_settings(name)
            self._active_auto_actions[name].set()
            function(*args, **kwargs)
            self._active_auto_actions[name].clear()
            time.sleep(interval)

    def fall(self):
        """Move the bot to the next highest solid block."""
        if self._is_moving.is_set():
            return
        with self._move_lock:
            pos = self.position
            if None in pos:
                return
            x, y, z = pos
            standing = (
                self.world.is_solid_block(x, y - 1, z) or
                self.world.is_water_block(x, y - 1, z)
            )
            if standing is None or standing:
                return
            next_pos = self.world.get_next_highest_solid_block(x, y, z)
            if next_pos is None:
                return
            self.on_ground = False
            x, y, z = next_pos
            self.on_ground = self._move(x, y + 1, z)

    def defend(self, mob_types=types.HOSTILE_MOBS):
        """Attack entities within range."""
        eids_in_range = [e.eid for e in self.iter_entities_in_range(mob_types)]
        if not eids_in_range:
            return False
        if self._inventory_lock.acquire(False):
            self.equip_any_item_from_list([
                'Diamond Sword',
                'Golden Sword',
                'Iron Sword',
                'Stone Sword',
                'Wooden Sword',
            ])
            self._inventory_lock.release()
        for eid in eids_in_range:
            self._send(self.proto.PlayServerboundUseEntity.id,
                       target=eid,
                       type=1
                       )
        return True

    def start(self, name, **kwargs):
        """Enable an auto action."""
        if kwargs:
            self.set_auto_settings(name, **kwargs)
        auto_action = self._enabled_auto_actions.get(name)
        if auto_action is None:
            return False
        auto_action.set()
        return True

    def stop(self, name):
        """Disable an auto action."""
        auto_action = self._enabled_auto_actions.get(name)
        if auto_action is None:
            return False
        auto_action.clear()
        return True

    @property
    def auto_defend_mob_types(self):
        """Get the current list of mobs to attack."""
        args, kwargs = self.get_auto_settings('defend')
        return kwargs.get('mob_types', set([]))

    def set_auto_defend_mob_types(self, mob_types):
        """Set the list of mobs to attack."""
        self.set_auto_settings('defend', mob_types=mob_types)

    @contextmanager
    def add_mob_types(self, mob_types):
        """Temporarily Set the list of mobs to attack."""
        original_set = self.auto_defend_mob_types.copy()
        self.set_auto_settings('defend',
                               mob_types=original_set.union(mob_types))
        yield
        self.set_auto_settings('defend', mob_types=original_set)

    def eat(self, target=20):
        """Find food in inventory and consume it."""
        if self.food >= target:
            return True
        with self._inventory_lock:
            if not self.equip_any_item_from_list(types.FOOD):
                log.warning('Hungry, but no food')
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
        """Search for certain mob types and hunt them down.

        Keyword Arguments:
            home -- position to return to after killing a mob
            mob_types -- names of mobs to hunt
            space -- how close to get to the mobs
            speed -- how fast to move
            _range -- how far out from home position to search
        """
        with self._mission_lock:
            self.don_armor()
            self.start('defend')
            mob_types = types.HOSTILE_MOBS if mob_types is None else mob_types
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

    def gather(self, items=None, _range=50, timeout=10, _return=False):
        """Look for and move to dropped items."""
        if items is None:
            return False
        with self._mission_lock:
            x0, y0, z0 = self.get_position(floor=True)
            for _object in self.iter_objects_in_range(items=items,
                                                      reach=_range):
                log.info("gathering object: %s", str(_object))
                x, y, z = _object.get_position(floor=True)
                path = self.world.find_path(x0, y0, z0, x, y, z, space=1,
                                            timeout=timeout)
                if path:
                    break
            else:
                return False
            if not _return:
                return self.follow_path(path)
            path.reverse()
            path.append((x0, y0, z0))
            return self.follow_path(path)

    def follow_entity(self, entity, space=3, timeout=None):
        """Continuously move to an entity's position."""
        with self._move_lock:
            start_time = time.time()
            while entity.eid in self.world.entities:
                x, y, z = entity.get_position(floor=True)
                if not self.navigate_to(x, y, z, space=space, timeout=2):
                    break
                elif timeout is not None and time.time() - start_time > timeout:
                    break
                time.sleep(0.1)

    def don_armor(self):
        """Put on best armor in inventory."""
        if not self._inventory_lock.acquire(False):
            return
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
        self._inventory_lock.release()

    def move_to_player(self, player_name=None):
        """Move to a player's position."""
        if player_name is None:
            return False
        player_position = self.world.get_player_position(
            player_name=player_name)
        if player_position is not None:
            return self.navigate_to(*player_position, space=3)
        return False

    def find_items(self, items, invert=False):
        """Find items in the inventory."""
        if invert:
            return [s.name for s in
                    self.inventory.player_inventory if
                    s is not None and s.name not in items]
        else:
            return [i for i in items if i in
                    self.inventory.player_inventory]
        return []

    def drop(self, items=None, slot_num=None, position=None, invert=False):
        """Drop items from inventory."""
        def _drop(slot_num):
            log.debug('Item slot: %s', slot_num)
            return self.inventory.ctrl_q_click(slot_num)

        if items is None and slot_num is None:
            return False
        if slot_num:
            return _drop(slot_num)
        if items is not None:
            items_to_drop = self.find_items(items, invert=invert)
        if not items_to_drop:
            log.debug('No items to drop')
            return True
        if position is not None and not self.navigate_to(*position):
            log.error('Could not navigate to position: %s', position)
            return False
        log.info('Dropping items: %s', str(items_to_drop))
        for item in items_to_drop:
            for _ in xrange(self.inventory.player_inventory.count(item)):
                slot_num = self.inventory.player_inventory.index(item)
                if slot_num is None:
                    break
                _drop(slot_num)
        self.close_window()
        return True

    def get_items(self, items=None, chest_position=None, dig=False):
        """Get items from chest at the specified location."""
        if items is None:
            return False
        with self._mission_lock:
            if None not in self.inventory:
                log.error('Inventory is full')
                return False
            if not self.move_and_open(chest_position, dig):
                return False
            for item in items:
                while None in self.open_window.player_inventory:
                    slot_num = self.open_window.custom_inventory.index(item)
                    target_index = self.open_window.player_inventory.index(None)
                    if None in (slot_num, target_index):
                        break
                    self.open_window.swap_slots(slot_num, target_index)
            self.close_window()
            return True

    def get_enchantable_items(self, chest_position=None, dig=False):
        """Get items from chest at the specified location."""
        with self._mission_lock:
            if None not in self.inventory:
                log.error('Inventory is full')
                return False
            if not self.move_and_open(chest_position, dig):
                return False
            for slot_num in self.open_window.custom_inventory.get_enchantables():
                target_index = self.open_window.player_inventory.index(None)
                if target_index is None:
                    break
                log.info('Getting %s from chest',
                         self.open_window.get_slot(slot_num).name)
                self.open_window.swap_slots(slot_num, target_index)
            self.close_window()
            return True

    def move_and_open(self, chest_position, dig=False):
        """Move to a chest and open it."""
        if chest_position is None:
            # TODO search for nearby chest
            return False
        if not dig and not self.navigate_to(*chest_position, space=4):
            log.error('Could not navigate to chest: %s', chest_position)
            return False
        elif dig and not self.dig_to(*chest_position, space=4):
            log.error('Could not dig to chest: %s', chest_position)
            return False
        if not self.click_inventory_block(*chest_position):
            log.error('Could not open chest: %s', chest_position)
            return False
        return True

    def store_items(self, items=None, chest_position=None, invert=False, dig=False):
        """Put items from inventory into a chest at the specified location.

        Keyword arguments:
            items -- list of item names to store
            chest_position -- coordinates of chest to store items in
            invert -- everything except the items listed will be stored
            dig -- whether to allow digging to the chest (default False)
        """
        if items is None:
            return False
        items_to_store = self.find_items(items, invert=invert)
        if not items_to_store:
            log.debug('No items to store')
            return True
        with self._mission_lock():
            if not self.move_and_open(chest_position, dig):
                return False
            log.info('Storing items: %s', str(items_to_store))
            for item in items_to_store:
                while None in self.open_window.custom_inventory:
                    slot_num = self.open_window.player_inventory.index(item)
                    target_index = self.open_window.custom_inventory.index(None)
                    if None in (slot_num, target_index):
                        break
                    log.debug('Item slot: %s', slot_num)
                    if not self.open_window.swap_slots(slot_num, target_index):
                        self.close_window()
                        return False
            self.close_window()
            return True

    def store_enchanted_items(self, chest_position=None, dig=False):
        """Store only items that have been enchanted."""
        if not self.inventory.player_inventory.get_enchanted():
            log.debug('No items to store')
            return True
        with self._mission_lock:
            if not self.move_and_open(chest_position, dig):
                return False
            for slot_num in self.open_window.player_inventory.get_enchanted():
                log.info('Storing enchanted %s',
                         self.open_window.get_slot(slot_num).name)
                target_index = self.open_window.custom_inventory.index(None)
                if target_index is None:
                    break
                if not self.open_window.swap_slots(slot_num, target_index):
                    self.close_window()
                    return False
            self.close_window()
            return True

    def escape(self, min_health=10, max_entities=500):
        """Disconnect if health is low or there are too many entities."""
        if self.health is not None:
            if self.health < self._last_health:
                log.warn('health is dropping: %s', self.health)
                if self.health < min_health:
                    log.warn('health too low, escaping: %s', self.health)
                    os.kill(os.getpid(), signal.SIGTERM)
                    time.sleep(1)
                    os.kill(os.getpid(), signal.SIGKILL)
            self._last_health = self.health
        if len(self.world.entities) > max_entities:
                log.warn('Too many entities, escaping: %s',
                         len(self.world.entities))
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(1)
                os.kill(os.getpid(), signal.SIGKILL)

    def plant(self, items, home=None, _range=10):
        """Plant crops or tree saplings."""
        pass
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

    def harvest(self, home=None, types=types.HARVESTABLE_BLOCKS, _range=10):
        """Find harvestable or given blocks and break them."""
        def try_to_harvest(spot):
            """Move to block and break it."""
            if self.world.get_name(*spot) in types:
                self.navigate_to(*spot, space=1, timeout=2)
                self.break_block(*spot)
                time.sleep(0.5)

        with self._mission_lock:
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

    def break_blocks_by_type(self, block_types=types.ORE, home=None, num=1,
                             timeout=10, digging=True):
        """Break blocks of given types."""
        if None not in self.inventory.player_inventory:
            log.warn('No room in inventory')
            return False
        with self._mission_lock:
            x, y, z = self.get_position(floor=True) if home is None else home
            block_iter = self.world.iter_nearest_from_block_types(
                x, y, z, block_types)
            for (x, y, z) in block_iter:
                if (x, y, z) in self.unbreakable:
                    continue
                log.info('Found %s at: %s', self.world.get_name(x, y, z),
                         str((x, y, z)))
                if digging and not self.dig_to(x, y, z, timeout=timeout):
                    self.unbreakable.add((x, y, z))
                    continue
                elif not self.navigate_to(x, y, z, space=5,
                                          timeout=timeout):
                    self.unbreakable.add((x, y, z))
                    continue
                elif not self.break_block(x, y, z):
                    self.unbreakable.add((x, y, z))
                    continue
                num -= 1
                if num <= 0:
                    break
            else:
                # No blocks could be reached
                return False
            time.sleep(0.5)
            return True

    def mine(self, block_types=types.ORE, home=None, num=4, timeout=10):
        return self.break_blocks_by_type(block_types=block_types, home=home,
                                         num=num, timeout=timeout, digging=True)

    def chop(self, block_types=None, home=None, num=1, timeout=2):
        block_types = ('Wood', 'Wood2') if block_types is None else block_types
        return self.break_blocks_by_type(block_types=block_types,
                                         home=home, num=num, timeout=timeout,
                                         digging=False)

    def move_to_block_types(self, block_types):
        """Move to the nearest block of given types."""
        x0, y0, z0 = self.position
        for x, y, z in self.world.iter_nearest_from_block_types(x0, y0, z0, block_types):
            if euclidean(self.position, (x, y, z)) <= 4:
                return (x, y, z)
            if self.navigate_to(x, y, z, space=3):
                return (x, y, z)
        log.info('could not get to a: %s', block_types)
        return None

    def enchant(self, types=types.ENCHANT_ITEMS):
        """Enchant enchantable items in the inventory."""
        with self._mission_lock:
            if self.xp_level < 30:
                log.debug('xp too low: %d', self.xp_level)
                return False
            if self.inventory.count('Lapis Lazuli') < 3:
                log.warn('not enough lapis')
                return False
            if not self.inventory.player_inventory.get_enchantables(types):
                log.warn('nothing to enchant')
                return False
            table = self.move_to_block_types(['Enchantment Table'])
            if not table:
                log.warn('could not find enchanting table')
                return False
            if not self.click_inventory_block(*table):
                log.warn('could not open enchanting table')
                return False
            for slot_num in self.open_window.player_inventory.get_enchantables(types):
                if self.inventory.count('Lapis Lazuli') < 3:
                    log.info('not enough lapis')
                    break
                slot = self.open_window.get_slot(slot_num)
                if slot is None:
                    continue
                tries = 0
                while self.open_window.get_slot_count(1) < 3 and tries < 3:
                    lapis_slot = self.open_window.player_inventory.index(
                        'Lapis Lazuli')
                    self.open_window.swap_slots(lapis_slot, 1)
                    tries += 1
                if self.open_window.get_slot_count(1) < 3:
                    log.info('Not enough lapis in slot')
                    break
                if not self.open_window.swap_slots(slot_num, 0):
                    log.error('Could not put item on table: %d', slot_num)
                    break
                if not self._wait_for(
                        lambda: self.open_window.get_property(2) is not None,
                        timeout=2):
                    log.error('Window property did not update')
                    self.open_window.swap_slots(slot_num, 0)
                    break
                log.info('Enchanting %s', slot.name)
                self._send(self.proto.PlayServerboundEnchantItem.id,
                           window_id=self.open_window._id,
                           enchantment=2
                           )
                self._wait_for(
                    lambda: self.open_window.get_slot(0).nbt is not None)
                self.open_window.swap_slots(0, slot_num)
                if self.open_window.count('Lapis Lazuli') < 3:
                    break
                if self.xp_level < 30:
                    break
            if self.open_window.get_slot_count(1) > 0:
                self.open_window.left_click(1)
                self.open_window.left_click(lapis_slot)
            self.close_window()

    def dig_to_surface(self):
        """Find the highest solid block above the bot and dig to it."""
        x0, y0, z0 = self.position
        x, y, z = self.world.get_next_highest_solid_block(x0, 255, z0)
        return self.dig_to(x, y + 1, z)

    def excavate(self, corner_a, corner_b, update_rate=64, ignore=None):
        """Excavate an area given two opposite corners."""
        bounding_box = bb.BoundingBox(corner_a, corner_b)
        last_time = time.time()
        count = 0
        if ignore is None:
            ignore = set([])
        if self.has_damaged_tool():
            log.info('Need new tool')
            return False
        for point in bounding_box.iter_points(
                axis_order=[1, 2, 0], ascending=False, zig_zag=[0, 2]):
            block_name = self.world.get_name(*point)
            if (block_name is None or
                    block_name == 'Air' or
                    not self.world.is_safe_to_break(*point) or
                    (ignore and self.world.get_name(*point) in ignore)):
                continue
            elif self.navigate_to(*point, space=4):
                # See if bot is standing on block to break
                if point == self.get_position(dy=-1, floor=True):
                    # Look for a nearby block to stand on
                    for neighbor in self.world.iter_moveable_adjacent(
                            *self.position):
                        if self._move(*neighbor):
                            if self.break_block(*point):
                                count += 1
                            break
                    else:
                        continue
                else:
                    if self.break_block(*point):
                        count += 1
            elif self.dig_to(*point):
                count += 1
            else:
                log.info('Could not clear block: %s', str(point))
            if count >= update_rate:
                log.info('Average block break time: %dms',
                         int(time.time() - last_time) * 1000 // 64)
                last_time = time.time()
                count = 0
                if self.has_damaged_tool():
                    log.info('Need new tool')
                    return False
        for point in bounding_box.iter_points():
            if (self.world.is_solid_block(*point) and
                    self.world.is_safe_to_break(*point) and
                    (not ignore or self.world.get_name(*point) not in ignore)):
                return False
        return True

    def has_damaged_tool(self, warn_level=0.8, error_level=0.9):
        tool_at_error_level = False
        for _type, max_damage in types.DURABILITY.iteritems():
            max_damage = float(max_damage)
            for index, slot in self.inventory.find(_type):
                damage_percent = slot.damage / max_damage
                if damage_percent >= error_level:
                    log.info('Tool is about to break: %d: %s',
                             index, str(slot))
                    tool_at_error_level = True
                elif damage_percent >= warn_level:
                    log.info('Tool is wearing down: %d: %s',
                             index, str(slot))
        return tool_at_error_level

    def fill(self, corner_a, corner_b, block_type, update_rate=64):
        bounding_box = bb.BoundingBox(corner_a, corner_b)
        last_time = time.time()
        count = 0
        for point in bounding_box.iter_points(
                axis_order=[1, 2, 0], zig_zag=[0, 2]):
            name = self.world.get_name(*point)
            if name is not None and name not in types.PLACEABLE:
                continue
            elif self.navigate_to(*point, space=4):
                # See if bot is standing on point to fill
                if point != self.position:
                    if self.place_block(*point, block_type=block_type):
                        count += 1
                    continue
                # Look for a nearby block to stand on
                for neighbor in self.world.iter_moveable_adjacent(
                        *self.position):
                    if not self._move(*neighbor):
                        continue
                    if self.place_block(*point, block_type=block_type):
                        count += 1
                        break
                else:
                    log.info('Could not place block: %s', str(point))
                    return False
            else:
                log.info('Could not place block: %s', str(point))
            if count >= update_rate:
                log.info('Average block placement time: %dms',
                         int(time.time() - last_time) * 1000 // 64)
                last_time = time.time()
                count = 0
        for point in bounding_box.iter_points():
            name = self.world.get_name(*point)
            if name is None or name in types.PLACEABLE:
                return False
        return True

    def light_area(self, x0, z0, x1, z1, top=None):
        """Set torches at optimal lighting positions."""
        if top is None:
            _, top, _ = self.position
            top += 16
        bounding_box = bb.BoundingBox((x0, z0), (x1, z1))
        for x, z in bounding_box.iter_points(zig_zag=[0, 1]):
            ground = self.world.get_next_highest_solid_block(x, top, z)
            y = ground[1] + 1
            name = self.world.get_name(x, y, z)
            name = 'Air' if name is None else name
            optimal_spot = self.world.is_optimal_lighting_spot(x, y, z)
            if optimal_spot and name == 'Air':
                log.info('Spot needs torch: %s', str((x, y, z)))
                if self.navigate_to(x, y, z, space=4):
                    if self.place_block(x, y, z, block_type='Torch'):
                        log.info('Torch placed: %s', str((x, y, z)))
            elif not optimal_spot and name == 'Torch':
                log.info('Spot should not have torch: %s', str((x, y, z)))
                if self.navigate_to(x, y, z, space=4):
                    if self.break_block(x, y, z):
                        log.info('Torch broken: %s', str((x, y, z)))
        for x, z in bounding_box.iter_points():
            if not self.world.is_optimal_lighting_spot(x, 0, z):
                continue
            _, ground, _ = self.world.get_next_highest_solid_block(x, top, z)
            name = self.world.get_name(x, ground + 1, z)
            if not name or name != 'Torch':
                return False
        return True

    def terraform(self, corner_a, corner_b, fill='Dirt', sub_fill='Stone'):
        log.info('Excavating to ground level')
        if not self.excavate(corner_a, corner_b, ignore=['Torch']):
            log.warning('Could not excavate top area')
            return False
        ground_level = min(corner_a[1], corner_b[1]) - 1
        x0, _, z0 = corner_a
        x1, _, z1 = corner_b
        log.info('Clearing ground level')
        if not self.excavate((x0, ground_level, z0), (x1, ground_level, z1),
                             ignore=['Dirt', 'Grass Block']):
            log.warning('Could not excavate top area')
            return False
        log.info('Filling sub-level')
        if not self.fill((x0, ground_level - 1, z0), (x1, ground_level - 1, z1),
                         sub_fill):
            log.warning('Could not fill sub-terrain')
            return False
        log.info('Filling ground level')
        if not self.fill((x0, ground_level, z0), (x1, ground_level, z1), fill):
            log.warning('Could not fill terrain')
            return False
        log.info('Lighting area')
        if not self.light_area(x0, z0, x1, z1):
            log.warning('Could not light area')
            return False
        log.info('Terraforming complete')
        return True

    def listen(self, name='peon'):
        message = self._chat_queue.get()
        log.info('Received message: %s', str(message))
        if message.message_type != 'message':
            log.info('Not a chat message.')
            return
        tokens = message.message.split()
        log.info('Tokens: %s', str(tokens))
        if len(tokens) < 2:
            return
        called_name = tokens.pop(0)
        if called_name != name:
            return
        command = tokens.pop(0)
        args = []
        kwargs = {}
        for token in tokens:
            left, _, right = token.partition('=')
            if not right:
                args.append(left)
            else:
                kwargs[left] = right
        if not hasattr(self, command):
            return self.send_chat_message("I don't understand")
        attribute = getattr(self, command)
        if hasattr(attribute, '__call__'):
            if attribute(*args, **kwargs):
                return self.send_chat_message('done')
            else:
                return self.send_chat_message("I'm having trouble with that")
        else:
            return self.send_chat_message(str(attribute))

    def send_chat_message(self, message):
        self._send(self.proto.PlayServerboundChatMessage.id, chat=message)
