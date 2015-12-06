# Slowly reimplemnt bits of gevent/twisted/pygame until
#   I get bored :/
import threading
import Queue
import time

class Timer(object):
    CLEAR = 'clear'
    def __init__(self):
        self.expired = threading.Event()
        self.expires = []
        self.q = Queue.Queue()

    def expire_loop(self):
        while True:
            if self.expires:
                timeout = min(self.expires) - time.time()
            else:
                timeout = None

            try:
                if timeout is None or timeout > 0:
                    new_expires = self.q.get(timeout=timeout, block=True)
                else:
                    new_expires = None
            except Queue.Empty:
                pass

            if new_expires is not None:
                self.expires.append(new_expires)
                self.expired.clear()

            if new_expires == self.CLEAR:
                self.expires = []
                self.expired.clear()

            if self.expires and (min(self.expires) < time.time()):
                self.expired.set()
                self.expires = []

    def set_delay(self, delay):
        self.q.put(time.time() + delay)

    def tick(self):
        self.q.put(time.time())

    def clear(self):
        self.q.put(self.CLEAR)

    def wait(self):
        self.expired.wait()

def spawn(f):
    t = threading.Thread(target=f)
    t.setDaemon(True)
    t.start()
    return t
