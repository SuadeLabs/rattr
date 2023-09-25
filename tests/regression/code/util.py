from enum import Enum

from rattr.analyser.annotations import rattr_results

from .first import some_function
from .module.foo import my_lib_function


def recursive(x):
    if not x.xs:
        return 0

    if len(x.xs) == 1:
        return x.xs[0].single_value

    return sum(_x.multivalue for _x in x.xs)


def _one_fn(arg_a, arg_b):
    return arg_a.attr + some_function(arg_b.some_thing, 1, 2)


def _two_fn(first, second):
    return _one_fn(second, first)


def _three_fn(arg_a, arg_b):
    return sum(
        [
            (getattr(arg_a, "first", 0) * getattr(arg_b, "first", 0))
            + (getattr(arg_a, "second", 0) * getattr(arg_b, "second", 0))
            + (getattr(arg_a, "third", 0) * getattr(arg_b, "third", 0))
        ]
    )


def _four_fn(arg_a, arg_b=None):
    try:
        my_lib_function(arg_a)
    except Exception:
        return 0
    return arg_a.accessed_in_four


class Things(Enum):
    one = 1
    two = 2
    three = 3


_functions_by_thing = {
    Things.one: _one_fn,
    Things.two: _two_fn,
    Things.three: _three_fn,
    # Things.four: _four_fn,  # this is skipped but will be in results, deliberately
}


@rattr_results(
    gets={
        "data.discriminator",
        "data.wrapped",
    },
    calls=[
        ("_one_fn()", (["data.wrapped"], {})),
        ("_two_fn()", (["data.wrapped"], {})),
        ("_three_fn()", (["data.wrapped"], {})),
        ("_four_fn()", (["data.wrapped"], {})),
    ],
)
def dispatcher(data):
    return _functions_by_thing[data.discriminator](data.wrapped)
