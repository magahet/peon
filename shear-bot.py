#!/usr/bin/env python

import peon
import argparse
import logging
import sys
import time
import utils


def start_shear_bot(host, username, password, port=25565, auth=True):
    bot = peon.Client()
    #bot.interesting.extend([
        ##bot.proto.PlayClientboundSpawnMob.id,
        ##bot.proto.PlayClientboundEntityMetadata.id,
        ##bot.proto.PlayClientboundPlayerPositionAndLook.id,
        ##bot.proto.PlayClientboundChunkData.id
    #])
    bot.connect(host, username, password, port, auth)
    utils.start_shear_thread(bot)
    utils.start_chat_interface(bot)


if __name__ == '__main__':
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%H:%M')
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description='Shearing bot with chat for minecraft.')
    parser.add_argument('host', help='host server')
    parser.add_argument('username', help='username')
    parser.add_argument('password', help='password')
    parser.add_argument('--no-auth', '-a', dest='auth', default=True,
                        action='store_false', help='disable authentication')
    parser.add_argument('--port', '-p', default=25565, type=int,
                        help='server port')
    args = parser.parse_args()
    start_shear_bot(args.host, args.username, args.password, args.port, args.auth)
