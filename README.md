# Rattr rats on your attrs.

Rattr (pronounced 'ratter') is a tool to determine attribute usage in python functions. It can parse python files, follow imports and then report to you about the attributes accessed by function calls in that file.

# Status

Currently this project is under active development and likely to change significantly in the future. However we hope it might be useful and interesting to the wider python community.

# But why?

We developed rattr to help with some analytics work in python where type checkers like mypy and pyre are cumbersome.
In analytics work, we often have functions that look like this:
```python
def compute_cost_effectiveness(person):
    return person.sales / person.salary
```

because we're pythonistas, the exact type of `person` is unimportant to us in this example - what's important is that it has a sales and salary attribute and that those are numbers. Annotating this function with that information for mypy would be cumbersome - and with thousands of functions it would be hard to do.

Rattr is a tool that solves the first part of this - it can detect that `compute_cost_effectiveness` needs to access "sales" and "salary" attributes and so it could tell us that the following would fail:

```python
def create_report():
    people = some_database.query(Person.name, Person.sales).all()
    return {person.name: compute_cost_effectiveness(person) for person in people}
```

It can also effectively compute the provenance of attributes. Suppose that you have a wide array of functions for computing information about financial products - like
```python
def compute_some_complex_risk_metric_for(security, other_data):
    # proprietary and complicated logic here
    security.riskiness = bla
    return security
```

and you have other functions that consume that information:
```python
def should_i_buy(security):
    if security.riskiness > 5:
        return False
    # More logic here ...
```

rattr can help you determine which functions are required for a calculation. Effectively allowing you to build powerful directed graph structures for your function libraries.

# Configuration

Rattr is configurable both via pyproject.toml and the command line.

## Command Line Args:

```
  -h, --help            show this help message and exit

  -v, --version         show program's version number and exit

  -f {0,1,2,3}, --follow-imports {0,1,2,3}
                        follow imports level meanings:
                        0 - do not follow imports
                        1 - follow imports to local modules (default)
                        2 - follow imports to local and pip installed modules
                        3 - follow imports to local, pip installed, and stdlib modules
                        NB: following stdlib imports when using CPython will cause issues

  -F PATTERN, --exclude-import PATTERN
                        do not follow imports to modules matching the given pattern, regardless of the
                        level of -f

  -x PATTERN, --exclude PATTERN
                        exclude functions and classes matching the given regular expression from being
                        analysed

  -w {none,file,all,ALL}, --show-warnings {none,file,all,ALL}
                        show warnings level meaning:
                        none - do not show warnings
                        file - show warnings for <file>
                        all  - show warnings for all files (default)
                        All  - show warnings for all files, including low-priority
                        NB: errors and fatal errors are always shown

  -p {none,short,full}, --show-path {none,short,full}
                        show path level meaning:
                        none  - do not show the file path in errors/warnings
                        short - show an abbreviated path (default)
                        full  - show the full path
                        E.g.: "/home/user/very/deep/dir/path/file" becomes "~/.../dir/path/file"

  --strict              run rattr in strict mode, i.e. fail on any error
  --permissive THRESHOLD
                        run rattr in permissive mode, with the given badness threshold (when threshold
                        is zero or omitted, it is taken as infinite) (default: --permissive 0 when
                        group omitted)
                        
                        typical badness values:
                        +0 - info
                        +1 - warning
                        +5 - error
                        +∞ - fatal
                        
                        NB: badness is only contributed to by the target <file> and by the
                        simplification stage (e.g. resolving function calls, etc).

  -i, --show-ir         show the IR for the file and imports
  -r, --show-results    show the results of analysis
  -s, --show-stats      show stats Rattr statisitics
  -S, --silent          show only errors and warnings

  --cache CACHE         the file to cache the results to, if successful

  <filter-string>       filter the output to functions matching the given regular expression

  <file>                the Python source file to analyse

```
## pyproject.toml

Example toml config:

```toml
[tool.rattr]
follow-imports = 0      # options are: (0, 1, 2, 3)
strict = true
# permissive = 1        # (can be any positive int & mutex with 'strict = true')
silent = true
# show-ir = true        # (mutex with 'silent = true')
# show-results = true   # (mutex with 'silent = true')
# show-stats = true     # (mutex with 'silent = true')
show-path = 'none'      # options are: ('none', 'short', 'full')
show-warnings = 'none'  # options are ('none', 'file', 'all', 'ALL')
exclude-import = [    
    'a\.b\.c.*',
    'd\..*',
    '^e$'
]
exclude = [
    'a_.*',
    'b_.*',
    '_c.*',
]
cache = 'cache.json'
```

Without setting any command line or toml arguments specifically, the default configuration for rattr is the following:

```toml
[tool.rattr]
follow-imports = 1
permissive = 0
show-ir = false
show-results = true
show-stats = false
show-path = 'short'
show-warnings = 'all'
exclude-import = []
exclude = []
cache = ''
```


# Developer Notes

## Use of Undocumented Behaviour

In `rattr/analyser/types.py` several `Union` types are defined for
convenience. In Python 3.8 to check if the variable `a` is an instance of any
of the types within the `Union` the `typing` module provides `get_args` i.e.
one would use `isinstance(a, get_args(UnionTypeName))`. However, this function
is not provided in Python 3.7 and so the undocumented attribute `__args__` of
the `UnionTypeName` must be used i.e. `isinstance(a, UnionTypeName.__args__)`.
As this is undocumented it should be changed when we upgrade to Python 3.8+
(and `$EDITOR` will not syntax highlight or tab-complete it).


## Annotations

Rattr provides the ability to annotate functions in the target file such that
they may be ignored completely, ignored with their results determined manually,
etc. Additionally, each assertor may provide it's own annotations to ignore
and/or define behaviour.

General Rattr annotations are located in `rattr/analyser/annotations.py` and
assertor specific annotations are to be added by the assertion developer --
however they should be placed in the file containing the `Assertor` class.

### Annotation Format

Annotations should take the form `rattr_<annotation_name>` to avoid namespace
conflicts in importing code.

### Detecting and Parsing Annotations

The `rattr/analyser/utils.py` file provides the following annotation utility
functions:

* `has_annotation(name: str, fn: ast.FunctionDef) -> bool`
* `get_annotation(name: str, fn: ast.FunctionDef) -> Optional[ast.AST]`
* `parse_annotation(name: str, fn: ast.FunctionDef) -> Dict[str, Any]`
* `parse_rattr_results_from_annotation(fn: ast.FunctionDef) -> Dict[str, Literal[...]]:`
* `safe_eval(expr: ast.expr, culprit: Optional[ast.AST]) -> Union[Literal, Iterable[Iterable[...[Literal]]]]`
* `is_name(name: Any) -> bool`
* `is_set_of_names(set_of_names: Any) -> bool`
* `is_args(args: Any) -> bool`


### Provided Annotations

Annotation Name                             | Location
:-------------------------------------------|:--------------------------------
`rattr_ignore`                              | `rattr/analyser/annotations.py`
`rattr_results(<results>)`                  | `rattr/analyser/annotations.py`

### Results Annotation Grammar

```python

@rattr_results(
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

See `python rattr -h`.


## Errors and Warnings

Rattr can give five types of error/warnings: raised Python errors, output
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

Pythonic Name   | Python Example                | Rattr Result Format
:---------------|:------------------------------|:---------------------
Name            | `name`                        | `name`
Starred         | `*name`                       | `*name`
Attribute       | `name.attr`                   | `name.attr`
Call            | `name(a, b, ...)`             | `name()`
Subscript       | `name[0]` or `name['key']`    | `name[]`

The above can be nested in Rattr as in Python, for example the Python snippet
`name.method(arg_one, arg_two, ...).result_attr['some key']` will become
`name.method().result_attr[]`.

However, some expression do not have resolvable names. For example, given the
class `A` and instances `a_one`, `a_two`; assuming that `A` implements
`__add__`, which over two names of type `A` returns an `A`; and, `A` provides
the attribute `some_attr`; the following is legal Python code
`(a_one + a_two).some_attr`. Another example of code whose name is unresolvable
is `(3).to_bytes(length=1, byteorder='big')`.

Rattr will handle the above cases by returning a produced local name -- the
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
effect Rattr and how it works, namely:

1. the introduction of the walrus operator;
2. the addition of `posonlyargs` to `ast.arguments`;
3. complete rework of the representation of constants in `ast`.

As it stands Rattr will run on-and-under Python 3.8, however, with varying
support for the above. Specifically: 1. is not supported, and usage will cause
an error; 2. is not supported, and usage results in undefined behaviour; and 3.
is fully supported.

An additional issue with Python 3.7/3.8 cross-compatibility is the introduction
of `typing.get_origin` and `typing.get_args`, removing the need to rely on the
undefined behaviour of `Union().__args__`. Though, as the latter works in both,
this does not affect the execution of Rattr -- it just results in some
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

For now these will throw a fatal error -- in the future Rattr should be more
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

Rattr will produce `{ "sets": {"m.attr_one", "m.attr_two"} }`\
But should produce `{ "sets": {"m.attr_one", "@local:m.atter_two"} }`?
