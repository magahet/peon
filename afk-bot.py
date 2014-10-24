#!/usr/bin/env python

import peon
import utils
import argparse


def start_afk_bot(host, username, password, port=25565, auth=True):
    bot = peon.Client()
    bot.connect(host, username, password, port, auth)
    utils.start_afk_thread(bot)
    utils.start_chat_interface(bot)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AFK bot with chat for minecraft.')
    parser.add_argument('host', help='host server')
    parser.add_argument('username', help='username')
    parser.add_argument('password', help='password')
    parser.add_argument('--no-auth', '-a', dest='auth', default=True,
                        action='store_false', help='disable authentication')
    parser.add_argument('--port', '-p', default=25565, type=int,
                        help='server port')
    args = parser.parse_args()
    start_afk_bot(args.host, args.username, args.password, args.port, args.auth)
