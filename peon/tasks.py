import types
import time


def hunt(player, home=None, mob_types=None):
    if player._health <= 10:
        print 'health low:', player._health
        return False
    home = player.get_position(floor=True) if home is None else home
    player.enable_auto_defend()
    if mob_types:
        for _type in mob_types:
            if isinstance(_type, basestring):
                _type = types.MobTypes().get_id(_type)
            player.auto_defend_mob_types.add(_type)
    for entity in player.iter_entities_in_range(mob_types, reach=30):
        print entity
        eid = entity.eid
        while eid in player.world.entities and player._health > 10:
            x, y, z = entity.position
            if not player.navigate_to(x, y, z, space=3, limit=60):
                print "can't nav to entity"
                break
            time.sleep(0.1)
        else:
            return player.navigate_to(*home)
    return player.navigate_to(*home)
