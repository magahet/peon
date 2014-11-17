import peon
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()
log.setLevel(logging.INFO)

bot = peon.Client()
bot.connect('localhost', 'peon', '', auth=False)

bot.player.enable_auto_action('eat')
bot.player.enable_auto_action('defend')
#bot.player.enable_auto_action('hunt')
