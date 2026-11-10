"""Gmail-connector redirect links (google.com/url?q=...) unwrapped in the note and the admin sent log (Nov 10)."""
import json
import os
import sys
import tempfile
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), HERE]
import check  # noqa: E402
import fixtures  # noqa: E402
import render  # noqa: E402

# Real sent-log lines from the admin email: one layer (RY) and two layers (KKR).
RY = ("2026-11-09|RY|m-a-rbc-agreed-to-acquire-australian-active-mana|https://www.google.com/url?q=https://www.prnewswire.com/"
      "news-releases/royal-bank-of-canada-announces-agreement-to-acquire-yarra-capital-management-302932829.html"
      "&source=gmail&ust=1794405064121000&sa=E")
KKR = ("2026-10-26|KKR|filing-kkr-filed-an-8-k-saying-former-goldman-s|https://www.google.com/url?q=https://www.google.com/"
       "url?q%3Dhttps://www.sec.gov/Archives/edgar/data/1404912/000114036126040706/ef20084337_ex99-1.htm%26source%3Dgmail"
       "%26ust%3D1794056136728000%26sa%3DE&source=gmail&ust=1794318794523000&sa=E")
RY_URL = ("https://www.prnewswire.com/news-releases/royal-bank-of-canada-announces-agreement-to-acquire-yarra-capital-"
          "management-302932829.html")
KKR_URL = "https://www.sec.gov/Archives/edgar/data/1404912/000114036126040706/ef20084337_ex99-1.htm"
QS_URL = "https://www.example.com/news/story?id=123&lang=en&ref=a%2Fb#part-2"


def wrap(url, ust="1794500000000000"):
    """One more layer, the way Gmail adds it (as in the KKR line: '=', '&' and '%' encoded, ':/?' left)."""
    return "https://www.google.com/url?q=%s&source=gmail&ust=%s&sa=E" % (urllib.parse.quote(url, safe=":/?"), ust)


def url_of(line):
    return line.split("|", 3)[3]


class Unwrap(unittest.TestCase):
    def test_one_layer_real_line(self):
        self.assertEqual(render.unwrap_link(url_of(RY)), RY_URL)

    def test_two_layers_real_line(self):
        self.assertEqual(render.unwrap_link(url_of(KKR)), KKR_URL)

    def test_three_layers(self):
        self.assertEqual(render.unwrap_link(wrap(url_of(KKR))), KKR_URL)
        self.assertEqual(render.unwrap_link(wrap(wrap(url_of(RY)))), RY_URL)

    def test_own_query_string_comes_back_whole(self):
        for n in (1, 2, 3):
            u = QS_URL
            for _ in range(n):
                u = wrap(u)
            self.assertEqual(render.unwrap_link(u), QS_URL, n)

    def test_own_query_string_left_raw_by_the_redirect(self):
        u = "https://www.google.com/url?q=https://www.example.com/a?id=1&lang=en&source=gmail&ust=1&sa=E"
        self.assertEqual(render.unwrap_link(u), "https://www.example.com/a?id=1&lang=en")

    def test_plain_links_unchanged(self):
        for u in (RY_URL, KKR_URL, QS_URL, "https://www.google.com/search?q=rbc", "https://news.google.com/url?x=1",
                  "https://www.google.com/url?sa=E", ""):
            self.assertEqual(render.unwrap_link(u), u)


class Log(unittest.TestCase):
    def test_lines_unwrapped(self):
        self.assertEqual(render.unwrap_log([RY, KKR, KKR.rsplit("|", 1)[0] + "|" + wrap(url_of(KKR))]),
                         [RY.rsplit("|", 1)[0] + "|" + RY_URL, KKR.rsplit("|", 1)[0] + "|" + KKR_URL])

    def test_same_ticker_and_url_keeps_first(self):
        a = "2026-11-08|RY|first-key|" + wrap(wrap(RY_URL))
        other = "2026-11-08|TD|other-ticker|" + RY_URL  # same URL, different ticker: kept
        out = render.unwrap_log([a, RY, other])
        self.assertEqual(out, ["2026-11-08|RY|first-key|" + RY_URL, "2026-11-08|TD|other-ticker|" + RY_URL])

    def test_admin_text_and_check(self):
        a = {"subject": "Book admin", "date_label": "Nov 10", "run_line": "run", "sections": [],
             "log": [RY, KKR, "2026-11-08|RY|again|" + wrap(url_of(RY))], "closes": ["2026-11-09 RY=208.75"]}
        _, t = render.render_admin(a)
        self.assertNotIn("google.com/url", t)
        self.assertIn("|" + RY_URL + "\n", t)
        self.assertIn("|" + KKR_URL + "\n", t)
        self.assertEqual(t.count(RY_URL), 1)
        d = tempfile.mkdtemp()
        ap, tp = os.path.join(d, "a.json"), os.path.join(d, "a.txt")
        json.dump(a, open(ap, "w"))
        open(tp, "w").write(t)
        F, _, ok = check.check_admin(ap, tp)
        self.assertEqual(F, [])
        self.assertIn("log 2 lines", ok)
        open(tp, "w").write(t.replace(RY_URL, url_of(RY)))
        F, _, _ = check.check_admin(ap, tp)
        self.assertTrue(any("Google redirect" in f for f in F), F)

    def test_300_line_sample_shrinks(self):
        before, after = sample_sizes()
        self.assertLess(after, before / 2)


def sample_log(n=300):
    """n lines like the real log: a third each wrapped one, two and three times; every 10th repeats an earlier link."""
    out = []
    for i in range(n):
        t = fixtures.HOLD[i % len(fixtures.HOLD)]
        u = (KKR_URL if i % 2 else RY_URL).replace(".htm", "-%d.htm" % i) if i % 10 else QS_URL
        for _ in range(1 + i % 3):
            u = wrap(u, str(1794000000000000 + i))
        out.append("2026-10-%02d|%s|item-key-%03d-%s|%s" % (1 + i % 28, t, i, "x" * 30, u))
    return out


def sample_sizes(n=300):
    log = sample_log(n)
    return len("\n".join(log).encode()), len("\n".join(render.unwrap_log(log)).encode())


class NoteLinks(unittest.TestCase):
    def test_every_link_unwrapped_and_check_fails_on_leftover(self):
        d = fixtures.full_note()
        n = [0]

        def wrap_all(x):
            if isinstance(x, dict):
                if "url" in x and isinstance(x["url"], str):
                    n[0] += 1
                    x["url"] = wrap(wrap(x["url"]))
                for v in x.values():
                    wrap_all(v)
            elif isinstance(x, list):
                for v in x:
                    wrap_all(v)
        wrap_all(d)
        self.assertGreater(n[0], 50)
        h, _ = render.render_note(d)
        self.assertNotIn("google.com/url", h)
        self.assertIn('href="https://www.example.com/news/2026/11/05/item-1"', h)
        self.assertEqual(check.redirects(h), [])
        self.assertEqual(len(check.redirects(h.replace("https://www.example.com/news/2026/11/05/item-1",
                                                       wrap(RY_URL).replace("&", "&amp;"), 1))), 1)

    def test_check_note_fails(self):
        dd = tempfile.mkdtemp()
        d = fixtures.note()
        h, t = render.render_note(d)
        h = h.replace('href="https://www.example.com/news/2026/11/05/item-0"', 'href="%s"' % wrap(RY_URL).replace("&", "&amp;"), 1)
        paths = [os.path.join(dd, x) for x in ("n.json", "n.html", "n.txt", "f.txt")]
        json.dump(d, open(paths[0], "w"))
        open(paths[1], "w").write(h)
        open(paths[2], "w").write(t)
        open(paths[3], "w").write(fixtures.facts_email(fixtures.facts_lines()))
        F, _, _ = check.check_note(*paths)
        self.assertTrue(any("Google redirect" in f for f in F), F)


class ClosingHigh(unittest.TestCase):
    def test_label_when_highs_come_from_facts(self):
        h, _ = render.render_note(fixtures.note(v2=True))
        self.assertIn("52w high = highest daily close", h)

    def test_no_label_for_web_highs(self):
        h, _ = render.render_note(fixtures.note())
        self.assertNotIn("highest daily close", h)


if __name__ == "__main__":
    before, after = sample_sizes()
    print("300-line sample log: %d bytes (%.1f KB) before, %d bytes (%.1f KB) after"
          % (before, before / 1024, after, after / 1024))
