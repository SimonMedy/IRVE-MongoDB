# Rapport de Profiling des Données IRVE (Base Nationale)

Document généré à partir des données officielles consolidées de *data.gouv.fr* et *transport.data.gouv.fr*.

## 1. Fiche de Synthèse Architecturale

| Relation | Cardinalité mesurée | Choix retenu | Pourquoi | Coût / Limite |
|---|---:|---|---|---|
| **Station → Points de recharge** | **Moyenne : 3,45**<br>Médiane : 2<br>p75 : 4<br>p95 : 10<br>p99 : 20<br>Max : 505 | **Embarquer** dans un tableau `points_recharge` | Faible cardinalité dans la grande majorité des stations : 95 % ont 10 PDC ou moins, et les PDC appartiennent naturellement à leur station. | Les analyses granulaires par PDC nécessitent souvent un `$unwind`, ce qui augmente le nombre de documents intermédiaires. Quelques stations atypiques possèdent de gros tableaux, avec un maximum observé de 505 PDC. |
| **Point de recharge → Statut dynamique** | **60,9 %** des PDC statiques couverts (100 838 PDC sur 165 593) | **Référencer** dans une collection `statuts_pdc` | Séparer des données qui n'ont pas le même cycle de vie : les caractéristiques statiques évoluent peu, tandis que l'état d'occupation ou de fonctionnement a vocation à être actualisé plus fréquemment à la source. | Certaines requêtes combinant caractéristiques statiques et état courant nécessitent un `$lookup` ou plusieurs lectures. |

## 2. Métriques Clés du Dataset

| Indicateur | Valeur réelle | Décision d'architecture MongoDB |
|---|---:|---|
| **Lignes statiques** | **165 595** | Volume suffisant pour mesurer l'effet des index avec `explain()`. |
| **PDC distincts** | **165 593** | Deux doublons d'identifiant PDC sont présents dans les données statiques et doivent être pris en compte lors de l'import. |
| **Stations uniques** | **48 040** | Environ 48 040 documents attendus dans la collection `stations` si l'on conserve un document par station. |
| **Coordonnées GPS renseignées** | **165 584 / 165 595** (~99,99 %) | Vérification nécessaire avant transformation en GeoJSON. |
| **Coordonnées validées par la source** | **139 248** (84,1 %) | Les coordonnées explicitement validées peuvent alimenter l'index spatial `2dsphere` après transformation en GeoJSON. |
| **Coordonnées à contrôler** | **26 347** (15,9 %) | Ces lignes doivent être contrôlées ou exclues de l'index géospatial selon la règle de nettoyage retenue. |
| **Lignes dynamiques (snapshot)** | **115 159** | Le fichier téléchargé représente un instantané des données dynamiques. |
| **PDC dynamiques distincts** | **104 046** | Le dynamique ne couvre pas tous les PDC présents dans le statique. |
| **PDC dynamiques multi-lignes** | **11 098** | Certains PDC apparaissent plusieurs fois dans le snapshot consolidé et nécessitent une règle de dédoublonnage ou de sélection du statut courant. |

## 3. Justifications Architecturales Détaillées

### Station → Points de recharge

Nous avons d'abord mesuré la cardinalité réelle. Le dataset contient **165 595 lignes statiques** réparties sur **48 040 stations** et **165 593 PDC distincts**.

Une station possède en moyenne **3,45 PDC**, avec une médiane de **2**.  
75 % des stations ont **4 PDC ou moins**, 95 % en ont **10 ou moins** et 99 % en ont **20 ou moins**.

Nous avons donc retenu l'embarquement des PDC dans un tableau `points_recharge` au sein du document station, car la cardinalité est faible dans la grande majorité des cas et les PDC appartiennent naturellement à leur station.

**Coût de ce choix :** les analyses au niveau du PDC nécessitent souvent `$unwind`, ce qui augmente le nombre de documents intermédiaires dans le pipeline. Il existe également quelques stations atypiques beaucoup plus grandes, avec un maximum observé de **505 PDC**.

Si les tableaux devenaient beaucoup plus volumineux ou si la majorité des requêtes travaillaient directement au niveau du PDC, une collection `points_recharge` séparée pourrait devenir plus adaptée.

### Point de recharge → Statut dynamique

Le fichier dynamique contient **115 159 lignes pour 104 046 PDC uniques**. Parmi les PDC du fichier statique, **100 838** disposent d'au moins un statut dynamique, soit environ **60,9 %** de couverture.

Nous avons choisi de stocker ces informations dans une collection `statuts_pdc` séparée afin de découpler les données statiques des données d'occupation et d'état de fonctionnement, qui n'ont pas le même cycle de vie.

Le fichier téléchargé représente toutefois un **snapshot à un instant donné**. Il ne constitue pas à lui seul un flux temps réel ou un historique. Pour disposer d'états réellement actualisés dans l'application, il faudrait mettre en place un mécanisme de rafraîchissement périodique depuis la source.

**Coût de ce choix :** certaines requêtes combinant les caractéristiques statiques d'un PDC et son état courant nécessiteront un `$lookup` ou plusieurs lectures.

Par ailleurs, **11 098 PDC apparaissent plusieurs fois dans le snapshot dynamique**. L'import devra donc définir une règle permettant d'identifier le statut à conserver, par exemple à partir des informations d'horodatage lorsque celles-ci permettent de départager les lignes.

## 4. Qualité des Coordonnées Géographiques

La quasi-totalité des lignes possède des coordonnées renseignées : **165 584 sur 165 595**.

Cependant, la source ne valide explicitement que **139 248 lignes**, soit **84,1 %** du dataset.  
**26 347 lignes**, soit environ **15,9 %**, sont signalées comme étant à contrôler.

Avant de créer les objets GeoJSON et l'index `2dsphere`, l'import devra donc appliquer une règle de validation ou d'exclusion des coordonnées non fiables.

Les coordonnées GeoJSON seront stockées dans l'ordre :

```text
[longitude, latitude]
```

Exemple :

```javascript
{
  localisation: {
    type: "Point",
    coordinates: [2.3522, 48.8566]
  }
}
```

## 5. Répartition des Puissances

- **Standard (< 50 kW)** : 119 111 (71,9 %)
- **Rapide (50 à 149 kW)** : 15 033 (9,1 %)
- **Ultra-rapide (≥ 150 kW)** : 31 451 (19,0 %)

Cette répartition pourra alimenter les agrégations et visualisations métier du projet.

## 6. Top 5 des Opérateurs

- **Bouygues Energies & Services** : 15 012 points de recharge (9,1 %)
- **IZIVIA** : 11 745 points de recharge (7,1 %)
- **Freshmile | FR*FR1** : 9 488 points de recharge (5,7 %)
- **Power Dot France** : 7 619 points de recharge (4,6 %)
- **GROUPE INDIGO** : 7 507 points de recharge (4,5 %)

Ces résultats pourront être utilisés pour une agrégation comparant le nombre de PDC et la puissance moyenne par opérateur.

## 7. Types de Connecteurs Disponibles

- **Prise EF** : 45 499 (27,5 %)
- **Prise Type 2** : 116 568 (70,4 %)
- **Prise COMBO CCS** : 43 105 (26,0 %)
- **Prise CHAdeMO** : 6 877 (4,2 %)
- **Prise autre** : 3 144 (1,9 %)

Un même PDC pouvant proposer plusieurs types de connecteurs, ces pourcentages ne sont pas exclusifs et leur somme peut dépasser 100 %.

## 8. Conclusion du Profiling

Le profiling confirme que le jeu de données est adapté au projet MongoDB :

- le volume est largement supérieur à 10 000 documents ;
- la relation Station → PDC possède une faible cardinalité dans la grande majorité des cas, ce qui rend l'embarquement raisonnable ;
- les données dynamiques ont un cycle de vie distinct et justifient une collection séparée ;
- les coordonnées géographiques permettent une exploitation avec GeoJSON et `2dsphere`, sous réserve de nettoyage ;
- les puissances, opérateurs et connecteurs offrent plusieurs axes d'agrégation métier.

Ces mesures servent directement à justifier les choix de modélisation retenus pour la base MongoDB.
