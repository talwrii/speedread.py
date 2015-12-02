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
import display
import contextutils

PARSER = argparse.ArgumentParser(description='')
PARSER.add_argument('--wpm', '-w', type=float, help='Speed of output in words per minute', default=200.)
PARSER.add_argument('--debug-print', action='store_true', help='Add pauses between prints to debug printing', default=False)
PARSER.add_argument('--disable-clear', action='store_true', help='Do not clear any printing (for debugging)', default=False)
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

        term = blessings.Terminal()

        if args.disable_clear:
            writer = display.NonclearingWriter(sys.stdout)
        else:
            writer = display.ClearingWriter(sys.stdout, term)

        display = Display(term, writer)

        pusher = Pusher(reader, display, 60. / args.wpm )
        controller = Controller(pusher, display)

        if args.no_controls:
            pusher.run()
        else:
            spawn(pusher.run)
            controller.run()

class Controller(object):
    def __init__(self, pusher, display):
        self.pusher = pusher
        self.display = display
        self.back_pressed_time = None

    def back_sentence(self):
        if self.back_pressed_time and time.time() - self.back_pressed_time < 0.1:
            self.pusher.back_two_sentences()
            self.back_pressed_time = None
        else:
            self.back_pressed_time = time.time()
            self.pusher.back_sentence()

    def run(self):
        while True:
            COMMANDS = {
                's': self.pusher.show_sentence,
                #'p': self.pusher.show_paragraph,
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
    BEFORE_COMMA = 'before_comma'
    SPACE = 'space'
    SENTENCE_END = 'sentence_end'
    SENTENCE_BEGIN = 'sentence_begin'
    NORMAL = 'normal'

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

    def read_line(self):
        line = self.stream.readline().decode('utf8')
        if not line:
            return None, None

        rest = line
        while True:
            word, sep, rest = re_partition(rest, '[, ;.]+')
            self.read_word_id += 1
            word_type = self.word_classifier.read_ahead_word(word, sep)
            word_info = WordInfo(id=self.read_word_id, type=word_type, word=word.strip(), sep=sep)

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

WordInfo = collections.namedtuple('WordInfo', 'id type word sep')

class Pusher(object):
    def __init__(self, reader, display, word_period):
        self.reader = reader
        self.display = display
        self.word_period = word_period
        self.q = Queue.Queue()
        self.lock = threading.RLock()

    def back_sentence(self):
        with self.lock:
            self.reader.forward_sentence(reverse=True)

    def back_two_sentences(self):
        with self.lock:
            self.reader.forward_sentence(reverse=True, count=2)

    def forward_sentence(self):
        with self.lock:
            self.reader.forward_sentence()

    def show_sentence(self):

        with self.lock:
            self.display.show_sentence(self.reader.current_sentence())

    def run(self):
        while True:
            with self.lock:
                word_info = self.reader.get_word()

            if word_info is None:
                return
            else:
                self.display.display_word(word_info.word)
                delay = word_multiple(word_info.type, word_info.word) * self.word_period
                time.sleep(delay)

def word_multiple(word_type, word):
    word_scaling = math.sqrt(len(word)) / math.sqrt(4)
    return {
        WORD_TYPE.BEFORE_COMMA: 2,
        WORD_TYPE.SENTENCE_BEGIN: 3,
        WORD_TYPE.NORMAL: word_scaling,
        WORD_TYPE.SENTENCE_END: word_scaling
    }[word_type]


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

    def show_sentence(self, sentence):
        if self.word_display is not None:
            self.word_display.exit()
        print sentence

    def format_insert_line(self, focus_column):
        return ' ' * (focus_column) + 'v'

    def format_word_line(self, focus_column, word):
        term = self.term
        focus_char = find_focus_char(word)
        space = ''.join([' '] * (focus_column - focus_char))
        return display.DecoratedText(term, [space, word[:focus_char], (term.bold, word[focus_char]), word[focus_char + 1:]])


def find_focus_char(word):
    if len(word) > 13:
        return 4
    else:
        return (0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3)[len(word)]

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

if __name__ == '__main__':
    main()
