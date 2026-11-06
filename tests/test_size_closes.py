import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [ROOT, HERE]
import check  # noqa: E402
import fixtures  # noqa: E402
import render  # noqa: E402


class Size(unittest.TestCase):
    def test_full_note_under_60_kb(self):
        h, _ = render.render_note(fixtures.full_note())
        size = len(h.encode("utf-8"))
        print("\nfull note: %.1f KB" % (size / 1024), file=sys.stderr)
        self.assertLess(size, check.MAX_KB * 1024)


class Closes(unittest.TestCase):
    def test_closes_line_from_the_facts_email(self):
        lines = render.closes_lines(fixtures.facts_email(fixtures.facts_lines() + ["DAVE: no price on 2026-11-06 (x)."]))
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertTrue(re.match(r"\d{4}-\d{2}-\d{2} [A-Z.]+=", line))  # check.py --admin closes rule
        pairs = dict(x.split("=") for x in line.split(" ", 1)[1].split(","))
        self.assertEqual(pairs["MSFT"], "535.93")
        self.assertEqual(pairs["KLAC"], "1234.56")  # no thousands separator inside the comma-separated list
        self.assertIn("RY", pairs)
        self.assertNotIn("RY.TO", pairs)
        self.assertEqual(len(pairs), 30)

    def test_one_line_per_close_date(self):
        text = fixtures.facts_email(["A closed at 1.00 USD on 2026-11-05.", "RY.TO closed at 2.00 CAD on 2026-11-04."])
        self.assertEqual(render.closes_lines(text), ["2026-11-04 RY=2.00", "2026-11-05 A=1.00"])

    def test_cli(self):
        f = os.path.join(tempfile.mkdtemp(), "facts.txt")
        open(f, "w").write(fixtures.facts_email(fixtures.facts_lines()))
        p = subprocess.run([sys.executable, os.path.join(ROOT, "render.py"), "closes", f], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.startswith("2026-11-05 ABBV=100.00,"))

    def test_cli_without_block_fails(self):
        f = os.path.join(tempfile.mkdtemp(), "facts.txt")
        open(f, "w").write("no block")
        p = subprocess.run([sys.executable, os.path.join(ROOT, "render.py"), "closes", f], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)


if __name__ == "__main__":
    unittest.main()
