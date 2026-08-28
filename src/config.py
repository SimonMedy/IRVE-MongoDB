import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env.local", override=True)

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DB_NAME", "irve")
COLLECTION_STATIONS = os.environ.get("COLLECTION_STATIONS", "stations")
COLLECTION_STATUTS = os.environ.get("COLLECTION_STATUTS", "statuts_pdc")


def verifier_configuration():
    """Vérifie que la variable obligatoire est présente."""
    if not MONGODB_URI:
        raise RuntimeError(
            "MONGODB_URI est absente. Copiez .env.example vers .env.local "
            "et renseignez votre URI MongoDB Atlas."
        )
