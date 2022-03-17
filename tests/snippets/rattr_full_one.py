"""Rattr quasi-end-to-end test #1."""

import os.path as path
from math import pi


def a_normal_function(arg_one):
    if arg_one.attr > 100:
        raise ValueError("That is too high!")
    return arg_one.attr / 100


def update_attribute(obj, new_value, config=None):
    if config.get("debug"):
        print("Updating .target on", obj.name)

    obj.target = new_value


@circle_condition
def area(circle):
    return pi * circle.radius * circle.radius


@datatype_condition
def is_a_foorbar(datatype, unused_arg):
    filepath = datatype.target_file

    if not path.isfile(filepath):
        return False

    return datatype.is_foo and datatype.is_bar


@assignee_condition
def make_an_assignment(assignee, value):
    assignee.attr = value
