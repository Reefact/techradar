---
name: veille-memoire
description: Interroge la mémoire de la veille, dérivée des fichiers du jour (data/memory.json) et complétée par data/notes.md : un sujet ou une URL est-il déjà paru (publié, écarté, mis de côté) ? quels rappels de CFP sont dus ? quels sujets sont à reconsidérer ? À utiliser pour toute question sur ce qui a déjà été vu.
---

# Mémoire de la veille

- `data/memory.json` : dérivé de `data/days/*.json` par `tools/build_memory.py` (régénéré par l'Action à chaque push) ; ne jamais l'éditer.
- `data/notes.md` : ce qui n'est pas déductible des jours (préférences, dernières versions vues, vérifications en attente) ; s'édite à la main.

## Commandes

```bash
python3 tools/build_memory.py                      # régénère data/memory.json
python3 tools/build_memory.py --seen <URL>         # où et quand cette URL a été vue, avec son statut (code 0 = déjà publiée)
python3 tools/build_memory.py --due [AAAA-MM-JJ]   # rappels de CFP à émettre ce jour-là
python3 tools/build_memory.py --reconsiderer       # sujets mis de côté ou candidats non publiés
```

Seuls les sujets **publiés** bloquent l'anti-doublon ; un sujet écarté (motif indiqué) ou mis de côté reste reconsidérable.

## Exemples de demandes

« Est-ce qu'on a déjà parlé de cet article ? », « Quels rappels de CFP demain ? », « Qu'est-ce qui a été mis de côté cette semaine ? ».
