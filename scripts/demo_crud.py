"""Démonstration des opérations CRUD sur la collection `stations`.

Le script insère une station de test, la lit, la modifie, lui ajoute un point
de recharge puis la supprime. Il illustre également la gestion d'erreurs en
provoquant volontairement trois cas d'échec.

La station de test utilise un identifiant préfixé `FRDEMO` afin de ne jamais
entrer en collision avec les données IRVE réelles, et elle est supprimée en
fin d'exécution.
"""

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.crud import (
    DocumentInvalide,
    ErreurCRUD,
    StationDejaExistante,
    StationIntrouvable,
    ajouter_point_recharge,
    compter_stations,
    creer_station,
    lire_station,
    lister_stations,
    modifier_station,
    supprimer_station,
)
from src.database import connexion


ID_DEMO = "FRDEMO PDEMO1"


def station_demo():
    return {
        "_id": ID_DEMO,
        "nom": "Station de démonstration CRUD",
        "operateur": "Demo Energies",
        "amenageur": "Demo Amenagement",
        "adresse": "1 rue de la Demo, 75001 Paris",
        "code_insee": "75101",
        "departement": "75",
        "condition_acces": "Accès libre",
        "nbre_pdc": 1,
        "points_recharge": [
            {
                "id_pdc": "FRDEMO EDEMO1",
                "puissance_kw": 22.0,
                "prises": {"type2": True, "combo_ccs": False},
            }
        ],
        "localisation": {"type": "Point", "coordinates": [2.3522, 48.8566]},
    }


def titre(texte):
    print(f"\n{texte}")
    print("-" * len(texte))


def demonstration_create(db):
    titre("1. CREATE")

    # Nettoyage préalable : le script doit être rejouable même après un échec.
    try:
        supprimer_station(db, ID_DEMO)
        print("  (station de démo résiduelle supprimée)")
    except StationIntrouvable:
        pass

    identifiant = creer_station(db, station_demo())
    print(f"  Station insérée : {identifiant}")


def demonstration_read(db):
    titre("2. READ")

    station = lire_station(db, ID_DEMO)
    print(f"  Nom       : {station['nom']}")
    print(f"  Opérateur : {station['operateur']}")
    print(f"  PDC       : {station['nbre_pdc']}")

    total = compter_stations(db)
    print(f"  Total des stations dans la collection : {total:,}")

    paris = lister_stations(
        db,
        filtre={"departement": "75"},
        projection={"nom": 1, "operateur": 1},
        limite=3,
    )
    print(f"  Exemple de filtre (departement = 75), {len(paris)} résultats :")
    for element in paris:
        print(f"    - {element.get('nom')}")


def demonstration_update(db):
    titre("3. UPDATE")

    station = modifier_station(
        db,
        ID_DEMO,
        {"operateur": "Demo Energies (renommé)", "condition_acces": "Accès réservé"},
    )
    print(f"  Nouvel opérateur : {station['operateur']}")
    print(f"  Nouvel accès     : {station['condition_acces']}")

    station = ajouter_point_recharge(
        db,
        ID_DEMO,
        {
            "id_pdc": "FRDEMO EDEMO2",
            "puissance_kw": 150.0,
            "prises": {"type2": False, "combo_ccs": True},
        },
    )
    print(f"  PDC après ajout  : {station['nbre_pdc']} (compteur resynchronisé)")


def demonstration_erreurs(db):
    titre("4. GESTION D'ERREURS")

    try:
        creer_station(db, station_demo())
    except StationDejaExistante as erreur:
        print(f"  Doublon détecté      : {erreur}")

    try:
        creer_station(db, {"_id": "FRDEMO PVIDE", "nom": "Sans opérateur"})
    except DocumentInvalide as erreur:
        print(f"  Document invalide    : {erreur}")

    try:
        creer_station(
            db,
            {
                "_id": "FRDEMO PGEO",
                "nom": "Coordonnées fausses",
                "operateur": "Demo",
                "localisation": {"type": "Point", "coordinates": [500, 48.8]},
            },
        )
    except DocumentInvalide as erreur:
        print(f"  GeoJSON invalide     : {erreur}")

    try:
        lire_station(db, "FRXXX PINEXISTANT")
    except StationIntrouvable as erreur:
        print(f"  Station introuvable  : {erreur}")


def demonstration_delete(db):
    titre("5. DELETE")

    station = supprimer_station(db, ID_DEMO)
    print(f"  Station supprimée : {station['_id']}")

    try:
        lire_station(db, ID_DEMO)
    except StationIntrouvable:
        print("  Vérification : la station n'est plus lisible.")


def main():
    client = None

    try:
        client, db = connexion()
        print(f"Connexion MongoDB OK - base : {db.name}")

        demonstration_create(db)
        demonstration_read(db)
        demonstration_update(db)
        demonstration_erreurs(db)
        demonstration_delete(db)

        print("\nDémonstration CRUD terminée.")

    except (ErreurCRUD, RuntimeError) as erreur:
        print(f"\nErreur : {erreur}")
        raise SystemExit(1)

    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
