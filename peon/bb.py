"""Provides an n-dimensional bounding box representation."""


class BoundingBox(object):

    """Represents an n-dimensional bounding box."""

    def __init__(self, p1, p2):
        """Set the edges of the bounding box based on the observed data."""
        self._max = tuple(max([p1[i], p2[i]]) for i in xrange(len(p1)))
        self._min = tuple(min([p1[i], p2[i]]) for i in xrange(len(p1)))

    def __contains__(self, point):
        """Determine if the given point is within the bounding box."""
        for index, value in enumerate(point):
            if value < self._min[index] or value > self._max[index]:
                return False
        return True

    def __repr__(self):
        """Return the min and max values of the bounding box."""
        return 'BoundingBox({}, {})'.format(self._max, self._min)

    def __str__(self):
        """Return string representation of the bounding box."""
        return self.__repr__()

    def __iter__(self):
        for point in self.iter_points():
            yield point

    def iter_points(self, axis_order=None, ascending=True, zig_zag=None,
                    point=None):
        """Iterate through points in the bounding box.

        Keyword arguments:
            axis_order -- the order in which dimensions are iterated over
            ascending -- whether to iterate in ascending order (default True)
            zig_zag -- a bool list indicating whether to iterate up then down
                       alternately for each axis.
            point -- used for recursive calls (do not set manually)
        """
        if axis_order is None:
            axis_order = range(len(self._max))
        if point is None:
            point = [None for i in xrange(len(self._max))]
        if zig_zag is None:
            zig_zag = [False for i in xrange(len(self._max))]
        index = axis_order.pop(0)
        if axis_order and axis_order[0] in zig_zag:
            zig_zag_current = True
        else:
            zig_zag_current = False
        start = self._min[index] if ascending else self._max[index]
        end = self._max[index] if ascending else self._min[index]
        step = 1 if ascending else -1
        for value in xrange(start, end + step, step):
            point[index] = value
            if len(axis_order) == 0:
                yield tuple(point)
            else:
                for sub_point in self.iter_points(
                        axis_order[:], ascending, zig_zag[:], point):
                    yield tuple(sub_point)
            ascending = not ascending if zig_zag_current else ascending
