from types import ItemTypes


class Window(object):
    def __init__(self, windowId, slots):
        self.slots = slots
        self.count = len(slots)
        self.inventory_type = None
        self.window_title = None

    def get_main_inventory(self):
        return self.slots[-36:-9]

    def get_held(self):
        return self.slots[-9:]

    def set_slot(self, index, slot):
        self.slots[index] = Slot(slot)


class Slot(object):
    def __init__(self, slot):
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
