from prefix import *

from chaperone.cutil.env import EnvScanner

TEST1 = (
    ('Nothing',),
    ('A normal $(expansion) is here',),
    ('An unterminated $(expansion is here',),
    ('Two $(expansions) are $(also) here',),
    ('Nested $(expansions are $(also) here) too.',),
    ('Nested $(expansions are "$(also" here) too.',),
    ('Nested $(expansions are ["$(also" here),$(next)] finally) too.',),
    ('Ignore $(stuff))) like this.',),
    ('escape \\$(stuff) like this.',),
    ('exp $(stuff) but \$(do not $(except [{$(foo)}] this) but \${not} like this.',),
    ('Nested ${expansions are ["$(also" here),$(next)] finally} too.',),
)

TEST1 = (
    ('Nothing', 'Nothing'),
    ('A normal $(expansion) is here', 'A normal <expansion> is here'),
    ('An unterminated $(expansion is here', 'An unterminated $(expansion is here'),
    ('Two $(expansions) are $(also) here', 'Two <expansions> are <also> here'),
    ('Nested $(expansions are $(also) here) too.', 'Nested <expansions are $(also) here> too.'),
    ('Nested $(expansions are "$(also" here) too.', 'Nested <expansions are "$(also" here> too.'),
    ('Nested $(expansions are ["$(also" here),$(next)] finally) too.', 'Nested <expansions are ["$(also" here),$(next)] finally> too.'),
    ('Ignore $(stuff))) like this.', 'Ignore <stuff>)) like this.'),
    ('escape \$(stuff) like this.', 'escape $(stuff) like this.'),
    ('exp $(stuff) but \$(do not $(except [{$(foo)}] this) but \${not} like this.', 'exp <stuff> but $(do not <except [{$(foo)}] this> but ${not} like this.'),
    ('Nested ${expansions are ["$(also" here),$(next)] finally} too.', 'Nested <expansions are ["$(also" here),$(next)] finally> too.'),
)

class ScanTester:
    
    def __init__(self, test):
        self._test = test
        self._scanner = EnvScanner()

    def run(self, tc):
        for t in self._test:
            r = self._scanner.parse(t[0], self.callback)
            #print("    ('{0}', '{1}'),".format(t[0], r))
            tc.assertEqual(t[1], r)

    def callback(self, buf, whole):
        return "<"+buf+">"


class TestScanner(unittest.TestCase):

    def test_parse1(self):
        t = ScanTester(TEST1)
        t.run(self)

if __name__ == '__main__':
    unittest.main()
