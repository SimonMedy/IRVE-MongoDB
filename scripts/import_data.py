import sys
from pathlib import Path

import pandas as pd
from pymongo.errors import PyMongoError


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import COLLECTION_STATIONS, COLLECTION_STATUTS
from src.database import connexion


DATA_DIR = ROOT_DIR / "data"
CSV_STATIQUE = DATA_DIR / "consolidation_transport_irve_statique.csv"


def valeur_simple(value):
    """Transforme une valeur pandas en valeur Python simple."""
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def valeur_bool(value):
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value

    texte = str(value).strip().lower()
    if texte in ("true", "1", "oui"):
        return True
    if texte in ("false", "0", "non"):
        return False
    return None


def valeur_date(value):
    if pd.isna(value):
        return None

    date = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(date):
        return None

    return date.to_pydatetime()


def normaliser_code_insee(value):
    if pd.isna(value):
        return None

    code = str(value).strip().upper()
    if code.endswith(".0"):
        code = code[:-2]

    if code.isdigit():
        code = code.zfill(5)

    return code or None


def departement_depuis_insee(code_insee):
    if not code_insee:
        return None

    if code_insee.startswith(("2A", "2B")):
        return code_insee[:2]

    if code_insee.startswith(("97", "98")) and len(code_insee) >= 3:
        return code_insee[:3]

    if len(code_insee) >= 2:
        return code_insee[:2]

    return None


def construire_pdc(row):
    """Construit le sous-document d'un point de recharge."""
    return {
        "id_pdc": valeur_simple(row["id_pdc_itinerance"]),
        "id_pdc_local": valeur_simple(row["id_pdc_local"]),
        "puissance_kw": valeur_simple(row["puissance_nominale"]),
        "prises": {
            "ef": valeur_bool(row["prise_type_ef"]),
            "type2": valeur_bool(row["prise_type_2"]),
            "combo_ccs": valeur_bool(row["prise_type_combo_ccs"]),
            "chademo": valeur_bool(row["prise_type_chademo"]),
            "autre": valeur_bool(row["prise_type_autre"]),
        },
        "gratuit": valeur_bool(row["gratuit"]),
        "paiement_acte": valeur_bool(row["paiement_acte"]),
        "paiement_cb": valeur_bool(row["paiement_cb"]),
        "paiement_autre": valeur_bool(row["paiement_autre"]),
        "tarification": valeur_simple(row["tarification"]),
        "reservation": valeur_bool(row["reservation"]),
        "cable_t2_attache": valeur_bool(row["cable_t2_attache"]),
    }


def localisation_station(groupe):
    """Retourne un Point GeoJSON seulement si la source valide les coordonnées."""
    lignes_valides = groupe[
        (groupe["consolidated_is_lon_lat_correct"] == True)
        & groupe["consolidated_longitude"].notna()
        & groupe["consolidated_latitude"].notna()
    ]

    if lignes_valides.empty:
        return None

    row = lignes_valides.iloc[0]
    longitude = float(row["consolidated_longitude"])
    latitude = float(row["consolidated_latitude"])

    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return None

    return {
        "type": "Point",
        "coordinates": [longitude, latitude],
    }


def construire_station(groupe):
    """Construit un document MongoDB pour une station."""
    row = groupe.iloc[0]
    code_insee = normaliser_code_insee(row["code_insee_commune"])
    points = [construire_pdc(pdc) for _, pdc in groupe.iterrows()]

    document = {
        "_id": valeur_simple(row["id_station_itinerance"]),
        "id_station_local": valeur_simple(row["id_station_local"]),
        "nom": valeur_simple(row["nom_station"]),
        "operateur": valeur_simple(row["nom_operateur"]),
        "amenageur": valeur_simple(row["nom_amenageur"]),
        "enseigne": valeur_simple(row["nom_enseigne"]),
        "implantation": valeur_simple(row["implantation_station"]),
        "adresse": valeur_simple(row["adresse_station"]),
        "code_insee": code_insee,
        "departement": departement_depuis_insee(code_insee),
        "condition_acces": valeur_simple(row["condition_acces"]),
        "horaires": valeur_simple(row["horaires"]),
        "accessibilite_pmr": valeur_simple(row["accessibilite_pmr"]),
        "station_deux_roues": valeur_bool(row["station_deux_roues"]),
        "date_mise_en_service": valeur_date(row["date_mise_en_service"]),
        "date_maj": valeur_date(row["date_maj"]),
        "nbre_pdc": len(points),
        "points_recharge": points,
    }

    localisation = localisation_station(groupe)
    if localisation:
        document["localisation"] = localisation

    return document


def trouver_csv_dynamique():
    fichiers = sorted(DATA_DIR.glob("*dynamique*.csv"))
    if not fichiers:
        return None
    return fichiers[0]


def importer_stations(collection):
    print("Lecture du fichier statique...")
    df = pd.read_csv(CSV_STATIQUE, low_memory=False)

    avant = len(df)
    df = df.drop_duplicates(subset=["id_pdc_itinerance"], keep="first")
    print(f"PDC en doublon retirés : {avant - len(df):,}")

    collection.delete_many({})

    lot = []
    total = 0

    for _, groupe in df.groupby("id_station_itinerance", sort=False):
        lot.append(construire_station(groupe))

        if len(lot) >= 500:
            collection.insert_many(lot, ordered=False)
            total += len(lot)
            print(f"  Stations importées : {total:,}", end="\r")
            lot = []

    if lot:
        collection.insert_many(lot, ordered=False)
        total += len(lot)

    print(f"\nStations importées : {total:,}")
    return set(df["id_pdc_itinerance"])


def construire_statut(row):
    prises = {}

    colonnes_prises = {
        "etat_prise_type_2": "type2",
        "etat_prise_type_combo_ccs": "combo_ccs",
        "etat_prise_type_chademo": "chademo",
        "etat_prise_type_ef": "ef",
    }

    for colonne, nom in colonnes_prises.items():
        if colonne in row.index:
            prises[nom] = valeur_simple(row[colonne])

    document = {
        "_id": valeur_simple(row["id_pdc_itinerance"]),
        "id_pdc": valeur_simple(row["id_pdc_itinerance"]),
        "etat": valeur_simple(row["etat_pdc"]),
        "occupation": valeur_simple(row["occupation_pdc"]),
        "horodatage": valeur_date(row["horodatage"]),
    }

    if prises:
        document["etat_prises"] = prises

    return document


def importer_statuts(collection, pdc_statiques):
    chemin = trouver_csv_dynamique()
    if chemin is None:
        print("Aucun CSV dynamique trouvé : import des statuts ignoré.")
        return 0

    print(f"Lecture du fichier dynamique : {chemin.name}")
    df = pd.read_csv(chemin, low_memory=False)

    colonnes_obligatoires = {
        "id_pdc_itinerance",
        "etat_pdc",
        "occupation_pdc",
        "horodatage",
    }
    manquantes = colonnes_obligatoires - set(df.columns)
    if manquantes:
        raise ValueError(
            "Colonnes manquantes dans le fichier dynamique : "
            + ", ".join(sorted(manquantes))
        )

    df["horodatage_tri"] = pd.to_datetime(
        df["horodatage"], errors="coerce", utc=True
    )
    df = df.sort_values("horodatage_tri", na_position="first")
    df = df.drop_duplicates(subset=["id_pdc_itinerance"], keep="last")

    avant_filtre = len(df)
    df = df[df["id_pdc_itinerance"].isin(pdc_statiques)]
    ignores = avant_filtre - len(df)

    collection.delete_many({})

    lot = []
    total = 0

    for _, row in df.iterrows():
        lot.append(construire_statut(row))

        if len(lot) >= 1000:
            collection.insert_many(lot, ordered=False)
            total += len(lot)
            print(f"  Statuts importés : {total:,}", end="\r")
            lot = []

    if lot:
        collection.insert_many(lot, ordered=False)
        total += len(lot)

    print(f"\nStatuts importés : {total:,}")
    print(f"Statuts sans PDC statique ignorés : {ignores:,}")
    return total


def main():
    if not CSV_STATIQUE.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {CSV_STATIQUE}\n"
            "Voir data/README.md pour le téléchargement."
        )

    client = None

    try:
        client, db = connexion()
        print(f"Connexion Atlas OK - base : {db.name}")

        stations = db[COLLECTION_STATIONS]
        statuts = db[COLLECTION_STATUTS]

        pdc_statiques = importer_stations(stations)
        importer_statuts(statuts, pdc_statiques)

        print("\nVérification finale :")
        print(f"  stations    : {stations.count_documents({}):,}")
        print(f"  statuts_pdc : {statuts.count_documents({}):,}")

    except (PyMongoError, ValueError, FileNotFoundError, RuntimeError) as erreur:
        print(f"\nErreur : {erreur}")
        raise SystemExit(1)

    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
