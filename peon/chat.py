class Message(object):
    """A message from the server."""
    def __init__(self, json):
        self.message_type = None
        self.message = None
        self.sender = None
        self.player = None
        self.event = None
        self.parse_json(json)

    def parse_json(self, json):
        if json.get('translate') == 'chat.type.text':
            self.message_type = 'message'
            message_list = []
            for section in json.get('with', []):
                if isinstance(section, basestring):
                    message_list.append(section)
                elif isinstance(section, dict):
                    self.sender = section.get('text')
                self.message = ' '.join(message_list)
        elif json.get('translate') in ['multiplayer.player.joined', 'multiplayer.player.left']:
            self.message_type = 'event'
            self.event = json.get(
                'translate', '').replace('multiplayer.player.', 'player ')
            self.player = json.get('with', [{}])[0].get('text', 'UNKNOWN')

    def __repr__(self):
        if self.message_type == 'message':
            return '<{}> {}'.format(self.sender, self.message)
        elif self.message_type == 'event':
            return '{}: {}'.format(self.event, self.player)
        else:
            return ''
