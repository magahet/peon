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

def click_chest(bot):
  #bot.nav_to(-2, 52, 67)
  xzy = Xzy(-6, 50, 66)
  s=bot.windows[0]._slots[36]
  bot.SendPlayerBlockPlacement(xzy.x, xzy.y, xzy.z, 1, s)
  

def find_shallow_iron(world, start, depth=10, width=10):
  y_range = range(start.y, start.y - depth*2 , -1)
  x_range = range(start.x - width, start.x + width)
  z_range = range(start.z - width, start.z + width)
  #print y_range, x_range, z_range
  blocks = []
  for y in y_range:
    for x in x_range:
      for z in z_range:
        block = Xzy(x, z, y)
        block_type = world.GetBlock(*block)
        if block_type == 15:
          i = 1
          while world.GetBlock(block.x, block.z, block.y + i) != 0:
            i+=1

          if i < depth:
            blocks.append((block, i))
  return blocks


def eat(bot):
  BREAD = 297
  if not bot.equip_tool(BREAD):
    return False

  slot = bot.get_slot(36)
  while slot.itemId == BREAD and slot.count > 0 and bot._food < 18:
    bot.SendPlayerBlockPlacement(-1, -1, -1, -1, slot)
    time.sleep(1)
    slot = bot.get_slot(36)
  time.sleep(1)
  bot.SendPlayerDigging(5, 0, 0, 0, 255)

  sys.stdout.write('fl%db%d' % (bot._food, slot.count))
  sys.stdout.flush()

  if bot._food >= 18:
    return True
  else:
    return False



def kill(bot):
  DIAMOND_SWORD = 276

  bot.MoveTo(-137, -177, 12)
  last_level = bot._xp_level + bot._xp_bar

  while True:
    current_level = bot._xp_level + bot._xp_bar
    if current_level > last_level + 0.1:
      if current_level >= 50:
        print 'DONE'
        bot.SendDisconnect()
        sys.exit()

      sys.stdout.write('%.1f' % current_level)
      sys.stdout.flush()
      last_level = current_level

    if bot._food < 10:
      sys.stdout.write('e')
      sys.stdout.flush()
      if not eat(bot):
        print 'no more food. leaving'
        bot.SendDisconnect()
        sys.exit()

    if bot._health < 15:
      print 'leaving'
      bot.SendDisconnect()
      sys.exit()

    if not bot.equip_tool(DIAMOND_SWORD):
      print 'No Sword. leaving'
      bot.SendDisconnect()
      sys.exit()

    attack_list = []
    entities = bot.world._entities
    for eid, e in entities.items():
      dist = euclidean(
          bot._pos.xzy(), e._pos.xzy())

      #print int(dist), e._player_name
      if dist <= 4 and e._player_name is None:
        attack_list.append(eid)

    #print len(attack_list),
    #if len(attack_list) > 0:
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
