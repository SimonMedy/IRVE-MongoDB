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
│   └── 01_exploration_profiling.ipynb
├── app/
│   └── app.py
├── data/
│   └── README.md
├── docs/
│   └── profiling_irve.md
├── scripts/
│   ├── import_data.py
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
- `scripts/` : import, création/mesure des index et administration MongoDB.
- `src/` : code Python réutilisable : configuration, connexion, CRUD et requêtes.
- `ROADMAP.md` : suivi des livrables, répartition du travail et critères de validation.

---

## Configuration

La connexion MongoDB Atlas est fournie par variables d’environnement.

Créer un fichier `.env.local` à partir de `.env.example` :

```env
MONGODB_URI=mongodb+srv://<USER>:<PASSWORD>@<CLUSTER>.mongodb.net/?retryWrites=true&w=majority
DB_NAME=irve
COLLECTION_STATIONS=stations
COLLECTION_STATUTS=statuts_pdc
```

> `.env.local` ne doit jamais être versionné. Aucun identifiant, mot de passe ou token ne doit apparaître dans le dépôt ou son historique Git.

---

## État du projet

Le profiling et la justification initiale de la modélisation sont terminés.

La suite du développement est suivie dans le
[ROADMAP](ROADMAP.md), qui reprend les livrables obligatoires, les bonus envisagés,
les validations à effectuer et la répartition du travail dans le groupe.
