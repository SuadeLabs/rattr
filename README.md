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
  -c TOML, --config TOML
                        override the default 'pyproject.toml' with another config file

  -v, --version         show program's version number and exit

  -f {0,1,2,3}, --follow-imports {0,1,2,3}
                        follow imports level meanings:
                        0 - do not follow imports
                        1 - follow imports to local modules (default)
                        2 - follow imports to local and pip installed modules
                        3 - follow imports to local, pip installed, and stdlib modules

                        NB: following stdlib imports when using CPython will cause issues

  -F PATTERN, --exclude-import PATTERN
                        do not follow imports to modules matching the given pattern,
                        regardless of the level of -f
                        
                        TOML example: exclude-imports=['a', 'b']

  -x PATTERN, --exclude PATTERN
                        exclude functions and classes matching the
                        given regular expression from being analysed
                        
                        TOML example: exclude=['a', 'b']

  -w {none,local,default,all}, --warning-level {none,local,default,all}
                        warnings level meaning:
                        none    - do not show warnings
                        local   - show warnings for <file>
                        default - show warnings for all files (default)
                        all     - show warnings for all files, including low-priority
                        
                        NB: errors and fatal errors are always shown
                        
                        TOML example: warning-level='all'

  -H, --collapse-home   collapse the user's home directory in error messages
                        E.g.: "/home/user/path/to/file" becomes "~/path/to/file"
                        
                        TOML example: collapse-home=true
  -T, --truncate-deep-paths
                        truncate deep file paths in error messages
                        E.g.: "/home/user/very/deep/dir/to/file" becomes "/.../dir/to/file"
                        
                        TOML example: truncate-deep-paths=true

  --strict              select strict mode, i.e. fail on any error
                        
                        TOML example: strict=true
  --threshold N         set the 'badness' threshold, where 0 is infinite (default: --threshold 0)
                        
                        typical badness values:
                        +0 - info
                        +1 - warning
                        +5 - error
                        +∞ - fatal
                        
                        NB: badness is calculated form the target file and simplification stage
                        
                        TOML example: threshold=10

  -o {stats,ir,results}, --stdout {stats,ir,results}
                        output selection:
                        silent  - do not print to stdout
                        ir      - print the intermediate representation to stdout
                        results - print the results to stdout (default)
                        
                        TOML example: stdout='results'

  <file>                the target source file
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
show-warnings = 'none'  # options are: ('none', 'file', 'all', 'ALL')
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
conflicts.

### Detecting and Parsing Annotations

The `rattr/analyser/utils.py` file provides the following annotation utility
functions:

* `has_annotation(name: str, target: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool`
* `get_annotation(name: str, target: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> ast.expr | None`
* `parse_annotation(name: str, fn_def: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[list[Any], dict[str, Any]]` \
    where the first return value is the list of the safely evaluated literal values of the positional arguments, and the second argument os the dict from the name to safely evaluated literal value of the keyword arguments\
    see `safe_eval(...)`
* `parse_rattr_results_from_annotation(fn_def: ast.FunctionDef | ast.AsyncFunctionDef, *, context: Context) -> FunctionIr`
* `safe_eval(expr: ast.expr, culprit: ast.AST) -> Any | None`
* `is_name(target: str | object) -> bool`
* `is_set_of_names(target: set[str] | object) -> bool`
* `is_list_of_names(target: list[str] | object) -> bool`
* `is_list_of_call_specs(call_specs: list[tuple[Identifier, tuple[list[Identifier], dict[Identifier, str]]]] | object) -> bool`


### Provided Annotations

The provided annotations can be found in `rattr/analyser/annotations.py`.

Ignore a function (treated as though it were not defined):
```python
def rattr_ignore(*optional_target: Callable[P, R]) -> Callable[P, R]:
    ...
```

Usage:
```python
@rattr_ignore
def i_can_be_used_without_brackets():
    ...


@rattr_ignore()
def or_with_them():
    ...
```

Manually specify the results of a function:
```python
def rattr_results(
    *,
    gets: set[Identifier] | None = None,
    sets: set[Identifier] | None = None,
    dels: set[Identifier] | None = None,
    calls: list[
        tuple[
            TargetName,
            tuple[
                list[PositionalArgumentName],
                dict[KeywordArgumentName, LocalIdentifier],
            ],
        ]
    ]
    | None = None,
) -> Callable[P, R]
    ...
```

For usage see below.


### Results Annotation Grammar

```python

@rattr_results(
    sets={"a", "b.attr"},
    calls=[
        ("the_name_of_the_callee_function", (["arg", "another"], {"kwarg": "a.some_attr"}))
    ]
)
def decorated_function(...):
    ...

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

## Supported Python Versions

At present `rattr` officially supports, and is tested under, Python versions 3.8
through 3.11 as the run-time interpreter (i.e. supports `python3.8 -m rattr ...`).
Previously Python 3.7 was supported but due to a number of `ast` changes (named
expressions and constant changes) and useful stdlib changes in Python 3.8, this it is
no longer supported (some code still makes exceptions for Python 3.7 which will be
refactored over time).

Python version outside of the given range may not be able to run `rattr` but,
hypothetically, any Python 3 code is a valid target. That is to say that while
`python3.7 -m rattr my_python_3_7_file.py` will not work
`python3.8 -m rattr my_python_3_7_file.py` (*sic*) will work.


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
