#!/usr/bin/env python3
# book-monitor v0.9 checker: check.py note.json note.html note.txt | check.py --admin admin.json admin.txt
import json, re, sys, html, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import data_checks, target_gaps
BANNED = ["stocktwits.com", "boerse-express", "gurufocus.com", "marketbeat.com", "trefis.com", "tradingkey",
          "simplywall.st", "kalkine", "zacks.com", "ad-hoc-news", "defenseworld", "ts2.tech", "parameter.io",
          "reddit.com", "seekingalpha.com/instablog", "weissratings"]
MATERIAL = {"Earnings", "Guidance", "M&A", "Management", "Legal", "Regulatory", "Rating", "Credit", "Dividend change", "Move"}
CATEGORIES = MATERIAL | {"Release", "Filing", "Insider", "Ownership", "Analyst", "Dividend", "Media", "Event", "Update"}
AI_CATEGORIES = {"Results", "Move", "Deal", "Funding", "Policy", "Analyst", "Strategist", "Breakthrough"}
URL = r"https?://|www\."


def check_note(dp, hp, tp):
    d, h, t = json.load(open(dp, encoding="utf-8")), open(hp, encoding="utf-8").read(), open(tp, encoding="utf-8").read()
    F, W = [], []
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
    if "—" in vt:
        F.append("Em dash in text")
    if re.search(r"background", h, re.I):
        F.append("Background style present")
    F += ["Markdown symbol in text: " + s for s in ("**", "##", "](http") if s in vt]
    P = [p for g in ("holdings", "watchlist") for p in d["prices"][g]]
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
    W += ["Data check shown in note: " + c for c in data_checks(d)]
    W += ["Target gap (admin only, put under Data conflicts): " + c for c in target_gaps(d)]
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
    kb = len(h.encode("utf-8"))
    if kb > 102 * 1024:
        F.append("HTML is %d KB; Gmail clips above 102 KB. Shorten items or move minor ones to Also today." % (kb // 1024))
    elif kb > 90 * 1024:
        W.append("HTML is %d KB, close to Gmail's 102 KB clip" % (kb // 1024))
    return F, W, "PASS (%d KB)" % (kb // 1024)


def check_admin(ap, tp):
    a, t = json.load(open(ap, encoding="utf-8")), open(tp, encoding="utf-8").read()
    F, W = [], []
    F += ["Admin plain text is missing the %s block" % s for s, x in (("--- SENT LOG ---", "--- END LOG ---"),
          ("--- CLOSES ---", "--- END CLOSES ---")) if s not in t or x not in t]
    F += ["Bad log line (want YYYY-MM-DD|TICKER|key|url): " + l[:80] for l in a.get("log") or []
          if l.count("|") < 3 or not re.match(r"\d{4}-\d{2}-\d{2}\|", l)]
    F += ["Bad closes line (want YYYY-MM-DD TICKER=close,...): " + l[:80] for l in a.get("closes") or []
          if not re.match(r"\d{4}-\d{2}-\d{2} [A-Z.]+=", l)]
    if not a.get("closes"):
        W.append("No closes stored; tomorrow's 5-day % will be blank")
    if len(t.encode("utf-8")) > 200 * 1024:
        W.append("Admin plain text over 200 KB; prune the log to the last 10 sessions")
    return F, W, "PASS (admin log %d lines, closes %d lines)" % (len(a.get("log") or []), len(a.get("closes") or []))


if __name__ == "__main__":
    v = sys.argv[1:]
    F, W, ok = check_admin(v[1], v[2]) if v and v[0] == "--admin" else check_note(*v[:3])
    for x in F:
        print("FAIL: " + x)
    for x in W:
        print("WARN: " + x)
    if not F:
        print(ok)
    sys.exit(1 if F else 0)
