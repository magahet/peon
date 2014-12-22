#!/usr/bin/env python

import peon
import argparse
import logging
import sys
import time
import utils
import ConfigParser
import yaml


def start_auto_bot(host, username, password, actions, port=25565, auth=True,
                   chat=False):
    client = peon.Client()
    client.connect(host, username, password, port, auth)
    bot = client.bot
    time.sleep(1)
    print bot
    for settings in actions:
        name = settings.pop('name', '')
        args = settings.pop('args', ())
        disabled = settings.pop('disabled', False)
        bot.set_auto_settings(name, *args, **settings)
        if not disabled:
            bot.start(name)
    if chat:
        utils.start_chat_interface(bot)
    return client, bot


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
    parser = argparse.ArgumentParser(
        description='Minecraft bot with many automated actions.')
    parser.add_argument('--actions-config', '-a', dest='actions_config',
                        help='yaml file specifying actions and settings')
    parser.add_argument('--server-settings', '-s', default='settings.cfg',
                        dest='settings_path', help='sever settings file path')
    parser.add_argument('--world', '-w', default='main',
                        help=('the world to login to. '
                              'must exist as a section in server settings.'))
    parser.add_argument('--chat', '-c', default=False, action='store_true',
                        help='enable chat')
    args = parser.parse_args()
    config = ConfigParser.RawConfigParser(
        {
            'port': 25565,
            'auth_enabled': 'true',
            'username': '',
            'password': '',
        },
        allow_no_value=True)
    config.read(args.settings_path)
    auth_enabled = config.getboolean(args.world, 'auth_enabled')
    server = config.get(args.world, 'server')
    port = config.getint(args.world, 'port')
    username = config.get(args.world, 'username')
    password = config.get(args.world, 'password')
    logger.info('logging into [%s:%d] as [%s]', server, port, username)
    if args.actions_config:
        with open(args.actions_config) as _file:
            actions = yaml.load(_file)
    else:
        actions = []
    logger.info('actions: %s', str(actions))
    client, bot = start_auto_bot(server, username, password, actions, port,
                                 auth_enabled, chat=args.chat)
