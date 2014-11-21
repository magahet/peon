import peon
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()
log.setLevel(logging.INFO)

client = peon.Client()
client.connect('localhost', 'peon', '', auth=False)
bot = client.bot

#bot.enable_auto_action('eat')
#bot.enable_auto_action('defend')
#bot.enable_auto_action('gather')
#bot.auto_gather_items.add('Wither Skeleton Skull')
#bot.auto_gather_items.add('Bone')
#bot.auto_hunt_settings = {'home': (-39, 64, -36), 'mob_types': ['Skeleton']}
#bot.enable_auto_action('hunt')
