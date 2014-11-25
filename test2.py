import peon
import logging
import time
import ConfigParser


logging.basicConfig(level=logging.INFO)
log = logging.getLogger()
log.setLevel(logging.INFO)

config = ConfigParser.RawConfigParser(allow_no_value=True)
config.read('settings.cfg')
server = config.get('credentials', 'server')
username = config.get('credentials', 'username')
password = config.get('credentials', 'password')

client = peon.Client()
client.connect(server, username, password)
bot = client.bot

time.sleep(3)

HOME = (94, 60, 96)
CHEST_HOME = (94, 60, 97)
RANGE = 75

bot.set_auto_settings(
    'hunt',
    home=HOME,
    mob_types=['Skeleton'],
    _range=RANGE
)

bot.set_auto_settings(
    'gather',
    ['Wither Skeleton Skull'],
    _range=RANGE
)

bot.set_auto_settings(
    'store',
    ['Diamond Sword', 'Cooked Chicken'],
    chest_position=CHEST_HOME,
    invert=True
)

bot.enable_auto_action('store')
bot.enable_auto_action('gather')
bot.enable_auto_action('hunt')
