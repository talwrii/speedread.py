import Queue
import sys
import threading
import blessings
import time
import contextlib

def spawn(f):
    t = threading.Thread(target=f)
    t.setDaemon(True)
    t.start()
    return t

def main():
    reader = Reader(sys.stdin)

    display = Display()

    pusher = Pusher(reader, display)
    pusher.run()

    #control = spawn_control(display)


class Reader(object):
    def __init__(self, stream):
        self.stream = stream
        self.line_words = None

    def get_word(self):
        if not self.line_words:
            line = self.stream.readline()
            if not line:
                return None
            self.line_words = line.split(' ')[::-1]
        return self.line_words.pop().strip()


class Pusher(object):
    def __init__(self, reader, display):
        self.reader = reader
        self.display = display

    def run(self):
        while True:
            word = self.reader.get_word()
            if word is None:
                return
            else:
                with self.display.display_word(word):
                    time.sleep(1)

class DecoratedText(object):
    # DecoratedText(term, (term.bold, 'THis is bold'), (None, 'This is not bold'))
    def __init__(self, term, format_pairs):
        self.format_pairs = [ (None, x) if isinstance(x, str) else x for x in format_pairs ]
        self.term = term

    def partition(self, sep):
        first_pairs, second_pairs  = [], []
        accum = first_pairs
        ret_sep = None
        for format, text in self.format_pairs:
            if sep in text:
                first, ret_sep, second = text.partition(sep)
                accum.append((format, first))
                accum = second_pairs
                accum.append((format, second))
            else:
                accum.append((format, text))

        return DecoratedText(self.term, first_pairs), ret_sep, DecoratedText(self.term, second_pairs)


    def __str__(self):
        term = self.term
        return ''.join((a if a is not None else term.normal) + b for a, b in self.format_pairs)

    def __len__(self):
        return sum(len(text) for formatting, text in self.format_pairs)

    def __add__(self, other):
        if isinstance(other, str):
            return DecoratedText(self.term, self.format_pairs + [other])
        else:
            return DecoratedText(self.term, self.format_pairs + other.format_pairs)

    def __radd__(self, other):
        return DecoratedText(self.term, [other] + self.format_pairs)


class ClearingWriter(object):
    def __init__(self, stream, term):
        self.stream = stream
        self.term = term

    @contextlib.contextmanager
    def write(self, text):
        line, _sep, rest = text.partition('\n')
        with self._write_line(line):
            if rest:
                with self.write(rest):
                    yield
            else:
                yield

    def format_line(self, line):
        if isinstance(line, str):
            return line
        else:
            return line.format()

    @contextlib.contextmanager
    def _write_line(self, line):
        self.stream.write(str(line))
        self.stream.write('\n')

        yield

        line_length = len(line)

        self.stream.write(self.term.move_up)
        for _ in xrange(line_length):
            self.stream.write(self.term.move_right)

        for _ in xrange(line_length):
            self.stream.write(self.term.move_left)


        for _ in xrange(line_length):
            self.stream.write(' ')

        for _ in xrange(line_length):
            self.stream.write(self.term.move_left)

class Display(object):
    def __init__(self):
        self.q = Queue.Queue()
        self.focus_column = 10
        self.term = blessings.Terminal()
        self.writer = ClearingWriter(sys.stdout, self.term)

    def display_word(self, word):
        marker_line = self.format_insert_line(self.focus_column)
        word_line = self.format_word_line(self.focus_column, word)
        return self.writer.write(marker_line + '\n' + word_line + '\n')

    def format_insert_line(self, focus_column):
        return ' ' * (focus_column) + 'v'

    def format_word_line(self, focus_column, word):
        term = self.term
        focus_char = find_focus_char(word)
        space = ''.join([' '] * (focus_column - focus_char))
        return DecoratedText(term, [space, word[:focus_char], (term.bold, word[focus_char]), word[focus_char + 1:]])

def find_focus_char(word):
    if len(word) > 13:
        return 4
    else:
        return (0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3)[len(word)]

def find_word_delay_factor(word):
    return 1

if __name__ == '__main__':
	main()
