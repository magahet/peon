#!/usr/bin/python

import socket
import struct
import sys
import urllib
import urllib2

from struct import pack, unpack


class MineCraftProtocol(object):
  def __init__(self, sock):
    self._sock = sock
    self._buf = ""
    self._parsers = {
        '\x00': self.ParseKeepAlive,
        '\x01': self.ParseLogin,
        '\x02': self.ParseHandshake,
        '\x03': self.ParseChatMessage,
        '\x04': self.ParseTimeUpdate,

        #'\x05': self.ParseEntityEquipment,

        '\x06': self.ParseSpawn,

        #'\x08': self.ParseUpdateHealth,
        #'\x09': self.ParseRespawn,

        '\x0d': self.ParsePlayerPositionLook,
        '\x14': self.ParseSpawnNamedEntity,
        '\x15': self.ParseSpawnDroppedItem,
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
        '\x32': self.ParseMapColumnAllocation,
        '\x3d': self.ParseSoundParticleEffect,
        '\x46': self.ParseChangeGameState,
        '\x36': self.ParseBlockAction,
        '\x67': self.ParseSetSlot,
        '\x68': self.ParseSetWindowItems,
        '\xca': self.ParsePlayerAbility,
        '\xc9': self.ParsePlayerListItem,
        '\xff': self.ParseKick,
        }

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
  # Protocol convenience methods

  def Send(self, packet):
    print '\nSending packet: %s' % hex(ord(packet[0]))
    self._sock.sendall(packet)

  def Recv(self, size=1024):
    self._buf += self._sock.recv(size)

  def RecvPacket(self):
    if len(self._buf) < 1024:
      self.Recv()
    while not self._buf:
      #print "len: ", len(self._buf)
      self.Recv()
    ilk = self._buf[0]
    self._buf = self._buf[1:]
    #print hex(ord(ilk)), len(self._buf)
    print '\nReceived packet: %s (buf: %d)' % (hex(ord(ilk)), len(self._buf))
    #for x in self._buf:
      #print hex(ord(x)), ' ',
    #print
    try:
      parsed = self._parsers[ilk]()
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
    value, = struct.unpack('!b', self._buf[:1])
    self._buf = self._buf[1:]
    return value

  def UnpackUint8(self):
    value, = struct.unpack('!B', self._buf[:1])
    self._buf = self._buf[1:]
    return value

  def UnpackInt16(self):
    value, = struct.unpack('!h', self._buf[:2])
    self._buf = self._buf[2:]
    return value

  def UnpackInt32(self):
    value, = struct.unpack('!i', self._buf[:4])
    self._buf = self._buf[4:]
    return value

  def UnpackInt64(self):
    value, = struct.unpack('!q', self._buf[:8])
    self._buf = self._buf[8:]
    return value

  def UnpackFloat(self):
    value, = struct.unpack('!f', self._buf[:4])
    self._buf = self._buf[4:]
    return value

  def UnpackDouble(self):
    value, = struct.unpack('!d', self._buf[:8])
    self._buf = self._buf[8:]
    return value

  def UnpackString(self):
    strlen = self.UnpackInt16()
    print 'strlen: ', strlen
    #print len(self._buf), strlen*2
    string = self._buf[:strlen*2].decode('utf_16_be')
    self._buf = self._buf[strlen*2:]
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
        data = self._buf[:arraySize]
        self._buf = self._buf[arraySize:]

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

    strlen = self.UnpackInt16()
    print 'strlen: ', strlen
    #print len(self._buf), strlen*2
    string = self._buf[:strlen*2].decode('utf_16_be')
    self._buf = self._buf[strlen*2:]
    print u'Got string: [%s]' % string
    return string

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
    return (self.UnpackInt32(), self.UnpackInt32(), self.UnpackInt32())

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

  def ParsePlayerAbility(self):
    return (
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8())

  def ParsePlayerListItem(self):
    return (
        self.UnpackString(),
        self.UnpackInt8(),
        self.UnpackInt16(),
        )

  def ParseTimeUpdate(self):
    return (
        self.UnpackInt64(),)

  def ParseMapColumnAllocation(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
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
    print "Array Size: ", slotCount
    slots = []
    for i in range(slotCount):
      if len(self._buf) < 1024:
        self.Recv(1024)
      slots.append(self.UnpackSlot())
    return (window, slots)


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

  def SendKeepAlive(self, token=0):
    self.Send(
        '\x00' +
        pack('!i', token)
        )


class MineCraftBot(MineCraftProtocol):

  def __init__(self, host, port, username, password):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    super(MineCraftBot, self).__init__(sock)

    self._sessionId = self.GetSessionId(username, password)
    print 'SessionId:', self._sessionId

    self.SendHandshake(username, host, port)
    self._serverId, = self.WaitFor('\x02')
    print 'Serverid:', self._serverId

    self.JoinServer(username, self._sessionId, self._serverId)

    self.SendLogin(username)
    print self.WaitFor('\x01')

    print self.WaitFor('\x0d')

    self._handlers = {
        '\x00': self.OnKeepAlive,
        }

  def OnKeepAlive(self, token):
    self.Send(
        '\x00' +
        pack('!i', token)
        )


def main():
  host = '108.59.83.223'    # The remote host
  port = 31337              # The same port as used by the server
  port = 25565

  username = u'johnbaruch'
  password = u'zoe77zoe'

  bot = MineCraftBot(host, port, username, password)
  while True:
    bot.RecvPacket()


if __name__ == '__main__':
  main()
