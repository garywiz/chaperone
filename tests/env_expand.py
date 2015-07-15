from prefix import *

from chaperone.cutil.env import Environment

ENV1 = {
    "HOME": '/usr/garyw',
    "APPS-DIR": '$(HOME)/apps',
    "ANOTHER": '$(APPS-DIR)/theap',
    "RECUR2": '$(RECUR1)..$(APPS-DIR)',
    "RECUR1": 'two-$(RECUR3)-$(HOME)',
    "REF-RECUR": "$(ANOTHER) BUT NOT $(RECUR1)",
    "RECUR3": 'three:$(RECUR9)',
}

RESULT1 = "[('ANOTHER', '/usr/garyw/apps/theap'), ('APPS-DIR', '/usr/garyw/apps'), ('HOME', '/usr/garyw'), ('RECUR1', 'two-three:$(RECUR9)-/usr/garyw'), ('RECUR2', 'two-three:$(RECUR9)-/usr/garyw../usr/garyw/apps'), ('RECUR3', 'three:$(RECUR9)'), ('REF-RECUR', '/usr/garyw/apps/theap BUT NOT two-three:$(RECUR9)-/usr/garyw')]"

ENV2 = {
    "HOME": '/usr/garyw',
    "APPS-DIR": '$(HOME)/apps',
    "ANOTHER": '$(APPS-DIR)/theap',
    "RECUR2": '$(RECUR1)..$(APPS-DIR)',
    "RECUR1": 'two-$(RECUR3)-$(HOME)',
    "REF-RECUR": "$(ANOTHER) BUT NOT $(RECUR1)",
    "RECUR3": 'three:$(RECUR2)',
}

RESULT2 = "[('ANOTHER', '/usr/garyw/apps/theap'), ('APPS-DIR', '/usr/garyw/apps'), ('HOME', '/usr/garyw'), ('RECUR1', 'two-three:two-$(RECUR3)-$(HOME)../usr/garyw/apps-/usr/garyw'), ('RECUR2', 'two-$(RECUR3)-$(HOME)../usr/garyw/apps'), ('RECUR3', 'three:two-$(RECUR3)-$(HOME)../usr/garyw/apps'), ('REF-RECUR', '/usr/garyw/apps/theap BUT NOT two-three:two-$(RECUR3)-$(HOME)../usr/garyw/apps-/usr/garyw')]"

ENV3 = {
    "HOME": '/usr/garyw',
    "APPS-DIR": '$(HOME)/apps',
    "ANOTHER": '$(APPS-DIR)/theap',
    "TWO": '$(HOME) and $(APPS-DIR)',
    "MAYBE1": '$(HOAX)/foo',
    "MAYBE10": '$(HOAX:-$(MAYBE11:-11here))/foo',
    "MAYBE11": 'to-$(MAYBE100:-10gone)',
    "MAYBE2": '$(HOAX:-blach)/footwo',
    "MAYBE3": '$(HOAX:+blach)/foo',
    "MAYBE4": '$(HOME:-blach)/foo',
    "MAYBE5": '$(HOME:+blach)/foo',
    "MAYBE6": '$(HOAX:-$(MAYBE2))/foo',
    "MAYBE7": '$(HOME:+blach.${MAYBE8:+8here})/foo',
    "MAYBE8": '$(HOAX:-${MAYBE7:-7here})/foo',
    "MAYBE9": '$(HOME:+blach.${MAYBE10:-10here})/foo',
}

ENV3 = {
    "HOME": '/usr/garyw',
    "APPS-DIR": '$(HOME)/apps',
    "ANOTHER": '$(APPS-DIR)/theap',
    "TWO": '$(HOME) and $(APPS-DIR)',
    "MAYBE1": '$(HOAX)/foo',
    "MAYBE10": '$(HOAX:-$(MAYBE11:-11here))/foo',
    "MAYBE11": 'to-$(MAYBE10:-10gone)',              # will trigger recursion
    "MAYBE12": 'circA-$(MAYBE13:-10gone)',           # will trigger recursion
    "MAYBE13": 'circB-$(MAYBE12:-10gone)',
    "MAYBE2": '$(HOAX:-blach)/footwo',
    "MAYBE3": '$(HOAX:+blach)/foo',
    "MAYBE4": '$(HOME:-blach)/foo',
    "MAYBE5": '$(HOME:+blach)/foo',
    "MAYBE6": '$(HOAX:-$(MAYBE2))/foo',
    "MAYBE7": '$(HOME:+blach.${MAYBE8:+8here})/foo',
    "MAYBE8": '$(HOAX:-${MAYBE7:-7here})/foo',
    "MAYBE9": '$(HOME:+blach.${MAYBE10:-10here})/foo',
}

RESULT3 = "[('ANOTHER', '/usr/garyw/apps/theap'), ('APPS-DIR', '/usr/garyw/apps'), ('HOME', '/usr/garyw'), ('MAYBE1', '$(HOAX)/foo'), ('MAYBE10', 'to-$(HOAX:-$(MAYBE11:-11here))/foo/foo'), ('MAYBE11', 'to-$(HOAX:-$(MAYBE11:-11here))/foo'), ('MAYBE12', 'circA-circB-circA-$(MAYBE13:-10gone)'), ('MAYBE13', 'circB-circA-$(MAYBE13:-10gone)'), ('MAYBE2', 'blach/footwo'), ('MAYBE3', '/foo'), ('MAYBE4', '/usr/garyw/foo'), ('MAYBE5', 'blach/foo'), ('MAYBE6', 'blach/footwo/foo'), ('MAYBE7', 'blach.8here/foo'), ('MAYBE8', 'blach.8here/foo/foo'), ('MAYBE9', 'blach.to-$(HOAX:-$(MAYBE11:-11here))/foo/foo/foo'), ('TWO', '/usr/garyw and /usr/garyw/apps')]"

ENV4 = {
    "HOME": '/usr/garyw',
    "APPS-DIR": '$(HOME)/apps',
    "ANOTHER": '$(APPS-DIR)/theap',
    "TWO": '$(HOME) and $(APPS-DIR)',
    "MAYBE1": '$(HOAX)/foo',
    "MAYBE10": '$(HOAX:-$(MAYBE11:-11here))/foo',
    "MAYBE11": 'to-$(MAYBE10:+10gone)',             # breaks recursion
    "MAYBE12": 'circA-$(MAYBE13:+10gone)',          # breaks recursion
    "MAYBE13": 'circB-$(MAYBE12:-10gone)',
    "MAYBE2": '$(HOAX:-blach)/footwo',
    "MAYBE3": '$(HOAX:+blach)/foo',
    "MAYBE4": '$(HOME:-blach)/foo',
    "MAYBE5": '$(HOME:+blach)/foo',
    "MAYBE6": '$(HOAX:-$(MAYBE2))/foo',
    "MAYBE7": '$(HOME:+blach.${MAYBE8:+8here})/foo',
    "MAYBE8": '$(HOAX:-${MAYBE7:-7here})/foo',
    "MAYBE9": '$(HOME:+blach.${MAYBE10:-10here})/foo',
    "UBERNEST": 'nest:$(HOME:+$(HOAX:-inside${TWO})) and:$(ANOTHER)',
    "UBERNEST-NOT": 'nest:$(HOME:+$(HOAX:-inside$(TWO))) and:$(ANOTHER)',
}

RESULT4 = "[('ANOTHER', '/usr/garyw/apps/theap'), ('APPS-DIR', '/usr/garyw/apps'), ('HOME', '/usr/garyw'), ('MAYBE1', '$(HOAX)/foo'), ('MAYBE10', 'to-10gone/foo'), ('MAYBE11', 'to-10gone'), ('MAYBE12', 'circA-10gone'), ('MAYBE13', 'circB-circA-10gone'), ('MAYBE2', 'blach/footwo'), ('MAYBE3', '/foo'), ('MAYBE4', '/usr/garyw/foo'), ('MAYBE5', 'blach/foo'), ('MAYBE6', 'blach/footwo/foo'), ('MAYBE7', 'blach.8here/foo'), ('MAYBE8', 'blach.8here/foo/foo'), ('MAYBE9', 'blach.to-10gone/foo/foo'), ('TWO', '/usr/garyw and /usr/garyw/apps'), ('UBERNEST', 'nest:inside/usr/garyw and /usr/garyw/apps and:/usr/garyw/apps/theap'), ('UBERNEST-NOT', 'nest:$(HOAX:-inside/usr/garyw and /usr/garyw/apps) and:/usr/garyw/apps/theap')]"

ENV4a = {
    'PATH': '/bin',
    'THEREPATH': '/there',
}

CONFIG4a = {
    'env_set': {
        'PATH': '/usr/local/bin:$(PATH)'
    }
}

CONFIG4c = {
    'env_set': {
        'PATH': '/usr/python/bin:$(PATH)',
        'PYPATH': '/pythonlibs:$(PYPATH)',
        'MISCPATH': '/mislibs$(MISCPATH:+:)$(MISCPATH)',
        'PYAGAIN': '/mislibs$(PYPATH:+:)$(PYPATH)',
        'THEREPATH': '/mislibs$(THEREPATH:+:)$(THEREPATH)',
    }
}

ENV7 = {
    "FIRSTPORT": '999',
    "ALTPORT": "777",
}

CONFIG7a = {
    'env_set': {
        "FIRSTPORT": '$(FIRSTPORT:-443)',
        "SECONDPORT": '$(SECONDPORT:-443)',
        "THIRDPORT": '$(FIRSTPORT:-443)',
        "FOURTHPORT": '$(ALTPORT:-443)',
    }
}

RESULT7 = "[('ALTPORT', '777'), ('FIRSTPORT', '999'), ('FOURTHPORT', '777'), ('SECONDPORT', '443'), ('THIRDPORT', '999')]"

def printdict(d):
    for k in sorted(d.keys()):
        print("{0} = {1}".format(k,d[k]))

def canonical(d):
    return str([(k,d[k]) for k in sorted(d.keys())])

class TestEnvOrder(unittest.TestCase):

    def test_expand1(self):
        env = Environment(from_env = ENV1).expanded()
        envstr = canonical(env)
        #print('RESULT1 = "' + envstr + '"')
        self.assertEqual(envstr, RESULT1)

    def test_expand2(self):
        env = Environment(from_env = ENV2).expanded()
        envstr = canonical(env)
        #print('RESULT2 = "' + envstr + '"')
        self.assertEqual(envstr, RESULT2)

    def test_expand3(self):
        env = Environment(from_env = ENV3).expanded()
        #printdict(env)
        envstr = canonical(env)
        #print('RESULT3 = "' + envstr + '"')
        self.assertEqual(envstr, RESULT3)

    def test_expand4(self):
        env = Environment(from_env = ENV4).expanded()
        #printdict(env)
        envstr = canonical(env)
        #print('RESULT4 = "' + envstr + '"')
        self.assertEqual(envstr, RESULT4)

    def test_expand5(self):
        "Try simple expansion"
        env = Environment(from_env = ENV4).expanded()
        self.assertEqual(env.expand("hello $(UBERNEST)"), 
                         "hello nest:inside/usr/garyw and /usr/garyw/apps and:/usr/garyw/apps/theap")
        self.assertEqual(env.expand("hello $(MAYBE5) and $(MAYBE4)"), "hello blach/foo and /usr/garyw/foo")
        self.assertEqual(env.expand("hello $(MAYBE5:+$(MAYBE5)b) and $(MAYBE41)"), "hello blach/foob and $(MAYBE41)")
        self.assertEqual(env.expand("hello $(MAYBE5:+$(MAYBE5)b) and $(MAYBE41:-gone$(MAYBE4))"), 
                         "hello blach/foob and gone/usr/garyw/foo")

    def test_expand6(self):
        "Try self-referential expansions"
        enva = Environment(ENV4a, CONFIG4a)
        self.assertEqual(canonical(enva.expanded()),
                         "[('PATH', '/usr/local/bin:/bin'), ('THEREPATH', '/there')]")
        envb = Environment(enva)
        self.assertEqual(canonical(envb.expanded()),
                         "[('PATH', '/usr/local/bin:/bin'), ('THEREPATH', '/there')]")
        envc = Environment(envb, CONFIG4c)
        self.assertEqual(canonical(envc.expanded()),
                         "[('MISCPATH', '/mislibs'), ('PATH', '/usr/python/bin:/usr/local/bin:/bin'), ('PYAGAIN', '/mislibs:/pythonlibs:'), ('PYPATH', '/pythonlibs:'), ('THEREPATH', '/mislibs:/there')]")

    def test_expand7(self):
        "Test some self-referential anomalies"
        env = Environment(ENV7, CONFIG7a).expanded()
        envstr = canonical(env)
        #print('RESULT7 = "' + envstr + '"')
        self.assertEqual(envstr, RESULT7)

if __name__ == '__main__':
    unittest.main()
