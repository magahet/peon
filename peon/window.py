class Window(object):
    def __init__(self, windowId, slots):
        self._slots = slots
        self._count = len(slots)
        self.inventory_type = None
        self.window_title = None

    def get_main_inventory(self):
        return self._slots[-36:-9]

    def get_held(self):
        return self._slots[-9:]

    def set_slot(self, index, slot):
        self._slots[index] = slot
