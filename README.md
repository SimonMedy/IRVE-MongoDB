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

Les métriques détaillées, la qualité des données et les cardinalités utilisées
pour justifier notre modélisation sont disponibles dans le
[rapport de profiling](docs/profiling_irve.md).

Le projet doit notamment permettre de répondre à des questions comme :

- Quelles stations se trouvent à moins de 2 km d’une position donnée ?
- Quels territoires disposent du plus grand nombre de points de recharge ?
- Quels opérateurs disposent du plus grand nombre de PDC ?
- Quelle est la puissance moyenne proposée selon les territoires ou les opérateurs ?
- Comment le nombre de stations mises en service évolue-t-il dans le temps ?
- Quel était l’état d’occupation ou de fonctionnement des PDC dans le snapshot dynamique importé ?

Le projet exploitera notamment :

- MongoDB Atlas ;
- les index géospatiaux `2dsphere` ;
- les pipelines d’agrégation ;
- les index mesurés avec `explain()` ;
- les données statiques et dynamiques IRVE.

---

## Source des données

Jeu de données :

**[BETA] Base Nationale des Points de Recharge pour Véhicules Électriques en France (IRVE)**

- [Page officielle du dataset](https://www.data.gouv.fr/datasets/beta-bases-nationales-des-points-de-recharge-pour-vehicules-electriques-en-france-irve)
- [Téléchargement des données statiques](https://transport.data.gouv.fr/resources/84013?locale=fr)
- [Téléchargement des données dynamiques](https://transport.data.gouv.fr/resources/84098)

Documentation des schémas :

- [Schéma IRVE statique](https://schema.data.gouv.fr/etalab/schema-irve-statique/)
- [Schéma IRVE dynamique](https://schema.data.gouv.fr/etalab/schema-irve-dynamique/)

Licence : **Licence Ouverte / Open Licence 2.0**

### Données statiques

Les données statiques décrivent notamment :

- les stations ;
- les points de recharge ;
- les coordonnées géographiques ;
- les opérateurs et aménageurs ;
- la puissance nominale ;
- les types de prises ;
- la tarification ;
- l’accessibilité ;
- les dates de mise en service.

### Données dynamiques

Les données dynamiques contiennent notamment :

- `id_pdc_itinerance` ;
- l’état de fonctionnement ;
- l’état d’occupation ;
- l’horodatage de l’information.

Les données statiques et dynamiques peuvent être reliées grâce à `id_pdc_itinerance`.

> Le fichier dynamique téléchargé représente un **snapshot à un instant donné**.
> Il ne constitue pas à lui seul un historique ni un flux temps réel.

---

## Pourquoi MongoDB ?

Le dataset est adapté à MongoDB car il contient :

- un volume largement supérieur à 10 000 documents ;
- plusieurs entités liées : stations, PDC et statuts dynamiques ;
- une forte dimension géographique ;
- des structures imbriquées adaptées à des tableaux de PDC ;
- des champs parfois absents ou à nettoyer ;
- de vraies décisions entre embarquement et référencement.

Le profiling montre qu’une station contient en moyenne **3,45 PDC**, avec une médiane de **2**.
**95 % des stations ont 10 PDC ou moins** et **99 % en ont 20 ou moins**.

Ces résultats soutiennent notre choix d’embarquer les PDC dans un tableau `points_recharge`
au sein du document station, tout en conservant les statuts dynamiques dans une collection séparée.

---

## Modélisation retenue

Deux collections principales :

- `stations` : informations de la station et tableau `points_recharge`
- `statuts_pdc` : état dynamique des points de recharge

La justification détaillée de ces choix, avec les cardinalités mesurées,
les avantages et les coûts associés, est disponible dans le
[rapport de profiling](docs/profiling_irve.md).

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

- `analysis/` : notebooks d’exploration et d’analyse.
- `app/` : interface d’interrogation Streamlit.
- `data/` : instructions pour récupérer les fichiers IRVE ; les CSV ne sont pas versionnés.
- `docs/` : profiling et documentation technique.
- `scripts/` : import, démonstration CRUD, création/mesure des index et administration MongoDB.
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

> `.env.local` ne doit jamais être versionné. Aucun identifiant, mot de passe ou token ne doit apparaître dans le dépôt ou son historique Git.

---

## Import des données vers MongoDB Atlas

### Prérequis

- Python 3.12 ou version compatible ;
- les dépendances de `requirements.txt` ;
- un cluster MongoDB Atlas accessible ;
- un fichier `.env.local` configuré à partir de `.env.example` ;
- les CSV IRVE placés dans `data/`.

Installer les dépendances :

```bash
python -m pip install -r requirements.txt
```

Le fichier statique doit être placé sous ce nom :

```text
data/consolidation_transport_irve_statique.csv
```

Pour le dynamique, le script détecte le premier fichier CSV dont le nom contient
`dynamique`.

Lancer l'import :

```bash
python scripts/import_data.py
```

Le script :

- vérifie la connexion à Atlas avec `ping` ;
- retire les doublons de `id_pdc_itinerance` dans le statique ;
- construit un document par station avec un tableau `points_recharge` ;
- ajoute un GeoJSON `localisation` uniquement quand les coordonnées sont validées par la source ;
- calcule `departement` à partir du code INSEE lorsqu'il est disponible ;
- conserve, dans le snapshot dynamique, la ligne la plus récente par PDC selon `horodatage` ;
- charge les collections `stations` et `statuts_pdc` ;
- affiche les volumes finaux pour contrôle.

> L'import reconstruit les deux collections : leur contenu existant est supprimé avant réinsertion.

---

## Index et performances

Trois index ont été mis en place et mesurés avec `explain("executionStats")` avant et après création.

| Index | Usage | Avant | Après |
|---|---|---|---|
| `operateur: 1` | Stations d'un opérateur | `COLLSCAN`, 48 040 docs, 29 ms | `IXSCAN`, 5 077 docs, 9 ms |
| `horodatage: -1` | 20 statuts les plus récents | `COLLSCAN + SORT`, 100 838 docs, 91 ms | `IXSCAN`, 20 docs, 1 ms |
| `localisation: "2dsphere"` | Recherche géographique | `COLLSCAN`, 48 040 docs, 95 ms | `IXSCAN`, 1 265 docs, 7 ms |

Les détails des requêtes et les mesures complètes sont disponibles dans
[docs/indexes.md](docs/indexes.md).

Le benchmark peut être reproduit avec :

```bash
python scripts/benchmark_indexes.py
```

---

## CRUD Python

Les opérations de lecture/écriture sur la collection `stations` sont regroupées
dans le module réutilisable [`src/crud.py`](src/crud.py).

| Opération | Fonction | Comportement |
|---|---|---|
| Create | `creer_station(db, document)` | Valide le document puis l'insère ; le doublon d'`_id` est rejeté par MongoDB |
| Read | `lire_station(db, id_station)` | Renvoie une station, lève `StationIntrouvable` si absente |
| Read | `lister_stations(db, filtre, projection, limite, tri)` | Recherche filtrée avec projection et tri |
| Read | `compter_stations(db, filtre)` | Compte les stations correspondant à un filtre |
| Update | `modifier_station(db, id_station, modifications)` | `$set` des champs fournis, renvoie le document à jour |
| Update | `ajouter_point_recharge(db, id_station, point)` | `$push` dans `points_recharge` et `$inc` de `nbre_pdc` |
| Delete | `supprimer_station(db, id_station)` | Supprime la station et renvoie le document supprimé |

### Gestion d'erreurs

Les erreurs PyMongo sont converties en exceptions métier explicites, afin que
l'appelant (script, notebook ou interface) n'ait pas à connaître les exceptions
internes du pilote :

```text
ErreurCRUD                  erreur générique d'accès à MongoDB
├── StationIntrouvable      identifiant absent de la collection
├── StationDejaExistante    violation de la clé primaire `_id`
└── DocumentInvalide        schéma minimal ou GeoJSON non conforme
```

La validation contrôle les champs obligatoires (`_id`, `nom`, `operateur`), le
type du tableau `points_recharge` et la validité du GeoJSON `localisation`
(type `Point`, couple `[longitude, latitude]` dans les bornes) : un point mal
formé rendrait la station inexploitable par l'index `2dsphere`.

> `ajouter_point_recharge` maintient `nbre_pdc` en même temps que le tableau.
> C'est le coût concret de notre choix d'embarquement : le compteur étant
> dénormalisé dans le document station, chaque écriture sur `points_recharge`
> doit le resynchroniser.

### Démonstration

```bash
python scripts/demo_crud.py
```

Le script enchaîne les quatre opérations sur une station de test
(`FRDEMO PDEMO1`), déclenche volontairement quatre cas d'erreur, puis supprime
la station. Il est rejouable et n'altère jamais les données IRVE réelles.
## Administration : Sauvegarde et Restauration

Le projet intègre des scripts Python automatisant `mongodump` et `mongorestore` en utilisant exclusivement les variables d'environnement configurées (aucun mot de passe en clair).

Prérequis : installer **MongoDB Database Tools** et vérifier les commandes :

```bash
mongodump --version
mongorestore --version
```

La procédure détaillée est disponible dans [docs/backup_restore.md](docs/backup_restore.md).

### 1. Sauvegarde (`mongodump`)

Créer un dump BSON horodaté de la base `irve` dans le dossier local `backups/` :

```bash
python scripts/backup.py
```

Le script génère automatiquement un dossier horodaté (ex : `backups/20260828_114322/irve/`) contenant les fichiers `.bson` et `.metadata.json` des collections `stations` et `statuts_pdc`.

### 2. Restauration (`mongorestore`)

Restaurer la sauvegarde la plus récente vers une base de démonstration isolée (`irve_restore_demo`) pour valider la procédure sans écraser la base principale `irve` :

```bash
python scripts/restore.py
```

Le script :
- détecte la dernière sauvegarde disponible dans `backups/` ;
- supprime avec `--drop` les collections cibles avant leur restauration ;
- restaure l'ensemble des 148 878 documents et reconstruit automatiquement tous les index associés.

---

## Agrégations et rapport analytique

Les pipelines sont regroupés dans le module réutilisable
[`src/queries.py`](src/queries.py) : chaque fonction `pipeline_*` renvoie le
pipeline **sans l'exécuter**, ce qui permet de l'afficher en soutenance, de le
réutiliser dans `explain()` pour mesurer un index, et de le tester sans
connexion. Les fonctions d'exécution correspondantes renvoient les résultats.

Le rapport analytique exécuté se trouve dans
[`analysis/02_aggregations.ipynb`](analysis/02_aggregations.ipynb).

| Question métier | Pipeline | `$unwind` |
|---|---|---|
| Quels territoires sont les mieux équipés ? | `pipeline_offre_par_departement` | Non |
| Quelle puissance moyenne selon les territoires ? | `pipeline_puissance_par_departement` | Oui |
| Quels opérateurs dominent, et avec quelle qualité de service ? | `pipeline_top_operateurs` | Oui |
| À quel rythme le réseau s'est-il déployé ? | `pipeline_evolution_annuelle` | Non |
| Quel était l'état du parc dans le snapshot ? | `pipeline_etat_parc` | Non |

### Pourquoi `$unwind` n'apparaît pas partout

`$unwind` n'est utilisé que lorsque l'analyse porte réellement sur le point de
recharge : compter les PDC un à un ou moyenner leur puissance impose de dérouler
le tableau embarqué. Dès que la question porte sur la station, le compteur
dénormalisé `nbre_pdc` permet de l'éviter et d'économiser le déroulage de plus
de 165 000 sous-documents.

C'est la contrepartie mesurable de notre choix d'embarquement : il coûte un
`$unwind` sur les analyses granulaires, et rien sur les analyses par station.

### Recherche géospatiale

```python
from src.queries import stations_proches

stations_proches(db, longitude=2.3522, latitude=48.8566,
                 rayon_metres=2000, puissance_min=50)
```

`stations_proches` utilise `$near` (tri par distance croissante), tandis que
`pipeline_stations_proches_avec_distance` utilise `$geoNear`, qui restitue en
plus la distance calculée. Les deux exigent l'index `2dsphere` sur
`localisation`.

### Exécution du notebook

```bash
python -m pip install -r requirements.txt
jupyter lab analysis/02_aggregations.ipynb
```

> Le notebook doit être ré-exécuté contre le cluster Atlas avant la remise,
> afin que les sorties visibles correspondent aux données réelles.

---

## Interface d'interrogation (Streamlit)

Interface permettant d'interroger la base sans passer par un terminal.

```bash
streamlit run app/app.py
```

L'application s'ouvre sur `http://localhost:8501` et comporte trois onglets :

| Onglet | Ce qu'il permet | Code appelé |
|---|---|---|
| **Recherche par proximité** | Choisir une ville ou des coordonnées libres, régler le rayon, la puissance minimale et le type de prise ; résultats sur carte, tableau et export CSV | `pipeline_stations_proches_avec_distance` |
| **Analyses** | Consulter les agrégations par territoire, par opérateur et dans le temps | `offre_par_departement`, `top_operateurs`, `evolution_annuelle` |
| **Fiche station** | Lire une station par son identifiant d'itinérance et détailler ses PDC | `lire_station` du module CRUD |

### Choix techniques

Les filtres de puissance et de type de prise sont placés dans la clé `query` de
`$geoNear`, et non dans un `$match` ultérieur : `$geoNear` doit rester le
premier étage du pipeline, et cette forme laisse MongoDB appliquer le filtre
en s'appuyant sur l'index `2dsphere` plutôt que de rapatrier puis écarter des
documents.

L'interface ne réimplémente aucune requête : elle consomme `src/queries.py` et
`src/crud.py`, les mêmes modules que le notebook et les scripts. Une correction
de pipeline profite donc aux trois.

La connexion est mise en cache avec `@st.cache_resource` et les résultats avec
`@st.cache_data(ttl=300)`, afin de ne pas rouvrir une connexion Atlas à chaque
interaction.

> L'onglet de recherche exige l'index `2dsphere` sur `localisation`. Sans lui,
> `$geoNear` échoue et l'interface affiche un message invitant à lancer
> `scripts/create_indexes.py`.

---

## État du projet

- Profiling et justification de la modélisation : **terminés**
  ([rapport de profiling](docs/profiling_irve.md)).
- Import Atlas : **terminé et vérifié** — 48 040 stations et 100 838 statuts
  chargés sur le cluster.
- Index : **terminés et mesurés** avant/après avec `explain()`
  ([docs/indexes.md](docs/indexes.md)).
- CRUD Python : **terminé**, démontré par `scripts/demo_crud.py`.
- Agrégations et rapport analytique : **terminés**
  ([notebook](analysis/02_aggregations.ipynb), [pipelines](src/queries.py)).
- Interface Streamlit : **terminée** ([`app/app.py`](app/app.py)).
- Sauvegarde/restauration : en cours (branche `feature/backup-restore`).
- Index, sauvegarde/restauration et interface : en cours.
- Profiling et justification de la modélisation : **terminés**.
- Import Atlas : **terminé et vérifié** — 48 040 stations et 100 838 statuts chargés.
- CRUD Python : **implémenté**, avec démonstration via `scripts/demo_crud.py`.
- Index : **terminés et mesurés** avec `explain("executionStats")`.
- Sauvegarde / restauration : **terminée et testée sur Atlas**.
- Agrégations et visualisations : **en cours de finalisation**.
- Interface Streamlit : **en cours de finalisation**.
