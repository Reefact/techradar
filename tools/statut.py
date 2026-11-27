#!/usr/bin/env python3
"""Change le statut de sujets dans un fichier du jour. Utilisé par le skill veille-publier.

  python3 tools/statut.py list AAAA-MM-JJ
  python3 tools/statut.py set  AAAA-MM-JJ <id>[,<id>…] <publie|candidat|ecarte> [--motif M] [--note "…"] [--force]

--force (publie seulement) : décision de l'utilisateur ; le sujet est marqué « force_utilisateur » et ne compte
ni dans les 15 publiés ni dans le plafond de sa catégorie. Les autres contrôles s'appliquent toujours.

Chaque changement ajoute une entrée à l'historique du sujet (« par » : utilisateur). Le fichier est ensuite
validé par tools/check_day.py (--partiel) ; en cas d'erreur, rien n'est écrit.
"""
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veille_lib import MOTIFS, STATUTS, day_path, load_json, plain, write_day  # noqa: E402
import check_day  # noqa: E402


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    cmd, iso = a[0], a[1]
    p = day_path(iso)
    if not p.exists():
        sys.exit(f"Aucun fichier du jour pour {iso} ({p}).")
    day = load_json(p)
    if cmd == "list":
        for st in STATUTS:
            sel = [s for s in day["sujets"] if s["statut"] == st]
            print(f"\n{st.upper()} ({len(sel)})")
            for s in sel:
                print(f"  {s['id']:<5} [{s['categorie']}] {plain(s['titre'])[:95]}" + (f"  — {s['motif']}" if s.get("motif") else ""))
        return
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes")
    note = a[a.index("--note") + 1] if "--note" in a else None
    if cmd == "set":
        ids, st = a[2].split(","), a[3]
        motif = a[a.index("--motif") + 1] if "--motif" in a else None
        if st not in STATUTS: sys.exit(f"Statut inconnu : {st}")
        if st == "ecarte" and motif not in MOTIFS: sys.exit(f"Un sujet écarté demande --motif parmi : {', '.join(MOTIFS)}")
        by_id = {s["id"]: s for s in day["sujets"]}
        for i in ids:
            s = by_id.get(i) or sys.exit(f"Sujet {i} introuvable.")
            if st == "publie" and not s.get("resume"): sys.exit(f"{i} n'a pas de résumé : il ne peut pas être publié tel quel.")
            s["statut"] = st
            if st == "publie" and "--force" in a: s["force_utilisateur"] = True
            elif st != "publie": s.pop("force_utilisateur", None)
            if st == "ecarte": s["motif"] = motif
            else: s.pop("motif", None)
            s.setdefault("historique", []).append({"date": now, "statut": st, "par": "utilisateur", **({"note": note} if note else {})})
            print(f"{i} → {st}")
    else:
        sys.exit(__doc__)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / p.parent.name / p.name
        write_day(tmp, day)
        errs, warns = check_day.check(tmp, None, partiel=True)
    if errs:
        print("\nREFUSÉ : le fichier deviendrait invalide :"); [print("  -", e) for e in errs]; sys.exit(1)
    write_day(p, day)
    print(f"\nÉcrit : {p.relative_to(p.parents[3])}" + (f" ({len(warns)} signal(aux) de langue)" if warns else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
