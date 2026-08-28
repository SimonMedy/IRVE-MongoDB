# Données IRVE (Base Nationale)

Les fichiers de données volumineux ne sont pas versionnés dans Git.

## Téléchargement des données officielles

### 1. Données statiques consolidées

- [Télécharger le CSV statique](https://www.data.gouv.fr/fr/datasets/r/eb76d20a-8501-400e-b336-d85724de5435)
- Placer le fichier dans `data/` sous le nom :

```text
consolidation_transport_irve_statique.csv
```

### 2. Données dynamiques

- [Page officielle des données IRVE](https://transport.data.gouv.fr/datasets/beta-bases-nationales-des-points-de-recharge-pour-vehicules-electriques-en-france-irve)
- Télécharger le CSV dynamique et le placer dans `data/`.

Le nom exact du fichier dynamique peut varier selon la date de téléchargement.
Le script `scripts/import_data.py` détecte automatiquement le premier fichier
CSV dont le nom contient `dynamique`.

> Le CSV dynamique téléchargé est un **snapshot à un instant donné**.
> Le fichier local ne se met pas à jour automatiquement.

## Import

Une fois les deux fichiers placés dans `data/` et `.env.local` configuré :

```bash
python scripts/import_data.py
```

Les CSV restent ignorés par Git.
