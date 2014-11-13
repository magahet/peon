from types import ItemTypes
import time
import fastmc.proto


class Window(object):
    def __init__(self, window_id, slots, action_num_counter, send_queue,
                 proto, recv_condition):
        self._id = window_id
        self.slots = slots
        self.count = len(slots)
        self.inventory_type = None
        self.window_title = None
        self.cursor_slot = None
        self._action_num_counter = action_num_counter
        self._send_queue = send_queue
        self._proto = proto
        self._recv_condition = recv_condition
        self._confirmations = {}
        self._click_handlers = {
            (0, 0): self._left_click,
        }

    def set_slot(self, index, slot):
        self.slots[index] = Slot(slot)

    def get_main_inventory(self):
        return self.slots[-36:-9]

    def get_held(self):
        return self.slots[-9:]

    def click(self, slot_num, button=0, mode=0):
        action_num = self._action_num_counter.next()
        slot = self.slots[slot_num]
        if slot is not None:
            slot = self.slots[slot_num].as_fastmc()
        print slot
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

    def _send(self, packet_id, **kwargs):
        self._send_queue.put((packet_id, kwargs))

    def _wait_for(self, what, timeout=10):
        start = time.time()
        with self._recv_condition:
            while not what() and time.time() - start < timeout:
                self._recv_condition.wait(timeout=1)
        return what()


class Slot(object):
    def __init__(self, slot):
        print slot
        self.item_id = slot.item_id
        self.count = slot.count
        self.damage = slot.damage
        self.nbt = slot.nbt

    def __repr__(self):
        return 'Slot(item_name="{}", count={}, damage={}'.format(
            self.name, self.count, self.damage)

    @property
    def name(self):
        return ItemTypes.get_name(self.item_id, self.damage)

    def as_fastmc(self):
        return fastmc.proto.Slot(
            self.item_id, self.count, self.damage, self.nbt)
