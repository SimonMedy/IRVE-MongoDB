# Index MongoDB — IRVE

Le projet demande au moins trois index, chacun associé à une requête réelle et mesuré avec `explain("executionStats")` avant et après création.

Les mesures sont réalisées avec :

```bash
python scripts/benchmark_indexes.py
```

Le script retire uniquement les trois index du projet, effectue les mesures avant/après, puis laisse les trois index finaux en place.

## 1. Index sur l'opérateur

Index :

```javascript
{ operateur: 1 }
```

Nom : `idx_stations_operateur`

Question métier : **retrouver les stations d'un opérateur donné**.

Requête de mesure :

```javascript
{ operateur: "Bouygues Energies & Services" }
```

Attendu : avant l'index, MongoDB doit parcourir la collection. Après création, il peut utiliser un `IXSCAN` pour accéder directement aux stations de l'opérateur.

### Mesures réelles

À compléter après exécution sur Atlas :

| Mesure | Avant | Après |
|---|---:|---:|
| Stage | - | - |
| `totalDocsExamined` | - | - |
| `totalKeysExamined` | - | - |
| `executionTimeMillis` | - | - |

---

## 2. Index sur l'horodatage dynamique

Index :

```javascript
{ horodatage: -1 }
```

Nom : `idx_statuts_horodatage`

Question métier : **récupérer rapidement les statuts les plus récents**.

Requête de mesure : trier `statuts_pdc` par `horodatage` décroissant et retourner les 20 premiers documents.

Sans index, le tri peut nécessiter un parcours important et un `SORT`. Avec l'index décroissant, MongoDB peut parcourir directement l'index dans le bon ordre et s'arrêter après les premiers résultats.

### Mesures réelles

À compléter après exécution sur Atlas :

| Mesure | Avant | Après |
|---|---:|---:|
| Stage | - | - |
| `totalDocsExamined` | - | - |
| `totalKeysExamined` | - | - |
| `executionTimeMillis` | - | - |
| Tri mémoire | - | - |

---

## 3. Index géospatial `2dsphere`

Index :

```javascript
{ localisation: "2dsphere" }
```

Nom : `idx_stations_localisation_2dsphere`

Question métier : **chercher des stations dans une zone géographique, puis permettre les recherches de proximité**.

Pour avoir une vraie comparaison avant/après, le benchmark utilise `$geoWithin` sur une zone autour de Paris. Cette requête peut être exécutée sans index, contrairement à `$near` qui nécessite un index géospatial.

Une fois l'index créé, l'application pourra également utiliser une recherche de proximité :

```javascript
{
  localisation: {
    $near: {
      $geometry: {
        type: "Point",
        coordinates: [2.3522, 48.8566]
      },
      $maxDistance: 2000
    }
  }
}
```

### Mesures réelles

À compléter après exécution sur Atlas :

| Mesure | Avant | Après |
|---|---:|---:|
| Stage | - | - |
| `totalDocsExamined` | - | - |
| `totalKeysExamined` | - | - |
| `executionTimeMillis` | - | - |

---

## Pourquoi ces trois index ?

Ils servent trois usages différents :

1. filtrage métier par opérateur ;
2. consultation des statuts dynamiques les plus récents ;
3. recherche géographique des stations.

Le coût des index est qu'ils occupent de l'espace disque et doivent être mis à jour lors des insertions et modifications. Ils sont donc créés uniquement pour des requêtes réellement utiles au projet.
