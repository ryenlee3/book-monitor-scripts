import html
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), HERE]
import check  # noqa: E402
import fixtures  # noqa: E402
import render  # noqa: E402


def price_rows(h):
    """[(ticker, close, 1-day, valuation or None)] from the Prices tables, in order."""
    out = []
    for row in check.ROW.findall(h):
        cells = check.CELL.findall(row)
        if len(cells) == 5 and re.fullmatch(r"[A-Z][A-Z0-9.\-]*", check.txt(cells[0][1])):
            out.append([check.txt(cells[0][1]), check.txt(cells[1][1]), check.txt(cells[2][1]), None])
        elif len(cells) == 1 and 'colspan="5"' in cells[0][0] and out and out[-1][3] is None:
            out[-1][3] = check.txt(cells[0][1])
    return out


class FactsPrices(unittest.TestCase):
    def setUp(self):
        self.d = fixtures.note()
        self.h, _ = render.render_note(self.d)
        self.rows = {r[0]: r for r in price_rows(self.h)}

    def test_valuation_row_under_each_name_with_one(self):
        lines = {render.book_ticker(render.parse_fact(l)["sym"]): l for l in self.d["facts"]}
        self.assertEqual(set(self.rows), set(lines))
        with_val = 0
        for t, l in lines.items():
            want = l.split("; ", 1)[1][:-1] if "; " in l else None
            self.assertEqual(self.rows[t][3], want, t)
            with_val += want is not None
        self.assertTrue(0 < with_val < len(lines))  # the fixture has names with and without one

    def test_one_price_per_name_from_facts(self):
        self.assertEqual(self.rows["MSFT"][1], "535.93")
        self.assertNotIn("536.21", self.h)  # the web close never shows
        vt = html.unescape(re.sub(r"<[^>]+>", "", self.h.replace("<br>", "\n")))
        self.assertIn("USD 535.93 " + self.rows["MSFT"][2], vt)
        self.assertEqual(self.rows["RY"][1], "208.75")  # RY means RY.TO, in CAD
        self.assertIn("CAD 208.75", vt)

    def test_missing_line_is_close_not_confirmed(self):
        d = fixtures.with_(self.d, facts=[l for l in self.d["facts"] if not l.startswith("MSFT ")])
        h, _ = render.render_note(d)
        r = {x[0]: x for x in price_rows(h)}
        self.assertEqual(r["MSFT"][1:], ["n/a", "n/a", None])
        self.assertNotIn("536.21", h)
        self.assertIn("close not confirmed", h)

    def test_no_price_line_is_close_not_confirmed(self):
        d = fixtures.with_(self.d, facts=["MSFT: no price on 2026-11-06 (no bars)." if l.startswith("MSFT ") else l
                                          for l in self.d["facts"]])
        r = {x[0]: x for x in price_rows(render.render_note(d)[0])}
        self.assertEqual(r["MSFT"][1], "n/a")

    def test_no_block_uses_web_prices_and_says_so(self):
        h, _ = render.render_note(fixtures.note(facts=False))
        r = {x[0]: x for x in price_rows(h)}
        self.assertEqual(r["MSFT"][1], "536.21")
        self.assertIn("Prices from the web: the engine's Book facts were not available.", h)
        self.assertTrue(all(x[3] is None for x in r.values()))

    def test_layout_styles_stay_inline(self):
        self.assertIn('<style>a{color:#1f4e8c;text-decoration:none}', self.h)
        self.assertIn('style="max-width:760px;margin:0 auto"', self.h)
        self.assertIn('style="width:130px"', self.h)
        self.assertIn('<font color="#137333">', self.h)
        lb = self.h.index("--- CURRENT LIST ---")  # the list block keeps its line breaks (white-space:pre-wrap)
        self.assertNotIn("\n", self.h[:lb])


if __name__ == "__main__":
    unittest.main()
