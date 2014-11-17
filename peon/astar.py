from heapq import heappush, heappop
from sys import maxint
import time


# Represent each node as a list, ordering the elements so that a heap of nodes
# is ordered by f = g + h, with h as a first, greedy tie-breaker and num as a
# second, definite tie-breaker. Store the redundant g for fast and accurate
# calculations.

F, H, NUM, G, POS, OPEN, VALID, PARENT = xrange(8)


def astar(start_pos, neighbors, goal, start_g, cost, heuristic, timeout=5,
          debug=None):

    """Find the shortest path from start to goal.

    Arguments:

      start_pos      - The starting position.
      neighbors(pos) - A function returning all neighbor positions of the given
                       position.
      goal(pos)      - A function returning true given a goal position, false
                       otherwise.
      start_g        - The starting cost.
      cost(a, b)     - A function returning the cost for moving from one
                       position to another.
      heuristic(pos) - A function returning an estimate of the total cost
                       remaining for reaching goal from the given position.
                       Overestimates can yield suboptimal paths.
      timeout        - The maximum number of seconds to search.
      debug(nodes)   - This function will be called with a dictionary of all
                       nodes.

    The function returns the best path found. The returned path excludes the
    starting position.
    """

    # Test for one step paths
    for pos in neighbors(start_pos):
        if goal(pos):
            return [pos]

    # Create the start node.
    nums = iter(xrange(maxint))
    start_h = heuristic(start_pos)
    start = [start_g + start_h, start_h, nums.next(), start_g, start_pos, True,
             True, None]

    # Track all nodes seen so far.
    nodes = {start_pos: start}

    # Maintain a heap of nodes.
    heap = [start]

    # Track the best path found so far.
    best = start

    # Record start time
    start_time = time.time()

    while heap:

        # Pop the next node from the heap.
        current = heappop(heap)
        current[OPEN] = False

        # Have we reached the goal?
        if goal(current[POS]):
            best = current
            break

        # Visit the neighbors of the current node.
        for neighbor_pos in neighbors(current[POS]):
            neighbor_g = current[G] + cost(current[POS], neighbor_pos)
            neighbor = nodes.get(neighbor_pos)
            if neighbor is None:

                # Limit the search.
                #if len(nodes) >= limit:
                    #continue
                if time.time() - start_time > timeout:
                    return None

                # We have found a new node.
                neighbor_h = heuristic(neighbor_pos)
                neighbor = [neighbor_g + neighbor_h, neighbor_h, nums.next(),
                            neighbor_g, neighbor_pos, True, True, current[POS]]
                nodes[neighbor_pos] = neighbor
                heappush(heap, neighbor)
                if neighbor_h < best[H]:

                    # We are approaching the goal.
                    best = neighbor

            elif neighbor_g < neighbor[G]:

                # We have found a better path to the neighbor.
                if neighbor[OPEN]:

                    # The neighbor is already open. Finding and updating it
                    # in the heap would be a linear complexity operation.
                    # Instead we mark the neighbor as invalid and make an
                    # updated copy of it.

                    neighbor[VALID] = False
                    nodes[neighbor_pos] = neighbor = neighbor[:]
                    neighbor[F] = neighbor_g + neighbor[H]
                    neighbor[NUM] = nums.next()
                    neighbor[G] = neighbor_g
                    neighbor[VALID] = True
                    neighbor[PARENT] = current[POS]
                    heappush(heap, neighbor)

                else:

                    # Reopen the neighbor.
                    neighbor[F] = neighbor_g + neighbor[H]
                    neighbor[G] = neighbor_g
                    neighbor[PARENT] = current[POS]
                    neighbor[OPEN] = True
                    heappush(heap, neighbor)

        # Discard leading invalid nodes from the heap.
        while heap and not heap[0][VALID]:
            heappop(heap)

    if debug is not None:
        # Pass the dictionary of nodes to the caller.
        debug(nodes)

    # Return the best path as a list.
    path = []
    current = best
    while current[PARENT] is not None:
        path.append(current[POS])
        current = nodes[current[PARENT]]
    path.reverse()
    return path
