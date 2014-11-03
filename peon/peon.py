import logging
import socket
import fastmc.proto
import fastmc.auth
import fastmc.util
import threading
import Queue
import os
import time
import math
from world import World
from player import Player
from entity import Entity
from window import Window
from chunk import ChunkColumn


log = logging.getLogger(__name__)


class Client(object):
    def __init__(self, protocol_version=47):
        self.world = World()
        self.player = None
        self.protocol_version = protocol_version
        self.proto = fastmc.proto.protocol(protocol_version)
        self._sock = None
        self._mc_sock = None
        self._sock_generation = 0
        self.writer = None
        self.reader = None
        self.in_buf = fastmc.proto.ReadBuffer()
        self._recv_condition = threading.Condition()
        self._send_queue = Queue.Queue(10)
        self.parent_pid = os.getppid()
        self.last_keepalive = time.time()
        self._threads = {}
        self._thread_funcs = {
            'reader': self._do_read_thread,
            'writer': self._do_send_thread,
            'position_update': self._do_send_position,
        }
        self._post_send_hooks = {
            (fastmc.proto.HANDSHAKE, self.proto.HandshakeServerboundHandshake.id): self.set_to_login_state,
            (fastmc.proto.LOGIN, self.proto.LoginServerboundEncryptionResponse.id): self.set_sock_cipher,
        }
        self.interesting = []
        self._handlers = {
            (fastmc.proto.LOGIN, self.proto.LoginClientboundEncryptionRequest.id): self.on_login_encryption_request,
            (fastmc.proto.LOGIN, self.proto.LoginClientboundLoginSuccess.id): self.on_login_login_success,
            (fastmc.proto.LOGIN, self.proto.LoginClientboundSetCompression.id): self.on_login_set_compression,
            (fastmc.proto.PLAY, self.proto.PlayClientboundKeepAlive.id): self.on_play_keepalive,
            (fastmc.proto.PLAY, self.proto.PlayClientboundSetCompression.id): self.on_play_set_compression,
            (fastmc.proto.PLAY, self.proto.PlayClientboundChatMesage.id): self.on_play_chat_message,
            (fastmc.proto.PLAY, self.proto.PlayClientboundHealthUpdate.id): self.on_play_health_update,
            (fastmc.proto.PLAY, self.proto.PlayClientboundSpawnMob.id): self.on_play_spawn_mob,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityVelocity.id): self.on_play_entity_velocity,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityRelativeMove.id): self.on_play_entity_relative_move,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityLook.id): self.on_play_entity_look,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityLookAndRelativeMove.id): self.on_play_entity_look_and_relative_move,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityTeleport.id): self.on_play_entity_teleport,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityMetadata.id): self.on_play_entity_metadata,
            (fastmc.proto.PLAY, self.proto.PlayClientboundDestroyEntities.id): self.on_play_destroy_entities,
            (fastmc.proto.PLAY, self.proto.PlayClientboundSetExperience.id): self.on_play_set_experience,
            (fastmc.proto.PLAY, self.proto.PlayClientboundChunkData.id): self.on_play_chunk_data,
            (fastmc.proto.PLAY, self.proto.PlayClientboundMapChunkBulk.id): self.on_play_map_chunk_bulk,
            (fastmc.proto.PLAY, self.proto.PlayClientboundPlayerPositionAndLook.id): self.on_play_player_position_and_look,
            (fastmc.proto.PLAY, self.proto.PlayClientboundOpenWindow.id): self.on_play_open_window,
            (fastmc.proto.PLAY, self.proto.PlayClientboundCloseWindow.id): self.on_play_close_window,
            (fastmc.proto.PLAY, self.proto.PlayClientboundSetSlot.id): self.on_set_slot,
            (fastmc.proto.PLAY, self.proto.PlayClientboundWindowItem.id): self.on_window_item,
        }

    def set_to_login_state(self):
        self.reader.switch_state(fastmc.proto.LOGIN)
        self.writer.switch_state(fastmc.proto.LOGIN)

    def set_sock_cipher(self):
        self._mc_sock.set_cipher(
            fastmc.auth.generated_cipher(self._shared_secret),
            fastmc.auth.generated_cipher(self._shared_secret),
        )

    def connect(self, host, username, password, port=25565, auth=True):
        if auth:
            self._session = fastmc.auth.Session.from_credentials(
                username, password)
            self.username = self._session.player_ign
        else:
            self._session = None
            self.username = username
        #self._sock = gevent.socket.create_connection((host, port))
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((host, port))
        self._mc_sock = fastmc.proto.MinecraftSocket(self._sock)
        self.reader, self.writer = fastmc.proto.Endpoint.client_pair(
            self.protocol_version)
        self.start_threads()
        self.send_login_request(host, port)
        log.info('logging in')
        while self.reader.state != fastmc.proto.PLAY:
            time.sleep(.1)

    def send_login_request(self, host, port=25565):
        self.send(self.proto.HandshakeServerboundHandshake.id,
                  version=self.writer.protocol.version,
                  addr=host,
                  port=port,
                  state=fastmc.proto.LOGIN,
                  )
        while self.writer.state != fastmc.proto.LOGIN:
            time.sleep(.5)
        self.send(self.proto.LoginServerboundLoginStart.id,
                  name=self.username
                  )

    def start_threads(self):
        for name, func in self._thread_funcs.iteritems():
            thread = threading.Thread(target=func, name=name)
            thread.daemon = True
            thread.start()
            self._threads[name] = thread

    ##############################################################################
    # Thread functions

    def _do_read_thread(self):
        try:
            my_generation = self._sock_generation
            while my_generation == self._sock_generation:
                self.recv_packet()
        finally:
            os.kill(self.parent_pid, 0)

    def _do_send_thread(self):
        try:
            my_generation = self._sock_generation
            sock = self._mc_sock
            queue = self._send_queue
            writer = self.writer
            while my_generation == self._sock_generation and self._mc_sock is not None:
                packet_id, kwargs = queue.get()
                out_buf = fastmc.proto.WriteBuffer()
                writer.write(out_buf, packet_id, **kwargs)
                sock.send(out_buf)
                hook = self._post_send_hooks.get((self.writer.state, packet_id))
                if hook:
                    hook()
        finally:
            os.kill(self.parent_pid, 0)

    def _do_send_position(self):

        def calc_yaw(x0, z0, x, z):
            l = x - x0
            w = z - z0
            c = math.sqrt(l * l + w * w)
            alpha1 = -math.asin(l / c) / math.pi * 180
            alpha2 = math.acos(w / c) / math.pi * 180
            if alpha2 > 90:
                return 180 - alpha1
            else:
                return alpha1

        try:
            while self.player is None:
                time.sleep(0.01)
            my_generation = self._sock_generation
            while my_generation == self._sock_generation and self._mc_sock is not None:
                first_position = self.player.position
                time.sleep(0.01)
                if first_position == self.player.position:
                    self.send(self.proto.PlayServerboundPlayerPosition.id,
                              x=self.player.x,
                              y=self.player.y,
                              z=self.player.z,
                              on_ground=self.player.on_ground)
                else:
                    yaw = calc_yaw(first_position[0], first_position[1],
                                   self.player.x, self.player.z)
                    self.send(self.proto.PlayServerboundPlayerPositionAndLook.id,
                              x=self.player.x,
                              y=self.player.y,
                              z=self.player.z,
                              yaw=yaw,
                              pitch=0,
                              on_ground=self.player.on_ground)
        finally:
            os.kill(self.parent_pid, 0)

    ##############################################################################

    def recv_packet(self):
        if self._mc_sock is None:
            log.debug('no mc sock')
            return
        sock = self._mc_sock
        reader = self.reader
        in_buf = self.in_buf
        data = sock.recv()
        if not data:
            return
        in_buf.append(data)
        while True:
            pkt, pkt_raw = reader.read(in_buf)
            if pkt is None:
                break
            log.debug('handler: (%s, %s)', reader.state, pkt.id)
            handler = self._handlers.get((reader.state, pkt.id))
            if handler:
                handler(pkt)
            else:
                self.on_unhandled(pkt)
            with self._recv_condition:
                self._recv_condition.notifyAll()

    def wait_for(self, what, timeout=10):
        start = time.time()
        with self._recv_condition:
            while not what() and time.time() - start < timeout:
                self._recv_condition.wait(timeout=1)
        return what()

    def send(self, packet_id, **kwargs):
        self._send_queue.put((packet_id, kwargs))

    def on_login_encryption_request(self, pkt):
        if pkt.public_key != '':
            rsa_key = fastmc.auth.decode_public_key(pkt.public_key)
            shared_secret = fastmc.auth.generate_shared_secret()
            self._shared_secret = shared_secret

            response_token = fastmc.auth.encrypt_with_public_key(
                pkt.challenge_token,
                rsa_key
            )
            encrypted_shared_secret = fastmc.auth.encrypt_with_public_key(
                shared_secret,
                rsa_key
            )

            server_hash = fastmc.auth.make_server_hash(
                pkt.server_id,
                shared_secret,
                rsa_key,
            )

            fastmc.auth.join_server(self._session, server_hash)

            self.send(self.proto.LoginServerboundEncryptionResponse.id,
                      shared_secret=encrypted_shared_secret,
                      response_token=response_token,
                      )

        else:
            self.send(self.proto.LoginServerboundEncryptionResponse.id,
                      shared_secret='',
                      response_token=pkt.challenge_token,
                      )

    def on_login_login_success(self, pkt):
        self.reader.switch_state(fastmc.proto.PLAY)
        self.writer.switch_state(fastmc.proto.PLAY)

    def on_login_set_compression(self, pkt):
        log.debug('setting compression threshold: %d', pkt.threshold)
        self.reader.set_compression_threshold(pkt.threshold)
        self.writer.set_compression_threshold(pkt.threshold)

    def on_play_keepalive(self, pkt):
        self.send(self.proto.PlayServerboundKeepAlive.id,
                  keepalive_id=pkt.keepalive_id
                  )
        self.last_keepalive = time.time()

    def on_play_set_compression(self, pkt):
        log.debug('setting reader compression threshold: %d', pkt.threshold)
        self.reader.set_compression_threshold(pkt.threshold)

    def on_play_chat_message(self, pkt):
        def parse_chat_json(json):
            if json.get('translate') == 'chat.type.text':
                message_list = []
                sender = ''
                for section in json.get('with', []):
                    if isinstance(section, basestring):
                        message_list.append(section)
                    elif isinstance(section, dict):
                        sender = section.get('text')
                return '<{}> {}'.format(sender, ' '.join(message_list))
            elif json.get('translate') in ['multiplayer.player.joined', 'multiplayer.player.left']:
                event = json.get('translate', '').replace('multiplayer.player.', 'player ')
                player = json.get('with', [{}])[0].get('text', 'UNKNOWN')
                return '{}: {}'.format(event, player)

        #log.info('chat: %s', str(pkt.chat))
        clean_message = parse_chat_json(pkt.chat)
        if clean_message:
            log.info('chat: %s', clean_message)

    def on_play_health_update(self, pkt):
        if self.player is not None:
            self.player._health = pkt.health
            self.player._food = pkt.food
            self.player._food_saturation = pkt.food_saturation

    def on_play_spawn_mob(self, pkt):
        self.world.entities[pkt.eid] = Entity(
            pkt.eid,
            pkt.type,
            pkt.x,
            pkt.y,
            pkt.z,
            pkt.pitch,
            pkt.head_pitch,
            pkt.yaw,
            pkt.velocity_x,
            pkt.velocity_y,
            pkt.velocity_z,
            pkt.metadata)

    def on_play_entity_velocity(self, pkt):
        if pkt.eid not in self.world.entities:
            return
        self.world.entities[pkt.eid].velocity_x = pkt.velocity_x
        self.world.entities[pkt.eid].velocity_y = pkt.velocity_y
        self.world.entities[pkt.eid].velocity_z = pkt.velocity_z

    def on_play_entity_relative_move(self, pkt):
        if pkt.eid not in self.world.entities:
            return
        self.world.entities[pkt.eid].move(pkt.dx, pkt.dy, pkt.dz)

    def on_play_entity_look(self, pkt):
        if pkt.eid not in self.world.entities:
            return
        self.world.entities[pkt.eid].look(pkt.yaw, pkt.pitch)

    def on_play_entity_look_and_relative_move(self, pkt):
        if pkt.eid not in self.world.entities:
            return
        self.world.entities[pkt.eid].move(pkt.dx, pkt.dy, pkt.dz)
        self.world.entities[pkt.eid].look(pkt.yaw, pkt.pitch)

    def on_play_entity_teleport(self, pkt):
        if pkt.eid not in self.world.entities:
            return
        self.world.entities[pkt.eid].teleport(pkt.x, pkt.y, pkt.z, pkt.yaw,
                                              pkt.pitch)

    def on_play_entity_metadata(self, pkt):
        if pkt.eid not in self.world.entities:
            return
        self.world.entities[pkt.eid].metadata.update(pkt.metadata)

    def on_play_destroy_entities(self, pkt):
        for eid in pkt.eids:
            if eid in self.world.entities:
                del self.world.entities[eid]

    def on_play_set_experience(self, pkt):
        if self.player is not None:
            self.player._xp_bar = pkt.bar
            self.player._xp_level = pkt.level
            self.player._xp_total = pkt.total_exp

    def on_play_chunk_data(self, pkt):
        self.world.chunks[(pkt.chunk_x, pkt.chunk_z)] = ChunkColumn(
            pkt.chunk_x,
            pkt.chunk_z,
            pkt.continuous,
            pkt.primary_bitmap,
            pkt.data
        )

    def on_play_map_chunk_bulk(self, pkt):
        print pkt
        print

    def on_play_player_position_and_look(self, pkt):
        if self.player is None:
            self.player = Player(pkt.x, pkt.y, pkt.z, pkt.yaw, pkt.pitch, self.world)
        else:
            self.player.teleport(pkt.x, pkt.y, pkt.z, pkt.yaw, pkt.pitch)

    def on_play_open_window(self, pkt):
        self.player._open_window_id = pkt.window_id
        if pkt.window_id not in self.player.windows:
            time.sleep(1)
        if pkt.window_id in self.player.windows:
            self.player.windows[pkt.window_id].inventory_type = pkt.type
            self.player.windows[pkt.window_id].window_title = pkt.title

    def on_play_close_window(self, pkt):
        self.player._open_window_id = 0

    def on_set_slot(self, pkt):
        if pkt.window_id == -1 and pkt.slot == -1:
            self._cursor_slot = pkt.slot
        elif pkt.window_id in self.player.windows:
            self.player.windows[pkt.window_id].set_slot(pkt.slot, pkt.item)

    def on_window_item(self, pkt):
        self.player.windows[pkt.window_id] = Window(pkt.window_id, pkt.slots)

    def on_unhandled(self, pkt):
        if pkt.id in self.interesting:
            print pkt
            print
