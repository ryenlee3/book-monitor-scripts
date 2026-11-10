"""The "Open your book" link to the book website (Nov 10): render.py puts it first under the title, check.py FAILs a
note without it or with it pointing anywhere else."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), HERE]
import check  # noqa: E402
import fixtures  # noqa: E402
import render  # noqa: E402
import test_check  # noqa: E402

URL = "https://4pv2a-hkg6m-wbagz.df2nu-94qec-veptg.workers.dev"


class Render(unittest.TestCase):
    def setUp(self):
        self.h, self.t = render.render_note(fixtures.note())

    def test_constant(self):
        self.assertEqual(render.SITE_URL, URL)

    def test_one_button_first_under_the_title_above_the_summary(self):
        self.assertEqual(self.h.count('data-bm="site-link"'), 1)
        block = check.SITE_WRAP.search(self.h).group(0)
        self.assertIn('<a href="%s"' % URL, block)
        self.assertIn(">Open your book</a>", block)
        i = self.h.index('data-bm="site-link"')
        self.assertLess(self.h.index("Book update"), i)
        self.assertLess(i, self.h.index(fixtures.note()["summary"]))
        self.assertEqual(self.h.count(URL), 1)

    def test_button_style_inline_tappable_and_without_background(self):
        a = re.search(r'<a href="%s" style="([^"]*)"' % re.escape(URL), self.h).group(1)
        for k in ("display:inline-block", "min-height:44px", "border:2px solid", "font-weight:700"):
            self.assertIn(k, a)
        self.assertNotIn("background", self.h.lower())

    def test_text_first_line_after_the_title(self):
        lines = self.t.split("\n")
        self.assertEqual(lines[0], fixtures.note()["subject"])
        self.assertEqual([l for l in lines[1:] if l][0], "Open your book: " + URL)

    def test_full_note_stays_under_the_60_kb_warning(self):
        size = len(render.render_note(fixtures.full_note())[0].encode("utf-8"))
        self.assertLess(size, check.WARN_KB * 1024)  # 61,334 bytes with the button (61,009 before), warning at 61,440

    def test_late_run_and_header_note_come_after_the_button(self):
        d = fixtures.note()
        d["late_run"], d["header_note"] = True, "A header note."
        h = render.render_note(d)[0]
        i = h.index('data-bm="site-link"')
        self.assertLess(i, h.index("Late run"))
        self.assertLess(i, h.index("A header note."))


class CheckLink(unittest.TestCase):
    setUp, run_check, assertFails = (test_check.Check.setUp, test_check.Check.run_check,
                                     test_check.Check.assertFails)  # Check's helpers, not its tests

    def test_rendered_note_passes_with_the_link(self):
        F, _, _ = self.run_check()
        self.assertEqual([f for f in F if "Open-your-book" in f], [])

    def _with(self, fn):
        h = render.render_note(self.d)[0]
        return self.run_check(h=fn(h))

    def test_missing_link_fails(self):
        res = self._with(lambda h: check.SITE_WRAP.sub("", h))
        self.assertFails(res, "Open-your-book link missing")

    def test_link_elsewhere_fails(self):
        res = self._with(lambda h: h.replace('href="%s"' % URL, 'href="https://example.com/book"'))
        self.assertFails(res, "points to https://example.com/book")

    def test_lookalike_host_fails(self):
        res = self._with(lambda h: h.replace('href="%s"' % URL, 'href="%s.evil.example/"' % URL))
        self.assertFails(res, "points to")

    def test_unmarked_wrapper_fails(self):
        res = self._with(lambda h: h.replace('data-bm="site-link"', 'data-bm="other"'))
        self.assertFails(res, "Open-your-book link missing")

    def test_repeated_block_fails(self):
        res = self._with(lambda h: h.replace("</body>", check.SITE_WRAP.search(h).group(0) + "</body>"))
        self.assertFails(res, "repeated 2 times")

    def test_wrong_label_fails(self):
        res = self._with(lambda h: h.replace(">Open your book</a>", ">Book</a>"))
        self.assertFails(res, "reads 'Book'")


if __name__ == "__main__":
    unittest.main()
