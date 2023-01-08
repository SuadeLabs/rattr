import sys as _sys
from argparse import (
    _UNRECOGNIZED_ARGS_ATTR,
    SUPPRESS,
    ArgumentError,
    ArgumentParser,
    Namespace,
)
from argparse import _AppendAction as AppendAction
from argparse import _AppendConstAction as AppendConstAction
from argparse import _copy_items
from argparse import _CountAction as CountAction
from argparse import _ExtendAction as ExtendAction
from argparse import _StoreAction as StoreAction
from argparse import _StoreConstAction as StoreConstAction
from argparse import _StoreFalseAction as StoreFalseAction
from argparse import _StoreTrueAction as StoreTrueAction


class _Namespace(Namespace):
    def __init__(self, *args, **kwargs):
        self.explicitly_set_args = set()
        super(_Namespace, self).__init__(*args, **kwargs)


class _StoreAction(StoreAction):
    def __init__(self, *args, **kwargs):
        super(_StoreAction, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        namespace.explicitly_set_args.add(self.dest)


class _StoreConstAction(StoreConstAction):
    def __init__(self, *args, **kwargs):
        super(_StoreConstAction, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        namespace.explicitly_set_args.add(self.dest)


class _StoreTrueAction(StoreTrueAction):
    def __init__(self, *args, **kwargs):
        super(_StoreTrueAction, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        namespace.explicitly_set_args.add(self.dest)


class _StoreFalseAction(StoreFalseAction):
    def __init__(self, *args, **kwargs):
        super(_StoreFalseAction, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)
        namespace.explicitly_set_args.add(self.dest)


class _AppendAction(AppendAction):
    def __init__(self, *args, **kwargs):
        super(_AppendAction, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None)
        items = _copy_items(items)
        items.append(values)
        setattr(namespace, self.dest, items)
        namespace.explicitly_set_args.add(self.dest)


class _AppendConstAction(AppendConstAction):
    def __init__(self, *args, **kwargs):
        super(_AppendConstAction, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None)
        items = _copy_items(items)
        items.append(self.const)
        setattr(namespace, self.dest, items)
        namespace.explicitly_set_args.add(self.dest)


class _CountAction(CountAction):
    def __init__(self, *args, **kwargs):
        super(_CountAction, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        count = getattr(namespace, self.dest, None)
        if count is None:
            count = 0
        setattr(namespace, self.dest, count + 1)
        namespace.explicitly_set_args.add(self.dest)


class _ExtendAction(ExtendAction):
    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None)
        items = _copy_items(items)
        items.extend(values)
        setattr(namespace, self.dest, items)
        namespace.explicitly_set_args.add(self.dest)


class _ArgumentParser(ArgumentParser):
    def __init__(self, *args, **kwargs):
        super(_ArgumentParser, self).__init__(*args, **kwargs)
        self.register("action", None, _StoreAction)
        self.register("action", "store", _StoreAction)
        self.register("action", "append", _AppendAction)
        self.register("action", "store_const", _StoreConstAction)
        self.register("action", "store_true", _StoreTrueAction)
        self.register("action", "store_false", _StoreFalseAction)
        self.register("action", "append_const", _AppendConstAction)
        self.register("action", "count", _CountAction)
        self.register("action", "extend", _ExtendAction)

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            # args default to the system args
            args = _sys.argv[1:]
        else:
            # make sure that args are mutable
            args = list(args)

        # default Namespace built from parser defaults
        if namespace is None:
            namespace = _Namespace()

        # add any action defaults that aren't present
        for action in self._actions:
            if action.dest is not SUPPRESS:
                if not hasattr(namespace, action.dest):
                    if action.default is not SUPPRESS:
                        setattr(namespace, action.dest, action.default)

        # add any parser defaults that aren't present
        for dest in self._defaults:
            if not hasattr(namespace, dest):
                setattr(namespace, dest, self._defaults[dest])

        # parse the arguments and exit if there are any errors
        if self.exit_on_error:
            try:
                namespace, args = self._parse_known_args(args, namespace)
            except ArgumentError as err:
                self.error(str(err))
        else:
            namespace, args = self._parse_known_args(args, namespace)

        if hasattr(namespace, _UNRECOGNIZED_ARGS_ATTR):
            args.extend(getattr(namespace, _UNRECOGNIZED_ARGS_ATTR))
            delattr(namespace, _UNRECOGNIZED_ARGS_ATTR)
        return namespace, args
