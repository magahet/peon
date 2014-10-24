import threading
import time
import os


def start_afk_thread(bot):
    def do_afk_thread(bot, pid):
        i = 0
        while True:
            if time.time() - bot.last_keepalive > 20:
                print 'Server disconnected. Exiting'
                os.kill(pid, 0)
                break
            bot.send(bot.proto.PlayServerboundHeldItemChange.id,
                     slot=i
                     )
            i = (i + 1) % 8
            time.sleep(55)

    pid = os.getppid()
    thread = threading.Thread(target=do_afk_thread, name='afk', args=(bot, pid))
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
