import argparse
import collections
import math
import Queue
import re
import sys
import threading
import time

import blessings
import readchar

import seeksearch
import termutils
import contextutils

def main():
    bindings_help = Controller.bindings_help()

    PARSER = argparse.ArgumentParser(description='', epilog=bindings_help, formatter_class=argparse.RawTextHelpFormatter)
    PARSER.add_argument('--wpm', '-w', type=float, help='Speed of output in words per minute', default=200.)
    PARSER.add_argument('--debug-print', action='store_true', help='Add pauses between prints to debug printing', default=False)
    PARSER.add_argument('--disable-clear', action='store_true', help='Do not clear any printing (for debugging)', default=False)
    PARSER.add_argument('--no-controls', action='store_true', help='Switch off keyboard controls ', default=False)
    PARSER.add_argument('filename', type=str, help='Speed of output in words per minute', nargs='?')
    args = PARSER.parse_args()

    with open(args.filename) as f:
        reader = Reader(f)
        term = blessings.Terminal()

        if args.disable_clear:
            writer = termutils.NonclearingWriter(sys.stdout)
        else:
            writer = termutils.ClearingWriter(sys.stdout, term)

        display = Display(term, writer)

        pusher = Pusher(reader, display, 60. / args.wpm )
        controller = Controller(pusher, display)

        if args.no_controls:
            pusher.run()
        else:
            spawn(pusher.run)
            controller.run()


def format_keybinding(c):
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    if ord(c) in range(1, 27):
        return "C-" + alphabet[ord(c) - 1]
    else:
        return c

class Controller(object):
    "Perform operations in response to key presses"

    @classmethod
    def commands(cls):
        return {
        's': cls.show_sentence,
        'b': cls.back_sentence,
        'f': cls.forward_sentence,
        'w': cls.forward_word,
        'j': cls.speed_up,
        'k': cls.slow_down,
        'h': cls.show_bindings,
        ' ': cls.pause,
        '\x03': cls.exit}


    def pause(self):
        "Pause display"
        self.pusher.toggle_pause()

    def exit(self):
        "Exit"
        sys.exit()

    def forward_word(self):
        "Move a word forward"
        self.pusher.forward_word()

    def show_sentence(self):
        "Show the current sentence"
        self.pusher.show_sentence()

    def show_paragraph(self):
        "Show the current paragraph"
        self.pusher.show_paragraph()

    def forward_sentence(self):
        "Move forward a sentence"
        self.pusher.forward_sentence()

    def __init__(self, pusher, display):
        self.pusher = pusher
        self.display = display
        self.back_pressed_time = None

    def back_sentence(self):
        "Move to the previous sentene"
        print self.back_pressed_time
        if self.back_pressed_time and time.time() - self.back_pressed_time < 0.5:
            self.pusher.back_two_sentences()
            self.back_pressed_time = None
        else:
            self.back_pressed_time = time.time()
            self.pusher.back_sentence()

    def show_bindings(self):
        self.pusher.display_text(self.bindings_help())

    @classmethod
    def bindings_help(cls):
        result = []
        for key, value in cls.commands().items():
            result.append("{} - {}".format(format_keybinding(key), value.__doc__))
        return '\n'.join(result)

    def run(self):
        commands = self.commands()
        while True:
            char = readchar.readchar()
            method = commands.get(char)
            if method:
                method(self)

    def speed_up(self):
        "Show words faster"
        # Should really be locked
        self.pusher.word_period *= 0.9

    def slow_down(self):
        "Show words more slowly"
        self.pusher.word_period /= 0.9

class Display(object):
    def __init__(self, term, writer):
        self.q = Queue.Queue()
        self.focus_column = 10
        self.term = term
        self.writer = writer
        self.word_display = None

    def display_word(self, word):
        if self.word_display is not None:
            self.word_display.exit()

        marker_line = self.format_insert_line(self.focus_column)
        word_line = self.format_word_line(self.focus_column, word)

        self.word_display = contextutils.WithContext(self.writer.write(marker_line + '\n' + word_line + '\n'))
        self.word_display.enter()

    def write_text(self, text):
        if self.word_display is not None:
            self.word_display.exit()

        print text

    def format_insert_line(self, focus_column):
        return ' ' * (focus_column) + 'v'

    def format_word_line(self, focus_column, word):
        term = self.term
        focus_char = Speedread.find_focus_char(word)
        space = ''.join([' '] * (focus_column - focus_char))
        return termutils.DecoratedText(term, [space, word[:focus_char], (term.bold, word[focus_char]), word[focus_char + 1:]])

class Pusher(object):
    def __init__(self, reader, display, word_period):
        self.reader = reader
        self.display = display
        self.word_period = word_period
        self.lock = threading.RLock()
        self.playing = True
        self.ticker = Ticker()

    def back_sentence(self):
        self.display.write_text('Back')
        with self.lock:
            self.reader.forward_sentence(reverse=True)
            self.ticker.tick()

    def back_two_sentences(self):
        self.display.write_text('Back two')
        with self.lock:
            self.reader.forward_sentence(reverse=True, count=2)
            self.ticker.tick()

    def forward_sentence(self):
        with self.lock:
            self.reader.forward_sentence()
            self.ticker.tick()

    def forward_word(self):
        with self.lock:
            self.ticker.tick()

    def show_sentence(self):
        with self.lock:
            self.display.write_text(self.reader.current_sentence())

    def show_paragraph(self):
        with self.lock:
            self.display.write_text(self.reader.current_paragraph())

    def display_text(self, text):
        with self.lock:
            self.display.write_text(text)

    def toggle_pause(self):
        with self.lock:
            self.playing = not self.playing
            if self.playing:
                self.ticker.tick()
            else:
                self.ticker.clear()

    def run(self):
        spawn(self.ticker.expire_loop)
        while True:
            with self.lock:
                word_info = self.reader.get_word()
                if word_info is None:
                    return
                else:
                    self.display.display_word(word_info.word)

                delay = Speedread.word_multiple(word_info.type, word_info.word) * self.word_period

                if self.playing:
                    self.ticker.set_delay(delay)

            self.ticker.wait()

            with self.lock:
                self.ticker.clear()

class Ticker(object):
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


class Reader(object):
    def __init__(self, stream):
        self.stream = stream
        self._read_ahead_words = collections.deque()
        self.word_classifier = WordClassifier()
        self.sentence_tracker = SentenceTracker()
        self.read_word_id = 0
        self.displayed_word_id = 0

    def forward_sentence(self, count=1, reverse=False):
        with seeksearch.save_excursion(self.stream):
            index = seeksearch.seek_find(self.stream, '.', count=count, reverse=reverse)

        if index != -1:
            self._read_ahead_words = collections.deque()
            self.read_word_id = 0
            self.sentence_tracker.reset()
            self.stream.seek(index)

    def current_sentence(self):
        while True:
            sentence = self.sentence_tracker.get_sentence(self.displayed_word_id)
            if sentence:
                return sentence
            self.read_line()

    def current_paragraph(self):
        while True:
            paragraph = self.paragraph_tracker.get_sentence(self.displayed_word_id)
            if paragraph:
                return paragraph

    def read_line(self):
        line = self.stream.readline().decode('utf8')
        if not line:
            return None, None

        rest = line
        while True:
            word, sep, rest = re_partition(rest, '[, ;.]+')
            self.read_word_id += 1
            word_type = self.word_classifier.read_ahead_word(word, sep)
            word_text = word.strip() + (sep if sep != ' ' and sep is not None else '')
            word_info = WordInfo(id=self.read_word_id, type=word_type, word=word_text, sep=sep)

            self.sentence_tracker.read_ahead_word(word_info)

            if word.strip():
                self._read_ahead_words.append(word_info)

            if sep is None:
                break

    def get_word(self):
        while not self._read_ahead_words:
            self.read_line()
        word_info = self._read_ahead_words.popleft()
        self.displayed_word_id = word_info.id
        self.sentence_tracker.word_displayed(word_info)

        return word_info

class SentenceTracker(object):
    "Keep track of sentences that we have read but not yet displayed"
    def __init__(self):
        self._sentences_by_last_id = dict()
        self._current_sentence_parts = []

    def read_ahead_word(self, word_info):
        self._current_sentence_parts.append(word_info.word)
        if word_info.sep:
            self._current_sentence_parts.append(word_info.sep)

        if word_info.type == WORD_TYPE.SENTENCE_END:
            sentence = ''.join(self._current_sentence_parts)
            self._sentences_by_last_id[word_info.id] = sentence
            self._current_sentence_parts = []

    def word_displayed(self, word_info):
        if word_info.id in self._sentences_by_last_id:
            self._sentences_by_last_id.pop(word_info.id)

    def reset(self):
        self._sentences_by_last_id = dict()

    def get_sentence(self, word_id):
        for end_id, sentence in sorted(self._sentences_by_last_id.items()):
            if end_id > word_id:
                return sentence

class WordClassifier(object):
    "Classify types of word"

    def __init__(self):
        self.last_word_type = None

    def read_ahead_word(self, word, sep):
        word_type = self._get_word_type(word, sep, self.last_word_type)
        self.last_word_type = word_type
        return word_type

    @staticmethod
    def _get_word_type(word, sep, last_word_type):
        if sep is None:
            return WORD_TYPE.NORMAL
        elif ',' in sep or ';' in sep:
            return WORD_TYPE.BEFORE_COMMA
        elif '.' in sep:
            return WORD_TYPE.SENTENCE_END
        else:
            if last_word_type == WORD_TYPE.SENTENCE_END:
                return WORD_TYPE.SENTENCE_BEGIN
            else:
                return WORD_TYPE.NORMAL

class WORD_TYPE(object):
    BEFORE_COMMA = 'before_comma'
    SPACE = 'space'
    SENTENCE_END = 'sentence_end'
    SENTENCE_BEGIN = 'sentence_begin'
    NORMAL = 'normal'


class Speedread(object):
    "Purish logic related to the algorithm"
    @staticmethod
    def find_focus_char(word):
        if len(word) > 13:
            return 4
        else:
            return (0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3)[len(word)]

    @staticmethod
    def word_multiple(word_type, word):
        word_scaling = 1 + math.sqrt(len(word)) / math.sqrt(4)
        return {
            WORD_TYPE.BEFORE_COMMA: 2,
            WORD_TYPE.SENTENCE_BEGIN: 3,
            WORD_TYPE.NORMAL: word_scaling,
            WORD_TYPE.SENTENCE_END: word_scaling
        }[word_type]


def spawn(f):
    t = threading.Thread(target=f)
    t.setDaemon(True)
    t.start()
    return t

def re_partition(text, match_re):
    "Like str.partition by uses a regular expression for splitting"
    full_re = '(.*?)({})(.*)'.format(match_re)
    match = re.search(full_re, text)
    if match:
        return match.group(1), match.group(2), match.group(3)
    else:
        return text, None, ''

WordInfo = collections.namedtuple('WordInfo', 'id type word sep')


if __name__ == '__main__':
    main()
