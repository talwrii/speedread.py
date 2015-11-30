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

def seek_find(stream, needle, chunk_size=1000):
    for start, chunk in read_chunks(stream, chunk_size, len(needle)):
        print start, chunk
        pos = chunk.find(needle)
        if pos != -1:
            return start + pos
    else:
        return -1

def seek_rfind(stream, needle, chunk_size=1000):
    for start, chunk in rread_chunks(stream, chunk_size, len(needle)):
        pos = chunk.rfind(needle)
        if pos != -1:
            return pos + start
    else:
        return -1

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
        method = seek_rfind if args.reverse else seek_find
        print method(f, args.needle, chunk_size=args.chunk_size)
