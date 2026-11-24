#!/usr/bin/env python3
"""Génère feed.xml (Atom) à partir des rapports de reports/**/*.html.

Usage : python3 tools/build_feed.py [URL_DU_SITE]
Sans URL (ou via SITE_URL), les liens du flux sont relatifs à feed.xml.
"""
import html, re, sys, os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
SITE = ((sys.argv[1] if len(sys.argv) > 1 else "") or os.environ.get("SITE_URL", "")).rstrip("/")
TITLE = "TechRadar"
SUBTITLE = "Veille quotidienne : sécurité, .NET, IA, API et architecture, outils, conférences et CFP."

def meta_date(t):
    m = re.search(r'<meta\s+name="date"\s+content="(\d{4}-\d{2}-\d{2})"', t)
    return m.group(1) if m else None

def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()

entries = []
for p in sorted((ROOT / "reports").rglob("*.html")):
    t = p.read_text(encoding="utf-8")
    date = meta_date(t)
    if not date:
        print(f"ignoré (pas de <meta name=\"date\">) : {p}", file=sys.stderr)
        continue
    title = text(re.search(r"<title>(.*?)</title>", t, re.S).group(1)).removesuffix(" \u2013 Reefact")   # le suffixe est redondant dans le flux
    tldr = re.search(r'<div class="card tldr">(.*?)</div>', t, re.S)
    items = [text(x) for x in re.findall(r"<li>(.*?)</li>", tldr.group(1), re.S)] if tldr else []
    rel = p.relative_to(ROOT).as_posix()
    entries.append((date, title, rel, items))

entries.sort(reverse=True)
href = lambda rel: f"{SITE}/{rel}" if SITE else rel
esc = lambda s: html.escape(s, quote=True)
upd = (entries[0][0] if entries else datetime.now(timezone.utc).strftime("%Y-%m-%d")) + "T08:00:00Z"

out = ['<?xml version="1.0" encoding="utf-8"?>',
       '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="fr">',
       f"  <title>{esc(TITLE)}</title>",
       f"  <subtitle>{esc(SUBTITLE)}</subtitle>",
       f'  <link rel="self" href="{esc(href("feed.xml"))}"/>',
       f'  <link rel="alternate" href="{esc(href("index.html"))}"/>',
       f"  <id>{esc(href('feed.xml') if SITE else 'urn:techradar:feed')}</id>",
       f"  <updated>{upd}</updated>"]
for date, title, rel, items in entries:
    summary = " · ".join(items)
    content = "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>" if items else ""
    out += ["  <entry>",
            f"    <title>{esc(title)}</title>",
            f'    <link rel="alternate" href="{esc(href(rel))}"/>',
            f"    <id>{esc(href(rel) if SITE else 'urn:techradar:' + date)}</id>",
            f"    <updated>{date}T08:00:00Z</updated>",
            f"    <summary>{esc(summary)}</summary>"]
    if content:
        out.append(f'    <content type="html">{esc(content)}</content>')
    out.append("  </entry>")
out.append("</feed>")
(ROOT / "feed.xml").write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"feed.xml : {len(entries)} rapport(s)")
