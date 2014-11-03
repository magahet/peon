class ChunkColumn(object):
    def __init__(self, chunk_x, chunk_z, continuous, primary_bitmap, data):
        self.chunk_x = chunk_x
        self.chunk_z = chunk_z
        self.continuous = continuous
        self.primary_bitmap = primary_bitmap
        self.data = data

'''
  def _GetOffset(self, x, z, y):
    x, z, y = int(x), int(z), int(y)
    return (       (x - self.chunkX * 16) +
            (16 *  (z - self.chunkZ * 16)) +
            (256 * (y))
           )

  def SetBlock(self, x, z, y, newType, newMeta):
    # TODO: what about extra 4 bits?
    offset = self._GetOffset(x, z, y)
    self._blocks[offset] = (newType & 0xff)
    return newType

  def GetBlock(self, x, z, y):
    offset = self._GetOffset(x, z, y)
    if offset < len(self._blocks):
      blocktype = self._blocks[offset]
      return blocktype


    def parse(self, chunk_x, chunk_z, continuous, primary_bitmap, data):

        def PopByteArray(size):
            if len(data[0]) < size:
                raise Exception('data not big enough!')
            ret = array.array('B', data[0][:size])
            data[0] = data[0][size:]
            return  ret

        self.blocks = array.array('B')
        for i in range(16):
            if primary_bitmap & (1 << i):
                self.blocks.extend(PopByteArray(4096))
            else:
                blocks.extend([0] * 4096)

        meta = []
        for i in range(16):
        if primary_bitmap & (1 << i):
            meta.append(PopByteArray(2048))
        else:
            meta.append(array.array('B', [0] * 2048))

        light = []
        for i in range(16):
        if primary_bitmap & (1 << i):
            light.append(PopByteArray(2048))
        else:
            light.append(array.array('B', [0] * 2048))

        skylight = []
        for i in range(16):
        if primary_bitmap & (1 << i):
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
'''
