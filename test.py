import peon
import time


def test_moving(bot):
    pos = bot.player.get_position(floor=True)
    print pos
    test_positions = [p for p in bot.world.iter_moveable_adjacent(*pos)]
    for p in test_positions:
        print p
        bot.player.move_to(*p, center=True)
        time.sleep(0.5)
        bot.player.move_to(*pos, center=True)
        time.sleep(0.5)


bot = peon.Client()
bot.connect('localhost', 'peon', '', auth=False)
