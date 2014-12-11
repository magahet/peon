import threading
from fastmc.proto import NbtTag
import itertools
import scipy.spatial as ss
import numpy as np


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


def unpack_nbt(tag):
    if not isinstance(tag, NbtTag):
        return None
    if tag.tag_type == NbtTag.LIST:
        return [unpack_nbt(i) for i in tag.values]
    if tag.tag_type == NbtTag.COMPOUND:
        return {k: unpack_nbt(t) for k, t in tag.value.iteritems()}
    else:
        return tag.value


class Cluster(object):
    def __init__(self, cluster_points):
        self.centroid = tuple(int(i) for i in
                              np.mean(cluster_points, axis=0))
        self.points = tuple(tuple(int(i) for i in c) for
                            c in cluster_points)
        self.size = len(cluster_points)

    def __repr__(self):
        return 'Cluster(centroid={}, size={})'.format(self.centroid, self.size)


def get_clusters(points, radius):
    tree = ss.KDTree(np.array(points))
    neighbors = [tree.query_ball_point(p, radius * 2) for
                 i, p in enumerate(points)]
    clusters = set([tuple(set(a).intersection(b)) for
                    a, b in itertools.combinations(neighbors, 2)])
    return [Cluster(points[np.array(cluster)]) for
            cluster in list(clusters) if len(cluster) >= 2]
