from prefix import *

from chaperone.cutil.events import EventSource

class handlers:
    
    def __init__(self):
        self.results = list()

    def handler1(self, val):
        self.results.append("handler1:" + val)

    def handler2(self, val):
        self.results.append("handler2:" + val)

    def handler3(self, val):
        self.results.append("handler3:" + val)

class TestEvents(unittest.TestCase):

    def setUp(self):
        self.h = handlers()
        self.e = EventSource()

    def test_event1(self):
        self.e.add(onH1 = self.h.handler1)
        self.e.add(onH1 = self.h.handler1)
        self.e.onH1("First trigger")
        self.e.onH1("Second trigger")
        self.assertEqual(self.h.results,
                         ['handler1:First trigger', 'handler1:First trigger', 'handler1:Second trigger', 'handler1:Second trigger'])
        self.e.remove(onH1 = self.h.handler1)
        self.e.onH1("Third trigger")
        self.e.remove(onH1 = self.h.handler1)
        self.e.onH1("Fourth trigger")
        self.assertEqual(self.h.results,
                         ['handler1:First trigger', 'handler1:First trigger', 'handler1:Second trigger', 'handler1:Second trigger', 'handler1:Third trigger'])

    def test_event2(self):
        self.e.add(onH1 = self.h.handler1)
        self.assertRaisesRegex(TypeError, 'but 3 were given', lambda: self.e.onH1("arg1", "arg2"))

    def test_event3(self):
        self.e.add(onMulti = self.h.handler1)
        self.e.add(onMulti = self.h.handler2)
        self.e.onMulti("TWO")
        self.e.add(onMulti = self.h.handler3)
        self.e.onMulti("THREE")
        self.assertEqual(self.h.results,
                         ['handler1:TWO', 'handler2:TWO', 'handler1:THREE', 'handler2:THREE', 'handler3:THREE'])
        self.e.remove(onMulti = self.h.handler2)
        self.e.onMulti("AFTER-REMOVE")
        self.assertEqual(self.h.results,
                         ['handler1:TWO', 'handler2:TWO', 'handler1:THREE', 'handler2:THREE', 'handler3:THREE', 'handler1:AFTER-REMOVE', 'handler3:AFTER-REMOVE'])
        self.e.remove(onMulti = self.h.handler1)
        self.e.remove(onMulti = self.h.handler2)
        self.e.remove(onMulti = self.h.handler3)
        self.e.onMulti("EMPTY")
        self.assertEqual(self.h.results,
                         ['handler1:TWO', 'handler2:TWO', 'handler1:THREE', 'handler2:THREE', 'handler3:THREE', 'handler1:AFTER-REMOVE', 'handler3:AFTER-REMOVE'])

if __name__ == '__main__':
    unittest.main()
