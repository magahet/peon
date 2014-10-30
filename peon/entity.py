import collections.namedtuple


class Entity(object):

  def __init__(self, eid, _type, x, y, z, yaw, pitch, head_pitch, velocity_x,
               velocity_y, velocity_z, metadata):
    self._eid = eid
    self._type= _type
    self._pos = Position(x/32, y/32, (y/32)+1, z/32, yaw, pitch, 1)
    self._head_pitch = head_pitch
    self._velocity = Velocity(velocity_x, velocity_y, velocity_z)
    self._metadata = metadata

  def move(self, dx, dy, dz):
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


class Position(collections.namedtuple('Position',
    ('x', 'y', 'z', 'yaw', 'pitch', 'on_ground'))):

  def xzy(self):
      return Xzy(self.x, self.z, self.y)
