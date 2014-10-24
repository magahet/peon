import threading
import time


def start_afk_thread(bot):
    def do_afk_thread(bot):
        i = 0
        while True:
            bot.send(bot.proto.PlayServerboundHeldItemChange.id,
                     slot=i
                     )
            i = (i + 1) % 8
            time.sleep(55)

    thread = threading.Thread(target=do_afk_thread, name='afk', args=(bot,))
    thread.daemon = True
    thread.start()
    return thread


def start_chat_interface(bot):
    message = ''
    while message not in ['exit', 'quit']:
        message = raw_input('> ').strip()
        bot.send(bot.proto.PlayServerboundChatMessage.id,
                 chat=message
                 )
