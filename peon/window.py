from types import (ItemTypes, InventoryTypes, ENCHANT_ITEMS)
import time
import logging
import fastmc.proto
from textwrap import dedent


log = logging.getLogger(__name__)


class Window(object):
    def __init__(self, window_id, action_num_counter, send_queue,
                 proto, recv_condition, slots=None, _type=None, title=None):
        self._id = window_id
        self.slots = SlotList([])
        if slots is not None:
            for slot in slots:
                slot = Slot(slot) if slot is not None else None
                self.slots.append(slot)
        self._type = None if _type is None else _type
        self.title = None if title is None else title
        self.properties = {}
        self.cursor_slot = None
        self._action_num_counter = action_num_counter
        self._send_queue = send_queue
        self._proto = proto
        self._recv_condition = recv_condition
        self._confirmations = {}
        self._click_handlers = {
            (0, 0): self._left_click,
            (1, 0): self._shift_left_click,
            (4, 1): self._control_q,
        }

    def __repr__(self):
        slot_strings = []
        for index, slot in enumerate(self.slots):
            description = InventoryTypes.get_slot_description(
                self._type, index)
            slot_strings.append(
                '    {},  # {} {}'.format(str(slot),
                                          index,
                                          description))
        templ = dedent('''\
            Window(id={}, slots=[
            {}
            ])''')
        return templ.format(self._id, '\n'.join(slot_strings))

    def __contains__(self, _type):
        return _type in self.slots

    def index(self, _type):
        return self.slots.index(_type)

    def count(self, _type):
        return self.slots.count(_type)

    def window_index(self, _type):
        return self.slots.window_index(_type)

    def set_slot(self, index, slot):
        if slot is None:
            self.slots[index] = None
        else:
            self.slots[index] = Slot(slot)

    def set_cursor_slot(self, slot):
        self.cursor_slot = None if slot is None else Slot(slot)

    def set_slots(self, slots):
        self.slots = SlotList([])
        for slot in slots:
            slot = Slot(slot) if slot is not None else None
            self.slots.append(slot)

    def get_property(self, _property):
        return self.properties.get(_property)

    def set_property(self, _property, value):
        self.properties.update({_property: value})

    @property
    def custom_inventory(self):
        if len(self.slots) > 35:
            return SlotList(self.slots[:-36])

    @property
    def player_inventory(self):
        if len(self.slots) > 35:
            return SlotList(self.slots[-36:], start=len(self.slots) - 36)

    @property
    def main_inventory(self):
        if len(self.slots) > 35:
            return SlotList(self.slots[-36:-9], start=len(self.slots) - 36)

    @property
    def held(self):
        if len(self.slots) > 9:
            return SlotList(self.slots[-9:], start=len(self.slots) - 9)

    def click(self, slot_num, button=0, mode=0):
        action_num = self._action_num_counter.next()
        slot = self.slots[slot_num]
        cursor_slot = self.cursor_slot
        log.debug('Sending click window. slot_num: %d action_num: %d',
                 slot_num, action_num)
        log.debug('cursor: %s', str(self.cursor_slot))
        log.debug('slot: %s', str(slot))
        fastmc_slot = None if slot is None else slot.as_fastmc()
        self._send(self._proto.PlayServerboundClickWindow.id,
                   window_id=self._id,
                   slot=slot_num,
                   button=button,
                   action_num=action_num,
                   mode=mode,
                   clicked_item=fastmc_slot)
        if not self._wait_for(lambda: action_num in self._confirmations,
                              timeout=5):
            log.error('Did not get confirmation')
            return False
        if not self._confirmations.get(action_num):
            log.error('Transaction rejected: %d', action_num)
            return False
        log.debug('Confirmation received for %d: %s', action_num,
                 str(self._confirmations.get(action_num)))
        if (mode, button) in self._click_handlers:
            return self._click_handlers[(mode, button)](slot_num, cursor_slot,
                                                        slot)

    def shift_click(self, slot_num):
        return self.click(slot_num, mode=1)

    def drop_click(self, slot_num):
        return self.click(button=1, mode=4)

    def _left_click(self, slot_num, cursor_slot, slot):
        self.slots[slot_num] = cursor_slot
        self.cursor_slot = slot
        return True

    def _shift_left_click(self, slot_num, cursor_slot, slot):
        # TODO validate what happens to clicked items base on current inventory
        return True

    def _control_q(self, slot_num, cursor_slot, slot):
        return True

    def swap_slots(self, slot_num_a, slot_num_b):
        for num in [slot_num_a, slot_num_b, slot_num_a]:
            if not self.click(num):
                return False
        return True

    def _send(self, packet_id, **kwargs):
        self._send_queue.put((packet_id, kwargs))

    def _wait_for(self, what, timeout=10):
        start = time.time()
        with self._recv_condition:
            while not what() and time.time() - start < timeout:
                self._recv_condition.wait(timeout=1)
        return what()

    def get_slot(self, slot_num):
        if slot_num > len(self.slots):
            return None
        return self.slots[slot_num]

    def get_slot_count(self, slot_num):
        slot = self.get_slot(slot_num)
        if slot is None:
            return 0
        return slot.count

    def get_enchantables(self, types=None):
        return self.slots.get_enchantables(types=types)

    def get_enchanted(self, types=None):
        return self.slots.get_enchanted(types=types)


class SlotList(list):
    def __init__(self, *args, **kwargs):
        self.start = kwargs.get('start', 0)
        list.__init__(self, *args)

    def __contains__(self, _type):
        return (
            (_type is None and None in [s for s in self]) or
            self._get_name(_type) in [s.name for s in self if s is not None]
        )

    @staticmethod
    def _get_name(_type):
        if isinstance(_type, basestring):
            return _type
        elif isinstance(_type, tuple):
            item_id, damage = _type
            return ItemTypes.get_name(item_id, damage)
        elif isinstance(_type, int):
            return ItemTypes.get_name(_type, None)

    def index(self, _type, relative=False):
        name = self._get_name(_type)
        for index, slot in enumerate(self):
            if slot is not None and slot.name == name:
                if relative:
                    return index
                else:
                    return index + self.start

    def count(self, _type):
        name = self._get_name(_type)
        count = 0
        for index, slot in enumerate(self):
            if slot is not None and slot.name == name:
                count += slot.count
        return count

    def get_enchantables(self, types=None):
        if types is None:
            types = ENCHANT_ITEMS
        slot_nums = []
        for index, slot in enumerate(self):
            if slot is None or slot.name not in types:
                continue
            if not slot.has_data():
                slot_nums.append(index + self.start)
        return slot_nums

    def get_enchanted(self, types=None):
        if types is None:
            types = ENCHANT_ITEMS
        slot_nums = []
        for index, slot in enumerate(self):
            if slot is None or slot.name not in types:
                continue
            if slot.has_data():
                slot_nums.append(index + self.start)
        return slot_nums


class Slot(object):
    def __init__(self, slot):
        self.item_id = slot.item_id
        self.count = slot.count
        self.damage = slot.damage
        self.nbt = slot.nbt

    def __repr__(self):
        return 'Slot(item_name="{}", count={}, damage={}, has_data={})'.format(
            self.name, self.count, self.damage, self.has_data())

    def __eq__(self, _type):
        if _type is None:
            return False
        elif isinstance(_type, Slot):
            return _type.name == self.name
        return self._get_name(_type) == self.name

    @staticmethod
    def _get_name(_type):
        if isinstance(_type, basestring):
            return _type
        elif isinstance(_type, tuple):
            item_id, damage = _type
            return ItemTypes.get_name(item_id, damage)
        elif isinstance(_type, int):
            return ItemTypes.get_name(_type, None)

    @property
    def name(self):
        return ItemTypes.get_name(self.item_id, self.damage)

    def has_data(self):
        return bool(self.nbt)

    def as_fastmc(self):
        return fastmc.proto.Slot(
            self.item_id, self.count, self.damage, self.nbt)
