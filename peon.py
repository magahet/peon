#!/usr/bin/python

import json
import re
import numpy
from scipy.spatial.distance import cityblock, pdist
import pickle
import csv
import collections
import functools
import math
import Queue
import socket
import struct
import sys
import threading
import time
import urllib
import urllib2
import zlib
import random
import itertools

from mc import Slot, Window, Xzy, World, Position, ChunkColumn, MineCraftProtocol, Entity, Confirmation
from optparse import OptionParser
import ConfigParser
import multiprocessing
import atexit
import os
import astar

class MoveException(Exception):
  pass

class MineCraftBot(MineCraftProtocol):
  def __init__(self, host, port, username, password=None):
    super(MineCraftBot, self).__init__()

    self._host = host
    self._port = port
    self._username = username
    self._password = password
    self._serverId = None
    self._status = 'idle'
    self._food= 1
    self._xp_bar = -1
    self._xp_level = -1
    self._xp_total = -1

    self.world = World()
    self.windows = {}
    self._pos = Position(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1)

    self._entityId = None
    self._levelType = None
    self._serverMode = None
    self._dimension = None
    self._difficulty = None
    self._maxPlayers = None
    self._cursor_slot = Slot(itemId=-1, count=None, meta=None, data=None) 
    self._action_id = itertools.count(1)
    self._confirmations = {}
    self.bot_file = os.path.join('/tmp', self._username)

    self._threadFuncs.extend([
        #self._DoCrashThread,
        #self._DoWatchdogThread,
        self._DoPositionUpdateThread,
        ])
    self._handlers = {
        '\x00': self.OnKeepAlive,
        '\x01': self.OnLogin,
        '\x02': self.OnHandshake,
        '\x03': self.OnChatMessage,
        '\x05': self.OnEntityEquipment,
        '\x08': self.OnUpdateHealth,
        '\x0d': self.OnPlayerPositionLook,
        '\x14': self.OnSpawnNamedEntity,
        '\x18': self.OnSpawnMob,
        '\x1d': self.OnDestroyEntity,
        '\x1f': self.OnEntityRelativeMove,
        '\x21': self.OnEntityLookRelativeMove,
        '\x22': self.OnEntityTeleport,
        '\x2b': self.OnSetExperience,
        '\x33': self.world.MapChunk,
        '\x34': self.OnMultiBlockChange,
        '\x35': self.OnBlockChange,
        '\x67': self.OnSetSlot,
        '\x68': self.OnSetWindowItems,
        '\x6a': self.OnConfirmTransaction,
        }

    if os.path.isfile(self.bot_file):
      raise Exception("%s is already logged in" % self._username)

    open(self.bot_file, 'w').close()
    atexit.register(self.delbotfile)
    
    if password is None:
      self.Login()
    else:
      self.Login(authenticate=True)

    self.FloatDown()

  def delbotfile(self):
    os.remove(self.bot_file)

  def Login(self, authenticate=False):
    self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._sock.connect((self._host, self._port))
    self._sockGeneration += 1

    self.StartThreads()

    if authenticate:
      self._sessionId = self.GetSessionId(self._username, self._password)
      print 'sessionId:', self._sessionId
      self.SendHandshake(self._username, self._host, self._port)
      self.WaitFor(lambda: self._serverId is not None)
      print 'serverId:', self._serverId
      print 'joinserver status:', self.JoinServer(self._username, self._sessionId, self._serverId)

    print 'sending login...'
    self.SendLogin(self._username)

  def _DoCrashThread(self):
    time.sleep(60)
    while self._sock is not None:
      #print 'BADIDEA'
      #print self._buf
      self._buf = '\x1bADIDEA'
      #print self._buf
      time.sleep(1)

  def _DoWatchdogThread(self):
    try:
      myGeneration = self._sockGeneration
      # Give everyone a bit of time to wake up
      time.sleep(5)
      while all(t.is_alive() for t in self._threads):
        time.sleep(1)

      print "somebody died!"
      deadTime = time.time()
      self._sock = None
      self._sendQueue.put(None)
      self._sendQueue = None

      def OtherThreadIsAlive():
        return len([t for t in self._threads if t.is_alive()]) > 1
      while OtherThreadIsAlive() and time.time() - deadTime < 5:
        time.sleep(1)
      if OtherThreadIsAlive():
        print "somebody won't die! oh well."
      time.sleep(3)

      self._buf = ''
      self._sendQueue = Queue.Queue(10)
      self._pos = Position(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1)
      self.world = World()
      self.windows = {}
      print 'WatchDog: loggin in'
      self.Login()
      print 'WatchDog: floatin down'
      self.FloatDown()
    finally:
      print "Watchdog thread exiting", myGeneration

  def _DoPositionUpdateThread(self):
    try:
      self.WaitFor(lambda: self._pos.x != 0.0 and self._pos.y != 0.0)
      myGeneration = self._sockGeneration
      while myGeneration == self._sockGeneration:
        time.sleep(0.010)
        self.SendPositionLook()
        if os.getppid() != self.parentPID:
          print "Position update thread exiting", myGeneration
          #sys.exit()
    finally:
      os.kill(self.parentPID, 0)

  def OnKeepAlive(self, token):
    self.Send(
        '\x00' +
        struct.pack('!i', token)
        )

  def SendPositionLook(self, pos=None):
    if pos is None:
      pos = self._pos
    self.SendPlayerPositionAndLook(pos.x, pos.y, pos.stance, pos.z, pos.yaw, pos.pitch, pos.on_ground) 

  def OnLogin(self, entityId, levelType, serverMode, dimension, difficulty, maxPlayers):
      self._entityId = entityId
      self._levelType = levelType
      self._serverMode = serverMode
      self._dimension = dimension
      self._difficulty = difficulty
      self._maxPlayers = maxPlayers

  def OnHandshake(self, serverId):
      self._serverId = serverId

  def OnChatMessage(self, chat):
    print u"Chat: %s" % chat
    m = re.match('<\w+> peon, (.*)', chat)
    if m is not None:
        self.run_cmd(m.group(1))

  def OnEntityEquipment(self, entity_id, slot_num, item_id, damage):
    print 'Entity Equipment:', entity_id, slot_num, item_id, damage

  def OnUpdateHealth(self, health, food, food_saturation):
    self._health = health
    self._food= food
    self._food_saturation = food_saturation
    if health <= 0:
      self.WaitFor(lambda: self._dimension is not None)
      self.SendRespawn(self._dimension, self._difficulty, self._levelType)

  def OnPlayerPositionLook(self, x, stance, y, z, yaw, pitch, onGround):
    pos = Position(x, y, stance, z, yaw, pitch, onGround)
    print "Corrected Position: ", pos.x, pos.z, pos.y
    self.SendPositionLook(pos)
    self._pos = Position(x, y, stance, z, yaw, pitch, 1)

  def OnSpawnNamedEntity(self, eid, player_name, x, y, z, yaw, pitch, current_item):
    self.world._entities[eid] = Entity(
      eid, 0, x, y, z, yaw, pitch, player_name=player_name, current_item=current_item)

  def OnSpawnMob(self, eid, etype, x, y, z, yaw, pitch, head_yaw, metadata):
    self.world._entities[eid] = Entity(
      eid, etype, x, y, z, yaw, pitch, head_yaw=head_yaw, metadata=metadata)

  def OnDestroyEntity(self, eid):
    if eid in self.world._entities:
      del self.world._entities[eid]

  def OnEntity(self, eid):
    return

  def OnEntityRelativeMove(self, eid, x, y, z):
    if eid in self.world._entities:
      self.world._entities[eid].Move(x, y, z)

  def OnEntityLookRelativeMove(self, eid, x, y, z, yaw, pitch):
    if eid in self.world._entities:
      self.world._entities[eid].Move(x, y, z)

  def OnEntityTeleport(self, eid, x, y, z, yaw, pitch):
    if eid in self.world._entities:
      self.world._entities[eid].Teleport(x, y, z)

  def OnEntityHeadLook(self, eid, head_yaw):
    if eid in self.world._entities:
      self.world._entities[eid]._head_yaw = head_yaw

  def OnEntityStatus(self, eid, status):
    if eid in self.world._entities and status == 3:
      del self.world._entities[eid]

  def OnSetExperience(self, bar, level, total):
    self._xp_bar = bar
    self._xp_level = level
    self._xp_total = total

  def OnMultiBlockChange(self, blocks):
    for x, z, y, newType, newMeta in blocks:
      self.world.SetBlock(x, z, y, newType, newMeta)

  def OnBlockChange(self, x, y, z, newType, newMeta):
    #print "Block change:", (x, z, y), newType
    self.world.SetBlock(x, z, y, newType, newMeta)

  def OnMapChunks(self, chunk):
    self._chunks[chunk.chunkX, chunk.chunkZ] = chunk

  def OnSetSlot(self, windowId, slotIndex, slot):
    print 'SetSlot:', windowId, slotIndex, slot
    if windowId == -1 and slotIndex == -1:
      self._cursor_slot = slot
    elif windowId in self.windows:
      self.windows[windowId].SetSlot(slotIndex, slot)

  def OnSetWindowItems(self, windowId, slots):
    print 'SetWindowItems:', windowId
    for s in slots:
      print s
    window = Window(windowId, slots)
    self.windows[windowId] = window

  def OnConfirmTransaction(self, window_id, action_id, accepted):
    self._confirmations[action_id] = Confirmation(window_id, action_id, accepted)
    if not accepted:
        self.SendConfirmTransaction(window_id, action_id, accepted)

  def DoDig(self, x, z, y, face=1, retries=5):
    for i in range(retries):
        self.SendDig(x, z, y)

        if self.world.GetBlock(x, z, y) == 0:
            return True
    else:
        return False

  def SendDig(self, x, z, y, face=1):
    #print "sending dig:", (x, z, y)
    self.SendPlayerDigging(0, x, y, z, face)
    time.sleep(0.2)
    self.SendPlayerDigging(2, x, y, z, face)

    self.WaitFor(lambda: self.world.GetBlock(x, z, y) == 0, timeout=10)

  def nav_to(self, x, z, y): 
    self.WaitFor(lambda: self._pos.x != 0.0 and self._pos.y != 0.0)
    botXzy = Xzy(self._pos.x, self._pos.z, self._pos.y)
    nextXzy = Xzy(x, z, y)
    if botXzy == nextXzy:
      return

    print 'moving to:', nextXzy

    path = self.find_path(nextXzy)
    if path is not None:
      end = path[-1]
      for step in path:
        print 'minimove-', step
        self.MoveTo(*step)

  def MoveTo(self, x, z, y, speed=4.25, onGround=True):
    x+=0.5
    z+=0.5

    def MyDist(x, z, y):
      return abs(pos.x - x) + abs(pos.z - z) + abs(pos.y - y)

    def Go(x=None, z=None, y=None):
      self._pos = Position(x, y, y+1, z, yaw, 0, onGround)

    pos = self._pos
    yaw = pos.yaw
    if z - pos.z > .9:
      yaw = 0
    if z - pos.z < - .9:
      yaw = 180
    if x - pos.x > .9:
      yaw = 270
    if x - pos.x < - .9:
      yaw = 90

    tau = 0.010
    delta = speed * tau
    while MyDist(x, z, y) > (delta * 2):
      if pos.x - x > 0:
        new_x = pos.x - delta
      else:
        new_x = pos.x + delta
      if pos.z - z > 0:
        new_z = pos.z - delta
      else:
        new_z = pos.z + delta
      if pos.y - y > 0:
        new_y = pos.y - delta
      else:
        new_y = pos.y + delta

      Go(new_x, new_z, new_y)
      time.sleep(tau)
      if (self._pos.x, self._pos.z, self._pos.y) != (new_x, new_z, new_y):
        print 'did not small move'
        return False
      pos = self._pos

    Go(x, z, y)
    time.sleep(tau)
    if (self._pos.x, self._pos.z, self._pos.y) != (x, z, y):
      print 'did not move'
      return False

    return True

  def FloatDown(self):
    self.WaitFor(lambda: self._pos.x != 0.0 and self._pos.y != 0.0)
    self.WaitFor(lambda: self.world.GetBlock(
      self._pos.x, self._pos.z, self._pos.y) is not None)
    pos = self._pos.xzy()
    self.MoveTo(*pos)
    for y in range(pos.y + 1, 0, -1):
      print 'floating:', pos
      if self.world.IsStandable(*pos):
        self.MoveTo(*pos)
        return

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

  def get_best_tool(self, blockType, tool_name):
    print 'Looking for a', tool_name, 'to break:', blockType
    tools = {
      'pick': [257, 278],
      'shovel': [256, 277]
      }

    held_items = self.windows[0].GetHeld()

    for i, slot in enumerate(self.windows[0].GetHeld()):
      if slot.itemId in tools[tool_name]:
        print 'Switching to tool:', tool_name
        self.SendHeldItemChange(i)
        return True
    
    return False

  def get_slot(self, slot_num):
    return self.windows[0]._slots[slot_num]

  #TODO Fix this. Should reliably place tool in bot's hand.
  def click_slot(self, slot_num):
    action_id = self._action_id.next()
    if slot_num in range(45):
      slot_data = self.get_slot(slot_num)
    else:
      slot_data = Slot(itemId=-1, count=None, meta=None, data=None) 
    self.SendClickWindow(0, slot_num, 0, action_id, 0, slot_data)
    if self.WaitFor(lambda: action_id in self._confirmations.keys(), timeout=5):
      if self._confirmations[action_id].accepted:
        self.windows[0]._slots[slot_num] = self._cursor_slot
        self._cursor_slot = slot_data
        return True
    return False

  def find_tool(self, tool_id, held_only=False):
    for i, slot in enumerate(self.windows[0]._slots):
      if slot.itemId == tool_id:
        if not held_only or i >= 36:
          return i
    return None

  def equip_tool(self, tool_id):
    slot_num = self.find_tool(tool_id)
    print 'slot_num:', slot_num
    if slot_num is None:
      return False

    if slot_num < 36:
      click_list = [slot_num]
      target_slot_num = self.find_tool(-1, held_only=True)
      if target_slot_num is None:
        target_slot_num = random.randrange(36,45)
        click_list.append(target_slot_num)
        click_list.append(slot_num)
      else:
        click_list.append(target_slot_num)

      print 'click_list:', click_list
      for i in click_list:
        if not self.click_slot(i):
          return False
    else:
      target_slot_num = slot_num

    print 'target_slot_num:', target_slot_num
    self.SendHeldItemChange(target_slot_num-36)
    time.sleep(.5)
    return True


  def remove_non_tools(self):
    tools = [257, 278, 256, 277]
    for i, slot in enumerate(self.windows[0]._slots):
      if i >= 9 and slot.itemId < 256 and slot.itemId != -1:
        print 'removing item:', slot.itemId
        for x, s in enumerate(self.windows[0]._slots):
          print x, s
        self.SendClickWindow(0, i, 0, self._action_id.next(), 0, slot)
        time.sleep(.2)
        self.SendClickWindow(0, -999, 0, self._action_id.next(), 0, slot)
        time.sleep(.2)

  def move_tools_to_held(self):
    tools = [257, 278, 256, 277]
    slots = self.windows[0]._slots
    for i, slot_held in enumerate(slots[36:]):
      if slot_held.itemId != -1:
        continue
      for j, slot_main in enumerate(slots[:35]):
        if slot_main.itemId not in tools:
          continue
        self.SendClickWindow(0, j, 0, self._action_id.next(), 0, slot_main)
        time.sleep(.2)
        self.SendClickWindow(0, i, 0, self._action_id.next(), 0, slot_main)
        time.sleep(.2)


  def run_cmd(self, cmd):
        args = cmd.split()
        if len(args) == 0:
            return
        elif cmd == 'where are you?':
            self.SendChat('x: %d, y: %d, z: %d' % (self._pos.x, self._pos.y, self._pos.z))

  def move_up(self):
    self.MoveTo(self._pos.x, self._pos.z, self._pos.y + 100)

  def dig_area(self, bbox, home=None, dump=False, dig_height=0):
    print 'going to dig: %s' % str(bbox)
    time.sleep(3)
    best_against = {
      'pick': [1,4,14,15,16],
      'shovel': [2,3,12,13]
      }
    ignore_blocktypes = [0, 50]
    #ignore_blocktypes = [0]
    last_block_type = -1 
    y_range = range(max(bbox['y']), min(bbox['y']), -1)
    z_range = range(min(bbox['z']), max(bbox['z']))
    random.shuffle(z_range)
    x_range = range(min(bbox['x']), max(bbox['x']))
    for y in y_range:
        for z in z_range:
           for x in x_range:
                blockXzy = Xzy(x, z, y)
                if self.world.GetBlock(*blockXzy) is None:
                    print "Waiting for chunks to load..."
                    self.nav_to(x, z, max(bbox['y']))
                    self.WaitFor(lambda: self.world.GetBlock(*blockXzy) is not None)
                blockType = self.world.GetBlock(*blockXzy)
                if blockType in ignore_blocktypes:
                    continue
                if last_block_type != blockType:
                    last_block_type = blockType
                    for tool_name, block_list in best_against.iteritems():
                        if blockType in block_list:
                            if not self.get_best_tool(blockType, tool_name) and home is not None:
                              print 'going home to get better tools:', home
                              self.nav_to(*home)
                              while not self.get_best_tool(blockType, tool_name):
                                  self.remove_non_tools()
                                  self.move_tools_to_held()
                                  time.sleep(10)
                              self.nav_to(x, z, y + dig_height)
                self.nav_to(x, z, y + dig_height)
                if self.DoDig(x, z, y):
                  sys.stdout.write('.')
                else:
                  sys.stdout.write('!')
                sys.stdout.flush()

  def dig_to(self, x, z, y):
    self.MoveTo(*self._pos.xzy())
    path = self.find_path(Xzy(x,z,y), reachable_test=self.world.IsDiggable)
    if path is None:
      print 'could not find path'
      return False
    print path
    for p in path:
      print 'dig:', p
      if self.DoDig(*p) and self.DoDig(p.x, p.z, p.y + 1):
        if not self.MoveTo(*p):
          print 'could not move to:', p, 'made it to:', self._pos.xzy()
          return False
      else:
        print 'could not reach:', (x,z,y), 'made it to:', self._pos.xzy()
        return False
    print 'done'
    return True

  def find_path(self, end, reachable_test=None):
    if reachable_test is None:
      reachable_test = self.world.IsMoveable

    def iter_moveable_adjacent(start):
      l = []
      for xzy, block_type in self.world.IterAdjacent(*start):
        if reachable_test(*xzy):
          l.append(xzy)
      return l

    def at_goal(xzy):
      if xzy == end:
        return True
      else:
        return False

    def distance(a, b):
      return cityblock(a, b)

    def distance_to_goal(a):
      return cityblock(a, end)

    if not reachable_test(*end):
      print 'destination not reachable'
      return None

    pos = self._pos.xzy()
    #pos._replace(x=pos.x-1)
    return astar.astar(
        pos, iter_moveable_adjacent, at_goal, 0, 
        distance, distance_to_goal)

  def get_adjacent_blocks(self, block, max_height=64):
    blocks = []
    for offset_y in range(-1, 2):
      for offset_x in range(-1, 2):
        for offset_z in range(-1, 2):
          x = block.x + offset_x
          z = block.z + offset_z
          y = block.y + offset_y
          if y > 0 and y < max_height:
            blocks.append(Xzy(x, z, y))
    for xzy in blocks:
      yield xzy

  def iter_find_nearest_blocktype(self, start, types=[15]):
    height_dict = {
      14: 32, #gold
      15: 64, #iron
      56: 17, #diamonds
    }
    height_list = [h for t, h in height_dict.items() if t in types]
    if len(height_list) == 0:
      height = 96
    else:
      height = max(height_list)
    height = max(height, start.y)
    checked_blocks = set([])
    unchecked_blocks = collections.deque([start])
    block_type = 0
    while len(unchecked_blocks) != 0:
      block = unchecked_blocks.popleft()
      checked_blocks.add(block)
      for block in self.get_adjacent_blocks(block, max_height=height):
        if block not in checked_blocks and block not in unchecked_blocks and self.world.GetBlock(*block) is not None:
          unchecked_blocks.append(block)
      block_type = self.world.GetBlock(*block)
      if block_type in types:
        yield block

  def help_find_blocks(self, start, types=[15], chat=True):
    self.nav_to(start.x, start.z, 200)
    c = [ l for l in csv.DictReader(open('blocktypes.csv'), skipinitialspace=True) ]
    bt_name = dict([(l['type'], int(l['dec'])) for l in c ])
    bt_int = dict([(int(l['dec']), l['type']) for l in c ])
    interesting = [
      'diamond ore',
      #'gold ore',
      #'iron ore',
      #'coal ore'
    ]
    types = [ bt_name[i] for i in interesting ]

    print 'waiting for world to load...'
    self.WaitFor(lambda: self.world.GetBlock(self._pos.x, self._pos.z, self._pos.y) is not None)
    try:
      while True:
        block = self.find_nearest_blocktype(start, types=types)
        blocktype = self.world.GetBlock(*block)
        print block, bt_int[blocktype]
        if chat:
          self.SendChat('x: %d, y: %d, z: %d, type: %s' % (block.x, block.y, block.z, bt_int[blocktype]))
        while blocktype in types:
          blocktype = self.world.GetBlock(*block)
          time.sleep(10)
        start = block
    except KeyboardInterrupt:
      print
      return

  def get_player_position(self, player_name):
    for entity in self.world._entities.values():
      if entity._player_name == player_name:
        return entity._pos.xzy()

  def move_to_player(self, player_name):
    xzy = self.get_player_position(player_name)
    if xzy is not None:
      self.nav_to(*xzy)

if __name__ == '__main__':
  parser = OptionParser()
  parser.add_option("-s", "--server", dest="server", default="localhost",
                        help="server", metavar="SERVER")
  parser.add_option("-P", "--port", dest="port", default=25565, type="int",
                        help="port", metavar="PORT")
  parser.add_option("-u", "--user", dest="user",
                        help="user to login as", metavar="USER")
  parser.add_option("-p", "--pass", dest="password",
                        help="password", metavar="PASSWORD")
  parser.add_option("-b", "--bbox", dest="bbox", default='jungle',
                        help="digging bbox", metavar="BBOX")
  parser.add_option("-r", "--return-base", dest="return_base", default='base',
                        help="base to return to for better tools", metavar='BASE')
  (options, args) = parser.parse_args()


  with open('sites.json') as f:
    sites = json.load(f)
    bboxes = sites['bboxes']
    return_bases = sites['return_bases']

  bbox = bboxes[options.bbox]
  home = return_bases[options.return_base] 

  server = options.server
  port = options.port
  password = options.password

  if options.user is not None: 
    username = options.user
  else:
    bot_names = ['peon', 'serf', 'grunt', 'slave', 'drudge', 'farmboy', 'peasant']
    for name in bot_names:
      if not os.path.isfile(os.path.join('/tmp', name)):
        username = name
        print 'logging in as:', username
        break
    else:
      raise Exception('All usernames are logged in')

  if len(args) > 0: 
    cmd = args.pop(0)

    if cmd == 'kill':
      username = 'magahet'
      bot = MineCraftBot(server, port, username, password=password)
      bot.WaitFor(lambda: bot._pos.x != 0.0 and bot._pos.y != 0.0)
      time.sleep(2)
      import scrap
      scrap.kill(bot)
    elif cmd == 'explore':
      username = 'dora'
      bot = MineCraftBot(server, port, username, password=password)
      bot.WaitFor(lambda: bot._pos.x != 0.0 and bot._pos.y != 0.0)
      time.sleep(2)
      import scrap
      scrap.explore(bot)
    if cmd == 'test':
      bot = MineCraftBot(server, port, username, password=password)
      bot.WaitFor(lambda: bot._pos.x != 0.0 and bot._pos.y != 0.0)
      print 'bot ready'
    elif cmd == 'help':
      types = [14,15,16,56]
      start = Xzy(*args[0:3])
      bot = MineCraftBot(server, port, username, password=password)
      bot.help_find_blocks(start, types=types)
    elif cmd == 'dig':
      bot = MineCraftBot(server, port, username, password=password)
      bot.dig_area(bbox, home=home)

