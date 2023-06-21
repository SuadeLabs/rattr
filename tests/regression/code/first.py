from rattr.analyser.annotations import rattr_ignore, rattr_results

from .module.foo import my_lib_function


def my_foo(x):
    return x.attr


def some_function(x, y, z):
    x.some_thing = my_foo(x) + my_foo(y) + my_foo(z)

    if x.is_whatever:
        x.another_thing = x.whatever + 10
    else:
        x.another_thing = 0

    return x


@rattr_ignore()
def this_should_not_appear_in_the_results(foo):
    return foo.bar + foo.baz


@rattr_results(
    gets={
        "foobar.x",
        "foobar.y",
        "foobar.z",
    },
    sets={
        "some_other_var.attr",
    },
    calls=[
        ("this_should_not_appear_in_the_results()", (["foobar"], {})),
        ("some_function()", ([], {"a": "@Int", "b": "@Int", "c": "foobar"})),
    ],
)
def overwrite_me(foobar):
    print(foobar.baz)


def i_use_a_lib_function(data):
    good_data = [datum for datum in data if my_lib_function(datum)]

    if len(good_data):
        raise Exception(f"problem with {data[0].goodness}, ...")

    return good_data
