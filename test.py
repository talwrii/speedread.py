
import unittest
import textutils
import speedread
import StringIO

class CombinedTest(unittest.TestCase):
    def dont_test_line_to_words(self):
        #                                      01234567890123456
        words, rest = textutils.line_to_words('This is  a, line')
        self.assertEquals(rest, 'line')
        self.assertEquals([word.word for word in words], ['This', 'is', 'a'])
        self.assertEquals([word.sep for word in words], [' ', '  ', ', '])
        self.assertEquals([word.offset for word in words], [0, 5, 9])

    def test_read_line(self):
        #                      0 1234567 8 90123
        f = StringIO.StringIO('A\naa aaa\n\naaaa')
        reader = speedread.Reader(f)

        words = []
        while True:
            word = reader.get_word()
            if word.type == textutils.WORD_TYPE.PARAGRAPH:
                continue
            if word.type == textutils.WORD_TYPE.END_OF_FILE:
                break
            words.append(word)
        self.assertEquals([w.word for w in words], ['A', 'aa', 'aaa', 'aaaa'])
        self.assertEquals([w.offset for w in words], [0, 2, 5, 10])

if __name__ == "__main__":
	unittest.main()
