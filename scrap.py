from mc import Xzy
from scipy.spatial.distance import euclidean
from scipy.linalg import solve
import time
import sys
import random
import itertools
import numpy
import os
import cPickle
import math
import json

def terraform(bot, start_point='base'):
  def under(x, z, y, distance=1):
    return Xzy(x, z, y - distance)

  def above(x, z, y, distance=1):
    return Xzy(x, z, y + distance)

  def dig_down(bot, xzy_surface, GROUND_LEVEL):
    for y in range(xzy_surface.y, GROUND_LEVEL + 1, -1):
      if not bot.break_block(xzy_surface.x, xzy_surface.z, y): return False
    return True

  def near_mob(bot, distance=16):
    HOSTILE_MOBS = set([50, 51, 52, 53, 54, 55, 56, 58, 59, 61, 62, 63])
    for e in bot.world._entities.values():
      if e._type in HOSTILE_MOBS:
        if euclidean(e._pos.xzy(), bot._pos.xzy()) <= distance:
          return True
    return False

  GROUND_LEVEL = 62
  TORCH = bot._block_ids['torch']
  DIRT = bot._block_ids['dirt']
  GRASS = bot._block_ids['grass block']
  STONE = bot._block_ids['cobblestone']
  DIAMOND_PICKAXE = bot._block_ids['diamond pickaxe']
  DIAMOND_SHOVEL = bot._block_ids['diamond shovel']
  BREAD = bot._block_ids['bread']
  SOLID = set(range(1, 5) + [7] + range(12, 27))
  NON_SOLID = set([0] + range(8, 12))
  STOP_FOR_FOOD = True


  with open('sites.json') as f:
    sites = json.load(f)
    bboxes = sites['bboxes']
    points = sites['return_bases']
    points['bot'] = bot._pos.xzy()

  protected = bboxes['base']
  
  start = points[start_point]

  bot.drop_items([DIRT, STONE, TORCH, DIAMOND_PICKAXE, DIAMOND_SHOVEL, BREAD], invert=True)
  print bot.get_inventory()

  s = spiral()
  i = 0
  furthest = 0
  while True:
    if i > 128:
      count = 0
      for num, item in bot.get_inventory():
        if item.itemId in [DIRT, STONE]:
          count += item.count
      if count > 256:
        i = 0
        print 'starting from beginning'
        bot.drop_items([DIRT, STONE, TORCH, DIAMOND_PICKAXE, DIAMOND_SHOVEL, BREAD], invert=True)
        s = spiral()
    x, z = s.next()
    xzy = Xzy(x + start[0], z + start[1], GROUND_LEVEL)
    distance = int(euclidean(xzy, start))

    if near_mob(bot):
      print 'mob alert'
      while near_mob(bot, distance=128):
        bot.MoveTo(*above(*bot._pos.xzy(), distance=10))
      time.sleep(3)

    if bot._food < 18:
      if not bot.eat() and STOP_FOR_FOOD:
        print 'need bread'
        bot.nav_to(start[0], start[1], 67)
        while not bot.eat():
          time.sleep(5)

    if distance > furthest and distance > 100:
      print 'distance:', distance
      furthest = distance

    if in_bbox(protected, xzy):
      continue

    xzy_surface = find_surface(bot, *xzy)
    if xzy_surface is None: continue

    if xzy_surface.y < GROUND_LEVEL:
      xzy_surface = xzy

    if xzy_surface.y > GROUND_LEVEL + 1:
      print 'clear column:', xzy_surface
      if not dig_down(bot, xzy_surface, GROUND_LEVEL): continue
      i+=1
      xzy_surface = xzy_surface._replace(y=GROUND_LEVEL + 2)

    if bot.world.GetBlock(*under(*xzy)) in NON_SOLID:
      if bot.equip_tool(STONE): 
        print 'place sub-layer:', xzy_surface
        bot.place_block(under(*xzy))

    if bot.world.GetBlock(*xzy) not in [DIRT, GRASS]:
      if bot.world.GetBlock(*xzy) not in NON_SOLID:
        print 'remove surface layer:', xzy_surface
        if not bot.break_block(*xzy): continue
      if not bot.equip_tool(DIRT): continue
      print 'place surface layer:', xzy_surface
      if not bot.place_block(xzy): continue

    if is_optimal_lighting_spot(*xzy) and bot.world.GetBlock(*above(*xzy)) == TORCH:
      continue
    elif bot.world.GetBlock(*above(*xzy)) != 0:
      print 'remove block from above surface:', xzy_surface
      if not bot.break_block(*above(*xzy)): continue
    
    if is_optimal_lighting_spot(*xzy):
      print 'place torch on optimal block:', xzy_surface
      if not bot.equip_tool(TORCH): continue
      if not bot.place_block(above(*xzy)): continue



def light_area(bot, width=100):
  SOLID = set(range(1, 5) + [7] + range(12, 27))
  TORCH = bot._block_ids['torch']
  start = bot._pos.xzy()
  s=spiral()
  print 'looking for spot'
  while euclidean(start, bot._pos.xzy()) <= width:
    x, z = s.next()
    pos = Xzy(start.x + x, start.z + z, start.y)
    pos_under = Xzy(start.x + x, start.z + z, start.y - 1)
    if not is_optimal_lighting_spot(*pos):
      if bot.world.GetBlock(*pos) == TORCH:
        print 'found misplaced torch'
        bot.nav_to(*pos)
        bot.break_block(*pos)
        time.sleep(1)
    else:
      if bot.world.GetBlock(*pos) == 0 and bot.world.GetBlock(*pos_under) in SOLID:
        print 'found spot for torch'
        if bot.equip_tool(TORCH):
          if not bot.nav_to(*pos):
            return False
          bot.place_block(pos)
        else:
          print 'need torch'

  return True

def in_bbox(bbox, xzy):
  xzy_dict = xzy._asdict()
  for a in bbox.keys():
    if xzy_dict[a] < min(bbox[a]) or xzy_dict[a] > max(bbox[a]):
      return False
  else:
    return True




def find_surface(bot, x, z, y):
  for y in range(128, 0, -1):
    blocktype = bot.world.GetBlock(x, z, y)
    if blocktype is None:
      return
    elif blocktype != 0:
      return Xzy(x, z, y)

def spiral(x=0, y=0):
  dx = 0
  dy = -1
  while True:
    yield (x, y)
    if x == y or (x < 0 and x == -y) or (x > 0 and x == 1-y):
      dx, dy = -dy, dx
    x, y = x+dx, y+dy

def is_optimal_lighting_spot(x, z, y):
  return sum(solve(numpy.array([[13,6],[1,7]]),numpy.array([x, z]))) % 1 <= 0.001

def kill(bot):
  DIAMOND_SWORD = 276
  DIAMOND_AXE=278
  XP_POINT = (-137, -177, 12)
  last_level = bot._xp_level + bot._xp_bar
  print 'level:', bot._xp_level

  while True: 
    if bot._xp_level >= 50:
      print 'enchanting axe'
      if not bot.enchant(DIAMOND_AXE):
        print 'no tools to enchant. leaving'
        bot.SendDisconnect()
        sys.exit()
      last_level = bot._xp_level + bot._xp_bar

    if bot._pos.xzy() != XP_POINT:
      print 'moving to xp farm'
      bot.nav_to(*XP_POINT)

    current_level = bot._xp_level + bot._xp_bar
    if current_level > last_level + 0.1:
      sys.stdout.write('%.1f' % current_level)
      sys.stdout.flush()
      last_level = current_level

    if bot._food < 10:
      if not bot.eat():
        print 'no more food. leaving'
        bot.SendDisconnect()
        sys.exit()

    if bot._health < 15:
      print 'health too low. leaving'
      bot.SendDisconnect()
      sys.exit()

    if not bot.equip_tool(DIAMOND_SWORD):
      print 'no sword. leaving'
      bot.SendDisconnect()
      sys.exit()

    attack_list = []
    entities = bot.world._entities
    for eid, e in entities.items():
      dist = euclidean(
          bot._pos.xzy(), e._pos.xzy())

      if dist <= 4 and e._player_name is None:
        attack_list.append(eid)

    for eid in attack_list:
      sys.stdout.write('.')
      sys.stdout.flush()
      bot.SendUseEntity(bot._entityId, eid, 1)
      time.sleep(.3)
    time.sleep(1)


def explore(bot):
  time.sleep(5)
  searched_chunks = set([])
  pos = bot._pos
  bot.nav_to(pos.x, pos.z, 200)

  for x, z in spiral(x=0, y=0):
    bot.MoveTo(x*160, z*160, 200)
    for xz, chunk in bot.world._chunks.items():
      if xz not in searched_chunks:
        searched_chunks.add(xz)
        with open(os.path.join('/var/peon', '%s.%s.p' % xz), 'w') as f:
          cPickle.dump(chunk, f)
    print Xzy(bot._pos.x, bot._pos.z, bot._pos.y), len(searched_chunks)

def find_spawners():
  MONSTER_SPAWNER=52
  spawner_points = cPickle.load(open('spawner_points.p'))
  searched_chunks = cPickle.load(open('searched_chunks.p'))

  for fn in os.listdir('/var/peon'):
    parts = fn.split('.')
    try:
      x, z = int(parts[0]), int(parts[1])
    except:
      continue

    if (x,z) not in searched_chunks:
      print (x,z)
      with open(os.path.join('/var/peon', fn)) as f:
        chunk = cPickle.load(f)
        for p in search_for_points(chunk, MONSTER_SPAWNER):
          spawner_points.add(p)

        searched_chunks.add((chunk.chunkX, chunk.chunkZ))

        with open('spawner_points.p', 'w') as f2:
          cPickle.dump(spawner_points, f2)

        with open('searched_chunks.p', 'w') as f2:
          cPickle.dump(searched_chunks, f2)



def find_xp_site():    
  MONSTER_SPAWNER=52
  spawner_points = set([])

  for p in search_for_points(chunk, MONSTER_SPAWNER):
    spawner_points.add(p)
  cluster = find_cluster(spawner_points)
  if cluster  is not None:
    print 'FOUND:', cluster
    return

def search_for_points(chunk, block_type):
  points = []
  for i, v in enumerate(chunk._blocks):
    if v == block_type:
      y, r = divmod(i, 256)
      z, x = divmod(r, 16)
      points.append((x + (chunk.chunkX*16), y, z + (chunk.chunkZ*16)))
  return points


def find_cluster(points, size=3):
  def is_close(points, dist=32):
    for two_points in itertools.combinations(l, 2):
      if euclidean(two_points[0], two_points[1]) > dist:
        return False
    else:
      return True

  n = len(points)
  r = size
  num = math.factorial(n) / (math.factorial(n-r) * math.factorial(r))
  start = time.time()
  print 'Combinations to analyze:', num
  i = 0
  for l in itertools.combinations(points, size):
    if i%(num/100) == 0:
      print int(i/num) * 100
      print i / (time.time() - start)
    i+=1

    if is_close(l):
      centroid = [int(numpy.average([p[i] for p in l])) for i in range(3)]
      for p in l:
        if euclidean(p, centroid) > 16:
          break
      else:
        return l




def find_block_path(start, block_type=None):
    m = pickle.load(open('m.p', 'rb'))

    if block_type is None:
      block_list = m['diamond ore'] + m['gold ore']
    else:
      block_list = m[block_type]

    cluster = []
    cluster_list = []

    for block in block_list:
        for cluster in cluster_list:
            for b in cluster:
                if cityblock(block, b) < 5:
                    cluster.append(block)
                    break
            else:
                continue
            break
        else:
            cluster = [block]
            cluster_list.append(cluster)

  
    start = [start.x, start.z, start.y]
    sites = [ c[0] for c in cluster_list ]

    path = [start]
    while len(sites) > 0:
        i = find_nearest(path[-1], sites)
        path.append(sites.pop(i))

    #d = sorted(cluster_list, key=lambda b: cityblock(start, numpy.array(b[0]))) 

    print 'locations:' 
    for c in path:
        print c



def get_world_data(bot):
    print bot._pos
    bot.WaitFor(lambda: bot.world.GetBlock(bot._pos.x, bot._pos.z, bot._pos.y) is not None)

    print 'giving server time to load chucks'
    time.sleep(10)

    w = bot.world
    print 'saving world...'
    pickle.dump(w, open('world.p', 'wb'))
    print 'done'
    sys.exit()


def find_blocktypes():
    c = csv.DictReader(open('blocktypes.csv'), skipinitialspace=True)
    bt = dict([(int(l['dec']), l['type']) for l in c ])

    interesting = [
        'diamond ore',
        'gold ore',
        'iron ore',
        'monster spawner'
    ]

    print 'loading world...',
    w = pickle.load(open('world.p', 'rb'))
    print 'done'

    m = collections.defaultdict(list)
    print 'searching blocks...',
    for xz, chunk in w._chunks.items():
        print '.',
        cx, cz = xz

        for i, v in enumerate(chunk._blocks):
            #print bt[v]
            if bt[v] in interesting:
                y, r = divmod(i, 256)
                z, x = divmod(r, 16)
                m[bt[v]].append((x + (cx*16), y, z + (cz*16)))
    print

    print 'saving block lists...',
    pickle.dump(m, open('m.p', 'wb'))
    print 'done'


def find_nearest(start, sites):
  d = [ cityblock(start, site) for site in sites ]
  return d.index(min(d))






def DigShaft(self, xRange, zRange, yRange):
  def Dist(xzyA, xzyB):
    return math.sqrt(
        (xzyA.x - xzyB.x) * (xzyA.x - xzyB.x) +
        (xzyA.z - xzyB.z) * (xzyA.z - xzyB.z) +
        (xzyA.y - xzyB.y) * (xzyA.y - xzyB.y)
        )
  def Within(dist, xzyA, xzyB):
    if Dist(xzyA, xzyB) < dist and Xzy(xzyB.x, xzyB.z, xzyB.y - 1) != xzyA:
      return xzyB
  def WantSolid(x, z, y):
    for xzyAdj, typeAdj in self.world.IterAdjacent(x, z, y):
      if typeAdj in (8, 9, 10, 11): # lava, water
        return True
    if self.world.GetBlock(x, z, y + 1) in (12, 13): # sand, gravel
      return True
    xFirst, xLast = xRange[0], xRange[1] - 1
    zFirst, zLast = zRange[0], zRange[1] - 1
    # Steps against z walls
    if z == zFirst:
      return not ((x - xFirst + y) % 5)
    if z == zLast:
      return not ((xLast - x + y) % 5)
    # walkways on x walls, and flanking z-steps
    if x == xFirst or x == xLast or z == zFirst + 1 or z == zLast - 1:
      return not (y % 5)
    return False
  keepDigging = True
  while keepDigging:
    keepDigging = False
    for y in range(*yRange):
      for x in range(*xRange):
        for z in range(*zRange):
          blockXzy = Xzy(x, z, y)
          print "Waiting for chunks to load..."
          self.WaitFor(lambda: self.world.GetBlock(*blockXzy) is not None)
          blockType = self.world.GetBlock(*blockXzy)
          print "blockType:", blockType
          if blockType in ignore_blocktypes:
            continue
          if WantSolid(*blockXzy):
            #print "Want block solid:", blockXzy, blockType
            # TODO: place
            continue
          print "Wanna dig block:", blockXzy, blockType
          botXzy = Xzy(self._pos.x, self._pos.z, self._pos.y)
          nextXzy = self.world.FindNearestStandable(botXzy,
              functools.partial(Within, 6, blockXzy))
          if not nextXzy:
            print "But can't find a digging spot ;("
            continue
          print "Wanna go to:", nextXzy
          path = self.world.FindPath(botXzy, nextXzy)
          if not path:
            print "But no path :("
            continue
          print "Moving to:", nextXzy
          for xzy in path:
            print "mini - Move to:", xzy
            self.MoveTo(*xzy)
          print "Digging:", blockXzy, blockType
          if self.DoDig(blockXzy.x, blockXzy.z, blockXzy.y):
            keepDigging = True
            print "block broken!"
            self.FloatDown()
          else:
            print "block NOT broken!"
          #time.sleep(5)
