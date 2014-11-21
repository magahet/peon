import logging
import socket
import fastmc.proto
import fastmc.auth
import fastmc.util
import threading
import Queue
import os
import time
from world import World
from robot import Robot
from entity import (Entity, Object, PlayerEntity)
from window import Window
from utils import ThreadSafeCounter


log = logging.getLogger(__name__)


class Client(object):
    def __init__(self, protocol_version=47):
        self.protocol_version = protocol_version
        self.proto = fastmc.proto.protocol(protocol_version)
        self._send_queue = Queue.Queue(10)
        self._recv_condition = threading.Condition()
        self.world = World()
        self.bot = Robot(self.proto,
                         self._send_queue,
                         self._recv_condition,
                         self.world)
        self._sock = None
        self._mc_sock = None
        self._sock_generation = 0
        self.writer = None
        self.reader = None
        self.in_buf = fastmc.proto.ReadBuffer()
        self.parent_pid = os.getppid()
        self.last_keepalive = time.time()
        self._action_num_counter = ThreadSafeCounter(1)
        self._threads = {}
        self._thread_funcs = {
            'reader': self._do_read_thread,
            'writer': self._do_send_thread,
            'position_update': self._do_send_position,
        }
        self._active_threads = set(self._thread_funcs.keys())
        self._post_send_hooks = {
            (fastmc.proto.HANDSHAKE, self.proto.HandshakeServerboundHandshake.id): self.set_to_login_state,
            (fastmc.proto.LOGIN, self.proto.LoginServerboundEncryptionResponse.id): self.set_sock_cipher,
            (fastmc.proto.PLAY, self.proto.PlayServerboundHeldItemChange.id): self.set_held_item,
        }
        self.interesting = [
            #self.proto.PlayClientboundChunkData.id
            #self.proto.PlayClientboundSpawnObject.id,
            #self.proto.PlayClientboundEntityMetadata.id,
            #self.proto.PlayClientboundEntityEquipment.id,
            #self.proto.PlayClientboundPlayerPositionAndLook.id,
            #self.proto.PlayClientboundChatMesage.id,
            #self.proto.PlayClientboundPlayerListItem.id,
            self.proto.PlayClientboundOpenWindow.id,
            self.proto.PlayClientboundCloseWindow.id,
            #self.proto.PlayClientboundWindowItem.id,
            #self.proto.PlayClientboundSetSlot.id,
        ]
        self._handlers = {
            (fastmc.proto.LOGIN, self.proto.LoginClientboundEncryptionRequest.id): self.on_login_encryption_request,
            (fastmc.proto.LOGIN, self.proto.LoginClientboundLoginSuccess.id): self.on_login_login_success,
            (fastmc.proto.LOGIN, self.proto.LoginClientboundSetCompression.id): self.on_login_set_compression,
            (fastmc.proto.PLAY, self.proto.PlayClientboundKeepAlive.id): self.on_keepalive,
            (fastmc.proto.PLAY, self.proto.PlayClientboundSetCompression.id): self.on_set_compression,
            (fastmc.proto.PLAY, self.proto.PlayClientboundChatMesage.id): self.on_chat_message,
            (fastmc.proto.PLAY, self.proto.PlayClientboundHealthUpdate.id): self.on_health_update,
            (fastmc.proto.PLAY, self.proto.PlayClientboundSpawnObject.id): self.on_spawn_object,
            (fastmc.proto.PLAY, self.proto.PlayClientboundSpawnMob.id): self.on_spawn_mob,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityVelocity.id): self.on_entity_velocity,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityRelativeMove.id): self.on_entity_relative_move,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityLook.id): self.on_entity_look,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityLookAndRelativeMove.id): self.on_entity_look_and_relative_move,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityTeleport.id): self.on_entity_teleport,
            (fastmc.proto.PLAY, self.proto.PlayClientboundEntityMetadata.id): self.on_entity_metadata,
            (fastmc.proto.PLAY, self.proto.PlayClientboundDestroyEntities.id): self.on_destroy_entities,
            (fastmc.proto.PLAY, self.proto.PlayClientboundSetExperience.id): self.on_set_experience,
            (fastmc.proto.PLAY, self.proto.PlayClientboundChunkData.id): self.on_chunk_data,
            (fastmc.proto.PLAY, self.proto.PlayClientboundMultiBlockChange.id): self.on_multi_block_change,
            (fastmc.proto.PLAY, self.proto.PlayClientboundBlockChange.id): self.on_block_change,
            (fastmc.proto.PLAY, self.proto.PlayClientboundMapChunkBulk.id): self.on_map_chunk_bulk,
            (fastmc.proto.PLAY, self.proto.PlayClientboundPlayerPositionAndLook.id): self.on_player_position_and_look,
            (fastmc.proto.PLAY, self.proto.PlayClientboundSpawnPlayer.id): self.on_spawn_player,
            (fastmc.proto.PLAY, self.proto.PlayClientboundHeldItemChange.id): self.on_held_item_change,
            (fastmc.proto.PLAY, self.proto.PlayClientboundOpenWindow.id): self.on_open_window,
            (fastmc.proto.PLAY, self.proto.PlayClientboundCloseWindow.id): self.on_close_window,
            (fastmc.proto.PLAY, self.proto.PlayClientboundSetSlot.id): self.on_set_slot,
            (fastmc.proto.PLAY, self.proto.PlayClientboundWindowItem.id): self.on_window_item,
            (fastmc.proto.PLAY, self.proto.PlayClientboundConfirmTransaction.id): self.on_confirm_transaction,
            (fastmc.proto.PLAY, self.proto.PlayClientboundPlayerListItem.id): self.on_player_list_item,
        }

    def set_to_login_state(self, **kwargs):
        self.reader.switch_state(fastmc.proto.LOGIN)
        self.writer.switch_state(fastmc.proto.LOGIN)

    def set_sock_cipher(self, **kwargs):
        self._mc_sock.set_cipher(
            fastmc.auth.generated_cipher(self._shared_secret),
            fastmc.auth.generated_cipher(self._shared_secret),
        )

    def set_held_item(self, slot):
        self.bot._held_slot_num = slot

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
        self.send(self.proto.PlayServerboundHeldItemChange.id, slot=0)

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

    def respawn(self):
        self.send(self.proto.PlayServerboundClientStatus.id, action_id=0)

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
                    hook(**kwargs)
        finally:
            os.kill(self.parent_pid, 0)

    def _do_send_position(self):
        try:
            while self.bot.x is None:
                time.sleep(0.01)
            my_generation = self._sock_generation
            while my_generation == self._sock_generation and self._mc_sock is not None:
                self.send(self.proto.PlayServerboundPlayerPositionAndLook.id,
                          x=self.bot.x,
                          y=self.bot.y,
                          z=self.bot.z,
                          yaw=self.bot.yaw,
                          pitch=0,
                          on_ground=self.bot.on_ground)
                time.sleep(0.01)
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
            if pkt.id in self.interesting:
                print pkt
                print
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

    def on_keepalive(self, pkt):
        self.send(self.proto.PlayServerboundKeepAlive.id,
                  keepalive_id=pkt.keepalive_id
                  )
        self.last_keepalive = time.time()

    def on_set_compression(self, pkt):
        log.debug('setting reader compression threshold: %d', pkt.threshold)
        self.reader.set_compression_threshold(pkt.threshold)

    def on_chat_message(self, pkt):
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

    def on_health_update(self, pkt):
        self.bot.health = pkt.health
        self.bot.food = pkt.food
        self.bot._food_saturation = pkt.food_saturation

    def on_spawn_object(self, pkt):
        self.world.objects[pkt.eid] = Object(
            pkt.eid,
            pkt.type,
            pkt.x,
            pkt.y,
            pkt.z,
            pkt.pitch,
            pkt.yaw,
            pkt.data)

    def on_spawn_mob(self, pkt):
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

    def on_entity_velocity(self, pkt):
        if pkt.eid in self.world.entities:
            self.world.entities[pkt.eid].velocity_x = pkt.velocity_x
            self.world.entities[pkt.eid].velocity_y = pkt.velocity_y
            self.world.entities[pkt.eid].velocity_z = pkt.velocity_z

    def on_entity_relative_move(self, pkt):
        if pkt.eid in self.world.entities:
            self.world.entities[pkt.eid].move(pkt.dx, pkt.dy, pkt.dz)
        elif pkt.eid in self.world.objects:
            self.world.objects[pkt.eid].move(pkt.dx, pkt.dy, pkt.dz)
        elif pkt.eid in self.world.players:
            self.world.players[pkt.eid].move(pkt.dx, pkt.dy, pkt.dz)

    def on_entity_look(self, pkt):
        if pkt.eid in self.world.entities:
            self.world.entities[pkt.eid].look(pkt.yaw, pkt.pitch)
        elif pkt.eid in self.world.objects:
            self.world.objects[pkt.eid].look(pkt.yaw, pkt.pitch)
        elif pkt.eid in self.world.players:
            self.world.players[pkt.eid].look(pkt.yaw, pkt.pitch)

    def on_entity_look_and_relative_move(self, pkt):
        if pkt.eid in self.world.entities:
            self.world.entities[pkt.eid].move(pkt.dx, pkt.dy, pkt.dz)
            self.world.entities[pkt.eid].look(pkt.yaw, pkt.pitch)
        elif pkt.eid in self.world.objects:
            self.world.objects[pkt.eid].move(pkt.dx, pkt.dy, pkt.dz)
            self.world.objects[pkt.eid].look(pkt.yaw, pkt.pitch)
        elif pkt.eid in self.world.players:
            self.world.players[pkt.eid].move(pkt.dx, pkt.dy, pkt.dz)
            self.world.players[pkt.eid].look(pkt.yaw, pkt.pitch)

    def on_entity_teleport(self, pkt):
        if pkt.eid in self.world.entities:
            self.world.entities[pkt.eid].teleport(pkt.x, pkt.y, pkt.z, pkt.yaw,
                                                  pkt.pitch)
        elif pkt.eid in self.world.objects:
            self.world.objects[pkt.eid].teleport(pkt.x, pkt.y, pkt.z, pkt.yaw,
                                                 pkt.pitch)
        elif pkt.eid in self.world.players:
            self.world.players[pkt.eid].teleport(pkt.x, pkt.y, pkt.z, pkt.yaw,
                                                 pkt.pitch)

    def on_entity_metadata(self, pkt):
        if pkt.eid in self.world.entities:
            self.world.entities[pkt.eid].metadata.update(pkt.metadata)
        elif pkt.eid in self.world.objects:
            self.world.objects[pkt.eid].metadata.update(pkt.metadata)
        elif pkt.eid in self.world.players:
            self.world.players[pkt.eid].metadata.update(pkt.metadata)

    def on_destroy_entities(self, pkt):
        for eid in pkt.eids:
            if eid in self.world.entities:
                del self.world.entities[eid]
            elif eid in self.world.objects:
                del self.world.objects[eid]
            elif eid in self.world.players:
                del self.world.players[eid]

    def on_set_experience(self, pkt):
        self.bot._xp_bar = pkt.bar
        self.bot._xp_total = pkt.total_exp
        self.bot.xp_level = pkt.level

    def on_chunk_data(self, pkt):
        self.world.unpack_chunk_from_fastmc(
            pkt.chunk_x,
            pkt.chunk_z,
            pkt.continuous,
            pkt.primary_bitmap,
            pkt.data
        )

    def on_multi_block_change(self, pkt):
        for change in pkt.changes:
            self.world.put(
                change.x + pkt.chunk_x * 16,
                change.y,
                change.x + pkt.chunk_x * 16,
                'block_data',
                change.block_id
            )

    def on_block_change(self, pkt):
        self.world.put(
            pkt.location.x,
            pkt.location.y,
            pkt.location.z,
            'block_data',
            pkt.block_id
        )

    def on_map_chunk_bulk(self, pkt):
        self.world.unpack_from_fastmc(pkt.bulk)

    def on_held_item_change(self, pkt):
        self.bot._held_slot_num = pkt.slot

    def on_player_position_and_look(self, pkt):
        self.bot.move_corrected_by_server.set()
        self.bot.teleport(pkt.x, pkt.y, pkt.z, pkt.yaw, pkt.pitch)

    def on_spawn_player(self, pkt):
        self.world.players[pkt.eid] = PlayerEntity(
            pkt.eid,
            pkt.uuid,
            self.world.player_data.get(pkt.uuid, {}).get('name'),
            pkt.x,
            pkt.y,
            pkt.z,
            pkt.yaw,
            pkt.pitch,
            pkt.current_item,
            pkt.metadata,
        )

    def on_open_window(self, pkt):
        self.bot._open_window_id = pkt.window_id
        if pkt.window_id not in self.bot.windows:
            self.bot.windows[pkt.window_id] = Window(pkt.window_id,
                                                     self._action_num_counter,
                                                     self._send_queue,
                                                     self.proto,
                                                     self._recv_condition,
                                                     _type=pkt.type,
                                                     title=pkt.title
                                                     )
        else:
            self.bot.windows[pkt.window_id]._type = pkt.type
            self.bot.windows[pkt.window_id].title = pkt.title

    def on_close_window(self, pkt):
        self.bot._open_window_id = 0
        for _id in self.bot.windows.keys():
            if _id != 0:
                del self.bot.windows[_id]

    def on_set_slot(self, pkt):
        if pkt.window_id == -1 and pkt.slot == -1:
            self._cursor_slot = pkt.slot
        elif pkt.window_id in self.bot.windows:
            self.bot.windows[pkt.window_id].set_slot(pkt.slot, pkt.item)

    def on_window_item(self, pkt):
        if pkt.window_id not in self.bot.windows:
            self.bot.windows[pkt.window_id] = Window(pkt.window_id,
                                                     self._action_num_counter,
                                                     self._send_queue,
                                                     self.proto,
                                                     self._recv_condition,
                                                     slots=pkt.slots,
                                                     )
        else:
            self.bot.windows[pkt.window_id].set_slots(pkt.slots)

    def on_confirm_transaction(self, pkt):
        if pkt.window_id in self.bot.windows:
            window = self.bot.windows[pkt.window_id]
            window._confirmations[pkt.action_num] = pkt.accepted

    def on_player_list_item(self, pkt):
        if pkt.list_actions.action == 0:
            for player_data in pkt.list_actions.players:
                self.world.player_data.update({
                    player_data.uuid: {'name': player_data.name}
                })
                for eid in self.world.players:
                    if self.world.players[eid].uuid == player_data.uuid:
                        self.world.players[eid].name = player_data.name

    def on_unhandled(self, pkt):
        pass
        #if pkt.id in self.interesting:
            #print pkt
            #print
