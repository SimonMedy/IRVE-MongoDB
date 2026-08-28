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


def main():
    client = None

    try:
        client, db = connexion()
        stations = db[COLLECTION_STATIONS]
        statuts = db[COLLECTION_STATUTS]

        stations.create_index(
            [("operateur", 1)],
            name=INDEX_OPERATEUR,
        )
        statuts.create_index(
            [("horodatage", DESCENDING)],
            name=INDEX_HORODATAGE,
        )
        stations.create_index(
            [("localisation", GEOSPHERE)],
            name=INDEX_GEO,
        )

        print("Index créés :")
        print(f"- {INDEX_OPERATEUR}")
        print(f"- {INDEX_HORODATAGE}")
        print(f"- {INDEX_GEO}")

    except (PyMongoError, RuntimeError) as erreur:
        print(f"Erreur : {erreur}")
        raise SystemExit(1)

    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
