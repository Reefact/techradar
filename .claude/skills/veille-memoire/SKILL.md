---
name: veille-memoire
description: Interroge ou met à jour la mémoire de la veille TechRadar côté dépôt (data/memory.json dérivé des rapports, data/notes.md). À utiliser pour savoir si un sujet/une URL a déjà été publié, quels rappels de CFP sont dus un jour donné, ce que contient la mémoire, ou pour régénérer l'index après modification d'un rapport.
---

# Mémoire de la veille (dépôt)

La mémoire a deux parties :
- `data/memory.json` : **dérivée des rapports** (`reports/**`) par `tools/build_memory.py`. Elle contient les sujets publiés, toutes les URL déjà citées, les outils proposés, les conférences (dates limites de CFP, rappels ⏰ déjà émis), les signaux du radar par dépôt. **Ne jamais l'éditer à la main.**
- `data/notes.md` : ce qui n'est pas déductible des rapports (préférences, dernières versions vues, liste de surveillance, vérifications en attente). Elle s'édite à la main.

L'artefact « Veille — registre » reste en service en parallèle ; ne le modifie pas depuis ce skill.

## Commandes (depuis la racine du dépôt)

```bash
python3 tools/build_memory.py                 # régénère data/memory.json depuis les rapports
python3 tools/build_memory.py --seen <URL>    # cette URL a-t-elle déjà été publiée ? (affiche où et quand, ou « non »)
python3 tools/build_memory.py --due [AAAA-MM-JJ]   # rappels de CFP à émettre ce jour-là (J-30/14/7/3 pas encore vus)
```

## Utilisation

1. **Régénérer** après tout changement dans `reports/` (corriger un rapport, en promouvoir un brouillon). En principe l'Action `feed.yml` le fait sur `main` ; en local, lancer la commande puis relire `git diff data/memory.json`.
2. **Anti-doublon** : pour un sujet candidat, tester son URL avec `--seen`. Un sujet déjà publié ne revient que pour une grosse nouveauté (présenté comme « Mise à jour »).
3. **Rappels de CFP** : `--due` donne, pour la date voulue, les conférences dont le seuil J-30/J-14/J-7/J-3 est atteint sans badge ⏰ correspondant dans un rapport. Seules les dates limites **avec année** dans le tableau du rapport sont lues ; une date sans année (« à confirmer ») n'est pas comptée.
4. **Notes** : pour ajouter une préférence ou une vérification en attente, éditer `data/notes.md` (sections existantes) puis commiter.

## Limites à connaître

- La mémoire reflète ce que les rapports affichent : un rappel ou un sujet qui n'est pas dans un rapport n'existe pas pour elle.
- Les catégories viennent de la structure du rapport (`<h3>` de catégorie avant les `<article>`) ; un rapport qui ne suit pas le gabarit sera mal classé.
- Les dates limites en texte libre sans année, ou dans un format inhabituel, ne sont pas reconnues : le script ne les devine pas.
