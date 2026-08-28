# IRVE-MongoDB

## Projet final NoSQL — Mobilité électrique en France

**Sujet :** localisation, puissance et disponibilité des points de recharge IRVE en France.

Le projet construit une base **MongoDB Atlas** à partir de la Base Nationale IRVE et permet d'interroger, analyser et administrer les données de recharge électrique.

Après profiling :

- **165 595 lignes statiques** ;
- **165 593 PDC distincts** ;
- **48 040 stations** ;
- **115 159 lignes dynamiques** ;
- **104 046 PDC distincts dans le fichier dynamique**.

Le fichier dynamique importé correspond à un **snapshot à un instant donné** : il ne constitue pas un historique ni un flux temps réel.

---

## Sommaire des livrables

| Livrable | Où le trouver |
|---|---|
| 1. Base MongoDB Atlas | section [Import des données](#import-des-données-vers-mongodb-atlas) et base `irve` |
| 2. Modélisation justifiée | section [Modélisation](#modélisation-retenue) et [fiche de synthèse architecturale](docs/profiling_irve.md) |
| 3. CRUD Python | [`src/crud.py`](src/crud.py) et [`scripts/demo_crud.py`](scripts/demo_crud.py) |
| 4. Index justifiés et mesurés | [`docs/indexes.md`](docs/indexes.md), `scripts/create_indexes.py`, `scripts/benchmark_indexes.py` |
| 5. Rapport analytique par agrégations | [`analysis/02_aggregations.ipynb`](analysis/02_aggregations.ipynb) et [`src/queries.py`](src/queries.py) |
| 6. Backup / Restore | [`docs/backup_restore.md`](docs/backup_restore.md), `scripts/backup.py`, `scripts/restore.py` |
| 7. Vidéo de soutenance | déposée séparément selon les consignes du formateur |
| 8. Dépôt propre + README | ce dépôt et ce README |

---

## Source des données

**[BETA] Base Nationale des Points de Recharge pour Véhicules Électriques en France (IRVE)**

- [Page officielle du dataset](https://www.data.gouv.fr/datasets/beta-bases-nationales-des-points-de-recharge-pour-vehicules-electriques-en-france-irve)
- [Téléchargement des données statiques](https://transport.data.gouv.fr/resources/84013?locale=fr)
- [Téléchargement des données dynamiques](https://transport.data.gouv.fr/resources/84098)
- [Schéma IRVE statique](https://schema.data.gouv.fr/etalab/schema-irve-statique/)
- [Schéma IRVE dynamique](https://schema.data.gouv.fr/etalab/schema-irve-dynamique/)

Licence : **Licence Ouverte / Open Licence 2.0**.

---

## Pourquoi MongoDB ?

Le jeu de données contient :

- un volume largement supérieur à 10 000 documents ;
- plusieurs entités liées : stations, PDC et statuts dynamiques ;
- une dimension géographique forte ;
- des tableaux et structures imbriquées ;
- des champs parfois absents ou à nettoyer ;
- de vraies décisions entre embarquement et référencement.

Le profiling montre qu'une station contient en moyenne **3,45 PDC**, avec une médiane de **2**. **95 % des stations ont 10 PDC ou moins** et **99 % en ont 20 ou moins**.

Ces mesures justifient l'embarquement des PDC dans le document station pour la majorité des cas.

---

## Modélisation retenue

Deux collections principales :

- `stations` : un document par station avec un tableau `points_recharge[]` ;
- `statuts_pdc` : snapshot dynamique des états des points de recharge.

### Station → PDC

Les PDC sont **embarqués** dans `points_recharge[]`.

**Avantage :** une station et ses PDC sont récupérés ensemble.

**Coût :** les analyses au niveau de chaque PDC nécessitent souvent `$unwind`, ce qui augmente le nombre de documents intermédiaires. Quelques stations atypiques possèdent de très gros tableaux, avec un maximum observé de **505 PDC**.

### PDC → statut dynamique

Les statuts sont **référencés dans une collection séparée**.

**Avantage :** les données statiques et dynamiques ont des cycles de vie différents et restent découplées.

**Coût :** certaines requêtes combinant caractéristiques statiques et statut nécessitent un `$lookup` ou plusieurs lectures.

La fiche complète avec **relation, cardinalité mesurée, décision, justification et coût** se trouve dans [`docs/profiling_irve.md`](docs/profiling_irve.md), section **Fiche de Synthèse Architecturale**.

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

---

## Installation et configuration

### Prérequis

- Python 3.12 ou version compatible ;
- un cluster MongoDB Atlas accessible ;
- MongoDB Database Tools pour `mongodump` / `mongorestore` ;
- les fichiers CSV IRVE pour rejouer l'import.

Installer les dépendances :

```bash
python -m pip install -r requirements.txt
```

Créer `.env.local` à partir de `.env.example` :

```env
MONGODB_URI=mongodb+srv://<USER>:<PASSWORD>@<CLUSTER>.mongodb.net/?retryWrites=true&w=majority
DB_NAME=irve
COLLECTION_STATIONS=stations
COLLECTION_STATUTS=statuts_pdc
RESTORE_DB_NAME=irve_restore_demo
```

`.env.local` ne doit jamais être versionné. Aucun identifiant, mot de passe ou token ne doit apparaître dans le dépôt.

---

## Import des données vers MongoDB Atlas

Le fichier statique doit être placé sous ce nom :

```text
data/consolidation_transport_irve_statique.csv
```

Pour le dynamique, le script détecte le premier CSV dont le nom contient `dynamique`.

Lancer :

```bash
python scripts/import_data.py
```

Le script :

- vérifie la connexion Atlas avec `ping` ;
- transforme les `NaN` en valeurs nulles ;
- normalise booléens, dates et codes INSEE ;
- retire les doublons de `id_pdc_itinerance` dans le statique ;
- construit un document par station avec `points_recharge[]` ;
- ajoute un GeoJSON `localisation` uniquement lorsque les coordonnées sont validées et cohérentes ;
- conserve la ligne dynamique la plus récente par PDC selon `horodatage` ;
- ignore les statuts dynamiques sans PDC statique correspondant ;
- charge `stations` et `statuts_pdc`.

Validation réelle de l'import :

```text
stations    : 48 040
statuts_pdc : 100 838
2 doublons PDC statiques retirés
3 208 statuts dynamiques sans correspondance statique ignorés
```

> L'import reconstruit les deux collections : leur contenu existant est supprimé avant réinsertion.

---

## CRUD Python

Le CRUD est implémenté dans [`src/crud.py`](src/crud.py).

| Opération | Exemple de fonction |
|---|---|
| Create | `creer_station(...)` |
| Read | `lire_station(...)`, `lister_stations(...)`, `compter_stations(...)` |
| Update | `modifier_station(...)`, `ajouter_point_recharge(...)` |
| Delete | `supprimer_station(...)` |

La validation contrôle notamment les champs obligatoires, `points_recharge[]` et le GeoJSON `localisation`. Les erreurs MongoDB sont transformées en exceptions métier explicites.

Démonstration :

```bash
python scripts/demo_crud.py
```

La démonstration crée une station temporaire, exécute Create / Read / Update / Delete, vérifie plusieurs erreurs, puis supprime la station de test.

**Validation Atlas : OK.** La collection passe temporairement à **48 041 stations**, puis revient à **48 040** après suppression.

---

## Index et performances

Trois index métier ont été créés et mesurés avec `explain("executionStats")` avant et après création.

| Index | Usage | Avant | Après |
|---|---|---|---|
| `operateur: 1` | Stations d'un opérateur | `COLLSCAN`, 48 040 docs, 29 ms | `IXSCAN`, 5 077 docs, 9 ms |
| `horodatage: -1` | 20 statuts les plus récents | `COLLSCAN + SORT`, 100 838 docs, 91 ms | `IXSCAN`, 20 docs, 1 ms |
| `localisation: "2dsphere"` | Recherche géographique | `COLLSCAN`, 48 040 docs, 95 ms | `IXSCAN`, 1 265 docs, 7 ms |

Détails complets : [`docs/indexes.md`](docs/indexes.md).

Rejouer le benchmark :

```bash
python scripts/benchmark_indexes.py
```

---

## Agrégations et rapport analytique

Les pipelines réutilisables sont dans [`src/queries.py`](src/queries.py). Le rapport analytique exécuté et ses visualisations sont dans [`analysis/02_aggregations.ipynb`](analysis/02_aggregations.ipynb).

Analyses principales :

1. offre de recharge par département ;
2. puissance moyenne par département ;
3. comparaison des principaux opérateurs ;
4. évolution annuelle du déploiement ;
5. état du parc dans le snapshot dynamique.

`$unwind` est utilisé uniquement lorsque l'analyse doit travailler individuellement sur les éléments de `points_recharge[]`. Pour les analyses au niveau station, le compteur `nbre_pdc` évite un déroulage inutile.

Le notebook a été **ré-exécuté sur la vraie base Atlas `irve`**, avec **48 040 stations**, toutes les cellules exécutées sans erreur et les graphiques sauvegardés dans le notebook.

Pour l'ouvrir :

```bash
jupyter lab analysis/02_aggregations.ipynb
```

---

## Recherche géospatiale

Exemple :

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

`stations_proches` utilise `$near`. Une variante avec `$geoNear` restitue également la distance calculée. Ces requêtes utilisent l'index `2dsphere` sur `localisation`.

---

## Interface d'interrogation — Streamlit

Lancer :

```bash
streamlit run app/app.py
```

L'interface propose :

- recherche par proximité avec ville / coordonnées et rayon ;
- filtre de puissance minimale ;
- filtre par type de prise ;
- carte et tableau de résultats ;
- export CSV ;
- onglet Analyses ;
- fiche détaillée d'une station.

Validation fonctionnelle réalisée sur Atlas : recherche **Paris — Châtelet, 2 km**, filtres de puissance et de prise, carte, tableau, agrégations, fiche station existante et gestion propre d'un identifiant inexistant.

---

## Administration — Sauvegarde et restauration

Le projet utilise les outils officiels `mongodump` et `mongorestore`.

Vérifier les outils :

```bash
mongodump --version
mongorestore --version
```

Sauvegarde :

```bash
python scripts/backup.py
```

Restauration vers la base de démonstration `irve_restore_demo` :

```bash
python scripts/restore.py
```

Documentation : [`docs/backup_restore.md`](docs/backup_restore.md).

Validation réelle :

```text
stations restaurées    : 48 040
statuts_pdc restaurés  : 100 838
total                  : 148 878
échecs                 : 0
```

Les index `idx_stations_operateur`, `idx_stations_localisation_2dsphere` et `idx_statuts_horodatage` ont également été restaurés.

---

## Validation finale

La version finale a été contrôlée avec :

```bash
python -m compileall -q src scripts app
python scripts/demo_crud.py
streamlit run app/app.py
```

Résultats :

- compilation Python : **OK** ;
- CRUD complet sur Atlas : **OK** ;
- notebook d'agrégations exécuté sur `irve` / 48 040 stations : **OK** ;
- graphiques du rapport analytique : **OK** ;
- recherche géospatiale et filtres Streamlit : **OK** ;
- analyses Streamlit : **OK** ;
- fiche station et gestion d'identifiant invalide : **OK** ;
- backup / restore Atlas : **OK** ;
- CI GitHub Actions : **verte**.

Aucun CSV volumineux, dump BSON ou fichier `.env.local` n'est suivi dans l'arborescence Git.

---

## État du projet

- Base Atlas : **terminée et validée**.
- Modélisation et fiche architecturale : **terminées**.
- CRUD Python : **terminé et validé**.
- Index et `explain()` avant/après : **terminés et validés**.
- Agrégations + visualisations : **terminées et validées sur Atlas**.
- Backup / Restore : **terminé et validé**.
- Interface Streamlit : **terminée et validée**.
- README / dépôt : **finalisés**.

Le code est prêt à être figé pour la soutenance vidéo.
