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
        self.locks = [l for l in locks if l is not None]

    def __enter__(self, *args, **kwargs):
        for lock in self.locks:
            self.lock.acquire()

    def __exit__(self, *args, **kwargs):
        for lock in self.locks:
            self.lock.release()
