#!/usr/bin/env python3
# book-monitor v0.10 checker: check.py note.json note.html note.txt [facts_email.txt] | check.py --admin admin.json admin.txt
# facts_email.txt: the 06:45 "Book facts" email saved as text; required whenever note.json has "facts". Nov 9: its
# MARKET FACTS block, when present, is checked against note.json "market_facts" and every market number shown.
import json, re, sys, html, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import SITE_URL, SITE_LABEL
from render import (data_checks, target_gaps, with_facts, facts_block, facts_by_sym, facts_sym, facts_v2,
                    parse_fact, market_block, parse_market, money, pct, unwrap_log)
BANNED = ["stocktwits.com", "boerse-express", "gurufocus.com", "marketbeat.com", "trefis.com", "tradingkey",
          "simplywall.st", "kalkine", "zacks.com", "ad-hoc-news", "defenseworld", "ts2.tech", "parameter.io",
          "reddit.com", "seekingalpha.com/instablog", "weissratings"]
MATERIAL = {"Earnings", "Guidance", "M&A", "Management", "Legal", "Regulatory", "Rating", "Credit", "Dividend change", "Move"}
CATEGORIES = MATERIAL | {"Release", "Filing", "Insider", "Ownership", "Analyst", "Dividend", "Media", "Event", "Update"}
AI_CATEGORIES = {"Results", "Move", "Deal", "Funding", "Policy", "Analyst", "Strategist", "Breakthrough"}
URL = r"https?://|www\."
MAX_KB, WARN_KB = 72, 60  # PM proxy decision 28 (2026-11-06): FAIL above 72 KB, WARN above 60 KB
ROW = re.compile(r"<tr[^>]*>((?:(?!<tr[ >]).)*?)</tr>", re.S)  # innermost rows only
CELL = re.compile(r"<td([^>]*)>(.*?)</td>", re.S)
NAME_CELL = re.compile(r"<b[^>]*>([^<]+)</b><br><span[^>]*>[^<]*</span><br>(.*?)</td>", re.S)


def txt(x):
    return html.unescape(re.sub(r"<[^>]+>", "", x)).strip()


def redirects(x):
    """Each google.com/url link (or line holding one) still in a rendered note or admin text."""
    return [m.group(0) for m in re.finditer(r"[^\s\"'<>|]*google\.com/url\?[^\s\"'<>|]*", x, re.I)]


def first_diff(a, b):
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return "character %d: note %r, source %r" % (i + 1, a[i:i + 12], b[i:i + 12])


def check_facts(d, h, src_text):
    """Facts lines verbatim against the source email's block; every close, 1-day % and valuation row in the HTML
    against that ticker's source line (PM proxy decisions 25-27)."""
    F, W = [], []
    src = facts_block(src_text) if src_text is not None else None
    if not d.get("facts"):
        if src:
            F.append("The source email has a BOOK FACTS block but note.json has no \"facts\"")
        else:
            W.append("No BOOK FACTS block: prices are from the web")
        return F, W
    if src_text is None:
        return ["note.json has facts but no source email was given (check.py note.json note.html note.txt facts_email.txt)"], W
    if src is None:
        return ["The source email has no BOOK FACTS block"], W
    nf = d["facts"]
    if len(nf) != len(src):
        F.append("Facts: note.json has %d lines, the source block %d" % (len(nf), len(src)))
    for k, (a, b) in enumerate(zip(nf, src)):
        if a != b:
            F.append("Facts line %d differs from the source, %s" % (k + 1, first_diff(a, b)))
    W += ["Facts line not understood (no price taken from it): " + l[:80] for l in src if parse_fact(l) is None]
    S = facts_by_sym(src)
    names = set(d["list"]["hold"]) | set(d["list"]["watch"])
    W += ["%s has no facts line: close not confirmed" % t for t in sorted(names) if facts_sym(t) not in S]
    W += ["Facts line for %s matches no list name" % s for s in sorted(S) if s not in {facts_sym(t) for t in names}]
    v2 = facts_v2(S)
    exp, exp2 = {}, {}
    for t in names:
        f = S.get(facts_sym(t))
        ok = f is not None and f["close"] is not None
        exp[t] = (money(f["close"]) if ok else "n/a", txt(pct(f["pct1d"])) if ok else "n/a", f["val"] if f else None)
        if v2:  # 5-day and vs-52w cells: the line's own figures, n/a without its clause (PM proxy decision 39)
            exp2[t] = (txt(pct(f["pct5d"])) if ok else "n/a", txt(pct(f["vs52"])) if ok else "n/a")
    seen, vals, last = set(), {}, None
    for row in ROW.findall(h):
        cells = CELL.findall(row)
        if len(cells) == 5 and txt(cells[0][1]) in exp:
            last = txt(cells[0][1])
            seen.add(last)
            c, p, _ = exp[last]
            if txt(cells[1][1]) != c:
                F.append("Prices: %s close shows %s, its facts line says %s" % (last, txt(cells[1][1]), c))
            if txt(cells[2][1]) != p:
                F.append("Prices: %s 1-day shows %s, its facts line says %s" % (last, txt(cells[2][1]), p))
            if last in exp2:
                for k, what in ((3, "5-day"), (4, "vs 52-week high")):
                    if txt(cells[k][1]) != exp2[last][k - 3]:
                        F.append("Prices: %s %s shows %s, its facts line says %s" % (last, what, txt(cells[k][1]), exp2[last][k - 3]))
        elif len(cells) == 1 and 'colspan="5"' in cells[0][0] and last:
            vals[last] = txt(cells[0][1])
            last = None
        else:
            last = None
    for t in sorted(seen):
        want, got = exp[t][2], vals.get(t)
        if want != got:
            F.append("Prices: %s valuation line %s" % (t, "missing" if got is None else "should be absent" if want is None
                                                         else "differs from the source, " + first_diff(got, want)))
    cur = {p["ticker"]: p.get("currency", "USD") for g in ("holdings", "watchlist") for p in with_facts(d)["prices"][g]}
    for t, rest in NAME_CELL.findall(h):
        t = txt(t)
        if t not in exp:
            continue
        sub = txt(re.split(r"<br\s*/?>", rest)[0])
        c, p, _ = exp[t]
        want = "close not confirmed" if c == "n/a" else "%s %s %s" % (cur.get(t, "USD"), c, p)
        if sub != want:
            F.append("%s shows %r under its name; its facts line gives %r" % (t, sub, want))
    return F, W


MARKET_LABELS = {"spx": "S&P 500", "ndx": "Nasdaq 100", "tsx": "S&P/TSX", "usdcad": "USD/CAD"}
SAME_DAY = re.compile(r"S&P 500 same day (\S+)")


def check_market(d, h, src_text):
    """Every market number the source email's MARKET FACTS block carries, as shown in the note's market box and the
    prices line, and note.json's market_facts word for word against the block (PM proxy decision 39)."""
    F, W = [], []
    src = market_block(src_text) if src_text is not None else None
    if src is None:
        if d.get("market_facts"):
            F.append("note.json has market_facts but the source email has no MARKET FACTS block")
        elif src_text is not None:
            W.append("No MARKET FACTS block in the source email: market numbers are from the web")
        return F, W
    nm = d.get("market_facts")
    if not nm:
        W.append("note.json has no market_facts: the market box was built from the web and is checked against the block")
    else:
        if len(nm) != len(src):
            F.append("Market facts: note.json has %d lines, the source block %d" % (len(nm), len(src)))
        for k, (a, b) in enumerate(zip(nm, src)):
            if a != b:
                F.append("Market facts line %d differs from the source, %s" % (k + 1, first_diff(a, b)))
    M = parse_market(src)
    W += ["Market facts line not understood: " + l[:80] for l in src if not any(v["line"] == l for v in M.values())]
    want = {k: txt(pct(v["pct1d"])) if k != "usdcad" else "{:.4f}".format(v["rate"]) for k, v in M.items()}
    shown = {}
    for row in ROW.findall(h):
        cells = CELL.findall(row)
        if len(cells) == 2:
            shown.setdefault(txt(cells[0][1]), txt(cells[1][1]))
    for k, v in want.items():
        got = shown.get(MARKET_LABELS[k])
        if got is None:
            F.append("Market: %s is in the facts block but not in the note's market box" % MARKET_LABELS[k])
        elif got != v:
            F.append("Market: %s shows %s, the facts block says %s" % (MARKET_LABELS[k], got, v))
    m = SAME_DAY.search(html.unescape(re.sub(r"<[^>]+>", "", h)))
    if m and "spx" in want and m.group(1) != want["spx"]:
        F.append("Prices line: S&P 500 same day shows %s, the facts block says %s" % (m.group(1), want["spx"]))
    return F, W


SITE_WRAP = re.compile(r'<div data-bm="site-link"[^>]*>(.*?)</div>', re.S)


def check_site_link(h):
    """Nov 10: exactly one element marked data-bm="site-link", holding one link, to SITE_URL, labelled SITE_LABEL."""
    wraps = SITE_WRAP.findall(h)
    if len(wraps) != 1:
        return ["Open-your-book link %s (data-bm=\"site-link\")" % ("missing" if not wraps else "repeated %d times" % len(wraps))]
    a = re.findall(r'<a href="([^"]*)"[^>]*>(.*?)</a>', wraps[0], re.S)
    if len(a) != 1:
        return ["Open-your-book block holds %d links, not 1" % len(a)]
    href, label = html.unescape(a[0][0]), html.unescape(re.sub(r"<[^>]+>", "", a[0][1])).strip()
    F = []
    if href != SITE_URL:
        F.append("Open-your-book link points to %s, not %s" % (href[:80], SITE_URL))
    if label != SITE_LABEL:
        F.append("Open-your-book link reads %r, not %r" % (label[:40], SITE_LABEL))
    return F


def check_note(dp, hp, tp, fp=None):
    d, h, t = json.load(open(dp, encoding="utf-8")), open(hp, encoding="utf-8").read(), open(tp, encoding="utf-8").read()
    src_text = open(fp, encoding="utf-8").read() if fp else None
    F, W = check_facts(d, h, src_text)
    F2, W2 = check_market(d, h, src_text)
    F, W = F + F2, W + W2
    F += check_site_link(h)
    da = with_facts(d)
    vt = html.unescape(re.sub(r"<[^>]+>", " ", h))
    if re.search(URL, vt):
        F.append("Visible URL in text: " + re.search(r"\S*(https?://|www\.)\S*", vt).group(0)[:80])
    for href, label in re.findall(r'<a href="([^"]*)"[^>]*>(.*?)</a>', h):
        if href.startswith("#"):
            F.append("In-email jump link: " + href)
        elif not href.startswith(("http://", "https://")):
            F.append("Link without http(s): " + href[:80])
        if re.search(URL, html.unescape(label)):
            F.append("Link text is a URL: " + label[:80])
        F += ["Banned source %s: %s" % (b, href[:80]) for b in BANNED if b in href.lower()]
    F += ["Google redirect link left (render.py unwraps them): " + l[:100] for l in redirects(h)]
    if "—" in vt:
        F.append("Em dash in text")
    if re.search(r"background", h, re.I):
        F.append("Background style present")
    F += ["Markdown symbol in text: " + s for s in ("**", "##", "](http") if s in vt]
    P = [p for g in ("holdings", "watchlist") for p in da["prices"][g]]
    want, have = set(d["list"]["hold"]) | set(d["list"]["watch"]), set(p["ticker"] for p in P)
    if want - have:
        F.append("List names missing from Prices: " + ", ".join(sorted(want - have)))
    if have - want:
        F.append("Prices has names not on the list: " + ", ".join(sorted(have - want)))
    miss = [p["ticker"] for p in P if p.get("close") is None]
    if miss:
        W.append("Close not confirmed: " + ", ".join(miss))
    nohi = [p["ticker"] for p in P if p.get("close") is not None and not p.get("high52")]
    if nohi:
        W.append("No 52-week high: " + ", ".join(nohi))
    if not d.get("price_session_date"):
        W.append("price_session_date missing, so price dates were not checked")
    W += ["Data check shown in note: " + c for c in data_checks(da)]
    W += ["Target gap (admin only, put under Data conflicts): " + c for c in target_gaps(da)]
    for x in (h, t):
        if "--- CURRENT LIST ---" not in x or "--- END LIST ---" not in x:
            F.append("List block missing from " + ("HTML" if x is h else "plain text"))
    tks = [tk for s in ("holdings", "watchlist") for tk in d.get(s) or []]
    for tk in tks:
        for it in tk.get("items", []):
            if not it.get("links"):
                F.append("%s item without a link: %s" % (tk["ticker"], it["text"][:60]))
            if not it.get("date"):
                F.append("%s item without a date: %s" % (tk["ticker"], it["text"][:60]))
            if it.get("category") not in CATEGORIES:
                F.append("%s item has unknown category %r" % (tk["ticker"], it.get("category")))
    F += ["Also-today item without a link: " + a["text"][:60] for a in d.get("also_today") or [] if not a.get("links")]
    ai, names = d.get("ai") or [], set(d["list"]["hold"]) | set(d["list"]["watch"])
    if len(ai) > 8:
        F.append("AI section has %d items (max 8)" % len(ai))
    for it in ai:
        if not it.get("links"):
            F.append("AI item without a link: " + it["text"][:60])
        if not it.get("date"):
            F.append("AI item without a date: " + it["text"][:60])
        if it.get("category") not in AI_CATEGORIES:
            F.append("AI item has unknown category %r (use %s)" % (it.get("category"), ", ".join(sorted(AI_CATEGORIES))))
        if it.get("name") in names:
            F.append("AI item is about list name %s; put it under the ticker instead" % it["name"])
    top = d.get("top") or []
    if len(top) > 5:
        F.append("Top has %d rows (max 5)" % len(top))
    if len(top) != len(set(r["ticker"] for r in top)):
        F.append("Top repeats a ticker")
    ok = {tk["ticker"] for tk in tks if any(it.get("category") in MATERIAL for it in tk.get("items", []))}
    ok |= {eb["ticker"] for eb in d.get("earnings") or [] if eb.get("kind") == "results"}
    ok |= {x["ticker"] for x in d.get("no_source_moves") or []}
    F += ["Top row %s has no material item (categories %s), earnings result or unexplained move below"
          % (r["ticker"], ", ".join(sorted(MATERIAL))) for r in top if r["ticker"] not in ok]
    if not d.get("summary"):
        W.append("No summary line")
    F += ["%s preview has %d paragraphs (max 4)" % (eb["ticker"], len(eb["paragraphs"])) for eb in d.get("earnings") or []
          if eb.get("kind") == "preview" and len(eb.get("paragraphs", [])) > 4]
    if not d.get("sedi_names"):
        W.append("sedi_names empty: the SEDI disclosure line will not show")
    size = len(h.encode("utf-8"))
    if size > MAX_KB * 1024:
        F.append("HTML is %.1f KB, over the %d KB limit. Shorten items or move minor ones to Also today." % (size / 1024, MAX_KB))
    elif size > WARN_KB * 1024:
        W.append("HTML is %.1f KB, close to the %d KB limit" % (size / 1024, MAX_KB))
    return F, W, "PASS (%.1f KB)" % (size / 1024)


def check_admin(ap, tp):
    a, t = json.load(open(ap, encoding="utf-8")), open(tp, encoding="utf-8").read()
    F, W = [], []
    F += ["Admin plain text is missing the %s block" % s for s, x in (("--- SENT LOG ---", "--- END LOG ---"),
          ("--- CLOSES ---", "--- END CLOSES ---")) if s not in t or x not in t]
    F += ["Bad log line (want YYYY-MM-DD|TICKER|key|url): " + l[:80] for l in a.get("log") or []
          if l.count("|") < 3 or not re.match(r"\d{4}-\d{2}-\d{2}\|", l)]
    F += ["Bad closes line (want YYYY-MM-DD TICKER=close,...): " + l[:80] for l in a.get("closes") or []
          if not re.match(r"\d{4}-\d{2}-\d{2} [A-Z.]+=", l)]
    F += ["Google redirect link left in the admin (render.py unwraps them): " + l[:100] for l in redirects(t)]
    if not a.get("closes"):
        W.append("No closes stored; tomorrow's 5-day % will be blank")
    if len(t.encode("utf-8")) > 200 * 1024:
        W.append("Admin plain text over 200 KB; prune the log to the last 10 sessions")
    return F, W, "PASS (admin log %d lines, closes %d lines)" % (len(unwrap_log(a.get("log"))), len(a.get("closes") or []))


if __name__ == "__main__":
    v = sys.argv[1:]
    F, W, ok = check_admin(v[1], v[2]) if v and v[0] == "--admin" else check_note(*v[:4])
    for x in F:
        print("FAIL: " + x)
    for x in W:
        print("WARN: " + x)
    if not F:
        print(ok)
    sys.exit(1 if F else 0)
