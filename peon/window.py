from types import (ItemTypes, InventoryTypes)
import time
import fastmc.proto
from textwrap import dedent


class Window(object):
    def __init__(self, window_id, action_num_counter, send_queue,
                 proto, recv_condition, slots=None, _type=None, title=None):
        self._id = window_id
        self.slots = SlotList([])
        if slots is not None:
            for slot in slots:
                slot = Slot(slot) if slot is not None else None
                self.slots.append(slot)
        self._type = None
        self.title = None
        self.cursor_slot = None
        self._action_num_counter = action_num_counter
        self._send_queue = send_queue
        self._proto = proto
        self._recv_condition = recv_condition
        self._confirmations = {}
        self._click_handlers = {
            (0, 0): self._left_click,
            (1, 0): self._shift_left_click,
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

    def window_index(self, _type):
        return self.slots.window_index(_type)

    def set_slot(self, index, slot):
        if slot is None:
            self.slots[index] = None
        else:
            self.slots[index] = Slot(slot)

    def set_slots(self, slots):
        self.slots = SlotList([])
        for slot in slots:
            slot = Slot(slot) if slot is not None else None
            self.slots.append(slot)

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
        if slot is not None:
            slot = self.slots[slot_num].as_fastmc()
        self._send(self._proto.PlayServerboundClickWindow.id,
                   window_id=self._id,
                   slot=slot_num,
                   button=button,
                   action_num=action_num,
                   mode=mode,
                   clicked_item=slot)

        if not self._wait_for(lambda: action_num in self._confirmations.keys(),
                              timeout=5):
            return False
        if not self._confirmations.get(action_num):
            return False
        if (mode, button) in self._click_handlers:
            return self._click_handlers[(mode, button)](slot_num)

    def _left_click(self, slot_num):
        slot = self.slots[slot_num]
        self.slots[slot_num] = self.cursor_slot
        self.cursor_slot = slot
        return True

    def _shift_left_click(self, slot_num):
        # TODO validate what happens to clicked items base on current inventory
        return True

    def swap_slots(self, slot_num_a, slot_num_b):
        slot_a = self.slots[slot_num_a]
        slot_b = self.slots[slot_num_b]
        for num in [slot_num_a, slot_num_b, slot_num_a]:
            if not self.click(num):
                return False
        return self._wait_for(lambda: all([slot_a == self.slots[slot_num_b],
                                           slot_b == self.slots[slot_num_a]]))

    def _send(self, packet_id, **kwargs):
        self._send_queue.put((packet_id, kwargs))

    def _wait_for(self, what, timeout=10):
        start = time.time()
        with self._recv_condition:
            while not what() and time.time() - start < timeout:
                self._recv_condition.wait(timeout=1)
        return what()


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

    def index(self, _type):
        name = self._get_name(_type)
        for index, slot in enumerate(self):
            if slot is not None and slot.name == name:
                return index

    def window_index(self, _type):
        relative_index = self.index(_type)
        return relative_index + self.start


class Slot(object):
    def __init__(self, slot):
        self.item_id = slot.item_id
        self.count = slot.count
        self.damage = slot.damage
        self.nbt = slot.nbt

    def __repr__(self):
        return 'Slot(item_name="{}", count={}, damage={})'.format(
            self.name, self.count, self.damage)

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

    def as_fastmc(self):
        return fastmc.proto.Slot(
            self.item_id, self.count, self.damage, self.nbt)
