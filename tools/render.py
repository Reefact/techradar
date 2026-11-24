#!/usr/bin/env python3
"""Rendu du site à partir des fichiers du jour (data/days/AAAA/AAAAMMJJ.json).

  python3 tools/render.py <dossier_de_sortie> [SITE_URL]

Produit dans le dossier de sortie :
  reports/AAAA/AAAAMMJJ.html   rapport publié (sujets « publie » seulement)
  dossier/AAAA/AAAAMMJJ.html   dossier du jour (tous les sujets, statuts, journal)
  dossier/dossier.json         liste des jours pour la page /dossier/
  feed.xml                     flux Atom des rapports publiés
"""
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veille_lib import (SUFFIX, STATUTS, blocks, config, day_files, inline, load_json, ordered_categories,  # noqa: E402
                        plain, published, titre_jour)

E = lambda s: html.escape(s or "", quote=True)
HEAD = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title}</title>
<meta name="date" content="{date}">{extra_head}
<link rel="stylesheet" href="../../assets/report.css">
<link rel="icon" type="image/png" sizes="32x32" href="../../assets/favicon-32.png">
<link rel="icon" type="image/png" sizes="192x192" href="../../assets/icon-192.png">
<link rel="apple-touch-icon" href="../../assets/apple-touch-icon.png">
</head>
<body>
"""


# ---------- briques ----------
def tag_html(t, tags):
    key, txt = (t, None) if isinstance(t, str) else (t["tag"], t.get("texte"))
    d = tags[key]
    return f'<span class="badge {d["classe"]}">{E(txt or d["label"])}</span>'


# Icône « badge-check » (Lucide, licence ISC), dessinée en ligne pour rester sans dépendance.
BADGE_CHECK = ('<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
               'stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 '
               '4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"/>'
               '<path d="m9 12 2 2 4-4"/></svg>')
VERIF_TIP = {"vrai": "Information vérifiée — voir le détail", "faux": "Information démentie — voir le détail",
             "indetermine": "Vérification non tranchée — voir le détail"}
VERDICT_LABEL = {"vrai": "Vrai", "faux": "Faux", "indetermine": "Non tranché"}
VERDICT_CLASSE = {"vrai": "b-tool", "faux": "b-alert", "indetermine": "b-api"}


def date_fr(iso):
    """« 2026-11-24T06:40+01:00 » → « 24/11/2026 à 06:40 » (ou la date seule)."""
    d, _, h = (iso or "").partition("T")
    if len(d) != 10:
        return iso or ""
    return f"{d[8:]}/{d[5:7]}/{d[:4]}" + (f" à {h[:5]}" if len(h) >= 5 else "")


def link(x):
    return f'<a href="{E(x["url"])}" target="_blank" rel="noopener">{inline(x["texte"])}</a>'


def verif_button(s):
    v = s.get("verification")
    if not v:
        return ""
    vid, tip = f'verif-{s["id"]}', VERIF_TIP.get(v.get("verdict"), VERIF_TIP["vrai"])
    return (f'<button type="button" class="vf-btn vf-{E(v.get("verdict", ""))}" popovertarget="{vid}" title="{E(tip)}" '
            f'aria-label="{E(tip)}">{BADGE_CHECK}</button>')


def verif_popover(s):
    """Fenêtre de la vérification (API « popover » : sans JavaScript, fermeture par Échap, clic à côté ou bouton)."""
    v = s.get("verification")
    if not v:
        return ""
    vid, verdict = f'verif-{s["id"]}', v.get("verdict", "")
    src = v.get("source") or {}
    o = [f'<div class="vf-pop" id="{vid}" popover role="dialog" aria-labelledby="{vid}-t">',
         f'  <div class="vf-top"><span class="vf-ico vf-{E(verdict)}">{BADGE_CHECK}</span>'
         f'<p class="vf-title" id="{vid}-t">Vérification de l\'information</p>'
         f'<button type="button" class="vf-close" popovertarget="{vid}" popovertargetaction="hide" aria-label="Fermer">×</button></div>',
         f'  <p class="vf-subject">{inline(s["titre"])}</p>',
         f'  <p class="vf-meta"><span class="badge {VERDICT_CLASSE.get(verdict, "b-api")}">{E(VERDICT_LABEL.get(verdict, verdict))}</span> '
         f'vérifié le {E(date_fr(v.get("date")))}</p>']
    o += blocks(v.get("resume", ""))
    if src:
        o.append(f'  <p class="vf-h">Source initiale</p>')
        o.append(f'  <p><strong>{inline(src.get("nom", ""))}</strong>' + (f" — {inline(src['nature'])}" if src.get("nature") else "") + "</p>")
    if v.get("affirmations"):
        o.append('  <p class="vf-h">Affirmations vérifiées</p>')
        o.append('  <ul class="vf-list vf-ok">' + "".join(
            f'<li>{inline(a["texte"])}' + (f'<span class="vf-proof">{" · ".join(link(p) for p in a.get("preuves", []))}</span>' if a.get("preuves") else "") + "</li>"
            for a in v["affirmations"]) + "</ul>")
    if v.get("retirees"):
        o.append('  <p class="vf-h">Retiré du résumé</p>')
        o.append('  <ul class="vf-list vf-ko">' + "".join(
            f'<li>{inline(r["texte"])}<span class="vf-proof">{inline(r.get("raison", ""))}</span></li>' for r in v["retirees"]) + "</ul>")
    if v.get("ecarts"):
        o.append('  <p class="vf-h">Écarts entre sources</p>')
        o.append('  <ul class="vf-list">' + "".join(f"<li>{inline(x)}</li>" for x in v["ecarts"]) + "</ul>")
    if v.get("recoupements"):
        o.append('  <p class="vf-h">Recoupements</p>')
        o.append('  <ul class="vf-list">' + "".join(f"<li>{link(r)}</li>" for r in v["recoupements"]) + "</ul>")
    o.append("</div>")
    return "\n".join(o)


def card(s, cfg, statut_badge=None):
    cats, tags = cfg["categories"], cfg["tags"]
    c = cats[s["categorie"]]
    repo = f' data-repo="{E(s["depot"])}"' if s.get("depot") else ""
    badges = f'<span class="badge {c["classe"]}">{E(s.get("etiquette") or c["carte"])}</span>' + "".join(tag_html(t, tags) for t in s.get("tags", []))
    if statut_badge:
        badges = statut_badge + badges
    out = [f'<article class="card" id="{E(s["id"])}"{repo}>', f'  <div class="head">{badges}<h3>{inline(s["titre"])}</h3>{verif_button(s)}</div>']
    out += blocks(s.get("resume", ""))
    if s.get("details"):
        out.append('  <dl class="kv">' + "".join(f"<dt>{E(k)}</dt><dd>{inline(v)}</dd>" for k, v in s["details"].items()) + "</dl>")
    if s.get("pourquoi"):
        out.append(f'  <p class="why">{inline(s["pourquoi"])}</p>')
    links = [f'<a href="{E(x["url"])}" target="_blank" rel="noopener">{inline(x["texte"])}</a>' for x in s.get("sources", [])]
    links.append('<a class="back" href="#top">↑ sommaire</a>')
    out.append("  " + " · ".join(links))
    out.append("</article>")
    if s.get("verification"):
        out.append(verif_popover(s))
    return "\n".join(out)


def toc_item(s, cfg):
    tags = "".join(tag_html(t, cfg["tags"]) + " " for t in s.get("tags", []))
    meta = f'<span class="meta">{inline(s["meta"])}</span>' if s.get("meta") else ""
    return f'  <a class="item" href="#{E(s["id"])}">{tags}<strong>{inline(s.get("titre_sommaire") or s["titre"])}</strong>{meta}</a>'


def by_category(sujets, cfg):
    cats = cfg["categories"]
    order = {k: i for i, k in enumerate(ordered_categories(cats))}
    groups = {}
    for s in sujets:
        groups.setdefault(s["categorie"], []).append(s)
    return [(k, groups[k]) for k in sorted(groups, key=lambda k: order.get(k, 99))]


# ---------- rapport publié ----------
def render_report(day, cfg):
    cats = cfg["categories"]
    pub = published(day)
    conf = [s for s in pub if s["categorie"] == "conferences"]
    rest = [s for s in pub if s["categorie"] != "conferences"]
    h1 = titre_jour(day["date"])
    o = [HEAD.format(title=E(h1 + SUFFIX), date=day["date"], extra_head=""), '<div class="wrap">', "<header>",
         f"  <h1>{E(h1)}</h1>", f'  <p class="sub">{inline(day.get("sous_titre", ""))}</p>', "</header>", "",
         '<h2 id="top">À retenir aujourd\'hui</h2>', '<div class="card tldr"><ul>']
    o += [f"  <li>{inline(x['texte'])}</li>" for x in day.get("a_retenir", [])]
    o += ["</ul></div>", "", "<h2>Sommaire</h2>", '<div class="toc">']
    groups = by_category(rest, cfg)
    for i, (k, items) in enumerate(groups):
        o.append(f'  <span class="badge {cats[k]["classe"]}">{E(cats[k]["label"])}</span>')
        o += [toc_item(s, cfg) for s in items]
        if i < len(groups) - 1:
            o.append("")
    o += ["</div>", ""]
    if conf:
        o += [f"<h2>{E(cats['conferences']['label'])}</h2>", '<div class="tablewrap"><table>',
              "<thead><tr><th>Événement</th><th>Dates</th><th>Lieu</th><th>Date limite CFP</th></tr></thead>", "<tbody>"]
        for s in conf:
            k = s.get("conference", {})
            tags = "".join(" " + tag_html(t, cfg["tags"]) for t in s.get("tags", []))
            o.append(f'<tr><td><a href="#{E(s["id"])}">{inline(s.get("titre_sommaire") or s["titre"])}</a>{tags}</td>'
                     f'<td>{inline(k.get("dates", ""))}</td><td>{inline(k.get("lieu", ""))}</td><td>{inline(k.get("cfp", ""))}</td></tr>')
        o += ["</tbody></table></div>", ""]
    brief = published(day, "en_bref")
    if brief:
        o += ["<h2>En bref</h2>", '<ul class="brief">'] + [f"  <li>{inline(b['texte'])}</li>" for b in brief] + ["</ul>", ""]
    o += ["<h2>Résumés</h2>", '<div class="sum">']
    for i, (k, items) in enumerate(by_category(pub, cfg)):
        o.append(f'<h3 style="margin-top:{8 if i == 0 else 12}px"><span class="badge {cats[k]["classe"]}">{E(cats[k]["label"])}</span></h3>')
        for s in items:
            o += ["", card(s, cfg)]
        o.append("")
    o += ["</div>", "", "<footer>"] + [f"  <p>{inline(p)}</p>" for p in day.get("pied", [])] + ["</footer>", "</div>", "", "</body></html>", ""]
    return "\n".join(o)


# ---------- dossier du jour ----------
EXEC_LABEL = {"planifiee": "planifiée", "manuelle": "manuelle"}
STATUT_LABEL = {"publie": "Publié", "candidat": "Candidat", "mis-de-cote": "Mis de côté", "ecarte": "Écarté"}
STATUT_CLASSE = {"publie": "b-tool", "candidat": "b-api", "mis-de-cote": "b-ia", "ecarte": "b-alert"}
MOTIF_LABEL = {"deja-publie": "déjà publié", "hors-fenetre": "hors fenêtre de dates", "hors-perimetre": "hors périmètre",
               "non-verifiable": "source non vérifiable", "doublon": "doublon", "trop-mineur": "trop mineur",
               "plafond-atteint": "plafond de la catégorie atteint", "exclu-config": "exclu par la configuration",
               "rien-de-neuf": "vérifié, rien de neuf", "infirme": "information démentie après vérification"}

DOSSIER_STYLE = """<style>
.dz-stats{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 6px}
.dz-stats .badge{font-size:.72rem}
.dz-filters{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 20px}
.dz-filters button{font:600 .72rem/1 var(--font-m);letter-spacing:.06em;text-transform:uppercase;padding:7px 11px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--mute);cursor:pointer}
.dz-filters button[aria-pressed="true"]{border-color:var(--accent);color:var(--accent)}
.dz-journal{font-size:.88rem}
.dz-journal dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:6px 0 0}
.dz-journal dt{color:var(--mute)}
.dz-line{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;padding:9px 12px;margin:6px 0;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
.dz-line .t{font-weight:600}.dz-line .m{color:var(--mute);font-size:.82rem}
.dz-legend{font-size:.85rem;color:var(--mute)}.dz-legend dt{color:var(--fg)}
.dz-ask{display:flex;width:max-content;margin-top:12px;font:600 .72rem/1 var(--font-m);letter-spacing:.06em;text-transform:uppercase;padding:7px 12px;border-radius:999px;border:1px dashed currentColor;background:transparent;color:var(--accent);cursor:pointer}
details.card>summary{cursor:pointer;list-style:none}details.card>summary::-webkit-details-marker{display:none}
details.card[open]>summary{margin-bottom:8px}
</style>
"""


def statut_badge(s):
    st = s.get("statut", "candidat")
    return f'<span class="badge {STATUT_CLASSE[st]}" data-statut="{st}">{STATUT_LABEL[st]}</span>'


def render_dossier(day, cfg):
    cats, tags = cfg["categories"], cfg["tags"]
    allt = day.get("sujets", [])
    count = {st: sum(1 for s in allt if s.get("statut") == st) for st in STATUTS}
    h1 = titre_jour(day["date"])
    o = [HEAD.format(title=E("Dossier du " + h1.removeprefix("Veille technologique du ") + SUFFIX), date=day["date"],
                     extra_head='\n<meta name="robots" content="noindex, nofollow">').replace("<body>", "<body>\n" + DOSSIER_STYLE.rstrip()),
         '<div class="wrap">', "<header>", f"  <h1>Dossier du {E(h1.removeprefix('Veille technologique du '))}</h1>",
         '  <p class="sub">Tous les sujets analysés pour ce jour : publiés, candidats, mis de côté, écartés (avec leur motif).</p>',
         '  <div class="dz-stats">' + "".join(f'<span class="badge {STATUT_CLASSE[st]}">{STATUT_LABEL[st]} : {count[st]}</span>' for st in STATUTS) + "</div>",
         "</header>", ""]
    # journal de recherche
    j = day.get("journal", {})
    rows = []
    if j.get("recherches"):
        rows.append(("Recherches", ", ".join(f"{cats.get(k, {}).get('label', k)} : {v}" for k, v in j["recherches"].items())))
    if j.get("pages_ouvertes") is not None:
        rows.append(("Pages ouvertes", str(j["pages_ouvertes"])))
    if j.get("sources_illisibles"):
        rows.append(("Sources illisibles", ", ".join(j["sources_illisibles"])))
    vs = j.get("verifications_sources")
    if vs:
        rows.append(("Vérifications", f"{vs.get('lancees', 0)} lancée(s) : {vs.get('vrai', 0)} vrai, {vs.get('faux', 0)} faux, {vs.get('indetermine', 0)} non tranchée(s)"))
    for h in j.get("hypotheses", []):
        rows.append(("Hypothèse", h))
    for x in day.get("executions", []):
        rows.append(("Exécution", f"{EXEC_LABEL.get(x.get('type'), x.get('type', '?'))} · {x.get('debut', '?')}" + (f" · {x['note']}" if x.get("note") else "")))
    o += ['<h2 id="top">Journal de recherche</h2>', '<div class="card dz-journal">']
    o.append("  <dl>" + "".join(f"<dt>{E(k)}</dt><dd>{inline(v)}</dd>" for k, v in rows) + "</dl>" if rows else "  <p>Pas de journal pour ce jour (rapport antérieur au dossier).</p>")
    o += ["</div>", ""]
    # filtres
    o += ['<div class="dz-filters" role="group" aria-label="Filtrer par statut">',
          '  <button type="button" data-f="tous" aria-pressed="true">Tous</button>'] + \
         [f'  <button type="button" data-f="{st}" aria-pressed="false">{STATUT_LABEL[st]}</button>' for st in STATUTS] + ["</div>", ""]
    # sujets par catégorie
    o += ["<h2>Sujets</h2>", '<div class="sum">']
    for i, (k, items) in enumerate(by_category(allt, cfg)):
        o.append(f'<h3 style="margin-top:{8 if i == 0 else 12}px"><span class="badge {cats[k]["classe"]}">{E(cats[k]["label"])}</span></h3>')
        for s in items:
            st = s.get("statut", "candidat")
            if st == "ecarte" or (not s.get("resume") and st != "publie"):
                motif = MOTIF_LABEL.get(s.get("motif"), s.get("motif") or "")
                src = " · ".join(f'<a href="{E(x["url"])}" target="_blank" rel="noopener">{inline(x["texte"])}</a>' for x in s.get("sources", []))
                o += ["", f'<div class="dz-line" data-statut="{st}" id="{E(s["id"])}">{statut_badge(s)}<span class="t">{inline(s["titre"])}</span>'
                          f'<span class="m">{E(motif)}{" · " + inline(s["note"]) if s.get("note") else ""}</span>{(" " + src) if src else ""}{verif_button(s)}</div>']
                if s.get("verification"):
                    o.append(verif_popover(s))
            else:
                body = card(s, cfg, statut_badge(s)).replace(' · <a class="back" href="#top">↑ sommaire</a>', "")
                ask = "" if st == "publie" else f'\n  <button type="button" class="dz-ask" data-ask="Publie le sujet {E(s["id"])} (« {E(plain(s["titre"]))} ») du {day["date"]} dans le rapport.">Demander la publication</button>'
                body = body.replace(f'<article class="card" id="{E(s["id"])}"', f'<article class="card" data-statut="{st}" id="{E(s["id"])}"', 1)
                o += ["", body.replace("\n</article>", ask + "\n</article>")]
        o.append("")
    o += ["</div>", ""]
    # « En bref » et légende
    if day.get("en_bref"):
        o += ["<h2>En bref</h2>", '<ul class="brief">'] + [f'  <li data-statut="{b.get("statut", "candidat")}">{statut_badge(b)} {inline(b["texte"])}</li>' for b in day["en_bref"]] + ["</ul>", ""]
    o += ["<h2>Légende</h2>", '<div class="card dz-legend"><dl class="kv">']
    o += [f'  <dt><span class="badge {c["classe"]}">{E(c["label"])}</span></dt><dd>{E(c["description"])}</dd>' for c in (cats[k] for k in ordered_categories(cats))]
    o += [f'  <dt><span class="badge {t["classe"]}">{E(t["label"])}</span></dt><dd>{E(t["description"])}</dd>' for t in tags.values()]
    o += ["</dl></div>", "</div>", "", DOSSIER_SCRIPT, "</body></html>", ""]
    return "\n".join(o)


DOSSIER_SCRIPT = """<script>
// Filtres par statut, et boutons qui préparent la demande à coller dans Claude (une page statique ne peut pas écrire dans Git).
document.querySelectorAll('.dz-filters button').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.dz-filters button').forEach(x => x.setAttribute('aria-pressed', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('[data-statut]').forEach(el => { if (el.classList.contains('badge')) return; el.hidden = f !== 'tous' && el.dataset.statut !== f; });
}));
document.querySelectorAll('.dz-ask').forEach(b => b.addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(b.dataset.ask); b.textContent = 'Demande copiée : colle-la dans Claude'; }
  catch (e) { prompt('Copie cette demande et colle-la dans Claude :', b.dataset.ask); }
}));
</script>"""


# ---------- flux ----------
def render_feed(days, site):
    site = (site or "").rstrip("/")
    href = lambda rel: f"{site}/{rel}" if site else rel
    entries = [d for d in days if published(d)]
    entries.sort(key=lambda d: d["date"], reverse=True)
    upd = (entries[0]["date"] if entries else datetime.now(timezone.utc).strftime("%Y-%m-%d")) + "T08:00:00Z"
    o = ['<?xml version="1.0" encoding="utf-8"?>', '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="fr">',
         "  <title>TechRadar</title>", "  <subtitle>Veille quotidienne : sécurité, .NET, IA, API et architecture, outils, conférences et CFP.</subtitle>",
         f'  <link rel="self" href="{E(href("feed.xml"))}"/>', f'  <link rel="alternate" href="{E(href("index.html"))}"/>',
         f"  <id>{E(href('feed.xml') if site else 'urn:techradar:feed')}</id>", f"  <updated>{upd}</updated>"]
    for d in entries:
        rel = f"reports/{d['date'][:4]}/{d['date'].replace('-', '')}.html"
        items = [plain(x["texte"]) for x in d.get("a_retenir", [])]
        content = "<ul>" + "".join(f"<li>{E(i)}</li>" for i in items) + "</ul>" if items else ""
        o += ["  <entry>", f"    <title>{E(titre_jour(d['date']))}</title>", f'    <link rel="alternate" href="{E(href(rel))}"/>',
              f"    <id>{E(href(rel) if site else 'urn:techradar:' + d['date'])}</id>", f"    <updated>{d['date']}T08:00:00Z</updated>",
              f"    <summary>{E(' · '.join(items))}</summary>"] + ([f'    <content type="html">{E(content)}</content>'] if content else []) + ["  </entry>"]
    o.append("</feed>")
    return "\n".join(o) + "\n"


def main(out, site=""):
    out = Path(out)
    cfg = config()
    days = [load_json(p) for p in day_files()]
    listing = []
    for d in days:
        y, stem = d["date"][:4], d["date"].replace("-", "")
        for sub, fn in (("reports", render_report), ("dossier", render_dossier)):
            if sub == "reports" and not published(d):
                continue
            p = out / sub / y / f"{stem}.html"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(fn(d, cfg), encoding="utf-8")
        st = {k: sum(1 for s in d.get("sujets", []) if s.get("statut") == k) for k in STATUTS}
        listing.append({"date": d["date"], "href": f"{y}/{stem}.html", "titre": titre_jour(d["date"]), "statuts": st})
    (out / "dossier").mkdir(parents=True, exist_ok=True)
    (out / "dossier" / "dossier.json").write_text(json.dumps(sorted(listing, key=lambda x: x["date"], reverse=True), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "feed.xml").write_text(render_feed(days, site), encoding="utf-8")
    print(f"rendu : {len(days)} jour(s), {sum(1 for d in days if published(d))} rapport(s) publié(s) → {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dist", sys.argv[2] if len(sys.argv) > 2 else "")
