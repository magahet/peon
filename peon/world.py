from scipy.spatial.distance import euclidean
import scipy.spatial as ss
import numpy as np
from math import floor
import smpmap
import astar
from types import (MobTypes, ItemTypes, ObjectTypes, Door, TrapDoor)
from window import Slot
import logging
import time
import utils


log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class World(smpmap.World):

    adjacent_sets = (
        (1, (
            np.array([-1, 0, 0]),
            np.array([1, 0, 0]),
            np.array([0, -1, 0]),
            np.array([0, 1, 0]),
            np.array([0, 0, -1]),
            np.array([0, 0, 1]),
        )),
        (1.5, (
            np.array([-1, -1, 0]),
            np.array([1, -1, 0]),
            np.array([-1, 1, 0]),
            np.array([1, 1, 0]),
            np.array([0, -1, -1]),
            np.array([0, 1, -1]),
            np.array([0, -1, 1]),
            np.array([0, 1, 1]),
        )),
        (2, (
            np.array([-1, 0, -1]),
            np.array([1, 0, -1]),
            np.array([-1, 0, 1]),
            np.array([1, 0, 1]),
        )),
        (3, (
            np.array([-1, -1, -1]),
            np.array([1, -1, -1]),
            np.array([-1, 1, -1]),
            np.array([1, 1, -1]),
            np.array([-1, -1, 1]),
            np.array([1, -1, 1]),
            np.array([-1, 1, 1]),
            np.array([1, 1, 1]),
        )),
    )

    def __init__(self):
        self.columns = {}
        self.entities = {}
        self.block_entities = {}
        self.players = {}
        self.player_data = {}
        self.objects = {}
        self.dimmension = 0

    def iter_entities(self, types=None):
        if hasattr(types, '__iter__'):
            types = [t if isinstance(t, int)
                     else MobTypes.get_id(t)
                     for t in types]
        for entity in self.entities.values():
            if types is None or entity._type in types:
                yield entity

    def iter_objects(self, types=None, items=None):
        if hasattr(types, '__iter__'):
            types = [t if isinstance(t, int)
                     else ObjectTypes.get_id(t)
                     for t in types]
        if hasattr(items, '__iter__'):
            items = [i if isinstance(i, basestring)
                     else ItemTypes.get_name(*i)
                     for i in items]
        for obj in self.objects.values():
            if types is None or obj._type in types:
                if ObjectTypes.get_name(obj._type) == 'Item Stack':
                    slot = Slot(obj.metadata.get(10, (None, None))[1])
                    if items is None or slot.name in items:
                        yield obj
                elif items is None:
                    yield obj

    def is_solid_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        if _type is None:
            return False
        elif ItemTypes.is_solid(_type):
            return True
        elif ItemTypes.is_door(_type):
            door = Door(_type, self.get_meta(x, y, z))
            return door.is_closed()
        elif ItemTypes.is_trap_door(_type):
            trap_door = TrapDoor(_type, self.get_meta(x, y, z))
            return trap_door.is_closed()
        return False

    def is_water_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        if _type is None:
            return False
        return ItemTypes.is_water(_type)

    def is_unbreakable_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return False if _type is None else ItemTypes.is_unbreakable(_type)

    def is_climbable_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return False if _type is None else ItemTypes.is_climbable(_type)

    def is_breathable_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return True if _type is None else ItemTypes.is_breathable(_type)

    def is_safe_non_solid_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return True if _type is None else ItemTypes.is_safe_non_solid(_type)

    def is_liquid_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return False if _type is None else ItemTypes.is_liquid(_type)

    def is_falling_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        return False if _type is None else ItemTypes.is_falling(_type)

    def is_harvestable_block(self, x, y, z):
        _type = self.get_id(x, y, z)
        meta = self.get_meta(x, y, z)
        return False if _type is None else ItemTypes.is_harvestable(_type, meta)

    def get_next_highest_solid_block(self, x, y, z):
        for y in xrange(int(y), -1, -1):
            if self.is_solid_block(x, y, z):
                return (x, y, z)

    def get_player_position(self, player_name=None, eid=None, uuid=None):
        player = None
        if player_name is not None:
            for uuid, data in self.player_data.items():
                if data.get('name', '') == player_name:
                    for eid, cur_player in self.players.items():
                        if cur_player.uuid == uuid:
                            return cur_player.get_position(floor=True)
        elif eid is not None:
            player = self.players.get(eid)
        elif uuid is not None:
            for eid, cur_player in self.players.items():
                if player.uuid == uuid:
                    player = cur_player
                    break
        if player is not None:
            return player.get_position(floor=True)

    @classmethod
    def iter_adjacent(cls, x, y, z, center=False, degrees=3):
        point = np.array([x, y, z])
        if center:
            yield (x, y, z)
        for degree, dt_set in cls.adjacent_sets:
            if degree <= degrees:
                for dt in dt_set:
                    yield tuple(point + dt)

    @staticmethod
    def iter_adjacent_2d(x, z, center=False):
        for dx in xrange(-1, 2):
            for dz in xrange(-1, 2):
                if not center and (dx, dz) == (0, 0):
                    continue
                yield (x + dx, z + dz)

    def iter_moveable_adjacent(self, x0, y0, z0):
        for x, y, z in self.iter_adjacent(x0, y0, z0):
            if self.is_moveable(x0, y0, z0, x, y, z):
                yield (x, y, z)

    def iter_diggable_adjacent(self, x0, y0, z0):
        for x, y, z in self.iter_adjacent(x0, y0, z0, degrees=1.5):
            if self.is_diggable(x0, y0, z0, x, y, z):
                yield (x, y, z)

    def iter_reachable(self, x, y, z, _range=10):
        '''iter positions that are reachable within a given range'''
        _open = [(x, y, z)]
        closed = set([])
        while _open:
            current = _open.pop(0)
            yield current
            closed.add(current)
            for neighbor in self.iter_moveable_adjacent(*current):
                if neighbor in closed or neighbor in _open:
                    continue
                distance = euclidean((x, y, z), neighbor)
                if distance <= _range:
                    _open.append(neighbor)

    def iter_block_types(self, x, y, z, block_types, _range=None):
        '''iter blocks of a certain types'''
        block_types = [i if isinstance(i, int)
                       else ItemTypes.get_block_id(i)
                       for i in block_types]
        _open = [(x, y, z)]
        closed = set([])
        while _open:
            current = _open.pop(0)
            if self.get_id(*current) in block_types:
                yield current
            closed.add(current)
            for neighbor in self.iter_adjacent(*current):
                if neighbor in closed or neighbor in _open:
                    continue
                if self.get_id(*neighbor) == 0:  # Air block
                    continue
                if _range is None or euclidean((x, y, z), neighbor) <= _range:
                    _open.append(neighbor)

    def iter_nearest_from_block_types(self, x, y, z, block_types, limit=None):
        points = np.array(
            [p for p in
             self.iter_block_types_in_surrounding_chunks(x, y, z, block_types)])
        if len(points) < 2:
            for point in points:
                yield (int(i) for i in point)
        else:
            tree = ss.KDTree(points)
            result = tree.query((x, y, z), k=limit)
            indexies = result[1]
            for num in xrange(len(indexies)):
                yield (int(i) for i in points[indexies[num]])

    def iter_block_types_in_surrounding_chunks(self, x, y, z, block_types):
        cx, cz = x // 16, z // 16
        for (cx, cz) in self.iter_adjacent_2d(cx, cz, center=True):
            for position in self.iter_block_types_in_chunk(cx, cz, block_types):
                yield position

    def iter_block_types_in_chunk(self, cx, cz, block_types):
        ids = [ItemTypes.get_block_id(_type) for
               _type in block_types]
        column = self.columns.get((cx, cz))
        if column is not None:
            for y_index, chunk in enumerate(column.chunks):
                if chunk is None:
                    continue
                for index, data in enumerate(chunk['block_data'].data):
                    if data >> 4 in ids:
                        log.debug('c_index: %d, y_index: %d, (cx, cz): %s',
                                  index, y_index, str((cx, cz)))
                        dy, r = divmod(index, 16 * 16)
                        dz, dx = divmod(r, 16)
                        x, y, z = dx + cx * 16, dy + y_index * 16, dz + cz * 16
                        yield (x, y, z)

    def get_name(self, x, y, z):
        return ItemTypes.get_block_name(self.get_id(x, y, z))

    def get_height(self, x, y, z):
        return ItemTypes.get_block_height(self.get_id(x, y, z),
                                          self.get_meta(x, y, z))

    def is_moveable(self, x0, y0, z0, x, y, z, with_floor=True):
        # check target spot
        if with_floor:
            if not self.is_standable(x, y, z):
                return False
        else:
            if not self.is_passable(x, y, z):
                return False

        if y > y0:
            return (
                self.is_passable(x0, y, z0) and
                self.is_moveable(x0, y, z0, x, y, z)
            )
        elif y < y0:
            return self.is_moveable(x0, y0, z0, x, y0, z, with_floor=False)

        # check if horizontal x z movement
        if x0 == x or z0 == z:
            return True

        # check diagonal x z movement
        return (
            self.is_passable(x0, y, z) and
            self.is_passable(x, y, z0) and
            (
                self.is_safe_non_solid_block(x, y - 1, z0) or
                self.is_climbable_block(x, y - 1, z0)
            ) and
            (
                self.is_safe_non_solid_block(x0, y - 1, z) or
                self.is_climbable_block(x0, y - 1, z)
            )
        )

    def is_diggable(self, x0, y0, z0, x, y, z, with_floor=True):
        # don't dig or move straight up or down
        if (x0, z0) == (x, z):
            return False

        # if moveable, no need to dig
        if self.is_moveable(x0, y0, z0, x, y, z, with_floor=with_floor):
            return True

        # check target spot
        if not (
            self.is_safe_to_break(x, y, z) and
            self.is_safe_to_break(x, y + 1, z)
        ):
            #log.info('not safe to break: %s', str((x, y, z)))
            return False

        if (with_floor and
                not self.is_climbable_block(x, y - 1, z) and
                not self.is_water_block(x, y - 1, z)):
            #log.info('not climbable: %s', str((x, y - 1, z)))
            return False

        if y > y0:
            return (
                self.is_safe_to_break(x0, y, z0) and
                self.is_safe_to_break(x0, y + 1, z0) and
                self.is_diggable(x0, y, z0, x, y, z)
            )
        elif y < y0:
            return self.is_diggable(x0, y0, z0, x, y0, z, with_floor=False)

        # check if horizontal x z movement
        if x0 == x or z0 == z:
            return True

        #log.info('checking diag. should not: %s', str((x0, y0, z0, x, y, z)))
        # check diagonal x z movement
        return (
            self.is_safe_to_break(x0, y, z) and
            self.is_safe_to_break(x0, y + 1, z) and
            self.is_safe_to_break(x, y, z0) and
            self.is_safe_to_break(x, y + 1, z0) and
            (
                self.is_safe_non_solid_block(x, y - 1, z0) or
                self.is_climbable_block(x, y - 1, z0)
            ) and
            (
                self.is_safe_non_solid_block(x0, y - 1, z) or
                self.is_climbable_block(x0, y - 1, z)
            )
        )

    def get_blocks_to_break(self, x0, y0, z0, x, y, z):
        if (x0, y0, z0) == (x, y, z):
            return set([])
        positions = set([
            (x, y, z),
            (x, y + 1, z),
        ])
        if y > y0:
            positions.update([
                (x0, y, z0),
                (x0, y + 1, z0),
            ])
            positions.update(self.get_blocks_to_break(x0, y, z0, x, y, z))
        elif y < y0:
            positions.update(self.get_blocks_to_break(x0, y0, z0, x, y0, z))

        if x0 == x or z0 == z:
            return set([p for p in positions if self.is_solid_block(*p)])

        positions.update([
            (x0, y, z),
            (x0, y + 1, z),
            (x, y, z0),
            (x, y + 1, z0),
        ])

        return set([p for p in positions if self.is_solid_block(*p)])

    def is_safe_to_break(self, x, y, z):
        if self.is_unbreakable_block(x, y, z):
            return False
        if self.is_falling_block(x, y + 1, z):
            return False
        for x, y, z in self.iter_adjacent(x, y, z, degrees=1):
            if self.is_liquid_block(x, y, z):
                return False
        return True

    def is_standable(self, x, y, z):
        return (
            self.is_breathable_block(x, y + 1, z) and
            self.is_safe_non_solid_block(x, y + 1, z) and
            self.is_safe_non_solid_block(x, y, z) and
            (
                self.is_climbable_block(x, y - 1, z) or
                self.is_water_block(x, y - 1, z)
            )
        )

    def is_passable(self, x, y, z):
        return (
            self.is_safe_non_solid_block(x, y + 1, z) and
            self.is_safe_non_solid_block(x, y, z)
        )

    def find_path(self, x0, y0, z0, x, y, z, space=0, timeout=10,
                  digging=False, debug=None):

        def iter_moveable_adjacent(pos):
            return self.iter_adjacent(*pos)

        def iter_diggable_adjacent(pos):
            return self.iter_adjacent(*pos, degrees=1.5)

        def is_diggable(current, neighbor):
            x0, y0, z0 = current
            x, y, z = neighbor
            return self.is_diggable(x0, y0, z0, x, y, z)

        def is_moveable(current, neighbor):
            x0, y0, z0 = current
            x, y, z = neighbor
            return self.is_moveable(x0, y0, z0, x, y, z)

        def block_breaking_cost(p1, p2, weight=7):
            x0, y0, z0 = p1
            x, y, z = p2
            return 1 + len(self.get_blocks_to_break(x0, y0, z0, x, y, z)) * 0.5

        # TODO pre-check the destination for a spot to stand
        log.debug('looking for path from: %s to %s', str((x0, y0, z0)), str((x, y, z)))
        if digging:
            if not (
                self.is_safe_to_break(x, y, z) and
                self.is_safe_to_break(x, y + 1, z)
            ):
                return None
            neighbor_function = iter_diggable_adjacent
            #cost_function = block_breaking_cost
            cost_function = euclidean
            validation_function = is_diggable
        else:
            if space == 0 and not self.is_standable(x, y, z):
                return None
            neighbor_function = iter_moveable_adjacent
            cost_function = euclidean
            validation_function = is_moveable

        start = time.time()
        path = astar.astar(
            (floor(x0), floor(y0), floor(z0)),              # start_pos
            neighbor_function,                              # neighbors
            validation_function,                            # validation
            lambda p: euclidean(p, (x, y, z)) <= space,     # at_goal
            0,                                              # start_g
            cost_function,                                  # cost
            lambda p: euclidean(p, (x, y, z)),              # heuristic
            timeout,                                        # timeout
            debug,                                          # debug
            digging                                         # digging
        )
        if path:
            log.debug('Path found in %d sec. %d long.',
                      int(time.time() - start), len(path))
        else:
            log.debug('Path not found: %s to %s.',
                      str((x0, y0, z0)), str((x, y, z)))
        return path

    def get_mob_spawner_clusters(self):
        points = [p for p, b in self.block_entities.iteritems() if
                  b._type == 'MobSpawner']
        results = []
        for cluster in utils.get_clusters(points, 16):
            cluster.mob_types = [
                self.block_entities.get(p, {}).get('EntityId') for
                p in cluster.points]
            results.append(cluster)
        return results
