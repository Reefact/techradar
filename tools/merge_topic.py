#!/usr/bin/env python3
"""Copie des sujets (cartes, lignes « En bref ») d'un brouillon vers le rapport publié du MÊME jour.

  python3 tools/merge_topic.py list  <brouillon.html>
  python3 tools/merge_topic.py copy  <brouillon.html> [--card ID[,ID…]] [--brief N[,N…]] [--replace NOUVEAU=ANCIEN[,…]] [--apply]

`list` montre ce que le brouillon a en plus ou de différent par rapport au rapport du même jour.
`copy` fait un essai à blanc par défaut (aperçu) ; `--apply` écrit reports/AAAA/AAAAMMJJ.html.
Une copie est refusée si elle introduit une nouvelle erreur de `tools/check_report.py`.
Non gérés : cartes « conférence » (tableau des conférences à part) et « À retenir aujourd'hui ».
"""
import argparse, difflib, re, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_report import check   # noqa: E402

ORDER = ["alert", "radar", "dotnet", "ia", "ddd", "api", "tool", "retail", "conf"]
ART = re.compile(r'<article class="card" id="([^"]+)"[^>]*>.*?</article>', re.S)
HDR = re.compile(r'<h3 style="[^"]*"><span class="badge b-(\w+)">(.*?)</span></h3>', re.S)
URL = re.compile(r'href="(https?://[^"]+)"')
norm = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
strip_id = lambda s: re.sub(r'(<article class="card") id="[^"]+"', r"\1", s, count=1)


def meta_date(t):
    m = re.search(r'<meta\s+name="date"\s+content="(\d{4}-\d{2}-\d{2})"', t)
    return m.group(1) if m else None


def sum_region(t):
    a = t.index('<div class="sum">') + len('<div class="sum">')
    b = t.rindex("</div>", 0, t.index("<footer"))
    return a, b


def blocks(t):
    """Blocs de la zone « Résumés » : en-têtes de catégorie et articles, avec leur catégorie."""
    a, b = sum_region(t)
    seg, out, cat = t[a:b], [], None
    for m in sorted([*HDR.finditer(seg), *ART.finditer(seg)], key=lambda m: m.start()):
        if m.re is HDR:
            cat = m.group(1); out.append({"kind": "hdr", "cat": cat, "label": m.group(2), "s": a + m.start(), "e": a + m.end(), "text": m.group(0)})
        else:
            out.append({"kind": "art", "cat": cat, "id": m.group(1), "s": a + m.start(), "e": a + m.end(), "text": m.group(0)})
    return out


def toc_lines(t):
    a = t.index('<div class="toc">') + len('<div class="toc">')
    b = t.index("</div>", a)
    return a, b, t[a:b]


def brief_items(t):
    m = re.search(r'<ul class="brief">\n(.*?)</ul>', t, re.S)
    return [x.group(0) for x in re.finditer(r"<li>.*?</li>", m.group(1), re.S)] if m else []


def title_of(art):
    m = re.search(r"<h3>(.*?)</h3>", art, re.S)
    return norm(m.group(1)) if m else "?"


def paths(draft):
    d = Path(draft)
    t = d.read_text(encoding="utf-8")
    date = meta_date(t)
    if not date: sys.exit("Brouillon sans <meta name=\"date\">.")
    rep = ROOT / "reports" / date[:4] / (date.replace("-", "") + ".html")
    if not rep.exists(): sys.exit(f"Aucun rapport publié pour {date} ({rep.relative_to(ROOT)}) : utiliser la promotion du brouillon (workflow « Promote a draft report »).")
    r = rep.read_text(encoding="utf-8")
    if meta_date(r) != date: sys.exit("Les dates du brouillon et du rapport diffèrent.")
    return d, t, rep, r


def analyse(dt, rt):
    rurls = set(URL.findall(rt))
    rarts = {b["id"]: b for b in blocks(rt) if b["kind"] == "art"}
    out = []
    for b in blocks(dt):
        if b["kind"] != "art": continue
        urls = URL.findall(b["text"])
        same_url = [i for i, r in rarts.items() if set(urls) & set(URL.findall(r["text"]))]
        if b["cat"] == "conf": state = "conf"
        elif not urls: state = "sans-url"
        elif not same_url and not (set(urls) & rurls): state = "nouveau"
        else:
            twin = rarts.get(same_url[0]) if same_url else None
            state = "identique" if twin and norm(twin["text"]) == norm(b["text"]) else "differe"
        out.append({"id": b["id"], "cat": b["cat"], "title": title_of(b["text"]), "state": state, "twin": same_url[0] if same_url else None})
    return out


def cmd_list(a):
    d, dt, rep, rt = paths(a.draft)
    print(f"Brouillon : {d}\nRapport   : {rep.relative_to(ROOT)}\n")
    items = analyse(dt, rt)
    for st, label in (("nouveau", "NOUVEAUX (absents du rapport)"), ("differe", "DIFFÉRENTS (même source, texte différent)"), ("identique", "identiques"), ("conf", "conférences (non gérées ici)"), ("sans-url", "sans lien source")):
        sel = [i for i in items if i["state"] == st]
        if not sel: continue
        print(f"{label} : {len(sel)}")
        if st in ("identique",): continue
        for i in sel: print(f"  {i['id']:<5} [{i['cat']}] {i['title'][:90]}" + (f"   (≈ {i['twin']} dans le rapport)" if i["twin"] else ""))
    rurls = set(URL.findall(rt))
    br = brief_items(dt)
    rbr = {norm(li) for li in brief_items(rt)}
    new = [n for n, li in enumerate(br, 1) if not (set(URL.findall(li)) & rurls) and not (not URL.findall(li) and norm(li) in rbr)]
    print(f"\nLIGNES « EN BREF » nouvelles : {len(new)} / {len(br)}")
    for n in new: print(f"  {n:<3} {norm(br[n-1])[:110]}")


def next_id(rt, old):
    prefix = re.match(r"[a-z]+", old).group(0)
    nums = [int(x) for x in re.findall(rf'id="{prefix}(\d+)"', rt)]
    return f"{prefix}{max(nums + [0]) + 1}"


def cat_insert_pos_sum(rt, cat):
    bl = blocks(rt)
    same = [b for b in bl if b["cat"] == cat]
    if same: return max(b["e"] for b in same), False
    idx = ORDER.index(cat) if cat in ORDER else len(ORDER)
    later = [b for b in bl if b["kind"] == "hdr" and (ORDER.index(b["cat"]) if b["cat"] in ORDER else 99) > idx]
    return (min(b["s"] for b in later) if later else sum_region(rt)[1]), True


def add_card(rt, dt, art_id, replace_old=None):
    m = next((x for x in ART.finditer(dt) if x.group(1) == art_id), None)
    if not m: sys.exit(f"Carte {art_id} introuvable dans le brouillon.")
    b = next(b for b in blocks(dt) if b["kind"] == "art" and b["id"] == art_id)
    cat = b["cat"]
    if cat == "conf": sys.exit(f"{art_id} est une carte de conférence : non gérée (le tableau des conférences demande une mise à jour manuelle).")
    hdr_label = next((x["label"] for x in blocks(dt) if x["kind"] == "hdr" and x["cat"] == cat), cat)
    # entrée de sommaire du brouillon
    am = re.search(rf'^[ \t]*<a class="item" href="#{re.escape(art_id)}">.*?</a>[ \t]*$', toc_lines(dt)[2], re.M | re.S)
    toc_item = am.group(0) if am else None
    if not toc_item: sys.exit(f"Entrée de sommaire de {art_id} introuvable dans le brouillon.")
    card = m.group(0)
    if replace_old:
        new_id = replace_old
        old = next((x for x in ART.finditer(rt) if x.group(1) == replace_old), None)
        if not old: sys.exit(f"Carte à remplacer {replace_old} introuvable dans le rapport.")
    else:
        new_id = next_id(rt, art_id)
    card = card.replace(f'id="{art_id}"', f'id="{new_id}"', 1)
    toc_item = toc_item.replace(f'href="#{art_id}"', f'href="#{new_id}"', 1)
    if replace_old:
        rt = rt[:old.start()] + card + rt[old.end():]
        a, b2, seg = toc_lines(rt)
        seg2 = re.sub(rf'^[ \t]*<a class="item" href="#{re.escape(new_id)}">.*?</a>[ \t]*$', lambda _m: toc_item, seg, count=1, flags=re.M | re.S)
        return rt[:a] + seg2 + rt[b2:], new_id, cat
    # insertion dans « Résumés »
    pos, new_cat = cat_insert_pos_sum(rt, cat)
    block = ("\n\n" if not new_cat else "\n") + (f'<h3 style="margin-top:12px"><span class="badge b-{cat}">{hdr_label}</span></h3>\n\n' if new_cat else "") + card
    rt = rt[:pos] + (block if not new_cat else ("\n" + block.lstrip("\n") + "\n\n")) + rt[pos:] if not new_cat else rt[:pos] + block.lstrip("\n") + "\n\n" + rt[pos:]
    # insertion dans le sommaire
    a, b2, seg = toc_lines(rt)
    lines = seg.split("\n")
    hdr_re = re.compile(r'^\s*<span class="badge b-(\w+)">')
    cats = [(i, hdr_re.match(l).group(1)) for i, l in enumerate(lines) if hdr_re.match(l)]
    mine = [i for i, c in cats if c == cat]
    if mine:
        start = mine[0]
        nxt = [i for i, _ in cats if i > start]
        end = (nxt[0] if nxt else len(lines))
        last = max(j for j in range(start, end) if lines[j].lstrip().startswith("<a class=\"item\"") or j == start)
        lines.insert(last + 1, toc_item)
    else:
        idx = ORDER.index(cat) if cat in ORDER else 99
        later = [i for i, c in cats if (ORDER.index(c) if c in ORDER else 99) > idx]
        at = later[0] if later else len(lines) - 1 if lines and lines[-1].strip() == "" else len(lines)
        lines[at:at] = [f'  <span class="badge b-{cat}">{hdr_label}</span>', toc_item, ""]
    return rt[:a] + "\n".join(lines) + rt[b2:], new_id, cat


def add_brief(rt, dt, n):
    items = brief_items(dt)
    if not 1 <= n <= len(items): sys.exit(f"Ligne « En bref » {n} inexistante (1 à {len(items)}).")
    li = items[n - 1]
    if (set(URL.findall(li)) & set(URL.findall(rt))) or norm(li) in {norm(x) for x in brief_items(rt)}: sys.exit(f"Ligne « En bref » {n} : sa source est déjà dans le rapport.")
    i = rt.index("</ul>", rt.index('<ul class="brief">'))
    return rt[:i] + "  " + li + "\n" + rt[i:]


def cmd_copy(a):
    d, dt, rep, rt0 = paths(a.draft)
    if not (a.card or a.brief): sys.exit("Rien à copier : indiquer --card et/ou --brief (voir `list`).")
    repl = dict(x.split("=", 1) for x in a.replace.split(",")) if a.replace else {}
    rt, done = rt0, []
    for cid in (a.card.split(",") if a.card else []):
        rt, new_id, cat = add_card(rt, dt, cid, repl.get(cid)); done.append(f"carte {cid} → #{new_id} ({cat}){' [remplace ' + repl[cid] + ']' if cid in repl else ''}")
    for n in ([int(x) for x in a.brief.split(",")] if a.brief else []):
        rt = add_brief(rt, dt, n); done.append(f"« En bref » n°{n}")
    # contrôle : aucune nouvelle erreur
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f: f.write(rt0); b0 = f.name
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f: f.write(rt); b1 = f.name
    e0, e1 = check(b0)[0], check(b1)[0]
    new_err = [e for e in e1 if e not in e0]
    print("Copie prévue :\n  - " + "\n  - ".join(done))
    diff = list(difflib.unified_diff(rt0.splitlines(), rt.splitlines(), "avant", "après", lineterm="", n=0))
    print(f"\nChangements : {sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))} lignes ajoutées, {sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))} retirées")
    for l in diff[:40]: print("  " + l[:150])
    if new_err:
        print("\nREFUSÉ : la copie introduirait des erreurs :"); [print("  -", e) for e in new_err]; sys.exit(1)
    if a.apply:
        rep.write_text(rt, encoding="utf-8"); print(f"\nÉcrit : {rep.relative_to(ROOT)} (relire, puis commiter sur main).")
    else:
        print("\n(essai à blanc : rien n'a été écrit ; ajouter --apply pour appliquer)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list"); l.add_argument("draft"); l.set_defaults(f=cmd_list)
    c = sub.add_parser("copy"); c.add_argument("draft"); c.add_argument("--card"); c.add_argument("--brief"); c.add_argument("--replace"); c.add_argument("--apply", action="store_true"); c.set_defaults(f=cmd_copy)
    a = ap.parse_args(); a.f(a)
