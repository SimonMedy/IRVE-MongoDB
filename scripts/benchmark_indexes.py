import json
import sys
from pathlib import Path

from pymongo import DESCENDING, GEOSPHERE
from pymongo.errors import PyMongoError


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import COLLECTION_STATIONS, COLLECTION_STATUTS
from src.database import connexion


INDEX_OPERATEUR = "idx_stations_operateur"
INDEX_HORODATAGE = "idx_statuts_horodatage"
INDEX_GEO = "idx_stations_localisation_2dsphere"

OPERATEUR_TEST = "Bouygues Energies & Services"

ZONE_PARIS = {
    "type": "Polygon",
    "coordinates": [[
        [2.25, 48.80],
        [2.45, 48.80],
        [2.45, 48.92],
        [2.25, 48.92],
        [2.25, 48.80],
    ]],
}


def supprimer_index_si_present(collection, nom):
    noms = [index["name"] for index in collection.list_indexes()]
    if nom in noms:
        collection.drop_index(nom)


def trouver_stages(noeud):
    """Retourne les noms d'étages présents dans un plan explain."""
    stages = []

    if isinstance(noeud, dict):
        if "stage" in noeud:
            stages.append(noeud["stage"])
        for valeur in noeud.values():
            stages.extend(trouver_stages(valeur))

    elif isinstance(noeud, list):
        for valeur in noeud:
            stages.extend(trouver_stages(valeur))

    return stages


def expliquer(db, collection, filtre, tri=None, limite=None):
    """Lance explain('executionStats') sur une requête find simple."""
    commande = {
        "find": collection.name,
        "filter": filtre,
    }

    if tri:
        commande["sort"] = dict(tri)
    if limite:
        commande["limit"] = limite

    plan = db.command("explain", commande, verbosity="executionStats")
    stats = plan["executionStats"]
    stages = trouver_stages(stats["executionStages"])

    if "IXSCAN" in stages:
        stage = "IXSCAN"
    elif "COLLSCAN" in stages:
        stage = "COLLSCAN"
    else:
        stage = ", ".join(dict.fromkeys(stages))

    return {
        "stage": stage,
        "cles": stats["totalKeysExamined"],
        "docs": stats["totalDocsExamined"],
        "rendus": stats["nReturned"],
        "ms": stats["executionTimeMillis"],
        "tri_memoire": "SORT" in stages,
    }


def afficher(titre, resultat):
    tri = " | SORT mémoire" if resultat["tri_memoire"] else ""
    print(
        f"{titre:<18} "
        f"stage={resultat['stage']:<10} "
        f"clés={resultat['cles']:<8} "
        f"docs={resultat['docs']:<8} "
        f"rendus={resultat['rendus']:<6} "
        f"temps={resultat['ms']} ms{tri}"
    )


def benchmark_operateur(db, stations):
    print("\n=== INDEX 1 : opérateur ===")
    filtre = {"operateur": OPERATEUR_TEST}

    avant = expliquer(db, stations, filtre)
    stations.create_index([("operateur", 1)], name=INDEX_OPERATEUR)
    apres = expliquer(db, stations, filtre)

    print(f"Requête : stations de l'opérateur '{OPERATEUR_TEST}'")
    afficher("Avant index", avant)
    afficher("Après index", apres)


def benchmark_horodatage(db, statuts):
    print("\n=== INDEX 2 : statuts les plus récents ===")
    tri = [("horodatage", DESCENDING)]

    avant = expliquer(db, statuts, {}, tri=tri, limite=20)
    statuts.create_index([("horodatage", DESCENDING)], name=INDEX_HORODATAGE)
    apres = expliquer(db, statuts, {}, tri=tri, limite=20)

    print("Requête : récupérer les 20 statuts les plus récents")
    afficher("Avant index", avant)
    afficher("Après index", apres)


def benchmark_geo(db, stations):
    print("\n=== INDEX 3 : géospatial ===")
    filtre = {
        "localisation": {
            "$geoWithin": {
                "$geometry": ZONE_PARIS,
            }
        }
    }

    avant = expliquer(db, stations, filtre)
    stations.create_index([("localisation", GEOSPHERE)], name=INDEX_GEO)
    apres = expliquer(db, stations, filtre)

    print("Requête : stations présentes dans une zone autour de Paris")
    afficher("Avant index", avant)
    afficher("Après index", apres)


def main():
    client = None

    try:
        client, db = connexion()
        stations = db[COLLECTION_STATIONS]
        statuts = db[COLLECTION_STATUTS]

        # On retire uniquement les trois index du projet pour obtenir
        # une vraie mesure avant/après. L'index _id_ reste en place.
        supprimer_index_si_present(stations, INDEX_OPERATEUR)
        supprimer_index_si_present(stations, INDEX_GEO)
        supprimer_index_si_present(statuts, INDEX_HORODATAGE)

        print("Connexion Atlas OK")
        print(f"Stations : {stations.count_documents({}):,}")
        print(f"Statuts  : {statuts.count_documents({}):,}")

        benchmark_operateur(db, stations)
        benchmark_horodatage(db, statuts)
        benchmark_geo(db, stations)

        print("\nIndex finaux en place :")
        print([index["name"] for index in stations.list_indexes()])
        print([index["name"] for index in statuts.list_indexes()])

    except (PyMongoError, RuntimeError) as erreur:
        print(f"Erreur : {erreur}")
        raise SystemExit(1)

    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
