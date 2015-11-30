import argparse
import contextlib
import itertools
import math
import Queue
import re
import sys
import threading
import time

import blessings
import readchar
import seeksearch

PARSER = argparse.ArgumentParser(description='')
PARSER.add_argument('--wpm', '-w', type=float, help='Speed of output in words per minute', default=200.)
PARSER.add_argument('--debug-print', action='store_true', help='Add pauses between prints to debug printing', default=False)
PARSER.add_argument('--no-controls', action='store_true', help='Switch off keyboard controls ', default=False)
PARSER.add_argument('filename', type=str, help='Speed of output in words per minute', nargs='?')



def spawn(f):
    t = threading.Thread(target=f)
    t.setDaemon(True)
    t.start()
    return t

def main():
    args = PARSER.parse_args()
    with open(args.filename) as f:
        reader = Reader(f)

        display = Display()

        pusher = Pusher(reader, display, 60. / args.wpm )
        controller = Controller(pusher, display)

        if args.no_controls:
            pusher.run()
        else:
            push_thread = spawn(pusher.run)
            controller.run()

class Controller(object):
    def __init__(self, pusher, display):
        self.pusher = pusher
        self.display = display

    def run(self):
        while True:
            COMMANDS = {
                'b': self.pusher.back_sentence,
                'f': self.pusher.forward_sentence,
                'j': self.speed_up,
                'k': self.slow_down,
                '\x03': sys.exit
            }
            char = readchar.readchar()
            method = COMMANDS.get(char)
            if method:
                method()

    def speed_up(self):
        # Should really be locked
        self.pusher.word_period *= 0.9

    def slow_down(self):
        self.pusher.word_period /= 0.9


def re_partition(text, match_re):
    full_re = '(.*?)({})(.*)'.format(match_re)
    match = re.search(full_re, text)
    if match:
        return match.group(1), match.group(2), match.group(3)
    else:
        return text, None, ''

class WORD_TYPE(object):
    COMMA = 'comma'
    SPACE = 'space'
    SENTENCE = 'sentence'

class Reader(object):
    def __init__(self, stream):
        self.stream = stream
        self.line_words = None

    def back_sentence(self):
        with seeksearch.save_excursion(self.stream):
            index = seeksearch.seek_rfind(self.stream, '.')

        if index != -1:
            self.line_words = []
            self.stream.seek(index)

    def forward_sentence(self):
        with seeksearch.save_excursion(self.stream):
            index = seeksearch.seek_find(self.stream, '.')

        if index != -1:
            self.line_words = []
            self.stream.seek(index)

    def get_word(self):
        while not self.line_words:
            self.line_words = []
            line = self.stream.readline().decode('utf8')
            if not line:
                return None, None

            rest = line
            while True:
                word, sep, rest = re_partition(rest, '[, ;.]+')
                if sep is None:
                    word_type = WORD_TYPE.SENTENCE
                elif ',' in sep or ';' in sep:
                    word_type = WORD_TYPE.COMMA
                elif '.' in sep:
                    word_type = WORD_TYPE.SENTENCE
                else:
                    word_type = WORD_TYPE.SPACE

                if word.strip():
                    self.line_words.append((word_type, word.strip()))

                if sep is None:
                    break

            self.line_words = list(reversed(self.line_words))

        return self.line_words.pop()


class Pusher(object):
    def __init__(self, reader, display, word_period):
        self.reader = reader
        self.display = display
        self.word_period = word_period
        self.q = Queue.Queue()

    def back_sentence(self):
        self.reader.back_sentence()

    def forward_sentence(self):
        self.reader.forward_sentence()

    def run(self):
        while True:
            word_type, word = self.reader.get_word()
            if word is None:
                return
            else:
                with self.display.display_word(word):
                    delay = word_multiple(word_type, word) * self.word_period
                    time.sleep(delay)

def word_multiple(word_type, word):
    return {
        WORD_TYPE.COMMA: 2,
        WORD_TYPE.SENTENCE: 3,
        WORD_TYPE.SPACE: math.sqrt(len(word)) / math.sqrt(4)
    }[word_type]



class DecoratedText(object):
    # DecoratedText(term, (term.bold, 'THis is bold'), (None, 'This is not bold'))
    def __init__(self, term, format_pairs):
        self.format_pairs = [ (None, x) if isinstance(x, (str, unicode)) else x for x in format_pairs ]
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


    def __unicode__(self):
        term = self.term
        return u''.join((a if a is not None else term.normal) + b for a, b in self.format_pairs)

    def __len__(self):
        return sum(len(text) for formatting, text in self.format_pairs)

    def __add__(self, other):
        if isinstance(other, str):
            return DecoratedText(self.term, self.format_pairs + [other])
        else:
            return DecoratedText(self.term, self.format_pairs + other.format_pairs)

    def __radd__(self, other):
        return DecoratedText(self.term, [other] + self.format_pairs)


class NonclearingWriter(object):
    def __init__(self, stream):
        self.stream = stream

    @contextlib.contextmanager
    def write(self, text):
        self.stream.write(unicode(text))
        self.stream.flush()
        yield

class ClearingWriter(object):
    def __init__(self, stream, term, debug=False):
        self.stream = stream
        self.term = term
        self.debug = debug

    @contextlib.contextmanager
    def write(self, text):
        line, _sep, rest = text.partition('\n')
        with self._write_line(line):
            if rest:
                with self.write(rest):
                    yield
            else:
                yield

    def _write(self, text):
        self.stream.write(text.encode('utf8'))
        if self.debug:
            self.stream.flush(); time.sleep(1)

    @contextlib.contextmanager
    def _write_line(self, line):
        self._write(unicode(line))
        self._write('\r\n') # readchar switches off carriage returns

        yield

        line_length = len(line)

        self._write(self.term.move_up)
        for _ in xrange(line_length):
            self._write(self.term.move_right)

        for _ in xrange(line_length):
            self._write(self.term.move_left)

        for _ in xrange(line_length):
            self._write(' ')

        for _ in xrange(line_length):
            self._write(self.term.move_left)


class Display(object):
    def __init__(self):
        self.q = Queue.Queue()
        self.focus_column = 10
        self.term = blessings.Terminal()
        #self.writer = NonclearingWriter(sys.stdout)
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
