import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from csv_clear import InputError, main, merge, write_new


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, name, content, encoding="utf-8"):
        path = self.root / name
        with path.open("w", encoding=encoding, newline="") as stream:
            stream.write(content)
        return path

    def test_reordered_columns_and_leading_zeros(self):
        a = self.file("a.csv", "id,name\n001,A\n")
        b = self.file("b.csv", "name,id\nA,001\nB,002\n")
        cols, rows, report = merge([a, b])
        self.assertEqual(cols, ["id", "name"])
        self.assertEqual([r["id"] for r in rows], ["001", "002"])
        self.assertEqual(report["duplicates_removed"], 1)

    def test_conflicts_and_blank_keys(self):
        a = self.file("a.csv", "id,name\n1,A\n1,B\n,C\n,C\n")
        _, rows, report = merge([a], keys=["id"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["name"], "A")
        self.assertEqual(report["conflicting_duplicates"], 1)
        self.assertEqual(report["rows_with_blank_keys_kept"], 2)

    def test_encodings(self):
        for encoding in ("utf-8-sig", "gb18030", "utf-16"):
            with self.subTest(encoding=encoding):
                a = self.file("a.csv", "姓名\n小林\n", encoding)
                self.assertEqual(merge([a])[1], [{"姓名": "小林"}])

    def test_schema_union_and_strict(self):
        a = self.file("a.csv", "id,name\n1,A\n")
        b = self.file("b.csv", "id,city\n2,B\n")
        with self.assertRaises(InputError):
            merge([a, b])
        cols, rows, _ = merge([a, b], schema="union")
        self.assertEqual(cols, ["id", "name", "city"])
        self.assertEqual(rows[1], {"id": "2", "name": "", "city": "B"})
        with self.assertRaises(InputError):
            merge([a, b], schema="union", keys=["name"])

    def test_malformed_files(self):
        for content in ("", "id,id\n1,2\n", "id,\n1,2\n", "id\n1,2\n", 'id\n"unclosed'):
            with self.subTest(content=content), self.assertRaises(InputError):
                merge([self.file("bad.csv", content)])

    def test_multiline_quoted_field(self):
        a = self.file("a.csv", 'id,note\n1,"hello,\nworld"\n')
        self.assertEqual(merge([a])[1][0]["note"], "hello,\nworld")

    def test_provenance_does_not_prevent_deduplication(self):
        a = self.file("a.csv", "id\n1\n")
        b = self.file("b.csv", "id\n1\n")
        _, rows, _ = merge([a, b], source_column="source")
        self.assertEqual(rows, [{"id": "1", "source": str(a.resolve())}])
        with self.assertRaises(InputError):
            merge([a], source_column="id")

    def test_no_overwrite(self):
        a = self.file("a.csv", "original")
        with self.assertRaises(FileExistsError):
            write_new(a, "replacement", "utf-8")
        self.assertEqual(a.read_text(), "original")
        self.assertEqual(list(self.root.iterdir()), [a])

    def test_preview_and_export(self):
        a = self.file("a.csv", "id\n001\n001\n")
        out, audit = self.root / "out.csv", self.root / "audit.json"
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main([str(a)]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["mode"], "preview")
        self.assertFalse(out.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(a), "--output", str(out), "--report", str(audit)]), 0)
        self.assertEqual(out.read_text(encoding="utf-8-sig"), "id\n001\n")
        self.assertEqual(json.loads(audit.read_text())["duplicates_removed"], 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(a), "--output", str(out)]), 2)

    def test_keep_duplicates_and_delimiter(self):
        a = self.file("a.csv", "id;name\n1;A\n1;A\n")
        self.assertEqual(len(merge([a], delimiter=";", dedupe=False)[1]), 2)


if __name__ == "__main__":
    unittest.main()
