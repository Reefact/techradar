# Notes de la veille (données NON déductibles des rapports)

Le reste de la mémoire (sujets publiés, URLs, outils proposés, conférences, rappels de CFP, signaux du radar) est **dérivé des rapports** dans `data/memory.json` (généré par `tools/build_memory.py`, ne pas l'éditer à la main).
Ce fichier se modifie à la main ou par la tâche de veille. Repris du registre « Veille — registre » (artefact) au 2026-11-24 ; l'artefact reste en service pour l'instant.

## Préférences
- Résumés détaillés pour tous les sujets (8-12 lignes, listes de points quand utile) ; .NET / ASP.NET / EF : récapitulatif complet des nouveautés. *Demande du 2026-11-24, à confirmer pour les prochains briefs (le prompt de la tâche dit encore 4-6 lignes).*
- Le dépôt `api-contract-guardrails` est exclu du radar.

## Dernières versions vues (pour détecter un changement)
| Paquet | Version (date) |
|---|---|
| stryker (lib NuGet) | 5.1.0 (2026-11-10) |
| dotnet-stryker | non vérifié |
| AwesomeAssertions | 9.6.0 (2026-08-20) |
| Shouldly | 4.3.0 ; 5.0.0-preview.2 (2026-07-18) |
| AutoFixture | 4.18.1 ; 5.0.0-rc.1 (2026-07-31) |
| Bogus | 35.6.5 (2025-10-26) |
| ErrorOr | 2.1.1 (2026-05-15) |
| FluentResults | 4.0.0 (2025-06-29) |
| Slugify.Core | 5.2.0 (2026-10-26) |
| .NET | 11 sorti le 2026-11-10 |

## Liste de surveillance du radar (provisoire)
| Projet | Concurrents / écosystème |
|---|---|
| kill-mutants | Stryker.NET |
| unified-assertions | AwesomeAssertions, Shouldly, FluentAssertions |
| just-dummies | Bogus, AutoFixture |
| first-class-errors | unions C# 15, ErrorOr, FluentResults |
| slugger | Slugify |
| enum-member-name-binding | notes .NET / System.Text.Json sur les enums (rien dans .NET 11 au 2026-11-24 ; les paramètres enum non-JSON d'ASP.NET gardent les noms C#) |

À valider : les README des dépôts Reefact n'étaient pas lisibles par la tâche (erreur 403, dépôts non ajoutés).

## À vérifier / en attente
- Lire les README Reefact/* pour valider la liste de surveillance.
- Devoxx France 2027 : confirmer l'ouverture du CFP et l'heure limite (annonce du 2026-11-23 non confirmée sur cfp.dev).
- MiXiT 2027 : dates d'ouverture/clôture du CFP à confirmer.
- DDD : rien de vérifié le 2026-11-24.
- Java4Shell : vérifier l'alerte CISA du 2026-11-17 ; page MAUI 11 détaillée.
- Sources non lisibles : LSA, LeMagIT, Silicon.fr, ZDNet, Reddit, Product Hunt, Lobsters.

## Écartés (trop anciens)
- securityaffairs : 9 paquets NuGet (2025-11-10).
