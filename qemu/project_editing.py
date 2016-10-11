from common import \
    gen_class_args, \
    InverseOperation

from importlib import \
    import_module

class ProjectOperation(InverseOperation):
    def __init__(self, project, *args, **kw):
        InverseOperation.__init__(self, *args, **kw)

        self.p = project

    """
    The InverseOperation defines no read or write sets. Instead it raises an
    exception. As this is a base class of all machine editing operations it
    should define the sets. The content of the sets is to be defined by
    subclasses.
    """

    def __write_set__(self):
        return []

    def __read_set__(self):
        return []

class QemuObjectCreationHelper(object):
    """ The class helps implement Qemu model object creation operations. It
    automates handling of arguments for __init__ method of created objects.
    The helper class __init__ methods gets lists of handled class __init__
    arguments. Then it moves them from kw dictionary to self. The new method of
    the helper class creates object of handled class with this arguments. """

    def __init__(self, class_name, kw):
        self.nc = class_name

        for n in self.al + self.kwl:
            if n in kw:
                setattr(self, n, kw.pop(n))

    @property
    def nc(self):
        return self._nc[5:]

    @nc.setter
    def nc(self, class_name):
        if class_name:
            self._nc = "qemu." + class_name
            self.al, self.kwl = gen_class_args(self._nc)
        else:
            self._nc = "qemu."
            self.al, self.kwl = [], []

    def new(self):
        segments = self._nc.split(".")
        module, class_name = ".".join(segments[:-1]), segments[-1]
        Class = getattr(import_module(module), class_name)

        args = []
        for n in self.al:
            try:
                val = getattr(self, n)
            except AttributeError:
                val = None
            args.append(val)

        kw = {}
        for n in self.kwl:
            try:
                val = getattr(self, n)
            except AttributeError:
                pass
            else:
                kw[n] = val

        return Class(*args, **kw)

class DescriptionOperation(ProjectOperation):
    def __init__(self, description, *args, **kw):
        ProjectOperation.__init__(self, *args, **kw)
        # desc is cached value, the description identifier is desc_name
        self.desc = description
        self.desc_name = str(self.desc.name)

