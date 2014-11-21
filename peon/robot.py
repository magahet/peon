import threading
import time
import logging
from player import Player
import types
from fastmc.proto import Position


log = logging.getLogger(__name__)


class Robot(Player):

    def __init__(self, proto, send_queue, recv_condition, world):
        super(Robot, self).__init__(proto, send_queue, recv_condition, world)
        self.auto_defend_mob_types = types.HOSTILE_MOBS
        self.auto_gather_items = set([])
        self.auto_hunt_settings = {}
        self._enabled_auto_actions = ('fall', 'eat', 'defend')
        self._auto_eat_level = 18
        self._auto_actions = {}
        self._locks = {
            'movement': threading.Lock(),
            'action': threading.Lock(),
        }
        self._threads = {}
        self._thread_functions = (
            {
                'name': 'falling',
                'function': self.fall,
                'lock': 'movement',
            },
            {
                'name': 'defend',
                'function': self.defend,
                'lock': 'action',
            },
            {
                'name': 'eat',
                'function': self.eat,
                'lock': 'action',
                'interval': 10,
            },
            {
                'name': 'hunt',
                'function': self.hunt,
                'lock': 'movement',
                'interval': 5,
            },
            {
                'name': 'gather',
                'function': self.gather,
                'lock': 'movement',
                'interval': 5,
            },
        )
        self.start_threads()

    def __repr__(self):
        return 'Bot(xyz={}, health={}, food={}, xp={}, auto_actions={})'.format(
            self.get_position(floor=True),
            self.health,
            self.food,
            self.xp_level,
            self.auto_actions,
        )

    @property
    def auto_actions(self):
        return [n for n, e in self._auto_actions.iteritems() if e.is_set()]

    def start_threads(self):
        for settings in self._thread_funcs.iteritems():
            name = settings.get('name', '')
            if name not in self._auto_actions:
                self._auto_actions[name] = threading.Event()
            if name in self._enabled_auto_actions:
                self.enable_auto_action(name)
            thread = threading.Thread(
                target=self._do_auto_action,
                name=name,
                kwargs=settings)
            thread.daemon = True
            thread.start()
            self._threads[name] = thread

    def _do_auto_action(self, name='', function=None, lock=None, interval=0.1,
                        args=None, kwargs=None):
        auto_event = self._auto_actions.get(name)
        args = () if args is None else args
        kwargs = {} if kwargs is None else kwargs
        self._wait_for(
            lambda: None not in (self.inventory, self.food, self.health))
        while True:
            auto_event.wait()
            if lock is None:
                function(*args, **kwargs)
                time.sleep(interval)
            else:
                with lock:
                    function(*args, **kwargs)
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
        if not self.health or self.health <= 10:
            log.warn('health unknown or too low: %s', self.health)
            return False
        self.enable_auto_action('defend')
        if mob_types is None:
            mob_types = types.HOSTILE_MOBS
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
        self.follow_path(path)
        self.attack_entity(entity)
        self.navigate_to(*path[-1])
        path.reverse()
        path.append(home)
        return self.follow_path(path)

    def gather(self, items, _range=50):
        x0, y0, z0 = self.get_position(floor=True)
        for _object in self.iter_objects_in_range(items=items, reach=_range):
            log.info("gathering object: %s", str(_object))
            x, y, z = _object.get_position(floor=True)
            path = self.world.find_path(x0, y0, z0, x, y, z, space=1,
                                        timeout=30)
            if path:
                break
        else:
            return False
        self.follow_path(path)
        path.reverse()
        path.append((x0, y0, z0))
        return self.follow_path(path)

    def attack_entity(self, entity, space=3, timeout=6):
        on_kill_list = entity._type in self.auto_defend_mob_types
        if not on_kill_list:
            self.auto_defend_mob_types.add(entity._type)
        start = time.time()
        while self.health > 10 and entity.eid in self.world.entities:
            x, y, z = entity.get_position(floor=True)
            if not self.navigate_to(x, y, z, space=space, timeout=2):
                break
            elif time.time() - start > timeout:
                break
            time.sleep(0.1)
        if not on_kill_list:
            self.auto_defend_mob_types.remove(entity._type)

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
            return self.navigate_to(*player_position, space=2)
        return False

    def store_items(self, items, chest_position=None):
        items_to_store = [i for i in items if i in self.inventory]
        if not items_to_store:
            return True
        if chest_position is None:
            # TODO search for nearby chest
            return False
        if not self.navigate_to(*chest_position, space=3):
            log.error('Could not navigate to chest: %s', chest_position)
            return False
        if not self.click_inventory_block(*chest_position):
            log.error('Could not open chest: %s', chest_position)
            return False
        if None not in self.open_window.custom_inventory:
            log.error('Chest is full: %s', chest_position)
            self.close_window()
            return False
        for item in items_to_store:
            while (item in self.open_window.player_inventory and
                    None in self.open_window.custom_inventory):
                log.info('Storing item: %s', item)
                num = self.open_window.player_inventory.window_index(item)
                log.info('Item slot: %s', num)
                if not self.open_window.click(num, mode=1):
                    self.close_window()
                    return False
        self.close_window()
        return True
