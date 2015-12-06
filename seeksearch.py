import argparse
import itertools
import contextlib


def read_chunks(stream, size, overlap):
    "Get chunks of text out of a stream in order"
    start = stream.tell()
    old_chunk = ''
    pos = start
    while True:
        chunk = stream.read(size)
        if chunk == '':
            break
        else:
            overlap_chars = old_chunk[-overlap:]
            yield (pos - len(overlap_chars), overlap_chars + chunk)

        pos += size
        old_chunk = chunk

def rread_chunks(stream, size, overlap):
    start = stream.tell()
    old_chunk = ''
    for i in itertools.count(1):
        chunk_start = max(start - i * size, 0)
        chunk_end = max(start - i * size + size, 0)
        stream.seek(chunk_start)
        chunk = stream.read(chunk_end - chunk_start)
        if chunk == '':
            break
        else:
            yield (chunk_start, chunk + old_chunk[:overlap])

def enumerate_in_chunk(chunk, needle, reverse=False):
    chunk_searcher = search_string_backward if reverse else search_string_forward

    pos = None
    while True:
        pos = chunk_searcher(chunk, needle, pos)
        if pos == -1:
            break
        else:
            yield pos



def seek_find(stream, needle, chunk_size=1000, count=1, reverse=False):
    num_found = 0
    chunk_reader = rread_chunks if reverse else read_chunks

    for start, chunk in chunk_reader(stream, chunk_size, len(needle)):
        for pos in enumerate_in_chunk(chunk, needle, reverse=reverse):
            num_found += 1
            if num_found == count:
                return start + pos
    else:
        return -1

def search_string_forward(string, needle, start):
    if start is None:
        return string.find(needle)
    else:
        return string.find(needle, start + 1)

def search_string_backward(string, needle, end):
    if end is None:
        return string.rfind(needle)
    else:
        return string.rfind(needle, 0, end)


@contextlib.contextmanager
def save_excursion(stream):
    before = stream.tell()
    yield
    # Don't unnecessarily break caching
    if before != stream.tell():
        stream.seek(before)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(description='Search in large files')
    PARSER.add_argument('file', type=str, help='File to search in')
    PARSER.add_argument('needle', type=str, help='What to search for')
    PARSER.add_argument('--start-pos', type=int, help='Start searching at this position')
    PARSER.add_argument('--reverse', action='store_true', default=False, help='search backward')
    PARSER.add_argument('--chunk-size', '-s', type=int, help='How big a chunk to read a time', default=1000)
    args = PARSER.parse_args()

    with open(args.file) as f:
        if args.start_pos:
            f.seek(args.start_pos)
        print seek_find(f, args.needle, chunk_size=args.chunk_size, reverse=args.reverse)
