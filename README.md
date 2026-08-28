# IRVE-MongoDB

## Projet Final NoSQL — Mobilité électrique en France

### Sujet

**Mobilité électrique en France : localisation, puissance et disponibilité des points de recharge.**

L’objectif est de concevoir une base **MongoDB Atlas** à partir de la Base Nationale IRVE
(_Infrastructures de Recharge pour Véhicules Électriques_).

Après exploration du jeu de données :

- **165 595 lignes statiques**
- **165 593 points de recharge distincts (PDC)**
- **48 040 stations**
- **115 159 lignes dynamiques**
- **104 046 PDC distincts dans le fichier dynamique**

Les métriques détaillées, la qualité des données et les cardinalités utilisées pour justifier notre modélisation sont disponibles dans le [rapport de profiling](docs/profiling_irve.md).

Le projet permet notamment de répondre à des questions comme :

- Quelles stations se trouvent à moins de 2 km d’une position donnée ?
- Quels territoires disposent du plus grand nombre de points de recharge ?
- Quels opérateurs disposent du plus grand nombre de PDC ?
- Quelle est la puissance moyenne proposée selon les territoires ou les opérateurs ?
- Comment le nombre de stations mises en service évolue-t-il dans le temps ?
- Quel était l’état d’occupation ou de fonctionnement des PDC dans le snapshot dynamique importé ?

Le projet exploite notamment MongoDB Atlas, les index géospatiaux `2dsphere`, les pipelines d’agrégation, des index mesurés avec `explain()` et les données statiques et dynamiques IRVE.

---

## Source des données

Jeu de données : **[BETA] Base Nationale des Points de Recharge pour Véhicules Électriques en France (IRVE)**

- [Page officielle du dataset](https://www.data.gouv.fr/datasets/beta-bases-nationales-des-points-de-recharge-pour-vehicules-electriques-en-france-irve)
- [Téléchargement des données statiques](https://transport.data.gouv.fr/resources/84013?locale=fr)
- [Téléchargement des données dynamiques](https://transport.data.gouv.fr/resources/84098)
- [Schéma IRVE statique](https://schema.data.gouv.fr/etalab/schema-irve-statique/)
- [Schéma IRVE dynamique](https://schema.data.gouv.fr/etalab/schema-irve-dynamique/)

Licence : **Licence Ouverte / Open Licence 2.0**

Le fichier dynamique téléchargé représente un **snapshot à un instant donné**. Il ne constitue pas à lui seul un historique ni un flux temps réel.

---

## Pourquoi MongoDB ?

Le dataset est adapté à MongoDB car il contient :

- un volume largement supérieur à 10 000 documents ;
- plusieurs entités liées : stations, PDC et statuts dynamiques ;
- une forte dimension géographique ;
- des structures imbriquées adaptées à des tableaux de PDC ;
- des champs parfois absents ou à nettoyer ;
- de vraies décisions entre embarquement et référencement.

Le profiling montre qu’une station contient en moyenne **3,45 PDC**, avec une médiane de **2**. **95 % des stations ont 10 PDC ou moins** et **99 % en ont 20 ou moins**.

Ces résultats soutiennent notre choix d’embarquer les PDC dans un tableau `points_recharge` au sein du document station, tout en conservant les statuts dynamiques dans une collection séparée.

---

## Modélisation retenue

Deux collections principales :

- `stations` : informations de la station et tableau `points_recharge` ;
- `statuts_pdc` : état dynamique des points de recharge.

La justification détaillée de ces choix, avec les cardinalités mesurées, les avantages et les coûts associés, est disponible dans le [rapport de profiling](docs/profiling_irve.md).

---

## Structure du projet

```text
IRVE-MongoDB/
├── analysis/
│   ├── 01_exploration_profiling.ipynb
│   └── 02_aggregations.ipynb
├── app/
│   └── app.py
├── data/
│   └── README.md
├── docs/
│   ├── backup_restore.md
│   ├── indexes.md
│   └── profiling_irve.md
├── scripts/
│   ├── import_data.py
│   ├── demo_crud.py
│   ├── create_indexes.py
│   ├── benchmark_indexes.py
│   ├── backup.py
│   └── restore.py
├── src/
│   ├── config.py
│   ├── database.py
│   ├── crud.py
│   └── queries.py
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

- `analysis/` : notebooks d’exploration et d’analyse ;
- `app/` : interface d’interrogation Streamlit ;
- `data/` : instructions pour récupérer les fichiers IRVE ; les CSV ne sont pas versionnés ;
- `docs/` : profiling, mesures d’index et documentation backup/restore ;
- `scripts/` : import, démonstration CRUD, création/mesure des index et administration MongoDB ;
- `src/` : code Python réutilisable : configuration, connexion, CRUD et requêtes.

---

## Configuration

La connexion MongoDB Atlas est fournie par variables d’environnement.

Créer un fichier `.env.local` à partir de `.env.example` :

```env
MONGODB_URI=mongodb+srv://<USER>:<PASSWORD>@<CLUSTER>.mongodb.net/?retryWrites=true&w=majority
DB_NAME=irve
COLLECTION_STATIONS=stations
COLLECTION_STATUTS=statuts_pdc
RESTORE_DB_NAME=irve_restore_demo
```

`.env.local` ne doit jamais être versionné. Aucun identifiant, mot de passe ou token ne doit apparaître dans le dépôt ou son historique Git.

Installer les dépendances :

```bash
python -m pip install -r requirements.txt
```

---

## Import des données vers MongoDB Atlas

### Prérequis

- Python 3.12 ou version compatible ;
- les dépendances de `requirements.txt` ;
- un cluster MongoDB Atlas accessible ;
- un fichier `.env.local` configuré à partir de `.env.example` ;
- les CSV IRVE placés dans `data/`.

Le fichier statique doit être placé sous ce nom :

```text
data/consolidation_transport_irve_statique.csv
```

Pour le dynamique, le script détecte le premier fichier CSV dont le nom contient `dynamique`.

Lancer l’import :

```bash
python scripts/import_data.py
```

Le script :

- vérifie la connexion à Atlas avec `ping` ;
- retire les doublons de `id_pdc_itinerance` dans le statique ;
- construit un document par station avec un tableau `points_recharge` ;
- ajoute un GeoJSON `localisation` uniquement quand les coordonnées sont validées par la source ;
- calcule `departement` à partir du code INSEE lorsqu’il est disponible ;
- conserve, dans le snapshot dynamique, la ligne la plus récente par PDC selon `horodatage` ;
- charge les collections `stations` et `statuts_pdc` ;
- affiche les volumes finaux pour contrôle.

> L’import reconstruit les deux collections : leur contenu existant est supprimé avant réinsertion.

---

## Index et performances

Trois index ont été mis en place et mesurés avec `explain("executionStats")` avant et après création.

| Index | Usage | Avant | Après |
|---|---|---|---|
| `operateur: 1` | Stations d’un opérateur | `COLLSCAN`, 48 040 docs, 29 ms | `IXSCAN`, 5 077 docs, 9 ms |
| `horodatage: -1` | 20 statuts les plus récents | `COLLSCAN + SORT`, 100 838 docs, 91 ms | `IXSCAN`, 20 docs, 1 ms |
| `localisation: "2dsphere"` | Recherche géographique | `COLLSCAN`, 48 040 docs, 95 ms | `IXSCAN`, 1 265 docs, 7 ms |

Les détails des requêtes et les mesures complètes sont disponibles dans [docs/indexes.md](docs/indexes.md).

Le benchmark peut être reproduit avec :

```bash
python scripts/benchmark_indexes.py
```

---

## CRUD Python

Les opérations de lecture/écriture sur la collection `stations` sont regroupées dans [`src/crud.py`](src/crud.py).

| Opération | Fonction | Comportement |
|---|---|---|
| Create | `creer_station(db, document)` | Valide le document puis l’insère |
| Read | `lire_station(db, id_station)` | Lit une station, lève `StationIntrouvable` si absente |
| Read | `lister_stations(db, filtre, projection, limite, tri)` | Recherche filtrée avec projection et tri |
| Read | `compter_stations(db, filtre)` | Compte les stations correspondant à un filtre |
| Update | `modifier_station(db, id_station, modifications)` | `$set` des champs fournis |
| Update | `ajouter_point_recharge(db, id_station, point)` | `$push` dans `points_recharge` et `$inc` de `nbre_pdc` |
| Delete | `supprimer_station(db, id_station)` | Supprime la station et renvoie le document supprimé |

La validation contrôle les champs obligatoires (`_id`, `nom`, `operateur`), le type du tableau `points_recharge` et le GeoJSON `localisation`.

Démonstration reproductible :

```bash
python scripts/demo_crud.py
```

Le script utilise une station de test puis la supprime ; il ne doit pas modifier les données IRVE de référence.

---

## Agrégations et rapport analytique

Les pipelines sont regroupés dans [`src/queries.py`](src/queries.py). Le rapport analytique se trouve dans [`analysis/02_aggregations.ipynb`](analysis/02_aggregations.ipynb).

| Question métier | Pipeline | `$unwind` |
|---|---|---|
| Quels territoires sont les mieux équipés ? | `pipeline_offre_par_departement` | Non |
| Quelle puissance moyenne selon les territoires ? | `pipeline_puissance_par_departement` | Oui |
| Quels opérateurs dominent, et avec quelle qualité de service ? | `pipeline_top_operateurs` | Oui |
| À quel rythme le réseau s’est-il déployé ? | `pipeline_evolution_annuelle` | Non |
| Quel était l’état du parc dans le snapshot ? | `pipeline_etat_parc` | Non |

`$unwind` n’est utilisé que lorsque l’analyse porte réellement sur chaque PDC. Pour les analyses par station, le compteur dénormalisé `nbre_pdc` permet d’éviter de dérouler le tableau.

Exécution du notebook :

```bash
jupyter lab analysis/02_aggregations.ipynb
```

> **Avant la remise :** le notebook doit être ré-exécuté contre la vraie base Atlas `irve` avec ses sorties et graphiques visibles, puis sauvegardé.

---

## Recherche géospatiale

```python
from src.queries import stations_proches

stations_proches(
    db,
    longitude=2.3522,
    latitude=48.8566,
    rayon_metres=2000,
    puissance_min=50,
)
```

`stations_proches` utilise `$near`, tandis que `pipeline_stations_proches_avec_distance` utilise `$geoNear` pour restituer aussi la distance calculée. Les deux exigent l’index `2dsphere` sur `localisation`.

---

## Interface d’interrogation — Streamlit

L’interface permet d’interroger la base sans passer par un terminal :

```bash
streamlit run app/app.py
```

Elle comporte trois onglets :

| Onglet | Fonction |
|---|---|
| **Recherche par proximité** | Ville ou coordonnées, rayon, puissance minimale, type de prise, carte, tableau et export CSV |
| **Analyses** | Agrégations par territoire, opérateur et évolution temporelle |
| **Fiche station** | Consultation d’une station par son identifiant d’itinérance |

L’interface réutilise `src/queries.py` et `src/crud.py`, et ne duplique pas la logique métier. La connexion est mise en cache avec `@st.cache_resource` et les résultats avec `@st.cache_data(ttl=300)`.

> La recherche de proximité exige l’index `2dsphere` sur `localisation`.

---

## Administration — Sauvegarde et restauration

Le projet utilise les outils officiels `mongodump` et `mongorestore`.

Prérequis : installer **MongoDB Database Tools** puis vérifier :

```bash
mongodump --version
mongorestore --version
```

La procédure détaillée est disponible dans [docs/backup_restore.md](docs/backup_restore.md).

Sauvegarde :

```bash
python scripts/backup.py
```

Restauration vers la base de démonstration `irve_restore_demo` :

```bash
python scripts/restore.py
```

Validation réelle effectuée : **148 878 documents restaurés, 0 échec**, avec reconstruction des index associés.

---

## Validation finale avant remise

À exécuter sur la version finale du projet :

```bash
python -m pip install -r requirements.txt
python -m compileall -q src scripts app
python scripts/demo_crud.py
streamlit run app/app.py
```

Puis dans Jupyter : ouvrir `analysis/02_aggregations.ipynb`, faire **Restart Kernel and Run All Cells** sur la base Atlas `irve`, vérifier les résultats/graphiques puis sauvegarder le notebook.

Pour Streamlit, vérifier au minimum :

- recherche autour de Paris dans un rayon de 2 km ;
- filtre de puissance minimale ;
- filtre par type de prise ;
- carte et tableau ;
- onglet Analyses ;
- fiche d’une station existante ;
- comportement avec un identifiant inexistant.

---

## État du projet

- Profiling et justification de la modélisation : **terminés**.
- Import Atlas : **terminé et vérifié** — 48 040 stations et 100 838 statuts chargés.
- Index : **terminés, mesurés et documentés**.
- CRUD Python : **implémenté** ; validation finale Atlas à rejouer avant gel.
- Agrégations : **implémentées** ; notebook à ré-exécuter sur la vraie base Atlas avant gel.
- Interface Streamlit : **implémentée** ; validation fonctionnelle finale sur Atlas à effectuer avant gel.
- Sauvegarde / restauration : **terminée et testée sur Atlas**.

Le projet n’est considéré comme figé qu’après validation finale du CRUD, ré-exécution du notebook sur Atlas, test complet de Streamlit et CI verte sur la branche de finalisation.
