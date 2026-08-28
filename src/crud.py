"""Opérations CRUD sur la collection `stations`.

Chaque fonction reçoit la base en paramètre pour rester réutilisable et
testable : c'est l'appelant qui ouvre la connexion via `src.database.connexion`.

Les erreurs sont converties en exceptions métier explicites afin que
l'appelant (script, notebook ou interface Streamlit) puisse les traiter
sans dépendre des exceptions internes de PyMongo.
"""

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.config import COLLECTION_STATIONS


class ErreurCRUD(Exception):
    """Erreur générique lors d'une opération CRUD."""


class StationIntrouvable(ErreurCRUD):
    """La station demandée n'existe pas dans la collection."""


class StationDejaExistante(ErreurCRUD):
    """Une station possède déjà cet identifiant."""


class DocumentInvalide(ErreurCRUD):
    """Le document fourni ne respecte pas le schéma minimal attendu."""


CHAMPS_OBLIGATOIRES = ("_id", "nom", "operateur")


def _collection(db):
    return db[COLLECTION_STATIONS]


def valider_station(document):
    """Vérifie le schéma minimal d'une station avant écriture.

    On ne valide que le strict nécessaire : l'identifiant d'itinérance, le nom
    et l'opérateur, plus la cohérence du GeoJSON et du tableau de PDC quand ils
    sont présents. Le reste des champs IRVE est optionnel par nature, beaucoup
    étant absents dans la source.
    """
    if not isinstance(document, dict):
        raise DocumentInvalide("Le document doit être un dictionnaire.")

    manquants = [
        champ
        for champ in CHAMPS_OBLIGATOIRES
        if document.get(champ) in (None, "")
    ]
    if manquants:
        raise DocumentInvalide(
            "Champs obligatoires manquants : " + ", ".join(manquants)
        )

    points = document.get("points_recharge")
    if points is not None and not isinstance(points, list):
        raise DocumentInvalide("`points_recharge` doit être une liste.")

    localisation = document.get("localisation")
    if localisation is not None:
        _valider_localisation(localisation)

    return True


def _valider_localisation(localisation):
    """Contrôle qu'un GeoJSON Point est exploitable par un index 2dsphere."""
    if not isinstance(localisation, dict):
        raise DocumentInvalide("`localisation` doit être un objet GeoJSON.")

    if localisation.get("type") != "Point":
        raise DocumentInvalide("`localisation.type` doit valoir 'Point'.")

    coordonnees = localisation.get("coordinates")
    if not isinstance(coordonnees, (list, tuple)) or len(coordonnees) != 2:
        raise DocumentInvalide(
            "`localisation.coordinates` doit contenir [longitude, latitude]."
        )

    longitude, latitude = coordonnees
    if not all(isinstance(v, (int, float)) for v in (longitude, latitude)):
        raise DocumentInvalide("Les coordonnées doivent être numériques.")

    if not -180 <= longitude <= 180:
        raise DocumentInvalide(f"Longitude hors bornes : {longitude}")

    if not -90 <= latitude <= 90:
        raise DocumentInvalide(f"Latitude hors bornes : {latitude}")


# --------------------------------------------------------------------------
# CREATE
# --------------------------------------------------------------------------


def creer_station(db, document):
    """Insère une station et renvoie son identifiant.

    L'`_id` est l'identifiant d'itinérance de la station : une insertion en
    double est donc rejetée par MongoDB, ce qui protège la collection sans
    lecture préalable.
    """
    valider_station(document)

    try:
        resultat = _collection(db).insert_one(document)
    except DuplicateKeyError as erreur:
        raise StationDejaExistante(
            f"La station '{document['_id']}' existe déjà."
        ) from erreur
    except PyMongoError as erreur:
        raise ErreurCRUD(f"Échec de l'insertion : {erreur}") from erreur

    return resultat.inserted_id


# --------------------------------------------------------------------------
# READ
# --------------------------------------------------------------------------


def lire_station(db, id_station):
    """Renvoie une station par son identifiant d'itinérance."""
    try:
        station = _collection(db).find_one({"_id": id_station})
    except PyMongoError as erreur:
        raise ErreurCRUD(f"Échec de la lecture : {erreur}") from erreur

    if station is None:
        raise StationIntrouvable(f"Aucune station avec l'identifiant '{id_station}'.")

    return station


def lister_stations(db, filtre=None, projection=None, limite=20, tri=None):
    """Renvoie une liste de stations correspondant à un filtre.

    `limite=0` désactive la limite, conformément au comportement de PyMongo.
    """
    if limite < 0:
        raise DocumentInvalide("La limite doit être positive ou nulle.")

    try:
        curseur = _collection(db).find(filtre or {}, projection)
        if tri:
            curseur = curseur.sort(tri)
        if limite:
            curseur = curseur.limit(limite)
        return list(curseur)
    except PyMongoError as erreur:
        raise ErreurCRUD(f"Échec de la recherche : {erreur}") from erreur


def compter_stations(db, filtre=None):
    """Compte les stations correspondant à un filtre."""
    try:
        return _collection(db).count_documents(filtre or {})
    except PyMongoError as erreur:
        raise ErreurCRUD(f"Échec du comptage : {erreur}") from erreur


# --------------------------------------------------------------------------
# UPDATE
# --------------------------------------------------------------------------


def modifier_station(db, id_station, modifications):
    """Met à jour les champs fournis d'une station et renvoie le document à jour.

    Renvoie le document après modification pour éviter une seconde lecture
    côté appelant.
    """
    if not isinstance(modifications, dict) or not modifications:
        raise DocumentInvalide("Les modifications doivent être un dict non vide.")

    if "_id" in modifications:
        raise DocumentInvalide("L'identifiant `_id` n'est pas modifiable.")

    if "localisation" in modifications:
        _valider_localisation(modifications["localisation"])

    try:
        station = _collection(db).find_one_and_update(
            {"_id": id_station},
            {"$set": modifications},
            return_document=ReturnDocument.AFTER,
        )
    except PyMongoError as erreur:
        raise ErreurCRUD(f"Échec de la mise à jour : {erreur}") from erreur

    if station is None:
        raise StationIntrouvable(f"Aucune station avec l'identifiant '{id_station}'.")

    return station


def ajouter_point_recharge(db, id_station, point):
    """Ajoute un point de recharge au tableau embarqué et resynchronise `nbre_pdc`.

    Illustre concrètement le coût du choix d'embarquement : le compteur
    `nbre_pdc` étant dénormalisé dans le document station, toute écriture sur
    le tableau doit le maintenir cohérent.
    """
    if not isinstance(point, dict) or not point.get("id_pdc"):
        raise DocumentInvalide("Un point de recharge doit contenir `id_pdc`.")

    try:
        station = _collection(db).find_one_and_update(
            {"_id": id_station},
            {
                "$push": {"points_recharge": point},
                "$inc": {"nbre_pdc": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
    except PyMongoError as erreur:
        raise ErreurCRUD(f"Échec de l'ajout du PDC : {erreur}") from erreur

    if station is None:
        raise StationIntrouvable(f"Aucune station avec l'identifiant '{id_station}'.")

    return station


# --------------------------------------------------------------------------
# DELETE
# --------------------------------------------------------------------------


def supprimer_station(db, id_station):
    """Supprime une station et renvoie le document supprimé."""
    try:
        station = _collection(db).find_one_and_delete({"_id": id_station})
    except PyMongoError as erreur:
        raise ErreurCRUD(f"Échec de la suppression : {erreur}") from erreur

    if station is None:
        raise StationIntrouvable(f"Aucune station avec l'identifiant '{id_station}'.")

    return station
