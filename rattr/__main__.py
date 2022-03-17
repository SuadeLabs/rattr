#!/usr/bin/env python3
"""Rattr entry point."""

import json
from math import log10
from typing import Iterable, Set

from rattr import config, error
from rattr.analyser.context import Import, Symbol
from rattr.analyser.file import RattrStats, parse_and_analyse_file
from rattr.analyser.results import ResultsEncoder, generate_results_from_ir
from rattr.analyser.types import FileIR, FileResults, ImportsIR
from rattr.analyser.util import (
    cache_is_valid,
    create_cache,
    is_blacklisted_module,
    re_filter_ir,
    re_filter_results,
)
from rattr.cli import Namespace, parse_arguments
from rattr.error import get_badness


def main(arguments: Namespace) -> None:
    """Rattr entry point."""
    load_config(arguments)

    file_ir, imports_ir, stats = parse_and_analyse_file()

    results = generate_results_from_ir(file_ir, imports_ir)

    if not error.is_within_badness_threshold():
        error.fatal(f"exceeded allowed badness ({get_badness()} > {config.threshold})")

    if config.show_ir:
        show_ir(config.file, file_ir, imports_ir)

    if config.show_results:
        show_results(results)

    if config.show_stats:
        show_stats(stats)

    if config.cache:
        write_cache(results, file_ir, imports_ir)


def show_ir(file: str, file_ir: FileIR, imports_ir: ImportsIR) -> None:
    """Prettily print the given file and imports IR."""
    if config.filter_string:
        imports_ir = {
            i: re_filter_ir(ir, config.filter_string) for i, ir in imports_ir.items()
        }
        file_ir = re_filter_ir(file_ir, config.filter_string)

    jsonable_ir = dict()

    for i, ir in imports_ir.items():
        jsonable_ir[i] = {repr(c): r for c, r in ir.items()}

    jsonable_ir[file] = {repr(c): r for c, r in file_ir.items()}

    print(json.dumps(jsonable_ir, indent=4, cls=ResultsEncoder))


def show_results(results: FileResults) -> None:
    """Prettily print the given file results."""
    if config.filter_string:
        results = re_filter_results(results, config.filter_string)

    print(json.dumps(results, indent=4, cls=ResultsEncoder))


def show_stats(stats: RattrStats) -> None:
    """Prettily print the collected stats in tables."""
    row = "{:26} | {:18}"

    # Collate time stats
    table_header = row.format("", "Time (Seconds)")
    table_width = len(table_header)
    times = {
        "Parse <file>": stats.parse_time,
        "Build root context": stats.root_context_time,
        "Run assertor": stats.assert_time,
        "Parse / analyse imports": stats.analyse_imports_time,
        "Analyse <file>": stats.analyse_file_time,
    }

    # Print time stats
    print(end="\n\n")
    print(table_header)
    print("=" * table_width)
    for col_one, col_two in times.items():
        print(row.format(col_one, format(col_two, ".9f") + " s"))

    # Collate imports stats
    table_header = row.format("", "# of Imports")
    table_width = len(table_header)
    imports = {
        "Total number of imports": stats.number_of_imports,
        "... of which unique": stats.number_of_unique_imports,
    }

    # Print imports stats
    print(end="\n\n")
    print(table_header)
    print("=" * table_width)
    digits = 1 + int(log10(max(*imports.values(), 1)))
    for col_one, col_two in imports.items():
        print(row.format(col_one, format(col_two).zfill(digits)))

    # Collate line stats
    table_header = row.format("", "# of Lines")
    table_width = len(table_header)
    lines = {
        "<file>": stats.file_lines,
        "Imports": stats.import_lines,
    }

    # Print line stats
    print(end="\n\n")
    print(table_header)
    print("=" * table_width)
    digits = 1 + int(log10(max(*lines.values())))
    for col_one, col_two in lines.items():
        print(row.format(col_one, format(col_two).zfill(digits)))

    # Collate badness stats
    table_header = row.format("", "Magnitude")
    table_width = len(table_header)
    badness_stats = {
        "Total badness": sum(
            (config.file_badness, config.import_badness, config.simplify_badness)
        ),
        "... from <file>": config.file_badness,
        "... from imports": config.import_badness,
        "... from simplification": config.simplify_badness,
    }

    # Print badness stats
    print(end="\n\n")
    print(table_header)
    print("=" * table_width)
    if max(*badness_stats.values()) > 0:
        digits = 1 + int(log10(max(*badness_stats.values())))
    else:
        digits = 1
    for col_one, col_two in badness_stats.items():
        print(row.format(col_one, format(col_two).zfill(digits)))

    # Badness summary
    badness = config.file_badness + config.simplify_badness
    badness_summary_stats = {
        "True badness": badness,
        "Threshold": config.threshold if config.threshold > 0 else "∞",
        "Average badness/line": format(badness / stats.file_lines, ".3f")
        + " b/l (true badness / <file> lines)",
    }
    summary = f"{{:{1 + max(map(len, badness_summary_stats.keys()))}}}: {{}}"
    print(end="\n\n")
    for desc, stat in badness_summary_stats.items():
        print(summary.format(desc, stat))

    # Summary stats
    summary_stats = {
        "Total time": format(sum(times.values()), ".6f") + " s",
        "Total lines": sum(lines.values()),
        "Average lines/second": format(sum(lines.values()) / sum(times.values()), ".0f")
        + " l/s",
    }
    summary = f"{{:{1 + max(map(len, summary_stats.keys()))}}}: {{}}"
    print(end="\n\n")
    for desc, stat in summary_stats.items():
        print(summary.format(desc, stat))

    print(end="\n\n")


def write_cache(results: FileResults, file_ir: FileIR, imports_ir: ImportsIR) -> None:
    """Save the file results to the file cache."""
    if cache_is_valid(config.file, config.cache):
        return error.rattr(f"cache for '{config.file}' is already up to date")

    imports: Set[str] = set()

    for ctx in [file_ir.context, *[i.context for i in imports_ir.values()]]:
        symbols: Iterable[Symbol] = ctx.symbol_table.symbols()
        for sym in symbols:
            if not isinstance(sym, Import):
                continue

            if is_blacklisted_module(sym.module_name):
                continue

            if sym.module_spec is None or sym.module_spec.origin is None:
                continue

            if sym.module_spec.origin == "built-in":
                continue

            imports.add(sym.module_spec.origin)

    create_cache(results, imports, ResultsEncoder)


def load_config(arguments: Namespace) -> None:
    """Populate the config with the given arguments."""
    config.follow_imports = arguments.follow_imports
    config.follow_pip_imports = arguments.follow_imports >= 2
    config.follow_stdlib_imports = arguments.follow_imports >= 3

    config.excluded_imports = set(arguments.exclude_import)
    config.excluded_names = set(arguments.exclude)

    config.show_warnings = arguments.show_warnings != "none"
    config.show_imports_warnings = arguments.show_warnings in ("all", "ALL")
    config.show_low_priority_warnings = arguments.show_warnings == "ALL"

    config.show_path = arguments.show_path != "none"
    config.use_short_path = arguments.show_path == "short"

    config.strict = arguments.strict
    config.permissive = arguments.permissive
    config.threshold = arguments.threshold

    config.show_ir = arguments.show_ir
    config.show_results = arguments.show_results
    config.show_stats = arguments.show_stats
    config.silent = arguments.silent

    config.filter_string = arguments.filter_string
    config.file = arguments.file

    config.cache = arguments.cache


def entry_point():
    """Entry point for command line app."""
    main(parse_arguments())


if __name__ == "__main__":
    entry_point()
