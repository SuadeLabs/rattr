# **Ratter**

Ratter is a tool to determine attribute usage in Python functions.


# Developer Notes

## Use of Undocumented Behaviour

In `ratter/analyser/types.py` several `Union` types are defined for
convenience. In Python 3.8 to check if the variable `a` is an instance of any
of the types within the `Union` the `typing` module provides `get_args` i.e.
one would use `isinstance(a, get_args(UnionTypeName))`. However, this function
is not provided in Python 3.7 and so the undocumented attribute `__args__` of
the `UnionTypeName` must be used i.e. `isinstance(a, UnionTypeName.__args__)`.
As this is undocumented it should be changed when we upgrade to Python 3.8+
(and `$EDITOR` will not syntax highlight or tab-complete it).


## Annotations

Ratter provides the ability to annotate functions in the target file such that
they may be ignored completely, ignored with their results determined manually,
etc. Additionally, each assertor may provide it's own annotations to ignore
and/or define behaviour.

General Ratter annotations are located in `ratter/analyser/annotations.py` and
assertor specific annotations are to be added by the assertion developer --
however they should be placed in the file containing the `Assertor` class.

### Annotation Format

Annotations should take the form `ratter_<annotation_name>` to avoid namespace
conflicts in importing code.

### Detecting and Parsing Annotations

The `ratter/analyser/utils.py` file provides the following annotation utility
functions:

* `has_annotation(name: str, fn: ast.FunctionDef) -> bool`
* `get_annotation(name: str, fn: ast.FunctionDef) -> Optional[ast.AST]`
* `parse_annotation(name: str, fn: ast.FunctionDef) -> Dict[str, Any]`
* `parse_ratter_results_from_annotation(fn: ast.FunctionDef) -> Dict[str, Literal[...]]:`
* `safe_eval(expr: ast.expr, culprit: Optional[ast.AST]) -> Union[Literal, Iterable[Iterable[...[Literal]]]]`
* `is_name(name: Any) -> bool`
* `is_set_of_names(set_of_names: Any) -> bool`
* `is_args(args: Any) -> bool`


### Provided Annotations

Annotation Name                             | Location
:-------------------------------------------|:--------------------------------
`ratter_ignore`                             | `ratter/analyser/annotations.py`
`ratter_results(<results>)`                 | `ratter/analyser/annotations.py`

### Results Annotation Grammar

```python

@ratter_results(
    sets={"a", "b.attr"},
    calls=[
        ("callee_function", (["arg", "another"], {"kwarg": "some_var"}))
    ]
)
def decorated_function(...):
    # ...

```

Any argument to the decorator can be omitted and a default value will be used.


## Known Issues

Nested functions are not currently analysed properly, functions containing
nested functions must be annotated manually.

Comprehensions are not fully analysed, should be solvable by the same approach
as nested functions -- "un-nest" them.


--------------------------------------------------------------------------------


# Usage Notes

See `python ratter -h`.


## Security

### Caching and Serialisation

Both the `pickle` and `jsonpickle` libraries, used for serialisation in Python,
have known security issues which are inherited by Ratter (`jsonpickle` is used
s.t. the cache files remain human readable). As such you should not allow cache
files to be loaded from untrusted sources.

If you are concerned about security, or you are unable to ensure cache files
are trusted, you can run Ratter with the `--no-cache` argument to avoid the use
of the `jsonpickle` library.


[1] https://docs.python.org/3/library/pickle.html

[2] https://jsonpickle.github.io/#jsonpickle-usage


### Imports and `importlib`

Ratter uses `importlib.util.find_spec` to locate the source code for imported
modules when following imports. However, the function `find_spec(m)` has the
side-effect that, when called, the parent module of `m` will be imported, thus
the parent of `m` will be imported by Ratter and any code in the global scope
of `m`'s parent will be executed. As such you should not run Ratter on any
code you do not trust and would not be willing to execute.

If you wish to avoid the use of `find_spec` you can set the CLI argument
`--follow-imports 0` or `--follow-imports 1`, however, you must do so at your
own risk as this has not been thoroughly tested.

We intend to fix this vulnerability after moving to Python 3.8+ in the future,
by using the new `importlib.metadata` library [3], which appears to not
suffer from the same issue.


[3] https://docs.python.org/3.8/library/importlib.metadata.html


## Errors and Warnings

Ratter can give five types of error/warnings: raised Python errors, output
beginning with "info:" or "warning:", output beginning with "error:", and
output beginning with "fatal:". The former can be seen as a developer caused
error, and the latter four are user errors.

### User Error: "info" and "warning"

Warns the user of potential issues or bad practise that should not affect the
results of analysis. Low-priority (often class based) warnings begin with
"info".

### User Error: "error"

Warns the user of potential issues or bad practise that will likely affect the
results of analysis (though there are times when the results will still be
correct).

### User Error: "fatal"

Warns the user of potential issues or bad practise so severe that the results
can not be produced for the given file.


## Results Structure

A dictionary from functions to results, which is in turn a dictionary of the
variables, attributes, etc (collectively nameables) that are get, set, called,
or deleted.


## Nameables Format

Pythonic Name   | Python Example                | Ratter Result Format
:---------------|:------------------------------|:---------------------
Name            | `name`                        | `name`
Starred         | `*name`                       | `*name`
Attribute       | `name.attr`                   | `name.attr`
Call            | `name(a, b, ...)`             | `name()`
Subscript       | `name[0]` or `name['key']`    | `name[]`

The above can be nested in Ratter as in Python, for example the Python snippet
`name.method(arg_one, arg_two, ...).result_attr['some key']` will become
`name.method().result_attr[]`.

However, some expression do not have resolvable names. For example, given the
class `A` and instances `a_one`, `a_two`; assuming that `A` implements
`__add__`, which over two names of type `A` returns an `A`; and, `A` provides
the attribute `some_attr`; the following is legal Python code
`(a_one + a_two).some_attr`. Another example of code whose name is unresolvable
is `(3).to_bytes(length=1, byteorder='big')`.

Ratter will handle the above cases by returning a produced local name -- the
result of prepending the AST node type with an '@'. The former example
will become `@BinOp.some_attr`, and the latter `@Int.to_bytes`.


## Example Results

```
{
    ...

    "my_function": {
        "gets": [
            "variable_a",
            "variable_b",
            "object_a.some_attr",
        ],
        "sets": [
            "object_a.set_me",
        ],
        "dels": [],
        "calls": [
            "min()",
            "max()"
        ]
    },
}
```

## Support for Python 3.8

Between Python 3.7 and Python 3.8 there were several significant changes that
effect Ratter and how it works, namely:

1. the introduction of the walrus operator;
2. the addition of `posonlyargs` to `ast.arguments`;
3. complete rework of the representation of constants in `ast`.

As it stands Ratter will run on-and-under Python 3.8, however, with varying
support for the above. Specifically: 1. is not supported, and usage will cause
an error; 2. is not supported, and usage results in undefined behaviour; and 3.
is fully supported.

An additional issue with Python 3.7/3.8 cross-compatibility is the introduction
of `typing.get_origin` and `typing.get_args`, removing the need to rely on the
undefined behaviour of `Union().__args__`. Though, as the latter works in both,
this does not affect the execution of Ratter -- it just results in some
complaints by `mypy` which could be avoided it only Python 3.8 were supported.

Links regarding the above:

[1] https://stackoverflow.com/questions/45957615/check-a-variable-against-union-type-at-runtime-in-python-3-6
-- answers 1 and 2 specifically touch on the `typing.get_args` /
`Union().__args__` issue.

[2] https://greentreesnakes.readthedocs.io/en/latest/nodes.html#literals
-- literals are very different.

[3] https://greentreesnakes.readthedocs.io/en/latest/nodes.html#NamedExpr
-- walrus operator.

[4] https://greentreesnakes.readthedocs.io/en/latest/nodes.html#arguments
-- `posonlyargs`.


--------------------------------------------------------------------------------


# Known Issues

For now these will throw a fatal error -- in the future Ratter should be more
"feature complete" and should handle these cases properly.


## Globals

```python
>>> y = 8
>>> def fn(a):
...     global y
...     y = a
...
>>> fn(3)
>>> y
3
>>>
```


## Redefinitions

```python

def fn(m):
    print(m.attr_one)

    m = MyCoolClass()

    print(m.attr_two)

```

Ratter will produce `{ "sets": {"m.attr_one", "m.attr_two"} }`\
But should produce `{ "sets": {"m.attr_one", "@local:m.atter_two"} }`?
