from prefix import *

from cutil.config import ServiceDict

OT1 = {
    'one.service': { },
    'two.service': { 'group': 'foobar', 'after': 'default' },
    'three.service': { 'group': 'system', 'before': 'four.service' },
    'four.service': { 'group': 'system', 'before': 'default' },
    'five.service': { },
    'six.service': { 'after': 'seven.service' },
    'seven.service': { }
}

OT2 = {
    'one.service': { },
    'two.service': { 'group': 'foobar', 'after': 'default' },
    'three.service': { 'group': 'system', 'before': 'two.service' },
    'four.service': { 'group': 'system', 'before': 'three.service' },
    'five.service': { },
    'six.service': { },
    'seven.service': { }
}

OT3 = {
    'one.service': { },
    'two.service': { 'before': 'default' },
    'three.service': { 'group': 'system', 'before': 'four.service' },
    'four.service': { 'group': 'system', 'before': 'default' },
    'five.service': { 'before': 'two.service' },
    'six.service': { 'after': 'seven.service' },
    'seven.service': { }
}

def printlist(title, d):
    return
    print(title)
    for item in d:
        print("  ", item)

def checkorder(result, *series):
    """
    Checks to be sure that the items listed in 'series' are in order in the result set.
    """
    results = [r.name for r in result]
    indexes = list(map(lambda item: results.index(item+".service"), series))
    for n in range(len(indexes)-1):
        if indexes[n] > indexes[n+1]:
            return False
    return True

class TestServiceOrder(unittest.TestCase):

    def test_order1(self):
        sc = ServiceDict(OT1.items())
        slist = sc.get_startup_list()
        printlist("startup list: ", slist)
        self.assertTrue(checkorder(slist, 'three', 'four', 'seven', 'six', 'two'))
        self.assertTrue(checkorder(slist, 'three', 'one', 'two'))

    def test_order2(self):
        sc = ServiceDict(OT2.items())
        slist = sc.get_startup_list()
        printlist("startup list: ", slist)
        self.assertTrue(checkorder(slist, 'four', 'three', 'two'))

    def test_order3(self):
        sc = ServiceDict(OT3.items())
        self.assertRaisesRegex(Exception, '^Circular', lambda: sc.get_startup_list())

if __name__ == '__main__':
    unittest.main()
