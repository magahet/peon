from peon import Xzy
from scipy.spatial.distance import euclidean
import time
import sys
import random
import itertools
import numpy
import os
import cPickle
import math

def kill(bot):
  DIAMOND_SWORD = 276
  DIAMOND_AXE=278
  XP_POINT = (-137, -177, 12)
  last_level = bot._xp_level + bot._xp_bar
  print 'level:', bot._xp_level

  while True: 
    if bot._xp_level >= 50:

      bot.enchant(DIAMOND_AXE)
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


def spiral(x=0, y=0):
  dx = 0
  dy = -1
  while True:
    yield (x, y)
    if x == y or (x < 0 and x == -y) or (x > 0 and x == 1-y):
      dx, dy = -dy, dx
    x, y = x+dx, y+dy



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
