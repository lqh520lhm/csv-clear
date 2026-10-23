# CSV Clear

Preview, merge and deduplicate CSV exports locally, with a JSON audit report.
Python 3.10+ • MIT • No runtime dependencies • No network calls

适合合并每月导出的名单、订单或数据表。按列名对齐，保留文本及编号前导零，处理常见中文编码，并在写入前预览统计。当前版本为命令行工具。

## Quick start / 快速开始

Open a terminal in the extracted project folder. No installation required:

```sh
python csv_clear.py examples/january.csv examples/february.csv --key id
```

This previews 6 input records → 5 output records, removes 1 duplicate and preserves 1 record with a blank ID. It does not create a CSV.

确认统计后生成新文件：

```sh
python csv_clear.py examples/january.csv examples/february.csv --key id --output merged.csv --report report.json
```

Existing files are never overwritten. Choose new filenames for subsequent runs.
An optional local installation exposes the `csv-clear` command: `python -m pip install .`
This package has not been published to PyPI.

## Behavior

| Option | Meaning |
| --- | --- |
| No `--output` | Preview summary only; `--report` can still save a report |
| `--key id` | Deduplicate by ID, keeping the first row |
| Repeated `--key` | Composite key, e.g. `--key id --key month` |
| No `--key` | Deduplicate by all data columns |
| `--keep-duplicates` | Keep every input record |
| `--schema union` | Include all columns; missing values become empty strings |
| `--encoding gb18030` | Explicit input encoding |
| `--delimiter ";"` | Input delimiter; output always uses commas |
| `--source-column source` | Add absolute source paths; excluded from dedupe identity |

- Default strict mode requires matching column names, allowing different order.
- Empty or repeated column names, wrong row widths and malformed quoting are rejected.
- Strings are compared exactly: no automatic trimming, date conversion or case folding.
- Blank business keys are retained individually. Conflicting rows sharing a key are counted in the report; the first wins. Preview before writing or use `--keep-duplicates` if uncertain.
- Encoding auto mode tries UTF-8, then GB18030; UTF-16 requires a BOM. Heuristic decoding can be wrong: use an explicit encoding for other sources.
- Output is UTF-8 with BOM. Input bytes are not changed. Excel may still infer numeric types on opening: import ID columns as text to preserve leading zeros in Excel.
- CSV formula-like strings are preserved, not executed by this tool. Import untrusted CSV as text in spreadsheet software.
- Reports include input paths and hashes. Review before sharing them publicly.
- Files are processed in memory; this version is for small and medium exports, not multi-gigabyte datasets. A filesystem supporting hard links is needed for output publication.
- CSV and report are published separately. If report writing fails after CSV succeeds, the CSV remains available. Errors return exit code 2; success returns 0.

## Development

```sh
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Tests cover encoding, malformed input, column alignment, key conflicts, preservation of blank keys, quoted newlines and file protection.

## Status

Version 0.1.0 is an initial implementation developed with AI assistance. No adoption, performance or platform certification claims are made. CI configuration is included; hosted CI results are only available after publication.

Next candidates: user-tested desktop interface, conflict export, streaming for large files. Priorities should follow real bug reports and user feedback.
