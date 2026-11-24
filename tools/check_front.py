#!/usr/bin/env python3
"""Contrôle de cohérence entre la configuration et le front rendu (rapports et dossiers). Code retour 1 en cas d'erreur.

  python3 tools/check_front.py <page.html> [...]        (par défaut : toutes les pages de dist/reports et dist/dossier)

Tout ce qu'affiche un bloc ou la barre de filtres doit venir de config/, à l'identique :
  - catégorie : clé connue, badge avec le libellé et la classe déclarés (aucun libellé propre au sujet) ;
  - tags : clés connues, chacun affiché une fois (badge à son libellé, ou icône seule si le libellé commence par un emoji,
    avec une infobulle « <libellé> : <description> » qui ne dépend pas du sujet), aucun badge en trop ;
  - projet : dépôt déclaré dans config/sujets/projets.json, icône 📦 avec le nom du projet ;
  - filtres : chaque puce correspond à une clé déclarée et affiche son libellé déclaré.
"""
import html as H
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veille_lib import ROOT, STATUTS, config, projets  # noqa: E402

STATUT_LABEL = {"publie": "Publié", "candidat": "Candidat", "mis-de-cote": "Mis de côté", "ecarte": "Écarté"}
SPAN = re.compile(r'<span class="([^"]*)"(?: title="([^"]*)")?[^>]*>(.*?)</span>', re.S)
ATTR = lambda tag, name: (re.search(rf'\b{name}="([^"]*)"', tag) or [None, None])[1]
texte = lambda s: re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def emoji_label(label):
    """(emoji, reste) si le libellé commence par un emoji (« 🧪 Pépite »), sinon None."""
    m = re.match(r"^(\S+)\s+(.+)$", label)
    return (m.group(1), m.group(2)) if m and not re.match(r"[\w«(]", m.group(1)) else None


def check(raw, cfg, nom="page"):
    cats, tags, proj = cfg["categories"], cfg["tags"], projets(cfg)
    errs = []
    E = lambda m: errs.append(f"{nom} : {m}")
    # ---------- blocs ----------
    for m in re.finditer(r'(<details class="card"[^>]*>)\s*<summary class="head"><span class="badges">(.*?)</span><h3', raw, re.S):
        tag, inner = m.group(1), m.group(2)
        sid = ATTR(tag, "id") or "?"
        cat, repo = ATTR(tag, "data-cat"), ATTR(tag, "data-repo")
        tkeys = (ATTR(tag, "data-tags") or "").split()
        spans = [(cls.split(), H.unescape(title or ""), texte(t)) for cls, title, t in SPAN.findall(inner)]
        if spans and "badge" in spans[0][0] and spans[0][2] in STATUT_LABEL.values():
            spans = spans[1:]                                   # badge de statut (dossier)
        if cat not in cats:
            E(f"{sid} : catégorie « {cat} » absente de config/categories.json"); continue
        c = cats[cat]
        if not spans or spans[0][2] != c["label"] or c["classe"] not in spans[0][0]:
            E(f"{sid} : le badge de catégorie doit afficher « {c['label']} » (classe {c['classe']}), trouvé « {spans[0][2] if spans else '—'} »")
        rest = spans[1:]
        for k in tkeys:
            if k not in tags:
                E(f"{sid} : tag « {k} » absent de config/tags.json"); continue
            d = tags[k]
            em = emoji_label(d["label"])
            if em:
                want = f"{em[1]} : {d['description'][:1].lower()}{d['description'][1:]}"
                hit = [x for x in rest if "ico" in x[0] and "projet" not in x[0] and x[2] == em[0] and x[1] == want]
            else:
                hit = [x for x in rest if "badge" in x[0] and x[2] == d["label"] and d["classe"] in x[0]]
            if len(hit) != 1:
                E(f"{sid} : tag « {k} » non affiché à l'identique de sa déclaration (« {d['label']} »)")
            else:
                rest.remove(hit[0])
        pj = [x for x in rest if "projet" in x[0]]
        if repo:
            if repo not in proj: E(f"{sid} : dépôt « {repo} » absent de config/sujets/projets.json")
            elif len(pj) != 1 or pj[0][2] != "📦" or f"Projet {proj[repo]['nom']}" not in pj[0][1]:
                E(f"{sid} : icône 📦 du projet {proj[repo]['nom']} absente ou incorrecte")
        elif pj:
            E(f"{sid} : icône de projet sans dépôt déclaré")
        for x in rest:
            if x not in pj: E(f"{sid} : élément non déclaré dans l'en-tête : « {x[2]} » ({' '.join(x[0])})")
    # ---------- filtres ----------
    allowed = {"statut": {k: STATUT_LABEL[k] for k in STATUTS},
               "cat": {k: v["label"] for k, v in cats.items()},
               "tag": {**{k: v["label"] for k, v in tags.items()}, "frais": "☄️ Récent"},
               "projet": {k: "📦 " + v["nom"] for k, v in proj.items()}}
    for g, body in re.findall(r'<div class="fgroup" data-g="([^"]+)"[^>]*>(.*?)</div>', raw, re.S):
        if g not in allowed:
            E(f"groupe de filtres inconnu « {g} »"); continue
        for v, label in re.findall(r'<button type="button" class="chip[^"]*" data-v="([^"]*)"[^>]*>(.*?)<span class="n">', raw[raw.find(body):raw.find(body) + len(body)], re.S):
            v = H.unescape(v)
            if v not in allowed[g]: E(f"filtre {g} : valeur « {v} » non déclarée dans config/")
            elif texte(label) != allowed[g][v]: E(f"filtre {g} : « {texte(label)} » au lieu du libellé déclaré « {allowed[g][v]} »")
    return errs


if __name__ == "__main__":
    pages = sys.argv[1:] or [str(p) for p in sorted((ROOT / "dist").glob("*/[0-9][0-9][0-9][0-9]/*.html"))]
    cfg = config()
    bad = 0
    for p in pages:
        e = check(Path(p).read_text(encoding="utf-8"), cfg, Path(p).relative_to(ROOT).as_posix() if Path(p).is_absolute() else p)
        for x in e: print("  -", x)
        bad += bool(e)
    print(f"front : {len(pages)} page(s), " + ("OK" if not bad else f"{bad} page(s) en erreur"))
    sys.exit(1 if bad else 0)
