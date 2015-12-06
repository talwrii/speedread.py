#encoding: utf8

import re
import collections

WordInfo = collections.namedtuple('WordInfo', 'id type word sep offset')

def line_to_words(line):
    "Split a line into words"
    word_offset = 0
    words = []
    if line.strip() == '':
        return [], ''
    else:
        rest = line
        while rest:
            word_text, sep, rest = re_partition(rest, u'[, ;.—\-]+')
            if sep is not None:
                word_info = WordInfo(id=None, type=WORD_TYPE.UNKNOWN, word=word_text, sep=sep, offset=word_offset)
                words.append(word_info)
                word_offset += len((word_text + (sep or '')).encode('utf8'))

        return words, word_text

def re_partition(text, match_re):
    "Like str.partition by uses a regular expression for splitting"
    full_re = u'(.*?)({})(.*)'.format(match_re)
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
    PARAGRAPH = 'special'
    UNKNOWN = 'unknown'
    END_OF_FILE = 'eof'
    PARAGRAPH_END = 'paragraph_end'
