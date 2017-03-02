from common import \
    mlget as _, \
    gen_class_args, \
    get_class_defaults, \
    InverseOperation

from inspect import \
    getmro

from six import \
    binary_type, \
    string_types, \
    text_type, \
    integer_types

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

def none_import_hepler(val, helper):
    return None

basic_types = [
    text_type,
    binary_type,
    bool
] + list(integer_types) + list(string_types)

def basic_import_helper(val, helper):
    return type(val)(val)

class QemuObjectCreationHelper(object):
    """ The class helps implement Qemu model object creation operations. It
    automates handling of arguments for __init__ method of created objects.
    The helper class __init__ method gets lists of handled class __init__
    arguments. Then it moves them from kw dictionary to self. They are stored
    within tuples
    as attributes of the helper class instance. Names of the attributes are
    built using user defined prefix and names of corresponding handled class
    __init__ arguments. The 'new' method of the helper class creates object of
    handled class with this arguments.

    Supported argument value types are:
        bool
        int
        long
        str
        unicode
    None values are imported too.

    Argument describing tuple consists of:
        0: original argument value tuple
        1: an internal value that codes original one
    For supported types the internal value is just copy of original one.

    List of supported value types could be extended by defining two helpers
per each new type:
    mytype_import_helper
    mytype_export_helper

    Import helper of one argument is given a value of type to support and
should return value that will be given to export helper during object creation.
The export helper of one argument is given value returned by import helper
and should return a value appropriate for class __init__ method.

    Note that, it is possible to use class methods and/or function with default
arguments to pass extra data to helper.

    To get effect the methods should be added to:

    value_export_helpers,
    value_import_helpers

dictionaries of QemuObjectCreationHelper instance with new type as key. The
super class could be used as key. inspect.getmro class list order is used to
choose the helper.

    The type of intermediate value (returned by import helper, stored in 1-th
slot of the tuple) is not restricted.
    """

    value_export_helpers = {}

    value_import_helpers = {
        type(None): none_import_hepler
    }
    for basic_type in basic_types:
        value_import_helpers[basic_type] = basic_import_helper

    def __init__(self, class_name, kw, arg_name_prefix = ""):
        self.nc = class_name

        if arg_name_prefix and arg_name_prefix[0] == '_':
            """
            If attribute is set like o.__my_attr. The getattr(o, "__my_attr")
will return AttributeError while the attribute is accessible by o.__my_attr
expression. The valid attribute name for getattr is something about
_MyClassName__my_attr in this case. It is Python internals...
            """
            raise Exception( """Prefix for target constructor arguments storing\
 should not start with '_'."""
            )

        self.prefix = arg_name_prefix

        for n in self.al + self.kwl:
            if n in kw:
                val = kw.pop(n)
                try:
                    valdesc = self.import_value(val)
                except QemuObjectCreationHelper.CannotImport:
                    raise Exception("""Import values from kw is only supported
for types: %s""" % ", ".join(t.__name__ for t in self.value_import_helpers)
                    )
                setattr(self, self.prefix + n, valdesc)

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

    def export_value(self, _type, val):
        for t in getmro(_type):
            try:
                helper = self.value_export_helpers[t]
            except KeyError:
                continue
            else:
                return helper(val, self)
        return val

    def new(self):
        segments = self._nc.split(".")
        module, class_name = ".".join(segments[:-1]), segments[-1]
        Class = getattr(import_module(module), class_name)

        args = []
        for n in self.al:
            try:
                valdesc = getattr(self, self.prefix + n)
            except AttributeError:
                val = None
            else:
                val = self.export_value(*valdesc)
            args.append(val)

        kw = {}
        for n in self.kwl:
            try:
                valdesc = getattr(self, self.prefix + n)
            except AttributeError:
                pass
            else:
                val = self.export_value(*valdesc)
                kw[n] = val

        return Class(*args, **kw)

    class CannotImport (Exception):
        pass

    def import_value(self, val):
        for t in getmro(type(val)):
            try:
                helper = self.value_import_helpers[t]
            except KeyError:
                continue
            else:
                break
        else:
            raise QemuObjectCreationHelper.CannotImport()
        return (t, helper(val, self))

    """ The method imports from origin values for arguments of current class
__init__ method. By default the method uses getattr method. The attrinutes names
are assumed to be same as names of __init__ arguments. It is incorrect the
the origin object class can provide __get_init_arg_val__ method. The method
should be getattr-like:
    1-st argument is the reference to the origin
    2-nd argument is name of __init__ argument the value for which should be
returned.

Basic example:

    def __get_init_arg_val__(self, arg_name):
        return getattr(self, arg_name)

The behaviour in this case is same as if no __get_init_arg_val__ method is
defined.

    The import_argument_values does support only types for which a helper pair
is specified (including base supported types). If unsupported value is among
positional arguments then an exception is raised. If it is among keyword
arguments then it is skipped.
    """

    def import_argument_values(self, origin):
        try:
            import_method = type(origin).__get_init_arg_val__
        except AttributeError:
            import_method = getattr

        for attr_name in self.al:
            try:
                val = import_method(origin, attr_name)
            except AttributeError:
                raise Exception(
                    "Cannot import value of argument with name '%s'" % attr_name
                )

            try:
                valdesc = self.import_value(val)
            except QemuObjectCreationHelper.CannotImport:
                # print "skipping %s of type %s" % (
                #    attr_name, type(val).__name__
                # )
                continue

            setattr(self, self.prefix + attr_name, valdesc)

        def_args = get_class_defaults(self._nc)

        for attr_name in self.kwl:
            try:
                val = import_method(origin, attr_name)
            except AttributeError:
                # values of arguments with defaults are not important enough.
                continue

            # do not store default values
            if def_args[attr_name] == val:
                continue

            try:
                valdesc = self.import_value(val)
            except QemuObjectCreationHelper.CannotImport:
                # print "skipping %s of type %s" % (
                #    attr_name, type(val).__name__
                # )
                continue

            setattr(self, self.prefix + attr_name, valdesc)

    def set_with_origin(self, origin):
        self.nc = type(origin).__name__

        self.import_argument_values(origin)

class POp_AddDesc(ProjectOperation, QemuObjectCreationHelper):
    def __init__(self, desc_class_name, desc_name, *args, **kw):
        if not "directory" in kw:
            kw["directory"] = ""
        kw["name"] = desc_name

        QemuObjectCreationHelper.__init__(self, desc_class_name, kw, "desc_")
        ProjectOperation.__init__(self, *args, **kw)

        self.name = desc_name

    def __backup__(self):
        pass

    def __do__(self):
        self.p.add_description(self.new())

    def __undo__(self):
        desc = next(self.p.find(name = self.name))

        """ It is unexpected way to type independently check for the description
        is empty. """
        if desc.__children__():
            raise Exception("Not empty description removing attempt.")

        self.p.remove_description(desc)

    def __write_set__(self):
        return ProjectOperation.__write_set__(self) + [
            str(self.name)
        ]

    def get_kind_str(self):
        return (_("machine draft")
                if "MachineNode" in self.nc
            else _("system bus device template")
                if "SysBusDeviceDescription" in self.nc
            else _("PCI bus device template")
                if "PCIExpressDeviceDescription" in self.nc
            else _("an auto generated code")
        )

    def __description__(self):
        return _("'%s' QOM object addition (%s).") % (
            self.name,
            self.get_kind_str()
        )

class POp_DelDesc(POp_AddDesc):
    def __init__(self, desc_name, *args, **kw):
        POp_AddDesc.__init__(self, "QOMDescription", desc_name, *args, **kw)

    def __backup__(self):
        desc = next(self.p.find(name = self.name))
        self.set_with_origin(desc)

    __do__ = POp_AddDesc.__undo__
    __undo__ = POp_AddDesc.__do__

    def __description__(self):
        return _("'%s' QOM object deletion (%s).") % (
            self.name,
            self.get_kind_str()
        )

class DescriptionOperation(ProjectOperation):
    def __init__(self, description, *args, **kw):
        ProjectOperation.__init__(self, *args, **kw)

        self.desc_name = str(description.name)

    def find_desc(self):
        return next(self.p.find(name = self.desc_name))
