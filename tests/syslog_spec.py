from prefix import *

from cutil.syslog import _syslog_spec_matcher

SPECS = (
    ('*.*',                                    '(True)'),
    ('[crond].*',                              '((g and "crond" == g.lower()))'),
    ('.*',                                     'Invalid log spec syntax: .*'),
    ('kern.*;kern.!=crit',                     '((not (f==0) or not p==2)) and (((f==0)))'),
    ('kern.*;kern.!crit',                      '((not (f==0) or not p<=2)) and (((f==0)))'),
    ('kern.crit',                              '((f==0) and p<=2)'),
    ('*.=emerg;*.=crit',                       '(p==0) or (p==2)'),
    ('/not and\/or able/.*',                   '(bool(buf.search(s._regexes[0])))'),
    ('*.*;![debian-start].*;authpriv,auth.!*', '(not ((g and "debian-start" == g.lower())) and (not (f==10 or f==4)))'),
    ('*.*;![debian-start].*;!authpriv,auth.*', '(not ((g and "debian-start" == g.lower())) and not ((f==10 or f==4)))'),
    ('*.*;![debian-start].*;!authpriv,auth.!crit', '(not ((g and "debian-start" == g.lower())) and (not (f==10 or f==4) and not p<=2))'),
    ('kern.*',                                 '((f==0))'),
    ('*.*;*.!*',                               '((False))'),
    ('*.*;![chaperone].*',                     '(not ((g and "chaperone" == g.lower())))'),
    ('kern.*;!auth,authpriv.*',                '(not ((f==4 or f==10))) and (((f==0)))'),
    ('[cron].*;[daemon-tools].crit;/password/.!err', '((not bool(buf.search(s._regexes[0])) or not p<=3)) and (((g and "cron" == g.lower())) or ((g and "daemon-tools" == g.lower()) and p<=2))'),
    ('kern.*;![cron].!err',                    '((not (g and "cron" == g.lower()) and not p<=3)) and (((f==0)))'),
    ('[chaperone].err;[logrotate].err;!kern.*', '(not ((f==0))) and (((g and "chaperone" == g.lower()) and p<=3) or ((g and "logrotate" == g.lower()) and p<=3))'),
    ('/panic/.*;/segfault/.*;*.!=debug',       '((not p==7)) and ((bool(buf.search(s._regexes[0]))) or (bool(buf.search(s._regexes[1]))))'),
)


class TestSyslogSpec(unittest.TestCase):

    def test_specs(self):
        for s in SPECS:
            try:
                sm = _syslog_spec_matcher(s[0]).debugexpr
            except Exception as ex:
                sm = ex
                if 'unexpected' in str(sm):
                    raise
            #Uncomment to generate the test table, but CHECK IT carefully!
            #print("('{0:40} '{1}'),".format(s[0]+"',", sm))
            self.assertEqual(str(sm), s[1])

if __name__ == '__main__':
    unittest.main()
