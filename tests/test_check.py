import json
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


class Check(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.d = fixtures.note()
        self.src = fixtures.facts_email(fixtures.facts_lines())

    def run_check(self, d=None, h=None, src="default"):
        d = d or self.d
        if h is None:
            h, t = render.render_note(d)
        else:
            t = render.render_note(d)[1]
        paths = [os.path.join(self.dir, n) for n in ("n.json", "n.html", "n.txt", "f.txt")]
        json.dump(d, open(paths[0], "w"))
        open(paths[1], "w").write(h)
        open(paths[2], "w").write(t)
        if src is None:
            return check.check_note(*paths[:3])
        open(paths[3], "w").write(self.src if src == "default" else src)
        return check.check_note(*paths)

    def assertFails(self, res, words):
        F = res[0]
        self.assertTrue(any(words in f for f in F), "no FAIL containing %r in %r" % (words, F))

    def test_rendered_note_passes(self):
        F, W, ok = self.run_check()
        self.assertEqual(F, [])
        self.assertTrue(ok.startswith("PASS"))

    def test_one_character_changed_in_source(self):
        src = self.src.replace("535.93", "535.94")
        self.assertFails(self.run_check(src=src), "Facts line 15 differs from the source, character")
        self.assertFails(self.run_check(src=src), "MSFT close shows 535.93, its facts line says 535.94")

    def test_one_character_changed_in_note_facts(self):
        d = fixtures.with_(self.d, facts=[l.replace("median of", "median  of") for l in self.d["facts"]])
        self.assertFails(self.run_check(d), "differs from the source")
        self.assertFails(self.run_check(d), "valuation line differs from the source")

    def test_tampered_close_and_one_day(self):
        h, _ = render.render_note(self.d)
        self.assertEqual(h.count(">535.93<"), 1)
        self.assertFails(self.run_check(h=h.replace(">535.93<", ">536.21<")), "MSFT close shows 536.21")
        msft = render.parse_fact(next(l for l in self.d["facts"] if l.startswith("MSFT ")))
        shown = re.sub(r"<[^>]+>", "", render.pct(msft["pct1d"]))
        i = h.index(">535.93<")
        bad = h[:i] + h[i:].replace(shown, "+9.9%", 1)
        self.assertFails(self.run_check(h=bad), "MSFT 1-day shows +9.9%")

    def test_tampered_sub_line_under_the_name(self):
        h, _ = render.render_note(self.d)
        self.assertFails(self.run_check(h=h.replace("USD 535.93", "USD 536.21")), "MSFT shows")

    def test_valuation_row_missing_or_extra(self):
        h, _ = render.render_note(self.d)
        row = re.search(r'<tr><td colspan="5"[^>]*>[^<]*</td></tr>', h).group(0)
        self.assertFails(self.run_check(h=h.replace(row, "", 1)), "valuation line missing")

    def test_no_source_file(self):
        self.assertFails(self.run_check(src=None), "no source email was given")
        self.assertFails(self.run_check(src="an email without the block"), "has no BOOK FACTS block")

    def test_source_has_block_but_note_does_not(self):
        self.assertFails(self.run_check(fixtures.note(facts=False)), 'note.json has no "facts"')

    def test_no_block_anywhere_warns(self):
        F, W, _ = self.run_check(fixtures.note(facts=False), src=None)
        self.assertEqual(F, [])
        self.assertIn("No BOOK FACTS block: prices are from the web", W)

    def test_list_name_without_line_warns(self):
        d = fixtures.with_(self.d, facts=[l for l in self.d["facts"] if not l.startswith("MSFT ")])
        F, W, _ = self.run_check(d, src=fixtures.facts_email(d["facts"]))
        self.assertEqual(F, [])
        self.assertIn("MSFT has no facts line: close not confirmed", W)

    def test_over_60_kb_fails(self):
        h, _ = render.render_note(self.d)
        pad = "<!--" + "x" * (61 * 1024 - len(h.encode())) + "-->"
        self.assertFails(self.run_check(h=h.replace("</body>", pad + "</body>")), "over the 60 KB limit")

    def test_cli_with_four_arguments(self):
        self.run_check()
        p = subprocess.run([sys.executable, os.path.join(ROOT, "check.py")] +
                           [os.path.join(self.dir, n) for n in ("n.json", "n.html", "n.txt", "f.txt")],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("PASS", p.stdout)


if __name__ == "__main__":
    unittest.main()
