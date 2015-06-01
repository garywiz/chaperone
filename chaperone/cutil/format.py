def fstr(s):
    if s is None:
        return '-'
    if isinstance(s, bool):
        return str(s).lower()
    return str(s)

class TableFormatter(list):

    """
    A quick formatting class which allows you to build a table, then output it
    neatly with columns and headings.
    """

    attributes = None
    headings = None
    _sortfield = None

    def __init__(self, *args, sort=None):
        self.attributes = tuple(isinstance(a, tuple) and a[1] or a for a in args)
        self.headings = tuple(isinstance(a, tuple) and a[0] or a for a in args)
        self._hsize = list(len(h) for h in self.headings)
        if sort in self.attributes:
            self._sortfield = self.attributes.index(sort)

    def add_rows(self, rows):
        for r in rows:
            row = tuple(getattr(r, attr, None) for attr in self.attributes)
            for i in range(len(row)):
                self._hsize[i] = max(self._hsize[i], len(fstr(row[i])))
            self.append(row)

    def get_formatted_data(self):
        if self._sortfield is not None:
            rows = sorted(self, key=lambda r: r[self._sortfield])
        else:
            rows = self

        hz = self._hsize
        fieldcount = range(len(hz))
        sep = "  "
        dividers = tuple("-" * hz[i] for i in fieldcount)

        return "\n".join(sep.join(fstr(row[i]).ljust(hz[i])
                                  for i in fieldcount) 
                         for row in [self.headings] + [dividers] + rows)
