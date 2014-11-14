import types
import time


def hunt(player, home=None, mob_types=None, space=3, speed=10):
    if player._health <= 10:
        print 'health low:', player._health
        return False
    home = player.get_position(floor=True) if home is None else home
    player.enable_auto_defend()
    original_set = player.auto_defend_mob_types.copy()
    if mob_types:
        for _type in mob_types:
            if isinstance(_type, basestring):
                _type = types.MobTypes().get_id(_type)
            player.auto_defend_mob_types.add(_type)
    else:
        mob_types = types.HOSTILE_MOBS
    for entity in player.iter_entities_in_range(mob_types, reach=30):
        print entity
        eid = entity.eid
        count = 0
        while eid in player.world.entities and player._health > 10 and count < 100:
            count += 1
            x, y, z = entity.position
            if not player.navigate_to(
                    x, y, z, space=space, speed=speed, limit=60):
                print "can't nav to entity"
                break
            time.sleep(0.1)
        else:
            player.auto_defend_mob_types = original_set
            return player.navigate_to(*home)
    player.auto_defend_mob_types = original_set
    return player.navigate_to(*home)
