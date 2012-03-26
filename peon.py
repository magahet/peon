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
    self._handlers = {
        '\x00': self.OnKeepAlive,
        '\x01': self.OnLogin,
        '\x02': self.OnHandshake,
        '\x03': self.OnChatMessage,
        '\x04': self.OnTimeUpdate,

        #'\x05': self.OnEntityEquipment,

        '\x06': self.OnSpawn,

        #'\x08': self.OnUpdateHealth,
        #'\x09': self.OnRespawn,

        '\x0d': self.OnPlayerPositionLook,
        '\x14': self.OnSpawnNamedEntity,
        '\x15': self.OnSpawnDroppedItem,
        '\x17': self.OnSpawnObjectVehicle,
        '\x18': self.OnSpawnMob,
        '\x1a': self.OnSpawnExperienceOrb,
        '\x1c': self.OnEntityVelocity,
        '\x1d': self.OnDestroyEntity,
        '\x1f': self.OnEntityRelativeMove,
        '\x20': self.OnEntityLook,
        '\x21': self.OnEntityRelativeLookAndMove,
        '\x22': self.OnEntityTeleport,
        '\x23': self.OnEntityHeadLook,
        '\x26': self.OnEntityStatus,
        '\x28': self.OnEntityMetadata,
        '\x2a': self.OnRemoveEntityEffect,
        '\x32': self.OnMapColumnAllocation,
        '\x3d': self.OnSoundParticleEffect,
        '\x46': self.OnChangeGameState,
        '\x36': self.OnBlockAction,
        '\x67': self.OnSetSlot,
        '\x68': self.OnSetWindowItems,
        '\xca': self.OnPlayerAbility,
        '\xc9': self.OnPlayerListItem,
        '\xff': self.OnKick,
        }

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
    ilk = self._buf[0]
    self._buf = self._buf[1:]
    #print hex(ord(ilk)), len(self._buf)
    #print '\nReceived packet: %s (buf: %d)' % (hex(ord(ilk)), len(self._buf))
    #for x in self._buf:
      #print hex(ord(x)), ' ',
    #print
    try:
      return ilk, self._handlers[ilk]()
    except KeyError:
      sys.stderr.write('unknown packet: %s\n' % hex(ord(ilk)))
      for i in self._buf[:30]:
        sys.stderr.write('%s  ' % hex(ord(i)))
      raise

  def WaitFor(self, ilk):
    gotten_ilk = None
    while gotten_ilk != ilk:
      gotten_ilk, value = self.RecvPacket()
    print u'Got: %s' % hex(ord(gotten_ilk))
    return value

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
  # Handlers

  def OnKick(self):
    sys.stderr.write('Kicked: ' + self.UnpackString() + '\n')
    raise Exception()

  def OnHandshake(self):
    return self.UnpackString()

  def OnChatMessage(self):
    chat = self.UnpackString()
    print "Chat:", chat
    return chat

  def OnKeepAlive(self):
    token = self.UnpackInt32()
    self.SendKeepAlive(token)
    return token

  def OnLogin(self):
    entityId = self.UnpackInt32()
    trash = self.UnpackString()
    levelType = self.UnpackString()
    serverMode = self.UnpackInt32()
    dimension = self.UnpackInt32()
    difficulty = self.UnpackInt8()
    trash = self.UnpackUint8()
    maxPlayers = self.UnpackUint8()
    return (entityId, levelType, serverMode, dimension, difficulty, maxPlayers)

  def OnSpawn(self):
    return (self.UnpackInt32(), self.UnpackInt32(), self.UnpackInt32())

  def OnPlayerPositionLook(self):
    return (
        self.UnpackDouble(),
        self.UnpackDouble(),
        self.UnpackDouble(),
        self.UnpackDouble(),
        self.UnpackFloat(),
        self.UnpackFloat(),
        self.UnpackInt8(),
        )

  def OnSpawnNamedEntity(self):
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

  def OnSpawnDroppedItem(self):
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

  def OnSpawnObjectVehicle(self):
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

  def OnSpawnMob(self):
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

  def OnSpawnExperienceOrb(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt16(),
        )

  def OnEntityVelocity(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt16(),
        self.UnpackInt16(),
        self.UnpackInt16(),
        )

  def OnDestroyEntity(self):
    return (
        self.UnpackInt32(),
        )

  def OnEntityRelativeMove(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def OnEntityLook(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def OnEntityRelativeLookAndMove(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def OnEntityTeleport(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def OnEntityHeadLook(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        )

  def OnEntityStatus(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        )

  def OnEntityMetadata(self):
    return (
        self.UnpackInt32(),
        self.UnpackMetadata(),
        )

  def OnRemoveEntityEffect(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt8(),
        )

  def OnPlayerAbility(self):
    return (
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        self.UnpackInt8())

  def OnPlayerListItem(self):
    return (
        self.UnpackString(),
        self.UnpackInt8(),
        self.UnpackInt16(),
        )

  def OnTimeUpdate(self):
    return (
        self.UnpackInt64(),)

  def OnMapColumnAllocation(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        )

  def OnSoundParticleEffect(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt32(),
        self.UnpackInt32(),
        )

  def OnChangeGameState(self):
    return (
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def OnBlockAction(self):
    return (
        self.UnpackInt32(),
        self.UnpackInt16(),
        self.UnpackInt32(),
        self.UnpackInt8(),
        self.UnpackInt8(),
        )

  def OnSetSlot(self):
    return (
        self.UnpackInt8(),
        self.UnpackInt16(),
        self.UnpackSlot(),
        )

  def OnSetWindowItems(self):
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


def main():
  HOST = '108.59.83.223'    # The remote host
  PORT = 31337              # The same port as used by the server
  PORT = 25565
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.connect((HOST, PORT))
  #s.sendall('Hello, world')
  #data = s.recv(1024)
  #s.close()
  #print 'Received', repr(data)
  #pass

  username = u'johnbaruch'
  password = u'zoe77zoe'
  prot = MineCraftProtocol(s)

  sessionId = prot.GetSessionId(username, password)
  print 'SessionId:', sessionId

  prot.SendHandshake(username, HOST, PORT)
  serverId = prot.WaitFor('\x02')
  print 'Serverid:', serverId

  prot.JoinServer(username, sessionId, serverId)

  prot.SendLogin(u'johnbaruch')
  print prot.WaitFor('\x01')

  print prot.WaitFor('\x06')

  print prot.WaitFor('\x0d')

  while True:
    prot.RecvPacket()
    #print prot.RecvPacket()[1]


if __name__ == '__main__':
  main()
