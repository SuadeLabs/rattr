from argparse import (
    _StoreAction as StoreAction,
    _AppendAction as AppendAction,
    _StoreConstAction as StoreConstAction,
    _StoreTrueAction as StoreTrueAction,
    _StoreFalseAction as StoreFalseAction,
    _AppendConstAction as AppendConstAction,
    _CountAction as CountAction,
    _ExtendAction as ExtendAction,
    Namespace,
    ArgumentParser,
    _copy_items,
)


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
