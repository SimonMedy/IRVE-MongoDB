"""Interface Streamlit d'interrogation de la base IRVE.

Permet de rechercher des stations de recharge autour d'une position, avec
filtres de rayon, de puissance et de type de prise, puis d'afficher les
résultats sur une carte. Un second onglet expose les agrégations métier.

Lancement :

    streamlit run app/app.py
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from src.config import COLLECTION_STATIONS
from src.crud import ErreurCRUD, StationIntrouvable, lire_station
from src.database import connexion
from src.queries import (
    ErreurRequete,
    evolution_annuelle,
    offre_par_departement,
    pipeline_stations_proches_avec_distance,
    top_operateurs,
)


VILLES = {
    "Paris — Châtelet": (2.3470, 48.8583),
    "Lyon — Bellecour": (4.8320, 45.7578),
    "Marseille — Vieux-Port": (5.3698, 43.2951),
    "Bordeaux — Quinconces": (-0.5750, 44.8450),
    "Lille — Grand Place": (3.0635, 50.6370),
    "Toulouse — Capitole": (1.4442, 43.6045),
    "Nantes — Commerce": (-1.5540, 47.2130),
    "Strasbourg — Kléber": (7.7455, 48.5830),
}

PRISES = {
    "Type 2": "type2",
    "Combo CCS": "combo_ccs",
    "CHAdeMO": "chademo",
    "E/F (domestique)": "ef",
}


st.set_page_config(page_title="IRVE — Recherche de bornes", page_icon="🔌",
                   layout="wide")


@st.cache_resource
def obtenir_base():
    """Ouvre une connexion unique, réutilisée entre les interactions."""
    _, db = connexion()
    return db


@st.cache_data(ttl=300)
def chercher_stations(lon, lat, rayon, limite, puissance_min, prise):
    """Recherche géospatiale, avec filtres appliqués côté MongoDB."""
    db = obtenir_base()
    pipeline = pipeline_stations_proches_avec_distance(lon, lat, rayon, limite)

    conditions = {}
    if puissance_min > 0:
        conditions["points_recharge.puissance_kw"] = {"$gte": puissance_min}
    if prise:
        conditions[f"points_recharge.prises.{PRISES[prise]}"] = True

    # $geoNear doit rester le premier etage : les filtres sont donc places
    # dans sa cle "query", ou ils profitent de l'index 2dsphere.
    if conditions:
        pipeline[0]["$geoNear"]["query"] = conditions

    return list(db[COLLECTION_STATIONS].aggregate(pipeline))


@st.cache_data(ttl=300)
def charger_agregation(nom):
    db = obtenir_base()
    if nom == "departements":
        return offre_par_departement(db, limite=20)
    if nom == "operateurs":
        return top_operateurs(db, limite=10)
    return evolution_annuelle(db)


def resume_prises(station):
    """Liste lisible des types de prises disponibles sur la station."""
    presentes = set()
    for pdc in station.get("points_recharge", []):
        for libelle, champ in PRISES.items():
            if (pdc.get("prises") or {}).get(champ):
                presentes.add(libelle)
    return ", ".join(sorted(presentes)) or "—"


def puissance_max(station):
    valeurs = [
        p.get("puissance_kw")
        for p in station.get("points_recharge", [])
        if p.get("puissance_kw")
    ]
    return max(valeurs) if valeurs else None


# --------------------------------------------------------------------------
# En-tête
# --------------------------------------------------------------------------

st.title("🔌 Bornes de recharge en France")
st.caption(
    "Interrogation de la base IRVE sur MongoDB Atlas — "
    "collections `stations` et `statuts_pdc`."
)

try:
    base = obtenir_base()
except RuntimeError as erreur:
    st.error(f"Configuration manquante : {erreur}")
    st.stop()
except Exception as erreur:  # noqa: BLE001 - on affiche l'erreur de connexion
    st.error(f"Connexion à MongoDB impossible : {erreur}")
    st.info("Vérifiez `.env.local` et l'autorisation de votre IP sur Atlas.")
    st.stop()


onglet_carte, onglet_analyse, onglet_fiche = st.tabs(
    ["Recherche par proximité", "Analyses", "Fiche station"]
)


# --------------------------------------------------------------------------
# Onglet 1 — recherche géospatiale
# --------------------------------------------------------------------------

with onglet_carte:
    with st.sidebar:
        st.header("Critères de recherche")

        ville = st.selectbox("Point de départ", list(VILLES) + ["Coordonnées libres"])

        if ville == "Coordonnées libres":
            longitude = st.number_input("Longitude", value=2.3470, format="%.4f")
            latitude = st.number_input("Latitude", value=48.8583, format="%.4f")
        else:
            longitude, latitude = VILLES[ville]
            st.caption(f"Position : {longitude:.4f}, {latitude:.4f}")

        rayon_km = st.slider("Rayon de recherche (km)", 0.5, 30.0, 2.0, 0.5)
        puissance = st.select_slider(
            "Puissance minimale (kW)",
            options=[0, 7, 22, 50, 100, 150, 300],
            value=0,
        )
        prise = st.selectbox("Type de prise", ["Peu importe"] + list(PRISES))
        limite = st.slider("Nombre de résultats", 5, 200, 50, 5)

    try:
        resultats = chercher_stations(
            longitude,
            latitude,
            int(rayon_km * 1000),
            limite,
            puissance,
            None if prise == "Peu importe" else prise,
        )
    except ErreurRequete as erreur:
        st.error(str(erreur))
        st.info(
            "Si l'erreur mentionne un index, créez l'index géospatial avec "
            "`python scripts/create_indexes.py`."
        )
        resultats = []

    if not resultats:
        st.warning(
            f"Aucune station dans un rayon de {rayon_km:g} km avec ces critères. "
            "Élargissez le rayon ou abaissez la puissance minimale."
        )
    else:
        total_pdc = sum(s.get("nbre_pdc") or 0 for s in resultats)
        puissances = [p for p in (puissance_max(s) for s in resultats) if p]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Stations trouvées", len(resultats))
        c2.metric("Points de recharge", f"{total_pdc:,}".replace(",", " "))
        c3.metric("Station la plus proche", f"{resultats[0]['distance_m']:.0f} m")
        c4.metric(
            "Puissance max",
            f"{max(puissances):.0f} kW" if puissances else "—",
        )

        tableau = pd.DataFrame(
            [
                {
                    "Station": s.get("nom"),
                    "Opérateur": s.get("operateur"),
                    "Distance (m)": int(s.get("distance_m", 0)),
                    "PDC": s.get("nbre_pdc"),
                    "Puissance max (kW)": puissance_max(s),
                    "Prises": resume_prises(s),
                    "Adresse": s.get("adresse"),
                }
                for s in resultats
            ]
        )

        carte, liste = st.columns([3, 2])

        with carte:
            points = pd.DataFrame(
                [
                    {
                        "lon": s["localisation"]["coordinates"][0],
                        "lat": s["localisation"]["coordinates"][1],
                    }
                    for s in resultats
                    if s.get("localisation")
                ]
            )
            if not points.empty:
                st.map(points, latitude="lat", longitude="lon", size=40)
            else:
                st.info("Aucune coordonnée exploitable parmi ces résultats.")

        with liste:
            st.dataframe(tableau, hide_index=True, use_container_width=True,
                         height=420)

        st.download_button(
            "Télécharger les résultats (CSV)",
            tableau.to_csv(index=False).encode("utf-8"),
            file_name="stations_irve.csv",
            mime="text/csv",
        )


# --------------------------------------------------------------------------
# Onglet 2 — agrégations
# --------------------------------------------------------------------------

with onglet_analyse:
    st.subheader("Agrégations sur l'ensemble de la base")

    choix = st.radio(
        "Analyse",
        ["Territoires", "Opérateurs", "Déploiement dans le temps"],
        horizontal=True,
    )

    try:
        if choix == "Territoires":
            donnees = pd.DataFrame(charger_agregation("departements"))
            st.caption(
                "Nombre de points de recharge par département. Le pipeline somme "
                "`nbre_pdc` sans `$unwind` : la question porte sur la station."
            )
            st.bar_chart(donnees.set_index("departement")["nb_pdc"])
            st.dataframe(donnees, hide_index=True, use_container_width=True)

        elif choix == "Opérateurs":
            donnees = pd.DataFrame(charger_agregation("operateurs"))
            st.caption(
                "Classement par nombre de PDC, avec la part de recharge rapide "
                "(≥ 50 kW) : un gros réseau n'est pas forcément un réseau rapide."
            )
            st.bar_chart(donnees.set_index("operateur")["nb_pdc"])
            st.dataframe(donnees, hide_index=True, use_container_width=True)

        else:
            donnees = pd.DataFrame(charger_agregation("evolution"))
            st.caption(
                "Stations et PDC mis en service par année, d'après le champ "
                "déclaratif `date_mise_en_service`. La dernière année est tronquée."
            )
            st.line_chart(donnees.set_index("annee")[["nb_stations", "nb_pdc"]])
            st.dataframe(donnees, hide_index=True, use_container_width=True)

    except ErreurRequete as erreur:
        st.error(str(erreur))


# --------------------------------------------------------------------------
# Onglet 3 — lecture unitaire (CRUD)
# --------------------------------------------------------------------------

with onglet_fiche:
    st.subheader("Consulter une station par son identifiant")
    st.caption(
        "Utilise directement `lire_station` du module CRUD "
        "(`src/crud.py`) : l'interface et les scripts partagent le même code."
    )

    identifiant = st.text_input(
        "Identifiant d'itinérance",
        placeholder="FRXXXP12345",
    )

    if identifiant:
        try:
            station = lire_station(base, identifiant.strip())
        except StationIntrouvable as erreur:
            st.warning(str(erreur))
        except ErreurCRUD as erreur:
            st.error(str(erreur))
        else:
            g, d = st.columns(2)
            g.metric("Points de recharge", station.get("nbre_pdc", 0))
            pmax = puissance_max(station)
            d.metric("Puissance max", f"{pmax:.0f} kW" if pmax else "—")

            st.write(f"**{station.get('nom')}** — {station.get('operateur')}")
            st.write(station.get("adresse") or "Adresse non renseignée")

            if station.get("points_recharge"):
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "id_pdc": p.get("id_pdc"),
                                "puissance_kw": p.get("puissance_kw"),
                                **{
                                    libelle: bool((p.get("prises") or {}).get(champ))
                                    for libelle, champ in PRISES.items()
                                },
                            }
                            for p in station["points_recharge"]
                        ]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )

            if not station.get("localisation"):
                st.info(
                    "Cette station n'a pas de coordonnées validées par la source : "
                    "elle est absente de l'index géospatial et n'apparaît dans "
                    "aucune recherche de proximité."
                )
