from prefix import *

from chaperone.cutil.misc import Environment

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


def printdict(d):
    for k in sorted(d.keys()):
        print("{0} = {1}".format(k,d[k]))

class TestEnvOrder(unittest.TestCase):

    def test_expand1(self):
        env = Environment(from_env = ENV1).expanded()
        envstr = str([(k,env[k]) for k in sorted(env.keys())])
        #print('RESULT1 = "' + envstr + '"')
        self.assertEqual(envstr, RESULT1)

    def test_expand2(self):
        env = Environment(from_env = ENV2).expanded()
        envstr = str([(k,env[k]) for k in sorted(env.keys())])
        #print('RESULT2 = "' + envstr + '"')
        self.assertEqual(envstr, RESULT2)

    def test_expand3(self):
        env = Environment(from_env = ENV3).expanded()
        #printdict(env)
        envstr = str([(k,env[k]) for k in sorted(env.keys())])
        #print('RESULT3 = "' + envstr + '"')
        self.assertEqual(envstr, RESULT3)

    def test_expand4(self):
        env = Environment(from_env = ENV4).expanded()
        #printdict(env)
        envstr = str([(k,env[k]) for k in sorted(env.keys())])
        #print('RESULT4 = "' + envstr + '"')
        self.assertEqual(envstr, RESULT4)

if __name__ == '__main__':
    unittest.main()
