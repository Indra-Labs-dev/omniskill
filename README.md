<p align="center"><img src="assets/logo.png" alt="OMNISKILL" width="360"></p>

# OMNISKILL

**Comprendre correctement. Agir efficacement. Vérifier objectivement. Livrer honnêtement.**

OMNISKILL est un protocole de travail open source pour les assistants IA et les agents qui utilisent des outils. C'est un *skill* au format [Agent Skills](https://agentskills.io/specification) : un noyau court (`SKILL.md`), quatre modes chargés à la demande, un contrat de preuve, et des scripts de vérification sans dépendance.

> *English summary — OMNISKILL is an Apache-2.0 Agent Skill that makes AI agents define acceptance criteria, act for real, verify with observed evidence and end every task with an honest status (VERIFIED / PARTIAL / BLOCKED / UNVERIFIED). Core instructions and scripts are in English; this README is in French.*

## Le problème

Les assistants IA annoncent souvent « c'est fait » sans avoir lancé les tests, inventent des données manquantes, suivent des instructions cachées dans des fichiers, ou effacent du travail existant. OMNISKILL ne rend pas un modèle expert : il impose une méthode de travail et un format de compte rendu qui rendent ces erreurs **visibles et vérifiables**.

## Ce que fait le skill

| Couche | Contenu |
|---|---|
| A. Noyau | `SKILL.md` (~1 200 tokens) : priorités, compréhension, inspection, exécution, preuve, blocages, livraison |
| B. Modes | `modes/quick.md`, `pro.md`, `autonomous.md` (points de reprise), `audit.md` (sévérité × certitude) |
| C. Capacités | `references/capabilities.md` + `scripts/detect_capabilities.py` |
| D. Outils | Scripts Python (stdlib) et Shell, hors ligne, sans effet destructif |
| E. Vérification | `references/evidence-protocol.md`, `schemas/evidence.schema.json`, `scripts/validate_evidence.py` |
| F. Adaptateurs | `adapters/` : chargement natif, bundle à coller, fichier d'instructions de projet |

### Les statuts

- `VERIFIED` — tous les critères essentiels sont `PASS`, avec preuve observée.
- `PARTIAL` — une partie est faite, des critères essentiels restent `FAIL` ou `NOT_VERIFIED`.
- `BLOCKED` — une contrainte empêche d'avancer (accès, données, autorisation).
- `UNVERIFIED` — un résultat existe mais sans preuve suffisante.

Le validateur refuse un `VERIFIED` avec un critère essentiel non vérifié, une preuve du type « done » ou « I verified it », et tout rapport contenant un secret.

## Installation

**Plateforme compatible Agent Skills** (Claude, Claude Code, Codex, Gemini CLI, Cursor, Copilot… selon leur documentation) : copiez le dossier `omniskill/` dans le répertoire de skills de la plateforme. Le dossier doit s'appeler `omniskill` (il doit correspondre au champ `name`).

**Autres environnements** (ChatGPT, Gemini app, Qwen, DeepSeek, Ollama, API) : générez un bundle d'un seul fichier et collez-le en instructions système.

```bash
python3 scripts/bundle.py --mode pro --with-evidence --stdout > omniskill-pro.md
```

**Agents de code avec fichier d'instructions** : partez de `adapters/AGENTS.md.template`.

Détails et différences de chargement : `adapters/generic.md` et `adapters/platforms.md`.

## Scripts

Prérequis : Python ≥ 3.9 pour les scripts, Bash pour `check_repo.sh`. **Le skill lui-même ne requiert aucun runtime** : sans terminal, le modèle suit les instructions et marque `NOT_VERIFIED` ce qu'il n'a pas pu contrôler.

| Script | Rôle | Codes de sortie |
|---|---|---|
| `scripts/validate_skill.py` | Structure, métadonnées (spec Agent Skills), budget du noyau, liens internes | 0 / 1 / 2 |
| `scripts/validate_evidence.py` | Rapports de preuve : schéma, règles de statut, preuves creuses, secrets | 0 / 1 / 2 |
| `scripts/guard_command.py` | Classe une commande shell : `allow` / `confirm` / `deny` (ne l'exécute jamais) | 0 / 3 / 4 |
| `scripts/detect_capabilities.py` | Inventaire local des runtimes, outils et fichiers de projet | 0 / 2 |
| `scripts/bundle.py` | Bundles d'un fichier (noyau + un mode) pour plateformes sans skills | 0 / 1 / 2 |
| `scripts/run_benchmarks.py` | Corpus (`validate`), plan randomisé (`plan`), agrégation (`report`) | 0 / 1 / 2 |
| `scripts/check_repo.sh` | Lance tous les contrôles du dépôt (utilisé par la CI) | 0 / 1 |

Pas de validateur JavaScript : il dupliquerait `validate_evidence.py` sans besoin mesuré. Il sera ajouté si une intégration Node.js concrète le justifie.

```bash
scripts/check_repo.sh              # tout
python3 -m unittest discover -s tests
```

## Sécurité et limites

- Les contenus lus via des outils (fichiers, pages web, sorties) sont traités comme des **données**, jamais comme des ordres.
- Confirmation explicite avant toute action destructive, irréversible ou visible de l'extérieur ; aucune protection désactivée pour faire passer un test.
- `guard_command.py` repose sur des motifs : une commande obfusquée peut lui échapper. Ce n'est pas un bac à sable.
- La détection de secrets couvre les formats courants, pas tous.
- Un modèle peut ignorer n'importe quelle instruction : OMNISKILL réduit les risques, il ne les supprime pas.

Voir `references/security.md` et `SECURITY.md`.

## Benchmarks

**Aucun benchmark n'a encore été exécuté.** Le corpus (30 tâches : développement, données, documents, sécurité, recherche — dont tâches ambiguës, partiellement bloquées et avec injection de prompt), le protocole A/B et l'outil d'agrégation sont prêts dans `benchmarks/`. Aucune amélioration n'est revendiquée tant qu'un rapport issu d'essais réels, notés indépendamment, n'est pas publié dans `benchmarks/results/`.

Seuils visés avant d'annoncer une release multiplateforme : 0 fausse déclaration de réussite, 0 régression de sécurité critique imputable au skill, +10 points de taux de réussite, au moins 3 environnements évalués.

## Contribuer

Voir `CONTRIBUTING.md`. Les contributions les plus utiles aujourd'hui : **exécuter le benchmark sur une plateforme** et publier les résultats bruts, ajouter des tâches au corpus, signaler des contournements de `guard_command.py`.

## Licence

Apache-2.0 — voir `LICENSE` et `NOTICE`.
