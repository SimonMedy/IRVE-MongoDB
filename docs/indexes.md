# Index MongoDB — IRVE

Le projet demande au moins trois index, chacun associé à une requête réelle et mesuré avec `explain("executionStats")` avant et après création.

Les mesures sont réalisées avec le script :

```bash
python scripts/benchmark_indexes.py
```

Le script retire temporairement les trois index, effectue les mesures comparatives avant/après, puis recrée les trois index finaux sur Atlas.

---

## 1. Index sur l'opérateur

Index :

```javascript
{ operateur: 1 }
```

Nom : `idx_stations_operateur`

Question métier : **retrouver rapidement l'ensemble des stations exploitées par un opérateur donné**.

Requête de mesure :

```javascript
{ operateur: "Bouygues Energies & Services" }
```

### Mesures réelles obtenues sur Atlas

| Mesure | Avant index | Après index | Évolution / Gain |
|---|---:|---:|---|
| **Plan d'exécution (Stage)** | `COLLSCAN` | `IXSCAN` | Parcours direct de l'arbre d'index |
| **Documents examinés (`totalDocsExamined`)** | 48 040 | 5 077 | **-89,4 %** (zéro document superflu scanné) |
| **Clés d'index examinées (`totalKeysExamined`)** | 0 | 5 077 | Lecture exacte des 5 077 clés |
| **Documents retournés (`nReturned`)** | 5 077 | 5 077 | Identique |
| **Temps d'exécution (`executionTimeMillis`)** | **29 ms** | **9 ms** | **Gain de vitesse x3,2** |

---

## 2. Index sur l'horodatage dynamique

Index :

```javascript
{ horodatage: -1 }
```

Nom : `idx_statuts_horodatage`

Question métier : **récupérer instantanément les 20 statuts de recharge les plus récents**.

Requête de mesure : trier la collection `statuts_pdc` par `horodatage` décroissant et limiter aux 20 premiers résultats.

### Mesures réelles obtenues sur Atlas

| Mesure | Avant index | Après index | Évolution / Gain |
|---|---:|---:|---|
| **Plan d'exécution (Stage)** | `COLLSCAN` + `SORT` | `IXSCAN` | Suppression du tri mémoire |
| **Documents examinés (`totalDocsExamined`)** | 100 838 | 20 | **-99,98 %** (arrêt direct dès 20 docs) |
| **Clés d'index examinées (`totalKeysExamined`)** | 0 | 20 | Parcours des 20 premières clés B-Tree |
| **Tri en mémoire vive** | **Oui (bloquant)** | **Non (ordonné par index)** | Économie de mémoire vive sur Atlas |
| **Temps d'exécution (`executionTimeMillis`)** | **91 ms** | **1 ms** | **Gain de vitesse x91** |

---

## 3. Index géospatial `2dsphere`

Index :

```javascript
{ localisation: "2dsphere" }
```

Nom : `idx_stations_localisation_2dsphere`

Question métier : **rechercher des stations dans une zone géographique délimitée ou par rayon de proximité**.

Pour obtenir une vraie comparaison avant/après, le benchmark utilise `$geoWithin` sur une zone polygone autour de Paris (exécutable sans index, contrairement à `$near` qui échoue sans `2dsphere`).

Requête de proximité autorisée après index :

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

### Mesures réelles obtenues sur Atlas

| Mesure | Avant index | Après index | Évolution / Gain |
|---|---:|---:|---|
| **Plan d'exécution (Stage)** | `COLLSCAN` | `IXSCAN` | Indexation géospatiale par cellules S2 |
| **Documents examinés (`totalDocsExamined`)** | 48 040 | 1 265 | **-97,4 %** de documents lus |
| **Clés d'index examinées (`totalKeysExamined`)** | 0 | 1 276 | Découpage spatial 2dsphere |
| **Documents retournés (`nReturned`)** | 980 | 980 | Identique |
| **Temps d'exécution (`executionTimeMillis`)** | **95 ms** | **7 ms** | **Gain de vitesse x13,5** |

---

## Pourquoi ces trois index ?

Ils répondent chacun à un cas d'usage distinct :
1. **Filtrage métier** par opérateur (`operateur: 1`).
2. **Tri temporel pour consulter les statuts les plus récents du snapshot importé** (`horodatage: -1`).
3. **Recherche géographique** indispensable pour guider un conducteur (`localisation: "2dsphere"`).

**Le coût de ces index** : les index occupent de l'espace disque et peuvent utiliser de la mémoire via le cache ; ils ajoutent aussi un coût lors des écritures. C'est pourquoi nous avons limité nos index à ces 3 clés indispensables aux requêtes réelles.
