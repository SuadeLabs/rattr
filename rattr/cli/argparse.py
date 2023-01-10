import sys as _sys
from argparse import (
    _UNRECOGNIZED_ARGS_ATTR,
    SUPPRESS,
    ArgumentError,
    ArgumentParser,
    Namespace,
)


class _ArgumentParser(ArgumentParser):
    def __init__(self, *args, **kwargs):
        exit_on_error = kwargs.pop("exit_on_error", True)
        # Make sure to remove 'exit_on_error' from 'kwargs'
        # when calling parent constructor since Python
        # 3.7 and 3.8 versions of 'ArgumentParser' don't
        # expect it.
        super(_ArgumentParser, self).__init__(*args, **kwargs)
        # Save 'exit_on_error' as an instance attribute
        # AFTER calling parent constructor. This also
        # ensures that we overwrite default 'exit_on_error'
        # instance attributes for Python 3.9+ versions of
        # ArgumentParser.
        self.exit_on_error = exit_on_error

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            # args default to the system args
            args = _sys.argv[1:]
        else:
            # make sure that args are mutable
            args = list(args)

        # default Namespace built from parser defaults
        if namespace is None:
            namespace = Namespace()

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

    def exit(self, status=0, message=None):

        if not self.exit_on_error:
            raise ArgumentError(None, message)

        if message:
            self._print_message(message, _sys.stderr)
        if self.exit_on_error:
            _sys.exit(status)
