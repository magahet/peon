import array
import collections
import Queue
import struct
import sys
import os
import threading
import time
import urllib
import urllib2
import zlib
import math
import logging


class Slot(collections.namedtuple('Slot', ('itemId', 'count', 'meta', 'data'))):
  pass


class Window(object):
  def __init__(self, windowId, slots):
    self._slots = slots
    self._count = len(slots)
    self.inventory_type = None
    self.window_title = None

  def GetMainInventory(self):
    return self._slots[-36:-9]

  def GetHeld(self):
    return self._slots[-9:]

  def SetSlot(self, index, slot):
    self._slots[index] = slot


class Xzy(collections.namedtuple('Xzy', ('x', 'z', 'y'))):
  def __new__(cls, *args, **kwargs):
    args = map(math.floor, args)
    args = map(int, args)
    for k, v in kwargs.iteritems():
      kwargs[k] = int(math.floor(v))
    return super(Xzy, cls).__new__(cls, *args, **kwargs)

  def Offset(self, x=0, z=0, y=0):
    return Xzy(self.x + x, self.z + z, self.y + y)


class World(object):
  def __init__(self):
    self._chunks = {}
    self._entities= {}
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
    return (
        (self.GetBlock(x, z, y - 2) in SOLID or
         self.GetBlock(x, z, y - 1) in SOLID) and
        self.GetBlock(x, z, y)     not in SOLID and
        self.GetBlock(x, z, y + 1) == 0
        )

  def IsMoveable(self, x, z, y):
    NON_SOLID = set([0, 6, 18, 27,28,31,32,37,38,39,40,50,55,59,63,65,66,68,69,70,72,75,76,78,93,94,96,106,111,115,])
    standable = (
        self.GetBlock(x, z, y) in NON_SOLID and
        self.GetBlock(x, z, y + 1) in NON_SOLID
    )
    return standable

  def IsStandable(self, x, z, y):
    SOLID = set(range(1, 5) + [7] + range(12, 27))
    standable = (
        self.GetBlock(x, z, y - 1) in SOLID and
        self.GetBlock(x, z, y)     == 0 and
        self.GetBlock(x, z, y + 1) == 0
    )
    return standable

  def IsDiggable(self, x, z, y):
    NON_SOLID = set(range(8, 14))
    for xzy, block_type in self.IterAdjacent(x, z, y):
      if block_type in NON_SOLID:
        return False
    for xzy, block_type in self.IterAdjacent(x, z, y + 1):
      if block_type in NON_SOLID:
        return False
    return True

  def IterAdjacent(self, x, z, y):
    adjacents = [
        Xzy(x, z, y - 1),
        Xzy(x + 1, z, y),
        Xzy(x - 1, z, y),
        Xzy(x, z - 1, y),
        Xzy(x, z + 1, y),
        Xzy(x, z, y + 1),
        ]
    for xzy in adjacents:
      yield xzy, self.GetBlock(*xzy)

  def find_nearest_standable(self, xzy, within=100):
    maxD = 100
    d = {}
    d[xzy] = 0
    queue = [xzy]
    while queue:
      current_xzy = queue.pop(0)
      xzyD = d[current_xzy]
      if xzyD > maxD:
        break
      if self.IsStandable(*current_xzy) and cityblock(xzy, current_xzy) < within:
        return xzy
      for xzyAdj, blockAdj in self.IterAdjacent(*xzy):
        if xzyAdj in d:
          continue
        if self.IsJumpable(*xzyAdj):
          d[xzyAdj] = xzyD + 1
          queue.append(xzyAdj)
    return None


  def FindNearestStandable(self, xzy, condition):
    maxD = 100
    d = {}
    d[xzy] = 0
    queue = [xzy]
    while queue:
      xzy = queue.pop(0)
      xzyD = d[xzy]
      if xzyD > maxD:
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
    xzyA = Xzy(*xzyA)
    xzyB = Xzy(*xzyB)
    d = {}
    d[xzyA] = 0
    queue = [xzyA]
    while queue and xzyB not in d:
      xzy = queue.pop(0)
      xzyD = d[xzy]
      for xzyAdj, blockAdj in self.IterAdjacent(*xzy):
        if xzyAdj not in d and self.IsMoveable(*xzyAdj):
          d[xzyAdj] = xzyD + 1
          queue.append(xzyAdj)
    if xzyB not in d:
      return None
    path = [xzyB]
    while path[-1] != xzyA:
      for xzyAdj, blockAdj in self.IterAdjacent(*path[-1]):
        if xzyAdj in d and d[xzyAdj] < d[path[-1]]:
          path.append(xzyAdj)
          break
    path.reverse()
    return path


class Position(collections.namedtuple('Position',
    ('x', 'y', 'stance', 'z', 'yaw', 'pitch', 'on_ground'))):
  def xzy(self):
      return Xzy(self.x, self.z, self.y)

class Confirmation(collections.namedtuple('Confirmation', ('window_id', 'action_id', 'accepted'))):
  pass

class Entity(object):
  def __init__(self, eid, etype, x, y, z, yaw, pitch, player_name=None, current_item=None, head_yaw=0, metadata=None):
    self._eid = eid
    self._type= etype
    self._pos = Position(x/32, y/32, (y/32)+1, z/32, yaw, pitch, 1)
    self._player_name = player_name
    self._current_item = current_item
    self._head_yaw = head_yaw
    self._metadata = metadata

  def Move(self, dx, dy, dz):
    if None not in self._pos.xzy():
      x = self._pos.x + (dx/32.0)
      z = self._pos.z + (dz/32.0)
      y = self._pos.y + (dy/32.0)
      yaw = self._pos.yaw
      pitch = self._pos.pitch
      self._pos = Position(x, y, y+1, z, yaw, pitch, 1)

  def Teleport(self, x, y, z):
    yaw = self._pos.yaw
    pitch = self._pos.pitch
    self._pos = Position(x/32.0, y/32.0, (y/32.0)+1, z/32.0, yaw, pitch, 1)

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
  def __init__(self):
    self._sock = None
    self._sockGeneration = 0
    self._recvCondition = threading.Condition()
    self._buf = ""
    self._sendQueue = Queue.Queue(10)
    self.parentPID = os.getppid()

    self._threads = []
    self._threadFuncs = [
        self._DoReadThread,
        self._DoSendThread,
        ]

    self._parsers = {
        '\x00': self.ParseKeepAlive,
        '\x01': self.ParseLogin,
        '\x02': self.ParseHandshake,
        '\x03': self.ParseChatMessage,
        '\x04': self.ParseTimeUpdate,
        '\x05': self.ParseEntityEquipment,
        '\x06': self.ParseSpawn,
        #'\x07': client only
        '\x08': self.ParseUpdateHealth,
        '\x09': self.ParseRespawn,
        '\x10': self.ParseHeldItemChange,
        #'\x0a': client only
        #'\x0b': client only
        '\x0c': self.ParsePlayerLook,
        '\x0d': self.ParsePlayerPositionLook,
        #'\x0e': client only
        #'\x0f': client only
        #'\x10': client only
        '\x11': self.ParseUseBed,
        '\x12': self.ParseAnimation,
        #'\x13': client only
        '\x14': self.ParseSpawnNamedEntity,
        '\x15': self.ParseSpawnDroppedItem,
        '\x16': self.ParseCollectItem,
        '\x17': self.ParseSpawnObjectVehicle,
        '\x18': self.ParseSpawnMob,
        '\x19': self.ParseSpawnPainting,
        '\x1a': self.ParseSpawnExperienceOrb,
        #'\x1b': self.ParseStanceUpdate,
        '\x1c': self.ParseEntityVelocity,
        '\x1d': self.ParseDestroyEntity,
        '\x1e': self.ParseEntity,
        '\x1f': self.ParseEntityRelativeMove,
        '\x20': self.ParseEntityLook,
        '\x21': self.ParseEntityRelativeLookAndMove,
        '\x22': self.ParseEntityTeleport,
        '\x23': self.ParseEntityHeadLook,
        '\x26': self.ParseEntityStatus,
        '\x27': self.ParseAttachEntity,
        '\x28': self.ParseEntityMetadata,
        '\x29': self.ParseEntityEffect,
        '\x2a': self.ParseRemoveEntityEffect,
        '\x2b': self.ParseSetExperience,
        '\x32': self.ParseMapColumnAllocation,
        '\x33': self.ParseMapChunks,
        '\x34': self.ParseMultiBlockChange,
        '\x35': self.ParseBlockChange,
        '\x36': self.ParseBlockAction,
        '\x3c': self.ParseExplosion,
        '\x3d': self.ParseSoundParticleEffect,
        '\x46': self.ParseChangeGameState,
        '\x47': self.ParseThunderbolt,
        '\x64': self.ParseOpenWindow,
        '\x65': self.ParseCloseWindow,
        '\x67': self.ParseSetSlot,
        '\x68': self.ParseSetWindowItems,
        '\x69': self.ParseUpdateWindowProperty,
        '\x6a': self.ParseConfirmTransaction,
        '\x6b': self.ParseCreativeInventoryAction,
        '\x82': self.ParseUpdateSign,
        '\x83': self.ParseItemData,
        '\x84': self.ParseUpdateTileEntity,
        '\xc8': self.ParseIncrementStatistic,
        '\xc9': self.ParsePlayerListItem,
        '\xca': self.ParsePlayerAbility,
        '\xff': self.ParseKick,
        }

    self._interesting = set([
        #'\x00', #KeepAlive
        #'\x01', #Login
        #'\x02', #Handshake
        #'\x03', #ChatMessage
        #'\x04', #TimeUpdate
        #'\x05', #EntityEquipment
        #'\x06', #Spawn
        #'\x08', #UpdateHealth
        #'\x09', #Respawn
        #'\x0e', #PlayerDigging
        #'\x10', #HeldItemChange
        #'\x0c', #PlayerLook
        #'\x0d', #PlayerPositionLook
        #'\x11', #UseBed
        #'\x12', #Animation
        #'\x14', #SpawnNamedEntity
        #'\x15', #SpawnDroppedItem
        #'\x16', #CollectItem
        #'\x17', #SpawnObjectVehicle
        #'\x18', #SpawnMob
        #'\x19', #SpawnPainting
        #'\x1a', #SpawnExperienceOrb
        #'\x1b', #StanceUpdate
        #'\x1c', #EntityVelocity
        #'\x1d', #DestroyEntity
        #'\x1f', #EntityRelativeMove
        #'\x20', #EntityLook
        #'\x21', #EntityRelativeLookAndMove
        #'\x22', #EntityTeleport
        #'\x23', #EntityHeadLook
        #'\x26', #EntityStatus
        #'\x27', #AttachEntity
        #'\x28', #EntityMetadata
        #'\x29', #EntityEffect
        #'\x2a', #RemoveEntityEffect
        #'\x2b', #SetExperience
        #'\x32', #MapColumnAllocation
        #'\x33', #MapChunks
        #'\x34', #MultiBlockChange
        #'\x35', #BlockChange
        #'\x36', #BlockAction
        #'\x3c', #Explosion
        #'\x3d', #SoundParticleEffect
        #'\x46', #ChangeGameState
        #'\x47', #Thunderbolt
        #'\x64', #OpenWindow
        #'\x65', #CloseWindow
        #'\x67', #SetSlot
        #'\x68', #SetWindowItems
        #'\x69', #UpdateWindowProperty
        #'\x6a', #ConfirmTransaction
        #'\x6b', #CreativeInventoryAction
        #'\x82', #UpdateSign
        #'\x83', #ItemData
        #'\x84', #UpdateTileEntity
        #'\xc8', #IncrementStatistic
        #'\xc9', #PlayerListItem
        #'\xca', #PlayerAbility
        #'\xff', #Kick
        ])

    self._handlers = {}


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

  def StartThreads(self):
    self._threads = []
    for func in self._threadFuncs:
      thread = threading.Thread(target=func)
      thread.daemon = True
      thread.start()
      self._threads.append(thread)
    return self

  def _DoReadThread(self):
    try:
      myGeneration = self._sockGeneration
      while myGeneration == self._sockGeneration:
        self.RecvPacket()
        if os.getppid() != self.parentPID:
          pass
          #print "ReadThread exiting", myGeneration
          #sys.exit()
    finally:
      os.kill(self.parentPID, 0)

  def _DoSendThread(self):
    try:
      myGeneration = self._sockGeneration
      sock = self._sock
      queue = self._sendQueue
      while myGeneration == self._sockGeneration and self._sock is not None:
        sock.sendall(queue.get())
        if os.getppid() != self.parentPID:
          pass
          #print "SendThread exiting", myGeneration
    finally:
      os.kill(self.parentPID, 0)


  ##############################################################################
  # Protocol convenience methods

  def Send(self, packet):
    if packet[0] in self._interesting:
    #if True:
      sys.stderr.write('\nSending packet: %s\n' % hex(ord(packet[0])))
    self._sendQueue.put(packet)

  def Read(self, size):
    while len(self._buf) < size:
      recieved = self._sock.recv(4096)
      self._buf += recieved
    ret = self._buf[:size]
    self._buf = self._buf[size:]
    return ret

  def RecvPacket(self):
    ilk = self.Read(1)
    try:
      parsed = self._parsers[ilk]()
      if ilk in self._interesting:
        logging.debug('Parsed packet: %s (buf: %d)', hex(ord(ilk)), len(self._buf))
      handler = self._handlers.get(ilk)
      if handler:
        handler(*parsed)
      with self._recvCondition:
        self._recvCondition.notifyAll()
    except KeyError:
      sys.stderr.write('unknown packet: %s\n' % hex(ord(ilk)))
      raise
      i = ''
      while i != '\x00':
        i = self.Read(1)
        sys.stderr.write('%s  ' % hex(ord(i)))
      sys.stderr.write('back on track\n')


  def WaitFor(self, what, timeout=60):
    start = time.time()
    with self._recvCondition:
      while not what() and time.time() - start < timeout:
        self._recvCondition.wait(timeout=1)
    return what()

  def PackString(self, string):
    return struct.pack('!h', len(string)) + string.encode('utf_16_be')

  def PackSlot(self, slot_data):
    itemId, count, meta, data = slot_data
    packet = struct.pack('!h', itemId)
    if itemId == -1:
      return packet
    packet += (struct.pack('!b', count) +
      struct.pack('!h', meta)
      )
    if ((256 <= itemId <= 259) or
        (267 <= itemId <= 279) or
        (283 <= itemId <= 286) or
        (290 <= itemId <= 294) or
        (298 <= itemId <= 317) or
        itemId == 261 or itemId == 359 or itemId == 346):
      if data is None:
        packet += struct.pack('!h', -1)
      else:
        packet += struct.pack('!h', len(data)) + data
    return packet

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

  def UnpackBool(self):
    value, = struct.unpack('?', self.Read(1))
    return value

  def UnpackString(self):
    strlen = self.UnpackInt16()
    string = self.Read(strlen * 2).decode('utf_16_be')
    return string

  def UnpackSlot(self):
    itemId = self.UnpackInt16()
    if itemId == -1:
      return Slot(itemId, None, None, None)
    itemCount = self.UnpackInt8()
    meta = self.UnpackInt16()  # damage, or block meta
    data = None
    # These certain items are capable of having meta/enchantments
    if ((256 <= itemId <= 259) or
        (267 <= itemId <= 279) or
        (283 <= itemId <= 286) or
        (290 <= itemId <= 294) or
        (298 <= itemId <= 317) or
        itemId == 261 or itemId == 359 or itemId == 346):
      arraySize = self.UnpackInt16()
      if arraySize != -1:
        data = self.Read(arraySize)

    return Slot(itemId, itemCount, meta, data)
  
  def UnpackMetadata(self):
    metadata = {}
    x = self.UnpackUint8()
    while x != 127:
        index = x & 0x1F # Lower 5 bits
        ty    = x >> 5   # Upper 3 bits
        if ty == 0: val = self.UnpackInt8()
        if ty == 1: val = self.UnpackInt16()
        if ty == 2: val = self.UnpackInt32()
        if ty == 3: val = self.UnpackFloat()
        if ty == 4: val = self.UnpackString()
        if ty == 5:
            val = {}
            val["id"]     = self.UnpackInt16()
            val["count"]  = self.UnpackInt8()
            val["damage"] = self.UnpackInt16()
        if ty == 6:
            val = []
            for i in range(3):
                val.append(self.UnpackInt32())
        metadata[index] = (ty, val)
        x = self.UnpackInt8()
    return metadata

  ##############################################################################
  # Parsers

  def ParseKick(self):
    sys.stderr.write('Kicked: ' + self.UnpackString() + '\n')
    raise Exception()

  def ParseHandshake(self):
    return (self.UnpackString(),)

  def ParseChatMessage(self):
    chat = self.UnpackString()
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

  def ParseUseBed(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt32(),
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

  def ParseSpawnPainting(self):
    return (
        self.UnpackInt32(),
        self.UnpackString(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        )

  def ParseSpawnExperienceOrb(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt16(),
        )

  def ParseStanceUpdate(self):
    return (
        self.UnpackFloat(),
        self.UnpackFloat(),
        self.UnpackFloat(),
        self.UnpackFloat(),
        self.UnpackBool(),
        self.UnpackBool(),
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

  def ParseEntity(self):
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

  def ParseAttachEntity(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        )

  def ParseEntityMetadata(self):
    return (
        self.UnpackInt32(),
        self.UnpackMetadata(),
        )

  def ParseEntityEffect(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt16(),
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
      pass
      #print "WTF:", count, size
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

  def ParseExplosion(self):
    x = self.UnpackDouble()
    y = self.UnpackDouble()
    z = self.UnpackDouble()
    unknown = self.UnpackFloat()
    record_count = self.UnpackInt32()
    records = []
    for i in range(record_count):
      records.append(self.Read(3))
    return (x, y, z, unknown, record_count, records)

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

  def ParseThunderbolt(self):
    return (
        self.UnpackInt32(),
        self.UnpackBool(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        )

  def ParseOpenWindow(self):
    return (
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackString(),
        self.UnpackInt8(),
        )

  def ParseCloseWindow(self):
    return (
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
    windowId = self.UnpackInt8()
    slotCount = self.UnpackInt16()
    # enchantment table lies about its custom slot count
    if windowId != 0 and slotCount == 9:
      slotCount = 1 + 27 + 9
    slots = []
    for i in range(slotCount):
      slots.append(self.UnpackSlot())
    return (windowId, slots)

  def ParseUpdateWindowProperty(self):
    return (
        self.UnpackInt8(),
        self.UnpackInt16(),
        self.UnpackInt16(),
        )

  def ParseConfirmTransaction(self):
    return (
        self.UnpackInt8(),
        self.UnpackInt16(),
        self.UnpackBool(),
        )

  def ParseCreativeInventoryAction(self):
    return (
        self.UnpackInt16(),
        self.UnpackSlot(),
        )

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

  def ParseUpdateSign(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt16(),
        self.UnpackInt32(),
        self.UnpackString(),
        self.UnpackString(),
        self.UnpackString(),
        self.UnpackString(),
        )

  def ParseItemData(self):
    item_type = self.UnpackInt16()
    item_id = self.UnpackInt16()
    array_length = self.UnpackInt8()
    text = self.Read(arrayLength)
    return (item_type, item_id, array_length, text)


  ##############################################################################
  # Senders

  def SendLogin(self, username):
    packet = (
        '\x01' +
        struct.pack('!i', 29) +
        self.PackString(username) +
        self.PackString('') +
        struct.pack('!i', 0) +
        struct.pack('!i', 0) +
        struct.pack('!b', 0) +
        struct.pack('!B', 0) +
        struct.pack('!B', 0)
        )
    self.Send(packet)

  def SendHandshake(self, username, server, port):
    self.Send(
        '\x02' +
        self.PackString(u'%s;%s;%d' % (username, server, port))
        )

  def SendChat(self, msg):
    self.Send(
        '\x03' +
        self.PackString(u'%s' % (msg))
        )

  def SendUseEntity(self, user, target, mouse_button):
    self.Send(
        '\x07' +
        struct.pack('!i', user) +
        struct.pack('!i', target) +
        struct.pack('!b', mouse_button)
        )

  def SendRespawn(self, dimension, difficulty, levelType):
    packet = (
        '\x09' +
        struct.pack('!i', dimension) +
        struct.pack('!b', difficulty) +
        struct.pack('!b', 0) +
        struct.pack('!h', 256) +
        self.PackString(levelType)
        )
    self.Send(packet)

  def SendPlayer(self, on_ground):
    ''' Tell server whether player is on the ground '''
    self.Send(
        '\x0a' +
        struct.pack('!b', on_ground)
        )

  def SendPlayerPosition(self, x, y, stance, z, on_ground):
    self.Send(
        '\x0b' +
        struct.pack('!ddddb', x, y, stance, z, on_ground)
        )

  def SendPlayerLook(self, yaw, pitch, on_ground):
    self.Send(
        '\x0c' +
        struct.pack('!ffb', yaw, pitch, on_ground)
        )

  def SendPlayerPositionAndLook(self, x, y, stance, z, yaw, pitch, on_ground):
    self.Send(
        '\x0d' +
        struct.pack('!ddddffb', x, y, stance, z, yaw, pitch, on_ground)
        )

  def SendPlayerDigging(self, status, x, y, z, face):
    self.Send(
        '\x0e' +
        struct.pack('!b', status) +
        struct.pack('!i', x) +
        struct.pack('!b', y) +
        struct.pack('!i', z) +
        struct.pack('!B', face) # trying unsigned 
        )

  def SendPlayerBlockPlacement(self, x, y, z, direction, held_item):
    self.Send(
        '\x0f' +
        struct.pack('!i', x) +
        struct.pack('!b', y) +
        struct.pack('!i', z) +
        struct.pack('!b', direction)+
        self.PackSlot(held_item)
        )

  def SendHeldItemChange(self, slot_id):
    #print 'SendHeldItemChange:', (slot_id)
    packet = (
        '\x10' +
        struct.pack('!h', slot_id)
        )
    self.Send(packet)

  def SendAnimation(self, eid, animation):
    self.Send(
        '\x12' +
        struct.pack('!i', eid) +
        struct.pack('!b', animation)
        )

  def SendEntityAction(self, eid, action_id):
    self.Send(
        '\x13' +
        struct.pack('!i', eid) +
        struct.pack('!b', action_id)
        )

  def SendCloseWindow(self, window_id):
    self.Send(
        '\x65' +
        struct.pack('!b', window_id)
        )

  def SendClickWindow(self, window_id, slot_id, right_click, action_number, shift, slot_data):
    #print 'SendClickWindow:', window_id, slot_id, right_click, action_number, shift, slot_data
    packet = (
        '\x66' +
        struct.pack('!b', window_id) +
        struct.pack('!h', slot_id) +
        struct.pack('!b', right_click) +
        struct.pack('!h', action_number) +
        struct.pack('!b', shift) +
        self.PackSlot(slot_data)
        )
    self.Send(packet)

  def SendConfirmTransaction(self, window_id, action_number, accepted):
    self.Send(
        '\x6a' +
        struct.pack('!b', window_id) +
        struct.pack('!h', action_number) +
        struct.pack('!b', accepted)
        )

  def SendCreativeInventoryAction(self, slot, clicked_item):
    self.Send(
        '\x6b' +
        struct.pack('!h', slot) +
        self.PackSlot(clicked_item)
        )

  def SendEnchantItem(self, window_id, enchantment):
    self.Send(
        '\x6c' +
        struct.pack('!b', window_id) +
        struct.pack('!b', enchantment)
        )

  def SendUpdateSign(self, x, y, z, text1, text2, text3, text4):
    self.Send(
        '\x82' +
        struct.pack('!i', x) +
        struct.pack('!h', y) +
        struct.pack('!i', z) +
        self.PackString(text1) +
        self.PackString(text2) +
        self.PackString(text3) +
        self.PackString(text4)
        )

  def SendPlayerAbilities(self, invulnerability, is_flying, can_fly, instant_destroy):
    self.Send(
        '\xca' +
        struct.pack('!b', invulnerability) +
        struct.pack('!b', is_flying) +
        struct.pack('!b', can_fly) +
        struct.pack('!b', instant_destroy)
        )

  def SendListPing(self):
    self.Send(
        '\xfe'
        )

  def SendDisconnect(self, reason=''):
    self.Send(
        '\xff' +
        self.PackString(reason)
        )


