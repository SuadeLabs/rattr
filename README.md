# **Ratter (V2)**

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
