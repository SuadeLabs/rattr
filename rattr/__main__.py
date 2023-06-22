#!/usr/bin/env python3
"""Rattr entry point."""
from __future__ import annotations

import json
from math import log10

from rattr import error
from rattr.analyser.file import RattrStats, parse_and_analyse_file
from rattr.analyser.results import ResultsEncoder, generate_results_from_ir
from rattr.analyser.types import FileIr, FileResults, ImportsIr
from rattr.cli import parse_arguments
from rattr.config import Config, Output, State


def _init_rattr_config() -> Config:
    return Config(arguments=parse_arguments(), state=State())


def main(config: Config) -> None:
    """Rattr entry point."""
    file_ir, imports_ir, stats = parse_and_analyse_file()

    results = generate_results_from_ir(file_ir, imports_ir)

    if not config.is_within_badness_threshold:
        badness, threshold = config.state.badness, config.arguments.threshold
        error.fatal(f"exceeded allowed badness ({badness} > {threshold})")

    if config.arguments.stdout == Output.ir:
        show_ir(config.arguments.target, file_ir, imports_ir)

    if config.arguments.stdout == Output.results:
        show_results(results)

    if config.arguments.stdout == Output.stats:
        show_stats(stats)


def show_ir(file: str, file_ir: FileIr, imports_ir: ImportsIr) -> None:
    """Prettily print the given file and imports IR."""
    jsonable_ir = dict()

    for i, ir in imports_ir.items():
        jsonable_ir[i] = {repr(c): r for c, r in ir.items()}

    jsonable_ir[file] = {repr(c): r for c, r in file_ir.items()}

    print(json.dumps(jsonable_ir, indent=4, cls=ResultsEncoder))


def show_results(results: FileResults) -> None:
    """Prettily print the given file results."""
    print(json.dumps(results, indent=4, cls=ResultsEncoder))


def show_stats(stats: RattrStats) -> None:
    """Prettily print the collected stats in tables."""
    row = "{:26} | {:18}"
    config = Config()

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
        "Total badness": config.state.full_badness,
        "... from <file>": config.state.badness_from_target_file,
        "... from imports": config.state.badness_from_imports,
        "... from simplification": config.state.badness_from_simplification,
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
    threshold_or_inf = (
        str(config.arguments.threshold) if config.arguments.threshold > 0 else "∞"
    )
    avg_badness_per_line = config.state.badness / stats.file_lines

    badness_summary_stats = {
        "True badness": config.state.badness,
        "Threshold": threshold_or_inf,
        "Average badness/line": format(avg_badness_per_line, ".3f")
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


def entry_point():
    """Entry point for command line app."""
    main(_init_rattr_config())


if __name__ == "__main__":
    entry_point()
