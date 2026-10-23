"""Local CSV merge tool. Standard library only; no network operations."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile


class InputError(ValueError):
    """An actionable input or configuration problem."""


def read_csv(path: Path, encoding: str, delimiter: str):
    raw = path.read_bytes()
    if encoding == "auto":
        candidates = ["utf-8-sig", "gb18030"]
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            candidates = ["utf-16"]
    else:
        candidates = [encoding]
    for candidate in candidates:
        try:
            text = raw.decode(candidate)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise InputError(f"{path}: cannot decode input; specify --encoding")
    if "\x00" in text:
        raise InputError(f"{path}: NUL bytes detected; specify the correct --encoding")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        header = next(reader, None)
        if not header or any(not name.strip() for name in header):
            raise InputError(f"{path}: missing or blank column names")
        if len(set(header)) != len(header):
            raise InputError(f"{path}: duplicate column names")
        rows = []
        for row in reader:
            if not row:
                continue
            if len(row) != len(header):
                raise InputError(f"{path}, line {reader.line_num}: expected {len(header)} fields, got {len(row)}")
            rows.append(dict(zip(header, row)))
    except csv.Error as exc:
        raise InputError(f"{path}, line {reader.line_num}: {exc}") from exc
    return header, rows, {"path": str(path), "encoding": candidate,
                          "rows": len(rows), "sha256": hashlib.sha256(raw).hexdigest()}


def merge(paths, *, encoding="auto", delimiter=",", schema="strict", keys=None,
          dedupe=True, source_column=None):
    if len(delimiter) != 1 or delimiter in "\r\n\x00":
        raise InputError("--delimiter must be one non-newline character")
    if schema not in ("strict", "union"):
        raise InputError("schema must be strict or union")
    if not paths:
        raise InputError("provide at least one CSV file")
    resolved = [Path(p).resolve() for p in paths]
    if len(set(resolved)) != len(resolved):
        raise InputError("the same input file was supplied more than once")
    columns, batches, inputs = [], [], []
    for path in resolved:
        header, rows, info = read_csv(path, encoding, delimiter)
        if columns and schema == "strict" and set(header) != set(columns):
            raise InputError(f"{path}: columns differ; use --schema union to fill missing values")
        if source_column and source_column in header:
            raise InputError(f"source column already exists: {source_column}")
        for column in header:
            if column not in columns:
                columns.append(column)
        batches.append((path, header, rows))
        inputs.append(info)
    if keys:
        for path, header, _ in batches:
            missing = set(keys) - set(header)
            if missing:
                raise InputError(f"{path}: missing key columns: {', '.join(sorted(missing))}")
    identity = keys or columns
    seen, result, dropped, blank_keys, conflicts = {}, [], 0, 0, 0
    for path, _, rows in batches:
        for row in rows:
            normalized = {col: row.get(col, "") for col in columns}
            key = tuple(normalized[col] for col in identity)
            # Keep incomplete business keys: two unknown IDs need not be the same person.
            incomplete = bool(keys) and any(not value.strip() for value in key)
            blank_keys += int(incomplete)
            if dedupe and not incomplete:
                if key in seen:
                    dropped += 1
                    conflicts += int(seen[key] != normalized)
                    continue
                seen[key] = normalized.copy()
            if source_column:
                normalized[source_column] = str(path)
            result.append(normalized)
    report = {"version": "0.1.0", "inputs": inputs, "schema": schema,
              "columns": columns, "dedupe": dedupe, "keys": keys,
              "keep": "first", "input_rows": sum(i["rows"] for i in inputs),
              "output_rows": len(result), "duplicates_removed": dropped,
              "conflicting_duplicates": conflicts, "rows_with_blank_keys_kept": blank_keys,
              "source_column": source_column}
    return columns + ([source_column] if source_column else []), result, report


def write_new(path: Path, content: str, encoding: str):
    """Publish a complete file without replacing an existing destination."""
    path = path.resolve()
    if not path.parent.is_dir():
        raise InputError(f"output directory does not exist: {path.parent}")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding=encoding, newline="",
                                         dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link creation is atomic and fails if the destination exists.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, help="new CSV path; omitted means preview only")
    parser.add_argument("--report", type=Path, help="new JSON audit report path")
    parser.add_argument("--encoding", default="auto", help="auto: UTF-8/BOM, UTF-16 BOM, then GB18030")
    parser.add_argument("--delimiter", default=",")
    parser.add_argument("--schema", choices=["strict", "union"], default="strict")
    parser.add_argument("--key", action="append", help="exact column name; repeat for composite keys")
    parser.add_argument("--keep-duplicates", action="store_true")
    parser.add_argument("--source-column", help="append the absolute source filename")
    args = parser.parse_args(argv)
    try:
        destinations = [p.resolve() for p in (args.output, args.report) if p is not None]
        if len(destinations) != len(set(destinations)):
            raise InputError("output and report must have different paths")
        if args.key and args.keep_duplicates:
            raise InputError("--key cannot be combined with --keep-duplicates")
        for path in destinations:
            if path.exists():
                raise InputError(f"refusing to overwrite existing file: {path}")
            if not path.parent.is_dir():
                raise InputError(f"output directory does not exist: {path.parent}")
        columns, rows, report = merge(args.inputs, encoding=args.encoding,
            delimiter=args.delimiter, schema=args.schema, keys=args.key,
            dedupe=not args.keep_duplicates, source_column=args.source_column)
        if args.output:
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
            write_new(args.output, buffer.getvalue(), "utf-8-sig")
        report["mode"] = "written" if args.output else "preview"
        report["output"] = str(args.output.resolve()) if args.output else None
        serialized = json.dumps(report, ensure_ascii=False, indent=2)
        if args.report:
            write_new(args.report, serialized + "\n", "utf-8")
        print(serialized)
        return 0
    except (InputError, OSError, LookupError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
