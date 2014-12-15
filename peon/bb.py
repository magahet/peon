'''This module provides a class for representing the constraints of the area'''


class BoundingBox(object):
    '''Defines constraints of the box'''

    def __init__(self, p1, p2):
        '''Set the edges of the bounding box based on the observed data'''
        self._max = [max([p1[i], p2[i]]) for i in xrange(3)]
        self._min = [min([p1[i], p2[i]]) for i in xrange(3)]

    def iter_points(self, axis_order=None, assending=None):
        for y in xrange(self._max[1], self._min[1] + 1, -1):
            for z in xrange(self._max[2], self._min[2] + 1, -1):
                for x in xrange(self._max[0], self._min[0] + 1, -1):
                    yield (x, y, z)
