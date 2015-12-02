import contextlib
import time

class DecoratedText(object):
    "A str-like object with blessings decoration. Supports partition and length"
    # DecoratedText(term, (term.bold, 'THis is bold'), (None, 'This is not bold'))
    def __init__(self, term, format_pairs):
        self.format_pairs = [ (None, x) if isinstance(x, (str, unicode)) else x for x in format_pairs ]
        self.term = term

    def partition(self, sep):
        first_pairs, second_pairs  = [], []
        accum = first_pairs
        ret_sep = None
        for fmt, text in self.format_pairs:
            if sep in text:
                first, ret_sep, second = text.partition(sep)
                accum.append((fmt, first))
                accum = second_pairs
                accum.append((fmt, second))
            else:
                accum.append((fmt, text))

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
    "A trivial drop in replacement to ClearingWriter"
    def __init__(self, stream):
        self.stream = stream

    @contextlib.contextmanager
    def write(self, text):
        # readchar switches off linefeeds (I think)
        self.stream.write(unicode(text).replace('\n', '\r\n'))
        self.stream.flush()
        yield

class ClearingWriter(object):
    "An object to write to a stream, using the terminal escape codes to clear this output"
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
