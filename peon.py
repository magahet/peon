#!/usr/bin/python

import array
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

from pprint import pprint as pp
from struct import pack, unpack

class Xzy(collections.namedtuple('Xzy', ('x', 'z', 'y'))):
  def __new__(cls, *args, **kwargs):
    args = map(int, args)
    for k, v in kwargs.iteritems():
      kwargs[k] = int(v)
    return super(Xzy, cls).__new__(cls, *args, **kwargs)

  def Offset(self, x=0, z=0, y=0):
    return Xzy(self.x + x, self.z + z, self.y + y)


def Dist(xzyA, xzyB):
  return math.sqrt(
      (xzyA.x - xzyB.x) * (xzyA.x - xzyB.x) +
      (xzyA.z - xzyB.z) * (xzyA.z - xzyB.z) +
      (xzyA.y - xzyB.y) * (xzyA.y - xzyB.y)
      )


class World(object):
  def __init__(self):
    self._chunks = {}
    pass

  def MapChunk(self, chunk):
    self._chunks[chunk.chunkX, chunk.chunkZ] = chunk

  def SetBlock(self, x, z, y, newType, newMeta):
    chunk = self._chunks.get((int(x/16), int(z/16)))
    if not chunk:
      return None
    return chunk.SetBlock(int(x), int(z), int(y), newType, newMeta)

  def GetBlock(self, x, z, y):
    chunk = self._chunks.get((int(x/16), int(z/16)))
    if not chunk:
      return None
    return chunk.GetBlock(int(x), int(z), int(y))

  def IsJumpable(self, x, z, y):
    SOLID = set(range(1, 5) + [7] + range(12, 27))
    # LADDER =

    #print "types:", x, z, y, ':', 
    #print self.GetBlock(x, z, y - 2),
    #print self.GetBlock(x, z, y - 1),
    #print self.GetBlock(x, z, y)    ,
    #print self.GetBlock(x, z, y + 1)
    return (
        (self.GetBlock(x, z, y - 2) in SOLID or
         self.GetBlock(x, z, y - 1) in SOLID) and
        self.GetBlock(x, z, y)     not in SOLID and
        self.GetBlock(x, z, y + 1) not in SOLID
        )

  def IsStandable(self, x, z, y):
    SOLID = set(range(1, 5) + [7] + range(12, 27))
    # LADDER =

    #print "types:", x, z, y, ':', 
    #print self.GetBlock(x, z, y - 2),
    #print self.GetBlock(x, z, y - 1),
    #print self.GetBlock(x, z, y)    ,
    #print self.GetBlock(x, z, y + 1)
    return (
        self.GetBlock(x, z, y - 1) in SOLID and
        self.GetBlock(x, z, y)     not in SOLID and
        self.GetBlock(x, z, y + 1) not in SOLID
        )

  def IterAdjacent(self, x, z, y):
    adjacents = [
        # prefer down
        Xzy(x, z, y - 1),
        # front and back
        Xzy(x + 1, z, y),
        Xzy(x - 1, z, y),
        # sides
        Xzy(x, z + 1, y),
        Xzy(x, z - 1, y),
        # avoid up
        Xzy(x, z, y + 1),
        ]
    for xzy in adjacents:
      yield xzy, self.GetBlock(*xzy)

  def FindNearest(self, xzy, condition):
    maxD = 100
    d = {}
    d[xzy] = 0
    queue = [xzy]

    while queue:
      xzy = queue.pop(0)
      xzyD = d[xzy]
      if xzyD > maxD:
        print "too far!"
        break
      if self.IsStandable(*xzy) and condition(xzy):
        return xzy
      for xzyAdj, blockAdj in self.IterAdjacent(*xzy):
        if xzyAdj in d:
          continue
        if self.IsJumpable(*xzyAdj):
          d[xzyAdj] = xzyD + 1
          queue.append(xzyAdj)
    return None

  def FindPath(self, xzyA, xzyB):
    # TODO: A*
    xzyA = Xzy(*xzyA)
    xzyB = Xzy(*xzyB)
    #print xzyA, xzyB

    #if not self.IsStandable(*xzyA) or not self.IsStandable(*xzyB):
    if not self.IsStandable(*xzyB):
      print "not standable dest!"
      print xzyA, xzyB
      return None

    d = {}
    d[xzyA] = 0
    queue = [xzyA]

    while queue and xzyB not in d:
      xzy = queue.pop(0)
      xzyD = d[xzy]
      for xzyAdj, blockAdj in self.IterAdjacent(*xzy):
        if xzyAdj not in d and self.IsJumpable(*xzyAdj):
          d[xzyAdj] = xzyD + 1
          queue.append(xzyAdj)

    if xzyB not in d:
      print "dest not found"
      return None

    path = [xzyB]
    while path[-1] != xzyA:
      for xzyAdj, blockAdj in self.IterAdjacent(*path[-1]):
        if xzyAdj in d and d[xzyAdj] < d[path[-1]]:
          path.append(xzyAdj)
          break
    path.reverse()
    return path





class ChunkColumn(object):
  def __init__(self, chunkX, chunkZ,
      blockData, blockMeta, lightData, skyLightData, addArray, biomeData):
    self.chunkX = chunkX
    self.chunkZ = chunkZ
    self._blocks = blockData
    self._meta = blockMeta
    self._light = lightData
    self._skylight = skyLightData
    self._addArray = addArray
    self._skyLightData = skyLightData
    self._biome = biomeData

  def _GetOffset(self, x, z, y):
    x, z, y = int(x), int(z), int(y)
    #print x, z, y
    #print x - self.chunkX * 16, z - self.chunkZ * 16, y
    return (       (x - self.chunkX * 16) +
            (16 *  (z - self.chunkZ * 16)) +
            (256 * (y))
           )

  def SetBlock(self, x, z, y, newType, newMeta):
    # TODO: what about extra 4 bits?
    self._blocks[self._GetOffset(x, z, y)] = (newType & 0xff)
    return newType

  def GetBlock(self, x, z, y):
    blockType = self._blocks[self._GetOffset(x, z, y)]
    return blockType

class MineCraftProtocol(object):
  def __init__(self, sock):
    self._sock = sock
    self._buf = ""
    self._sendQueue = Queue.Queue(10)

    self._parsers = {
        '\x00': self.ParseKeepAlive,
        '\x01': self.ParseLogin,
        '\x02': self.ParseHandshake,
        '\x03': self.ParseChatMessage,
        '\x04': self.ParseTimeUpdate,

        '\x05': self.ParseEntityEquipment,

        '\x06': self.ParseSpawn,
        '\x08': self.ParseUpdateHealth,
        '\x09': self.ParseRespawn,
        '\x10': self.ParseHeldItemChange,

        '\x0c': self.ParsePlayerLook,
        '\x0d': self.ParsePlayerPositionLook,
        '\x12': self.ParseAnimation,
        '\x14': self.ParseSpawnNamedEntity,
        '\x15': self.ParseSpawnDroppedItem,
        '\x16': self.ParseCollectItem,
        '\x17': self.ParseSpawnObjectVehicle,
        '\x18': self.ParseSpawnMob,
        '\x1a': self.ParseSpawnExperienceOrb,
        '\x1c': self.ParseEntityVelocity,
        '\x1d': self.ParseDestroyEntity,
        '\x1f': self.ParseEntityRelativeMove,
        '\x20': self.ParseEntityLook,
        '\x21': self.ParseEntityRelativeLookAndMove,
        '\x22': self.ParseEntityTeleport,
        '\x23': self.ParseEntityHeadLook,
        '\x26': self.ParseEntityStatus,
        '\x28': self.ParseEntityMetadata,
        '\x2a': self.ParseRemoveEntityEffect,
        '\x2b': self.ParseSetExperience,
        '\x32': self.ParseMapColumnAllocation,
        '\x33': self.ParseMapChunks,
        '\x34': self.ParseMultiBlockChange,
        '\x35': self.ParseBlockChange,
        '\x3d': self.ParseSoundParticleEffect,
        '\x46': self.ParseChangeGameState,
        '\x36': self.ParseBlockAction,
        '\x67': self.ParseSetSlot,
        '\x68': self.ParseSetWindowItems,
        '\x84': self.ParseUpdateTileEntity,
        '\xca': self.ParsePlayerAbility,
        '\xc8': self.ParseIncrementStatistic,
        '\xc9': self.ParsePlayerListItem,
        '\xff': self.ParseKick,
        }

    self._interesting = set([
        #'\x00',
        '\x01',
        '\x03',
        '\x14',
        '\x06',
        '\x08',
        '\x16',
        #'\x0d',
        #'\x32',
        #'\x33',
        '\x34',
        '\x35',
        '\x46',
        '\xc8',
        '\xff',
        ])

    self._handlers = {}

    self._threads = [
        threading.Thread(target=self._DoReadThread),
        threading.Thread(target=self._DoSendThread),
        ]

    self._recvCondition = threading.Condition()


  ##############################################################################
  # minecraft.net methods

  def GetSessionId(self, username, password):
    data = urllib.urlencode((
        ('user', username),
        ('password', password),
        ('version', '1337'),
        ))
    sessionString = urllib2.urlopen('https://login.minecraft.net/', data).read()
    return sessionString.split(':')[3]

  def JoinServer(self, username, sessionId, serverId):
    data = urllib.urlencode((
        ('user', username),
        ('sessionId', sessionId),
        ('serverId', serverId),
        ))
    url = 'http://session.minecraft.net/game/joinserver.jsp?' + data
    return urllib2.urlopen(url).read()


  ##############################################################################
  # Thread functions

  def Start(self):
    for thread in self._threads:
      thread.daemon = True
      thread.start()

  def _DoReadThread(self):
    while True:
      #time.sleep(0.010)
      self.RecvPacket()
      with self._recvCondition:
        self._recvCondition.notifyAll()

  def _DoSendThread(self):
    while True:
      #time.sleep(0.010)
      #time.sleep(0.05)
      self._sock.sendall(self._sendQueue.get())


  ##############################################################################
  # Protocol convenience methods

  def Send(self, packet):
    if packet[0] in self._interesting:
      sys.stderr.write('\nSending packet: %s\n' % hex(ord(packet[0])))
    self._sendQueue.put(packet)

  def Read(self, size):
    while len(self._buf) < size:
      #print "reading ", size, len(self._buf)
      self._buf += self._sock.recv(4096)
    ret = self._buf[:size]
    self._buf = self._buf[size:]
    return ret

  def RecvPacket(self):
    ilk = self.Read(1)
    #print hex(ord(ilk)), len(self._buf)
    if ilk in self._interesting:
      print '\nReceived packet: %s (buf: %d)' % (hex(ord(ilk)), len(self._buf))
    #for x in self._buf:
      #print hex(ord(x)), ' ',
    #print
    try:
      parsed = self._parsers[ilk]()
      #if ilk in self._interesting:
        #print '\nParsed packet: %s (buf: %d)' % (hex(ord(ilk)), len(self._buf))
      handler = self._handlers.get(ilk)
      if handler:
        handler(*parsed)
      return ilk, parsed
    except KeyError:
      sys.stderr.write('unknown packet: %s\n' % hex(ord(ilk)))
      for i in self._buf[:30]:
        sys.stderr.write('%s  ' % hex(ord(i)))
      raise

  def WaitFor(self, what, timeout=30):
    start = time.time()
    with self._recvCondition:
      while not what():
        self._recvCondition.wait(timeout=2)
        if time.time() - start > timeout:
          return False
    return True

  def PackString(self, string):
    return struct.pack('!h', len(string)) + string.encode('utf_16_be')

  def UnpackInt8(self):
    value, = struct.unpack('!b', self.Read(1))
    return value

  def UnpackUint8(self):
    value, = struct.unpack('!B', self.Read(1))
    return value

  def UnpackInt16(self):
    value, = struct.unpack('!h', self.Read(2))
    return value

  def UnpackInt32(self):
    value, = struct.unpack('!i', self.Read(4))
    return value

  def UnpackInt64(self):
    value, = struct.unpack('!q', self.Read(8))
    return value

  def UnpackFloat(self):
    value, = struct.unpack('!f', self.Read(4))
    return value

  def UnpackDouble(self):
    value, = struct.unpack('!d', self.Read(8))
    return value

  def UnpackString(self):
    strlen = self.UnpackInt16()
    #print 'strlen: ', strlen
    #print len(self._buf), strlen*2
    string = self.Read(strlen * 2).decode('utf_16_be')
    print u'Got string: [%s]' % string
    return string

  def UnpackSlot(self):
    itemId = self.UnpackInt16()
    if itemId == -1:
      return (itemId,)
    itemCount = self.UnpackInt8()
    damage = self.UnpackInt16()

    #return (itemId, itemCount, damage)

    data = ''
    # These certain items are capable of having damage/enchantments
    if ((256 <= itemId <= 259) or
        (267 <= itemId <= 279) or
        (283 <= itemId <= 286) or
        (290 <= itemId <= 294) or
        (298 <= itemId <= 317) or
        itemId == 261 or itemId == 359 or itemId == 346):
      arraySize = self.UnpackInt16()
      print 'arraySize is: ', arraySize
      if arraySize != -1:
        data = self.Read(arraySize)

    return (itemId, itemCount, damage, data)

  def UnpackMetadata(self):
    unpackers = {
        0: self.UnpackInt8,
        1: self.UnpackInt16,
        2: self.UnpackInt32,
        3: self.UnpackFloat,
        4: self.UnpackString,
        5: lambda: (self.UnpackInt16, self.UnpackInt8, self.UnpackInt16),
        6: lambda: (self.UnpackInt32(), self.UnpackInt32(), self.UnpackInt32()),
        }
    values = []
    while True:
      what = self.UnpackInt8()
      if what == 127:
        return values
      key = 0x1F & what
      values.append((key, unpackers[what >> 5]()))
    print 'WTF?'
    return values

  ##############################################################################
  # Parsers

  def ParseKick(self):
    sys.stderr.write('Kicked: ' + self.UnpackString() + '\n')
    raise Exception()

  def ParseHandshake(self):
    return (self.UnpackString(),)

  def ParseChatMessage(self):
    chat = self.UnpackString()
    print "Chat:", chat
    return (chat,)

  def ParseKeepAlive(self):
    return (self.UnpackInt32(),)

  def ParseLogin(self):
    entityId = self.UnpackInt32()
    trash = self.UnpackString()
    levelType = self.UnpackString()
    serverMode = self.UnpackInt32()
    dimension = self.UnpackInt32()
    difficulty = self.UnpackInt8()
    trash = self.UnpackUint8()
    maxPlayers = self.UnpackUint8()
    return (entityId, levelType, serverMode, dimension, difficulty, maxPlayers)

  def ParseSpawn(self):
    print len(self._buf)
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        )

  def ParseUpdateHealth(self):
    return (
        self.UnpackInt16(),
        self.UnpackInt16(),
        self.UnpackFloat(),
        )

  def ParseRespawn(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt16(),
        self.UnpackString(),
        )

  def ParseHeldItemChange(self):
    return (
        self.UnpackInt16(),
        )

  def ParsePlayerLook(self):
    return (
        self.UnpackFloat(),
        self.UnpackFloat(),
        self.UnpackInt8(),
        )

  def ParsePlayerPositionLook(self):
    return (
        self.UnpackDouble(),
        self.UnpackDouble(),
        self.UnpackDouble(),
        self.UnpackDouble(),
        self.UnpackFloat(),
        self.UnpackFloat(),
        self.UnpackInt8(),
        )

  def ParseAnimation(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        )

  def ParseSpawnNamedEntity(self):
    return (
        self.UnpackInt32(),
        self.UnpackString(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),

        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt16(),
        )

  def ParseSpawnDroppedItem(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt16(),
        self.UnpackInt8(),
        self.UnpackInt16(),

        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def ParseCollectItem(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        )

  def ParseSpawnObjectVehicle(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt16(),
        self.UnpackInt16(),
        self.UnpackInt16(),
        )

  def ParseSpawnMob(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackMetadata(),
        )

  def ParseSpawnExperienceOrb(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt16(),
        )

  def ParseEntityVelocity(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt16(),
        self.UnpackInt16(),
        self.UnpackInt16(),
        )

  def ParseDestroyEntity(self):
    return (
        self.UnpackInt32(),
        )

  def ParseEntityRelativeMove(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def ParseEntityLook(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def ParseEntityRelativeLookAndMove(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def ParseEntityTeleport(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def ParseEntityHeadLook(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        )

  def ParseEntityStatus(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        )

  def ParseEntityMetadata(self):
    return (
        self.UnpackInt32(),
        self.UnpackMetadata(),
        )

  def ParseRemoveEntityEffect(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        )

  def ParseSetExperience(self):
    return (
        self.UnpackFloat(),
        self.UnpackInt16(),
        self.UnpackInt16(),
        )

  def ParsePlayerAbility(self):
    return (
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def ParseIncrementStatistic(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        )

  def ParsePlayerListItem(self):
    return (
        self.UnpackString(),
        self.UnpackInt8(),
        self.UnpackInt16(),
        )

  def ParseTimeUpdate(self):
    return (
        self.UnpackInt64(),)

  def ParseEntityEquipment(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt16(),
        self.UnpackInt16(),
        self.UnpackInt16(),
        )

  def ParseMapColumnAllocation(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        )

  def ParseMapChunks(self):
    chunkX = self.UnpackInt32()
    chunkZ = self.UnpackInt32()
    withBiome = self.UnpackInt8()
    primaryBitMap = self.UnpackInt16()
    addBitMap = self.UnpackInt16()

    arraySize = self.UnpackInt32()
    trash = self.UnpackInt32()  # "unused"

    compressed = self.Read(arraySize)
    data = [zlib.decompress(compressed)]
    #print len(data[0]), hex(primaryBitMap)

    def PopByteArray(size):
      if len(data[0]) < size:
        raise Exception('data not big enough!')
      ret = array.array('B', data[0][:size])
      data[0] = data[0][size:]
      return  ret

    blocks = array.array('B')
    for i in range(16):
      if primaryBitMap & (1 << i):
        blocks.extend(PopByteArray(4096))
      else:
        blocks.extend([0] * 4096)

    meta = []
    for i in range(16):
      if primaryBitMap & (1 << i):
        meta.append(PopByteArray(2048))
      else:
        meta.append(array.array('B', [0] * 2048))

    light = []
    for i in range(16):
      if primaryBitMap & (1 << i):
        light.append(PopByteArray(2048))
      else:
        light.append(array.array('B', [0] * 2048))

    skylight = []
    for i in range(16):
      if primaryBitMap & (1 << i):
        skylight.append(PopByteArray(2048))
      else:
        skylight.append(array.array('B', [0] * 2048))

    addArray = []
    for i in range(16):
      if addBitMap & (1 << i):
        addArray.append(PopByteArray(2048))
      else:
        addArray.append(array.array('B', [0] * 2048))

    if withBiome:
      biome = PopByteArray(256)
    else:
      biome = None

    if len(data[0]) > 0:
      raise Exception('Unused bytes!')

    return (ChunkColumn(chunkX, chunkZ,
        blocks, meta, light, skylight, addArray, biome),)
    return [chunkX, chunkZ, blocks, meta, light, skylight, addArray, biome]

    ret = [
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt8(),

        self.UnpackInt16(),
        self.UnpackInt16(),
        ]
    arraySize = self.UnpackInt32()
    ret.append(self.UnpackInt32())  # "unused"
    ret.append(self.Read(arraySize))
    return ret

  def ParseMultiBlockChange(self):
    blocks = []
    chunkX = self.UnpackInt32()
    chunkZ = self.UnpackInt32()

    count = self.UnpackInt16()
    size = self.UnpackInt32()

    if count *4 != size:
      print "WTF:", count, size
    for i in range(count):
      record = self.UnpackInt32()
      meta = record & 0xf # 4 bits
      record >> 4
      blockId = record & 0xfff # 12 bits
      record >> 12
      y = record & 0xf # 8 bits
      record >> 8
      relativeZ  = record & 0xf # 4 bits
      record >> 4
      relativeX  = record & 0xf # 4 bits
      record >> 4

      blocks.append((chunkX * 16 + relativeX,
                     chunkZ * 16 + relativeZ,
                     y,
                     blockId,
                     meta))
    return (blocks,)

  def ParseBlockChange(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def ParseSoundParticleEffect(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        )

  def ParseChangeGameState(self):
    return (
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def ParseBlockAction(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt16(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def ParseSetSlot(self):
    return (
        self.UnpackInt8(),
        self.UnpackInt16(),
        self.UnpackSlot(),
        )

  def ParseSetWindowItems(self):
    window = self.UnpackInt8()
    slotCount = self.UnpackInt16()
    #print "Array Size: ", slotCount
    slots = []
    for i in range(slotCount):
      slots.append(self.UnpackSlot())
    return (window, slots)

  def ParseUpdateTileEntity(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt16(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        )


  ##############################################################################
  # Senders

  def SendHandshake(self, username, server, port):
    self.Send(
        '\x02' +
        self.PackString(u'%s;%s;%d' % (username, server, port))
        )

  def SendLogin(self, username):
    packet = (
        '\x01' +
        pack('!i', 29) +
        self.PackString(username) +
        self.PackString('') +
        pack('!i', 0) +
        pack('!i', 0) +
        pack('!b', 0) +
        pack('!B', 0) +
        pack('!B', 0)
        )
    self.Send(packet)


class Position(collections.namedtuple('Position',
    ('x', 'y', 'stance', 'z', 'yaw', 'pitch', 'on_ground'))):
  def xzy(self):
    return Xzy(self.x, self.z, self.y)

class MineCraftBot(MineCraftProtocol):

  def __init__(self, host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    super(MineCraftBot, self).__init__(sock)

    self.world = World()
    self._pos = Position(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1)

    self._threads.append(threading.Thread(target=self._DoPositionUpdateThread))
    self._handlers = {
        '\x00': self.OnKeepAlive,
        '\x0d': self.OnPlayerPositionLook,
        '\x33': self.world.MapChunk,
        '\x34': self.OnMultiBlockChange,
        '\x35': self.OnBlockChange,
        }

  def Login(self, username, password):
    """
    self._sessionId = self.GetSessionId(username, password)
    print 'sessionId:', self._sessionId

    self.SendHandshake(username, host, port)
    self._serverId, = self.WaitFor('\x02')
    print 'serverId:', self._serverId

    self.JoinServer(username, self._sessionId, self._serverId)
    """

    print 'sending login...'
    self.SendLogin(username)
    self.FloatDown()

  def _DoPositionUpdateThread(self):
    time.sleep(2)
    while True:
      time.sleep(0.010)
      self.SendPositionLook()

  def OnKeepAlive(self, token):
    self.Send(
        '\x00' +
        pack('!i', token)
        )

  def SendPositionLook(self):
    self.Send(
        '\x0d' +
        #pack('!ddddffb', x, y, stance, z, yaw, pitch, onGround)
        pack('!ddddffb', *self._pos)
        )
    #print self._pos


  def OnPlayerPositionLook(self, x, stance, y, z, yaw, pitch, onGround):
    self._pos = Position(x, y, stance, z, yaw, pitch, onGround)
    print "Corrected Position: ", self._pos.x, self._pos.z, self._pos.y
    self.SendPositionLook()
    self._pos = Position(self._pos.x, self._pos.y, self._pos.stance,
        self._pos.z, self._pos.yaw, self._pos.pitch, 1)

  def OnMultiBlockChange(self, blocks):
    for x, z, y, newType, newMeta in blocks:
      self.world.SetBlock(x, z, y, newType, newMeta)

  def OnBlockChange(self, x, y, z, newType, newMeta):
    self.world.SetBlock(x, z, y, newType, newMeta)

  def OnMapChunks(self, chunk):
    self._chunks[chunk.chunkX, chunk.chunkZ] = chunk


  def DoDig(self, x, z, y, face, retries=3):
    bot.SendDig(x, z, y, 1)
    for i in range(retries):
      if bot.WaitFor(lambda: bot.world.GetBlock(*blockXzy) == 0):
        return True
      else:
        print "retrying"
        bot.SendDig(x, z, y, 1)


  def SendDig(self, x, z, y, face):
    self.Send(
        '\x0e' +
        pack('!b', 0) +
        pack('!i', x) +
        pack('!b', y) +
        pack('!i', z) +
        pack('!b', face)
        )
    self.Send(
        '\x0e' +
        pack('!b', 2) +
        pack('!i', x) +
        pack('!b', y) +
        pack('!i', z) +
        pack('!b', face)
        )

  def MoveTo(self, x, z, y, speed=4.25, onGround=True):
    def MyDist(x, z, y):
      return abs(self._pos.x - x) + abs(self._pos.z - z) + abs(self._pos.y - y)

    yaw = self._pos.yaw
    def Go(x=None, z=None, y=None):
      self._pos = Position(x, y, y+1, z,
          yaw, self._pos.pitch, onGround)

    if z - self._pos.z > .9:
      yaw = 0
    if z - self._pos.z < - .9:
      yaw = 180
    if x - self._pos.x > .9:
      yaw = 270
    if x - self._pos.x < - .9:
      yaw = 90

    tau = 0.010
    delta = speed * tau
    while MyDist(x, z, y) > (delta * 2):
      if self._pos.x - x > 0:
        new_x = self._pos.x - delta
      else:
        new_x = self._pos.x + delta
      if self._pos.z - z > 0:
        new_z = self._pos.z - delta
      else:
        new_z = self._pos.z + delta
      if self._pos.y - y > 0:
        new_y = self._pos.y - delta
      else:
        new_y = self._pos.y + delta
      Go(new_x, new_z, new_y)
      #print self._pos
      time.sleep(tau)
    Go(x, z, y)

  def FloatDown(self):
    self.WaitFor(lambda: self._pos.x != 0.0 and self._pos.y != 0.0)
    self.WaitFor(lambda: self.world.GetBlock(
      self._pos.x, self._pos.z, self._pos.y) is not None)
    print "block:", self.world.GetBlock(self._pos.x, self._pos.z, self._pos.y)
    while not self.world.IsStandable(self._pos.x, self._pos.z, self._pos.y):
      print "floatin..."
      self.MoveTo(int(self._pos.x) + .5, int(self._pos.z) + .5, self._pos.y - 1)
      time.sleep(0.100)
    print "block:", self.world.GetBlock(self._pos.x, self._pos.z, self._pos.y)

  def DigShaft(self, xRange, zRange):
    def Within(dist, xzyA, xzyB):
      if Dist(xzyA, xzyB) < dist:
        return xzyB

    def WantSolid(x, z, y):
      for xzyAdj, typeAdj in self.world.IterAdjacent(x, z, y):
        if typeAdj in (8, 9, 10, 11): # lava, water
          return True
      if self.world.GetBlock(x, z, y + 1) in (12, 13): # sand, gravel
        return True

      xFirst, xLast = xRange[0], xRange[1] - 1
      zFirst, zLast = zRange[0], zRange[1] - 1
      if x == xFirst or x == xLast or z == zFirst + 1 or z == zLast - 1:
        return not (y % 5)
      if z == zFirst:
        return not ((x - xFirst + y) % 5)
      if z == zLast:
        return not ((xLast - x + y) % 5)
      return False

    for y in range(127, -1, -1):
      for x in range(*xRange):
        for z in range(*zRange):
          blockXzy = Xzy(x, z, y)
          self.WaitFor(lambda: self.world.GetBlock(*blockXzy) is not None)
          blockType = self.world.GetBlock(*blockXzy)
          if WantSolid(*blockXzy):
            #print "Want block solid:", blockXzy, blockType
            # TODO: place
            continue
          if blockType == 0:
            continue
          print "Wanna dig block:", blockXzy, blockType
          botXzy = Xzy(self._pos.x, self._pos.z, self._pos.y)
          nextXzy = self.world.FindNearest(botXzy,
              functools.partial(Within, 1.5, blockXzy))
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
            self.MoveTo(xzy.x + .5, xzy.z + .5, xzy.y + .2)
          print "Digging:", blockXzy
          self.SendDig(blockXzy.x, blockXzy.z, blockXzy.y, 1)
          self.WaitFor(lambda: self.world.GetBlock(*blockXzy) == 0)
          print "block broken!"
          print
          print
          #time.sleep(5)



def main():
  host = '108.59.83.223'    # The remote host
  port = 31337              # The same port as used by the server
  port = 25565
  port = 4000

  username = u'johnbaruch'
  password = u'zoe77zoe'

  username = u'peon'

  #bot = MineCraftBot(host, port, username, password)
  bot = MineCraftBot(host, port)
  bot.Start()
  bot.Login(username, password)

  bot.FloatDown()
  print "done!", bot._pos.x

  #bot.DigShaft( (130, 150), (240, 260) )
  bot.DigShaft( (135, 150), (220, 235) )


if __name__ == '__main__':
  main()
