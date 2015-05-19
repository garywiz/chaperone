from prefix import *

from cutil.syslog import _syslog_spec_matcher

SPECS = (
    ('*.*',                    '[[]]'),
    ('[crond].*',              "[['(g and \"crond\" == g.lower())']]"),
    ('.*',                     "Invalid log spec syntax: .*"),
    ('*.=emerg;*.=crit',       "[['(p==0)'], ['(p==2)']]"),
    ('/not and\/or able/.*',   "[['(bool(buf.search(s._regexes[0])))']]"),
    ('kern.*',                 "[['(f==0)']]"),
    ('*.!*',                   "[['(False)']]"),
    ('![chaperone].*',         "[['not (g and \"chaperone\" == g.lower())']]")
)

class TestSyslogSpec(unittest.TestCase):

    def test_specs(self):
        for s in SPECS:
            try:
                sm = _syslog_spec_matcher(s[0]).debuglist
            except Exception as ex:
                sm = ex
            #print(str(sm))
            self.assertEqual(str(sm), s[1])

if __name__ == '__main__':
    unittest.main()
