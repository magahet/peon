import threading


class ThreadSafeCounter:
    def __init__(self, start=0, step=1):
        self.i = start
        self.step = step
        # create a lock
        self.lock = threading.Lock()

    def __iter__(self):
        return self

    def next(self):
        # acquire/release the lock when updating self.i
        with self.lock:
            self.i += self.step
            return self.i


class LocksWrapper(object):
    def __init__(self, locks):
        self.locks = locks

    def __repr__(self):
        return 'LocksWrapper([{}])'.format(
            ', '.join(self.locks.keys()))

    def __enter__(self, *args, **kwargs):
        for lock in self.locks.itervalues():
            lock.acquire()

    def __exit__(self, *args, **kwargs):
        for lock in self.locks.itervalues():
            lock.release()


def iter_spiral(x=0, y=0):
    dx = 0
    dy = -1
    while True:
        yield (x, y)
        if x == y or (x < 0 and x == -y) or (x > 0 and x == 1 - y):
            dx, dy = -dy, dx
        x, y = x + dx, y + dy
