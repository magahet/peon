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
        self.slots[index] = slot
