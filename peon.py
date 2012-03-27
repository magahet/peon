#!/usr/bin/python

import array
import collections
import Queue
import socket
import struct
import sys
import threading
import time
import urllib
import urllib2
import zlib

from struct import pack, unpack


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

  def GetBlock(self, x, z, y):
    x, z, y = int(x), int(z), int(y)
    #print x, z, y
    #print x - self.chunkX * 16, z - self.chunkZ * 16, y
    offset = (       (x - self.chunkX * 16) +
              (16 *  (z - self.chunkZ * 16)) +
              (256 * (y))
             )
    #print offset
    blockType = self._blocks[offset]
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
        #'\x35',
        '\x46',
        '\xc8',
        '\xff',
        ])

    self._handlers = {}

    self._threads = [
        threading.Thread(target=self._DoReadThread),
        threading.Thread(target=self._DoSendThread),
        ]


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

  def WaitFor(self, ilk):
    gotten_ilk = None
    while gotten_ilk != ilk:
      gotten_ilk, parsed = self.RecvPacket()
    print u'Got: %s' % hex(ord(gotten_ilk))
    return parsed

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
    ret = [
        self.UnpackInt32(),
        self.UnpackInt32(),
        ]
    self.UnpackInt16()
    ret.append(self.Read(self.UnpackInt32()))
    # TODO: parse the internals
    return ret

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


Position = collections.namedtuple('Position',
    ('x', 'y', 'stance', 'z', 'yaw', 'pitch', 'on_ground'))

class MineCraftBot(MineCraftProtocol):

  def __init__(self, host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    super(MineCraftBot, self).__init__(sock)

    self._handlers = {
        '\x00': self.OnKeepAlive,
        '\x0d': self.OnPlayerPositionLook,
        '\x35': self.OnBlockChange,
        '\x33': self.OnMapChunks,
        }
    self._pos = Position(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1)
    self._threads.append(threading.Thread(target=self._DoPositionUpdateThread))
    self._chunks = {}

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
    #print self.WaitFor('\x01')

    #print self.WaitFor('\x0d')

  def GetBlock(self, x, z, y):
    chunk = self._chunks.get((int(x/16), int(z/16)))
    if not chunk:
      return None
    return chunk.GetBlock(int(x), int(z), int(y))

  def _DoPositionUpdateThread(self):
    time.sleep(2)
    while True:
      time.sleep(0.050)
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
    print "Corrected Position: ", self._pos
    self.SendPositionLook()
    self._pos = Position(self._pos.x, self._pos.y, self._pos.stance,
        self._pos.z, self._pos.yaw, self._pos.pitch, 1)

  def OnBlockChange(self, x, y, z, newType, newMeta):
    if newType == 0:
      final_y = self._pos.y - 1 #int(self._pos.y - 2)
      print "new y:", final_y
      print x, y, z, newType, newMeta
      self._pos = Position(self._pos.x, final_y, final_y + 1,
          self._pos.z, self._pos.yaw, self._pos.pitch, 1)
      self.SendDig(self._pos.x, self._pos.z, self._pos.y - 1, 1)

  def OnMapChunks(self, chunk):
    self._chunks[chunk.chunkX, chunk.chunkZ] = chunk


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

  def MoveTo(self, x, z, y, speed=1.0, onGround=True):
    def Dist(x, z, y):
      return abs(self._pos.x - x) + abs(self._pos.z - z) + abs(self._pos.y - y)

    def Go(x=None, z=None, y=None):
      self._pos = Position(x, y, y+1, z,
          self._pos.yaw, self._pos.pitch, onGround)

    tau = 0.050
    while Dist(x, z, y) > speed:
      if self._pos.x - x > 0:
        new_x = self._pos.x - speed * tau
      else:
        new_x = self._pos.x + speed * tau
      if self._pos.z - z > 0:
        new_z = self._pos.z - speed * tau
      else:
        new_z = self._pos.z + speed * tau
      if self._pos.y - y > 0:
        new_y = self._pos.y - speed * tau
      else:
        new_y = self._pos.y + speed * tau
      Go(new_x, new_z, new_y)
      #print self._pos
      time.sleep(tau)
    Go(x, z, y)


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
  new_y = bot._pos.y #- 1 #int(bot._pos.y - 2)
  new_x = bot._pos.x - 1 #int(bot._pos.y - 2)
  while True:
    time.sleep(1)
    print 'Position: ', bot._pos.x, bot._pos.z, bot._pos.y
    '''
    print (bot._pos.x/16, bot._pos.z/16)
    print bot.GetBlock(bot._pos.x, bot._pos.z, bot._pos.y)
    print bot.GetBlock(bot._pos.x, bot._pos.z, bot._pos.y - 1)
    print bot.GetBlock(bot._pos.x, bot._pos.z, bot._pos.y - 2)
    print bot.GetBlock(bot._pos.x, bot._pos.z, 0)
    for i in range(bot._pos.y + 5):
      print "  i: ", i,  bot.GetBlock(bot._pos.x, bot._pos.z, i)
    '''
    for dest in [
        #(146, 248, 64),
        (139.5, 256.5, 64),
        (139.5, 256.5, 69),
        #(139.5, 256.5, 64),
        ]:
      time.sleep(5)
      bot.MoveTo(*dest)
    for i in range(bot._pos.y + 5):
      print "  i: ", i,  bot.GetBlock(bot._pos.x, bot._pos.z, i)
    continue
    #new_x = bot._pos.x - 1 #int(bot._pos.y - 2)
    new_y = bot._pos.y - 1 #int(bot._pos.y - 2)
    print bot._pos.y
    bot._pos = Position(new_x, new_y, new_y + 1,
        bot._pos.z, bot._pos.yaw, bot._pos.pitch, 1)


  # Dig
  bot.SendPositionLook()
  last_pos_update = 0
  start_time = time.time()
  print "start_y:", bot._pos.y
  final_y = bot._pos.y - 1 #int(bot._pos.y - 2)
  bot._pos = Position(bot._pos.x, final_y, final_y + 1,
      bot._pos.z, bot._pos.yaw, bot._pos.pitch, 1)
  bot.SendPositionLook()

  until = time.time() + 10
  while time.time() < until:
    if time.time() - last_pos_update > 0.05:
      bot.SendPositionLook()
      last_pos_update = time.time()
      #bot._pos = Position(bot._pos.x, final_y, final_y + 1,
          #bot._pos.z, bot._pos.yaw, bot._pos.pitch, 1)
      #('x', 'y', 'stance', 'z', 'yaw', 'pitch', 'on_ground'))
    bot.RecvPacket()

  last_dig = 0
  while True:
    if time.time() - last_pos_update > 0.05:
      bot.SendPositionLook()
      last_pos_update = time.time()
      #bot._pos = Position(bot._pos.x, final_y, final_y + 1,
          #bot._pos.z, bot._pos.yaw, bot._pos.pitch, 1)
      #('x', 'y', 'stance', 'z', 'yaw', 'pitch', 'on_ground'))
    if time.time() - last_dig > 20:
      pos = bot._pos
      bot.SendDig(pos.x, pos.z, pos.y - 1, 1)

    #while len(bot._buf) > 10:
      #print len(bot._buf)
    bot.RecvPacket()


if __name__ == '__main__':
  main()
