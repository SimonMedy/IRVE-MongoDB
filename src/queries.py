"""Pipelines d'agrégation et recherches géospatiales sur la base IRVE.

Chaque fonction `pipeline_*` renvoie le pipeline sous forme de liste, sans
l'exécuter. Cela permet de l'afficher dans le notebook ou la soutenance, de le
réutiliser dans `explain()` pour mesurer un index, et de le tester sans
connexion. Les fonctions `*_resultat` exécutent le pipeline et renvoient une
liste de documents.
"""

from pymongo.errors import PyMongoError

from src.config import COLLECTION_STATIONS, COLLECTION_STATUTS


class ErreurRequete(Exception):
    """Échec de l'exécution d'une agrégation ou d'une recherche."""


def _executer(collection, pipeline):
    try:
        return list(collection.aggregate(pipeline))
    except PyMongoError as erreur:
        raise ErreurRequete(f"Échec de l'agrégation : {erreur}") from erreur


# --------------------------------------------------------------------------
# Agrégation 1 — Offre de recharge par département
# --------------------------------------------------------------------------


def pipeline_offre_par_departement(limite=15):
    """Nombre de PDC, de stations et puissance moyenne par département.

    Question métier : quels territoires sont les mieux équipés, et la
    puissance y est-elle comparable ?

    `$unwind` est nécessaire parce que les PDC sont embarqués dans un tableau :
    tant qu'ils y sont, on ne peut ni les compter ni moyenner leur puissance
    individuellement. C'est le coût direct de notre choix d'embarquement.

    Le `$match` initial écarte les stations sans département : le code INSEE
    est absent d'une partie de la source, et un groupe `null` fausserait le
    classement.
    """
    return [
        {"$match": {"departement": {"$ne": None}}},
        {
            "$group": {
                "_id": "$departement",
                "nb_stations": {"$sum": 1},
                "nb_pdc": {"$sum": "$nbre_pdc"},
            }
        },
        {"$sort": {"nb_pdc": -1}},
        {"$limit": limite},
        {
            "$project": {
                "_id": 0,
                "departement": "$_id",
                "nb_stations": 1,
                "nb_pdc": 1,
            }
        },
    ]


def pipeline_puissance_par_departement(limite=15):
    """Puissance moyenne par département, calculée PDC par PDC.

    Variante de l'agrégation précédente qui descend au niveau du PDC avec
    `$unwind`, seule façon d'obtenir une moyenne de puissance non pondérée
    par station.
    """
    return [
        {"$match": {"departement": {"$ne": None}}},
        {"$unwind": "$points_recharge"},
        {"$match": {"points_recharge.puissance_kw": {"$gt": 0}}},
        {
            "$group": {
                "_id": "$departement",
                "nb_pdc": {"$sum": 1},
                "puissance_moyenne": {"$avg": "$points_recharge.puissance_kw"},
                "puissance_max": {"$max": "$points_recharge.puissance_kw"},
            }
        },
        {"$sort": {"nb_pdc": -1}},
        {"$limit": limite},
        {
            "$project": {
                "_id": 0,
                "departement": "$_id",
                "nb_pdc": 1,
                "puissance_moyenne": {"$round": ["$puissance_moyenne", 1]},
                "puissance_max": 1,
            }
        },
    ]


# --------------------------------------------------------------------------
# Agrégation 2 — Comparaison des opérateurs
# --------------------------------------------------------------------------


def pipeline_top_operateurs(limite=10):
    """Classement des opérateurs par nombre de PDC, avec profil de puissance.

    Question métier : qui sont les principaux opérateurs, et déploient-ils la
    même qualité de service ? Un opérateur peut être premier en volume tout en
    proposant surtout de la recharge lente.

    `$unwind` est là encore requis pour compter les PDC un à un. Le
    `$group` calcule au passage la part de recharge rapide, ce qui distingue
    un réseau de bornes 22 kW d'un réseau de bornes 150 kW et plus.
    """
    return [
        {"$match": {"operateur": {"$ne": None}}},
        {"$unwind": "$points_recharge"},
        {
            "$group": {
                "_id": "$operateur",
                "nb_pdc": {"$sum": 1},
                "puissance_moyenne": {"$avg": "$points_recharge.puissance_kw"},
                "nb_rapide": {
                    "$sum": {
                        "$cond": [
                            {"$gte": ["$points_recharge.puissance_kw", 50]},
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        {"$sort": {"nb_pdc": -1}},
        {"$limit": limite},
        {
            "$project": {
                "_id": 0,
                "operateur": "$_id",
                "nb_pdc": 1,
                "puissance_moyenne": {"$round": ["$puissance_moyenne", 1]},
                "part_rapide_pct": {
                    "$round": [
                        {
                            "$multiply": [
                                {"$divide": ["$nb_rapide", "$nb_pdc"]},
                                100,
                            ]
                        },
                        1,
                    ]
                },
            }
        },
    ]


# --------------------------------------------------------------------------
# Agrégation 3 — Évolution du déploiement dans le temps
# --------------------------------------------------------------------------


def pipeline_evolution_annuelle(annee_min=2010, annee_max=2026):
    """Nombre de stations et de PDC mis en service par année.

    Question métier : à quel rythme le réseau s'est-il déployé, et observe-t-on
    une accélération ?

    Pas de `$unwind` ici : on compte des stations, et chaque document est déjà
    une station. Les PDC sont obtenus en sommant le compteur `nbre_pdc`, ce qui
    évite de dérouler 165 000 sous-documents pour rien.

    Le filtre sur les années écarte les dates de mise en service aberrantes
    présentes dans la source (saisies erronées, années hors période plausible).
    """
    return [
        {"$match": {"date_mise_en_service": {"$type": "date"}}},
        {
            "$group": {
                "_id": {"$year": "$date_mise_en_service"},
                "nb_stations": {"$sum": 1},
                "nb_pdc": {"$sum": "$nbre_pdc"},
            }
        },
        {"$match": {"_id": {"$gte": annee_min, "$lte": annee_max}}},
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "annee": "$_id",
                "nb_stations": 1,
                "nb_pdc": 1,
            }
        },
    ]


# --------------------------------------------------------------------------
# Agrégation complémentaire — état du parc dans le snapshot dynamique
# --------------------------------------------------------------------------


def pipeline_etat_parc():
    """Répartition des PDC par état de fonctionnement dans le snapshot.

    S'appuie sur la collection `statuts_pdc`. Rappel de portée : le fichier
    dynamique est un instantané, ce résultat décrit donc l'état au moment du
    téléchargement, pas un état temps réel.
    """
    return [
        {
            "$group": {
                "_id": {"etat": "$etat", "occupation": "$occupation"},
                "nb_pdc": {"$sum": 1},
            }
        },
        {"$sort": {"nb_pdc": -1}},
        {
            "$project": {
                "_id": 0,
                "etat": "$_id.etat",
                "occupation": "$_id.occupation",
                "nb_pdc": 1,
            }
        },
    ]


# --------------------------------------------------------------------------
# Recherche géospatiale
# --------------------------------------------------------------------------


def stations_proches(db, longitude, latitude, rayon_metres=2000, limite=20,
                     puissance_min=None):
    """Stations situées à moins de `rayon_metres` d'une position.

    Utilise `$near`, qui trie les résultats du plus proche au plus éloigné et
    exige un index `2dsphere` sur `localisation`.

    `puissance_min` filtre sur les stations disposant d'au moins un PDC de
    cette puissance : le filtre porte sur un élément du tableau embarqué, donc
    il s'exprime naturellement sans `$unwind`.
    """
    filtre = {
        "localisation": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
                "$maxDistance": rayon_metres,
            }
        }
    }

    if puissance_min is not None:
        filtre["points_recharge.puissance_kw"] = {"$gte": puissance_min}

    try:
        curseur = db[COLLECTION_STATIONS].find(filtre).limit(limite)
        return list(curseur)
    except PyMongoError as erreur:
        raise ErreurRequete(f"Échec de la recherche géospatiale : {erreur}") from erreur


def pipeline_stations_proches_avec_distance(longitude, latitude,
                                            rayon_metres=2000, limite=20):
    """Variante en agrégation qui renvoie la distance calculée.

    `$geoNear` doit être le premier étage du pipeline et fournit `distance_m`,
    ce que `$near` ne permet pas. C'est la forme utilisée par l'interface pour
    afficher la distance à l'utilisateur.
    """
    return [
        {
            "$geoNear": {
                "near": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                },
                "distanceField": "distance_m",
                "maxDistance": rayon_metres,
                "spherical": True,
            }
        },
        {"$limit": limite},
        {
            "$project": {
                "_id": 1,
                "nom": 1,
                "operateur": 1,
                "adresse": 1,
                "nbre_pdc": 1,
                "localisation": 1,
                "points_recharge": 1,
                "distance_m": {"$round": ["$distance_m", 0]},
            }
        },
    ]


# --------------------------------------------------------------------------
# Exécution
# --------------------------------------------------------------------------


def offre_par_departement(db, limite=15):
    return _executer(db[COLLECTION_STATIONS], pipeline_offre_par_departement(limite))


def puissance_par_departement(db, limite=15):
    return _executer(db[COLLECTION_STATIONS], pipeline_puissance_par_departement(limite))


def top_operateurs(db, limite=10):
    return _executer(db[COLLECTION_STATIONS], pipeline_top_operateurs(limite))


def evolution_annuelle(db, annee_min=2010, annee_max=2026):
    return _executer(
        db[COLLECTION_STATIONS], pipeline_evolution_annuelle(annee_min, annee_max)
    )


def etat_parc(db):
    return _executer(db[COLLECTION_STATUTS], pipeline_etat_parc())
