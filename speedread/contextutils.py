class WithContext(object):
    """Iteract with a context manager without using
    __ methods and out side of a block"""

    def __init__(self, manager):
        self.manager = manager
        self.it = None

    def enter(self):
        def inner():
            with self.manager:
                yield
        self.it = inner()
        self.it.next()

    def exit(self):
        for _ in self.it:
            pass
