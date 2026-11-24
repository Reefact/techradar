"""Fonctions partagées par les outils de la veille : configuration, fichiers du jour, Markdown simple, dates."""
import html
import json
import re
from datetime import date as Date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DAYS = ROOT / "data" / "days"
SUFFIX = " – Reefact"          # suffixe des <title> (tiret demi-cadratin, comme reefact.net)
STATUTS = ("publie", "candidat", "mis-de-cote", "ecarte")
MOTIFS = ("deja-publie", "hors-fenetre", "hors-perimetre", "non-verifiable", "doublon", "trop-mineur",
          "plafond-atteint", "exclu-config", "rien-de-neuf")
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


# ---------- configuration ----------
def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def config():
    """Catégories, tags et sujets (index + fichiers actifs)."""
    cats = load_json(CONFIG / "categories.json")
    tags = load_json(CONFIG / "tags.json")
    index = load_json(CONFIG / "sujets.json")
    sujets = {f["chemin"]: load_json(CONFIG / f["chemin"]) for f in index["fichiers"] if f.get("actif", True)}
    return {"categories": cats, "tags": tags, "index": index, "sujets": sujets}


def ordered_categories(cats):
    return sorted(cats, key=lambda k: cats[k]["ordre"])


# ---------- fichiers du jour ----------
def day_files():
    return sorted(DAYS.glob("[0-9][0-9][0-9][0-9]/[0-9]*.json"))


def day_path(iso):
    return DAYS / iso[:4] / (iso.replace("-", "") + ".json")


def write_day(path, day):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(day, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def published(day, key="sujets"):
    return [s for s in day.get(key, []) if s.get("statut") == "publie"]


# ---------- dates ----------
def titre_jour(iso):
    d = Date.fromisoformat(iso)
    jour = "1er" if d.day == 1 else str(d.day)
    return f"Veille technologique du {JOURS[d.weekday()]} {jour} {MOIS[d.month - 1]} {d.year}"


# ---------- Markdown simple (gras, code, liens ; paragraphes et listes) ----------
_TOKEN = re.compile(r"`([^`]+)`|\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)\s]+)\)", re.S)


def inline(md):
    """Texte Markdown simple → HTML : **gras**, `code`, [texte](url). Tout le reste est échappé.
    Les liens externes s'ouvrent dans un nouvel onglet."""
    out, pos = [], 0
    for m in _TOKEN.finditer(md):
        out.append(html.escape(md[pos:m.start()], quote=False))
        if m.group(1) is not None:
            out.append(f"<code>{html.escape(m.group(1), quote=False)}</code>")
        elif m.group(2) is not None:
            out.append(f"<strong>{inline(m.group(2))}</strong>")
        else:
            url = m.group(4)
            ext = ' target="_blank" rel="noopener"' if re.match(r"https?://", url) else ""
            out.append(f'<a href="{html.escape(url)}"{ext}>{inline(m.group(3))}</a>')
        pos = m.end()
    out.append(html.escape(md[pos:], quote=False))
    return "".join(out)


def blocks(md, indent="  "):
    """Paragraphes séparés par une ligne vide ; lignes « - » consécutives = liste à puces."""
    res = []
    for chunk in re.split(r"\n\s*\n", (md or "").strip()):
        lines = [l for l in chunk.split("\n") if l.strip()]
        if not lines:
            continue
        if all(l.lstrip().startswith("- ") for l in lines):
            items = "\n".join(f"{indent}  <li>{inline(l.lstrip()[2:].strip())}</li>" for l in lines)
            res.append(f"{indent}<ul>\n{items}\n{indent}</ul>")
        else:
            res.append(f"{indent}<p>{inline(' '.join(l.strip() for l in lines))}</p>")
    return res


def plain(md):
    """Markdown simple → texte brut (pour le flux, la mémoire, les contrôles)."""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md or "")
    t = t.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", re.sub(r"^\s*- ", "", t, flags=re.M)).strip()


def urls(sujet):
    """Toutes les URL d'un sujet (sources + liens dans le texte)."""
    found = [s["url"] for s in sujet.get("sources", [])]
    for field in ("resume", "pourquoi", "texte"):
        found += re.findall(r"\]\((https?://[^)\s]+)\)", sujet.get(field) or "")
    for v in (sujet.get("details") or {}).values():
        found += re.findall(r"\]\((https?://[^)\s]+)\)", v)
    return found
