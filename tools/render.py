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
from datetime import date as Date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veille_lib import (SUFFIX, STATUTS, blocks, config, day_files, inline, load_json, ordered_categories, projets,  # noqa: E402
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
MOIS_COURT = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
STATUT_LABEL = {"publie": "Publié", "candidat": "Candidat", "mis-de-cote": "Mis de côté", "ecarte": "Écarté"}
STATUT_CLASSE = {"publie": "b-tool", "candidat": "b-api", "mis-de-cote": "b-ia", "ecarte": "b-alert"}
STATUT_AIDE = {"publie": "Publié dans le rapport du jour.",
               "candidat": "Analysé et rédigé, mais pas publié : peut être ajouté au rapport.",
               "mis-de-cote": "Intéressant mais pas retenu aujourd'hui ; peut revenir un autre jour.",
               "ecarte": "Écarté après analyse ; le motif est indiqué."}
def aide_recent(seuil):
    return (f"Sujets parus depuis le brief précédent ({date_courte(seuil)}), jour compris : "
            "le brief part à 6 h, ce qui paraît ensuite dans la journée n'avait pas encore été vu.")


def date_courte(iso):
    d = Date.fromisoformat(iso)
    return f"{d.day} {MOIS_COURT[d.month - 1]} {d.year}"


def seuil_frais(day, days=()):
    """Un sujet est « récent » si sa date est postérieure ou égale à celle du brief précédent (sinon : la veille)."""
    avant = [d["date"] for d in days if d["date"] < day["date"]]
    return max(avant) if avant else (Date.fromisoformat(day["date"]) - timedelta(days=1)).isoformat()


def badge(classe, texte, aide):
    return f'<span class="badge {classe}" title="{E(aide)}">{E(texte)}</span>'


def tag_key(t):
    return t if isinstance(t, str) else t["tag"]


def tag_html(t, tags):
    d = tags[tag_key(t)]
    return badge(d["classe"], (None if isinstance(t, str) else t.get("texte")) or d["label"], d["description"])


def statut_badge(s):
    st = s.get("statut", "candidat")
    return badge(STATUT_CLASSE[st], STATUT_LABEL[st], STATUT_AIDE[st])


def meta_of(s):
    if s.get("meta"):
        return s["meta"]
    k = s.get("conference") or {}
    parts = [k.get("dates"), k.get("lieu")] + ([f"CFP : {k['cfp']}"] if k.get("cfp") else [])
    return " · ".join(p for p in parts if p)


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


def titre_h3(s, blip=""):
    """Titre du sujet ; s'il y a une vérification, son badge se place juste à gauche du texte."""
    if not s.get("verification"):
        return f'<h3>{blip}{inline(s["titre"])}</h3>'
    return f'<h3 class="vf-h3">{blip}{verif_button(s)}<span>{inline(s["titre"])}</span></h3>'


def projet_badge(s, cfg):
    """Badge 📦 d'un sujet qui touche un de tes dépôts (config/sujets/projets.json)."""
    if not s.get("depot"):
        return ""
    p = projets(cfg).get(s["depot"], {})
    nom = p.get("nom") or s["depot"].split("/")[-1]
    # sur la carte, seule l'icône : le nom du projet est dans l'infobulle (le filtre « Projet » affiche les noms)
    aide = f"Projet {nom}" + (f" ({p['theme']})" if p.get("theme") else "") + f" : dépôt {s['depot']}"
    return f'<span class="badge b-projet" title="{E(aide)}" aria-label="{E(aide)}">📦</span>'


def card(s, cfg, seuil, dossier=False, date_jour=""):
    """Un sujet = un bloc dépliant : en-tête (badges, titre, ligne source · date) ; corps (résumé, détails, sources, actions)."""
    cats, tags = cfg["categories"], cfg["tags"]
    c = cats[s["categorie"]]
    st = s.get("statut", "candidat")
    frais = bool(s.get("date")) and s["date"] >= seuil
    attrs = f' data-cat="{E(s["categorie"])}" data-classe="{E(c["classe"])}" data-tags="{E(" ".join(tag_key(t) for t in s.get("tags", [])))}" data-statut="{st}"'
    if frais: attrs += " data-frais"
    if s.get("depot"): attrs += f' data-repo="{E(s["depot"])}"'
    badges = (statut_badge(s) if dossier else "") + badge(c["classe"], s.get("etiquette") or c["carte"], c["label"] + " : " + c["description"]) \
        + projet_badge(s, cfg) + "".join(tag_html(t, tags) for t in s.get("tags", []))
    blip = (f'<span class="fresh" title="Récent : paru le {date_courte(s["date"])}, depuis le brief précédent ({date_courte(seuil)}, jour compris)" '
            'aria-label="Récent">☄️</span>') if frais else ""
    meta = meta_of(s)
    out = [f'<details class="card" id="{E(s["id"])}"{attrs}>',
           f'  <summary class="head"><span class="badges">{badges}</span>{titre_h3(s, blip)}'
           + (f'<span class="meta">{inline(meta)}</span>' if meta else "") + "</summary>",
           '  <div class="body">']
    out += ["  " + b for b in blocks(s.get("resume", ""))]
    if s.get("details"):
        out.append('  <dl class="kv">' + "".join(f"<dt>{E(k)}</dt><dd>{inline(v)}</dd>" for k, v in s["details"].items()) + "</dl>")
    if dossier and st == "ecarte":
        motif = MOTIF_LABEL.get(s.get("motif"), s.get("motif") or "")
        out.append(f'  <p class="why">Écarté : {E(motif)}{" · " + inline(s["note"]) if s.get("note") else ""}</p>')
    elif s.get("pourquoi"):
        out.append(f'  <p class="why">{inline(s["pourquoi"])}</p>')
    links = " · ".join(f'<a href="{E(x["url"])}" target="_blank" rel="noopener">{inline(x["texte"])}</a>' for x in s.get("sources", []))
    ask = ""
    if dossier and st != "publie":
        ask = (f'<button type="button" class="ask" data-ask="Publie le sujet {E(s["id"])} (« {E(plain(s["titre"]))} ») du {date_jour} dans le rapport.">'
               "Demander la publication</button>")
    if links:
        out.append(f'  <p class="src">{links}</p>')
    out.append(f'  <div class="foot">{ask}<span class="actions"></span>'
               f'<a class="fold" href="#{E(s["id"])}" title="Replier ce sujet" aria-label="Replier ce sujet">⌃</a></div>')
    out += ["  </div>", "</details>"]
    if s.get("verification"):
        out.append(verif_popover(s))   # hors du <details> : visible même sujet replié
    return "\n".join(out)


def ordered(sujets, cfg):
    order = {k: i for i, k in enumerate(ordered_categories(cfg["categories"]))}
    # tri stable : dans une catégorie, les sujets de tes projets d'abord, puis l'ordre du fichier
    return sorted(sujets, key=lambda s: (order.get(s["categorie"], 99), not s.get("depot")))


def filters(sujets, cfg, seuil, dossier=False):
    """Barre de filtres (masquée sans JavaScript) : catégories, projets, tags (dont « récent »), statuts dans le dossier."""
    cats, tags = cfg["categories"], cfg["tags"]
    def chip(group_val, classe, label, aide, n):
        return f'<button type="button" class="chip {classe}" data-v="{E(group_val)}" aria-pressed="false" title="{E(aide)}">{E(label)} <span class="n">{n}</span></button>'
    groups = []
    if dossier:
        groups.append(("statut", "Statut", [chip(st, STATUT_CLASSE[st], STATUT_LABEL[st], STATUT_AIDE[st], n)
                                            for st in STATUTS if (n := sum(1 for s in sujets if s.get("statut") == st))]))
    present = [k for k in ordered_categories(cats) if any(s["categorie"] == k for s in sujets)]
    groups.append(("cat", "Catégorie", [chip(k, cats[k]["classe"], cats[k]["label"], cats[k]["description"], sum(1 for s in sujets if s["categorie"] == k)) for k in present]))
    proj = projets(cfg)
    present_p = [d for d in proj if any(s.get("depot") == d for s in sujets)]
    if present_p:
        groups.append(("projet", "Projet", [chip(d, "b-projet", "📦 " + proj[d]["nom"], f"Touche ton projet {proj[d]['nom']} ({proj[d].get('theme', '')})",
                                                 sum(1 for s in sujets if s.get("depot") == d)) for d in present_p]))
    tchips = []
    nf = sum(1 for s in sujets if s.get("date") and s["date"] >= seuil)
    if nf: tchips.append(chip("frais", "b-fresh", "☄️ Récent", aide_recent(seuil), nf))
    for k, t in tags.items():
        n = sum(1 for s in sujets if k in [tag_key(x) for x in s.get("tags", [])])
        if n: tchips.append(chip(k, t["classe"], (t["label"].replace("J-{n}", "Rappel CFP") if "{n}" in t["label"] else t["label"]), t["description"], n))
    if tchips: groups.append(("tag", "Tag", tchips))
    o = ['<div class="filters" id="filtres" hidden>']
    for g, label, chips in groups:
        o.append(f'  <div class="fgroup" data-g="{g}" role="group" aria-label="{label}"><span class="flabel">{label}</span>{"".join(chips)}</div>')
    o.append('  <div class="fbar"><span class="count" aria-live="polite"></span><button type="button" class="reset" hidden>Réinitialiser</button>'
             '<button type="button" class="expand">Tout déplier</button></div>')
    o.append("</div>")
    return o


TOTOP = '<a class="totop" href="#top" title="Revenir en haut" aria-label="Revenir en haut">⌃</a>'
SCRIPT = '<script src="../../assets/report.js" defer></script>'


# ---------- rapport publié ----------
def render_report(day, cfg, seuil=None):
    seuil = seuil or seuil_frais(day)
    pub = ordered(published(day), cfg)
    h1 = titre_jour(day["date"])
    o = [HEAD.format(title=E(h1 + SUFFIX), date=day["date"], extra_head=""), '<div class="wrap">', '<header id="top">',
         f"  <h1>{E(h1)}</h1>", f'  <p class="sub">{inline(day.get("sous_titre", ""))}</p>', "</header>", "",
         "<h2>À retenir aujourd'hui</h2>", '<div class="card tldr"><ul>']
    o += [f"  <li>{inline(x['texte'])}</li>" for x in day.get("a_retenir", [])]
    o += ["</ul></div>", "", "<h2>Sujets</h2>"] + filters(pub, cfg, seuil) + ['<div class="sum">']
    for s in pub:
        o += ["", card(s, cfg, seuil)]
    o += ["</div>", "", "<footer>"] + [f"  <p>{inline(p)}</p>" for p in day.get("pied", [])] + ["</footer>", "</div>", TOTOP, SCRIPT, "</body></html>", ""]
    return "\n".join(o)


# ---------- dossier du jour ----------
EXEC_LABEL = {"planifiee": "planifiée", "manuelle": "manuelle"}
MOTIF_LABEL = {"deja-publie": "déjà publié", "hors-fenetre": "hors fenêtre de dates", "hors-perimetre": "hors périmètre",
               "non-verifiable": "source non vérifiable", "doublon": "doublon", "trop-mineur": "trop mineur",
               "plafond-atteint": "plafond de la catégorie atteint", "exclu-config": "exclu par la configuration",
               "rien-de-neuf": "vérifié, rien de neuf", "infirme": "information démentie après vérification"}


def render_dossier(day, cfg, seuil=None):
    seuil = seuil or seuil_frais(day)
    allt = ordered(day.get("sujets", []), cfg)
    count = {st: sum(1 for s in allt if s.get("statut") == st) for st in STATUTS}
    jour = titre_jour(day["date"]).removeprefix("Veille technologique du ")
    o = [HEAD.format(title=E("Dossier du " + jour + SUFFIX), date=day["date"], extra_head='\n<meta name="robots" content="noindex, nofollow">'),
         '<div class="wrap dossier">', '<header id="top">', f"  <h1>Dossier du {E(jour)}</h1>",
         '  <p class="sub">Tous les sujets analysés pour ce jour : publiés, candidats, mis de côté, écartés (avec leur motif).</p>',
         '  <div class="dz-stats">' + "".join(badge(STATUT_CLASSE[st], f"{STATUT_LABEL[st]} : {count[st]}", STATUT_AIDE[st]) for st in STATUTS) + "</div>",
         "</header>", ""]
    j = day.get("journal", {})
    rows = []
    if j.get("recherches"):
        rows.append(("Recherches", ", ".join(f"{cfg['categories'].get(k, {}).get('label', k)} : {v}" for k, v in j["recherches"].items())))
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
    o += ["<h2>Journal de recherche</h2>", '<details class="card dz-journal">', "  <summary>Recherches, sources illisibles, exécutions</summary>"]
    o.append("  <dl>" + "".join(f"<dt>{E(k)}</dt><dd>{inline(v)}</dd>" for k, v in rows) + "</dl>" if rows else "  <p>Pas de journal pour ce jour.</p>")
    o += ["</details>", "", "<h2>Sujets</h2>"] + filters(allt, cfg, seuil, dossier=True) + ['<div class="sum">']
    for s in allt:
        o += ["", card(s, cfg, seuil, dossier=True, date_jour=day["date"])]
    o += ["</div>", "</div>", TOTOP, SCRIPT, "</body></html>", ""]
    return "\n".join(o)


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
        seuil = seuil_frais(d, days)
        for sub, fn in (("reports", render_report), ("dossier", render_dossier)):
            if sub == "reports" and not published(d):
                continue
            p = out / sub / y / f"{stem}.html"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(fn(d, cfg, seuil), encoding="utf-8")
        st = {k: sum(1 for s in d.get("sujets", []) if s.get("statut") == k) for k in STATUTS}
        listing.append({"date": d["date"], "href": f"{y}/{stem}.html", "titre": titre_jour(d["date"]), "statuts": st})
    (out / "dossier").mkdir(parents=True, exist_ok=True)
    (out / "dossier" / "dossier.json").write_text(json.dumps(sorted(listing, key=lambda x: x["date"], reverse=True), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "feed.xml").write_text(render_feed(days, site), encoding="utf-8")
    print(f"rendu : {len(days)} jour(s), {sum(1 for d in days if published(d))} rapport(s) publié(s) → {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dist", sys.argv[2] if len(sys.argv) > 2 else "")
