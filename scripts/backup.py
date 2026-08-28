import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import DB_NAME, MONGODB_URI, verifier_configuration


BACKUPS_DIR = ROOT_DIR / "backups"


def verifier_mongodump():
    if shutil.which("mongodump") is None:
        raise RuntimeError(
            "mongodump est introuvable. Installez MongoDB Database Tools "
            "et vérifiez que mongodump est disponible dans le PATH."
        )


def main():
    try:
        verifier_configuration()
        verifier_mongodump()

        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        dossier = BACKUPS_DIR / horodatage
        dossier.mkdir(parents=True, exist_ok=False)

        commande = [
            "mongodump",
            "--uri",
            MONGODB_URI,
            "--db",
            DB_NAME,
            "--out",
            str(dossier),
        ]

        print(f"Sauvegarde de la base '{DB_NAME}'...")
        subprocess.run(commande, check=True)

        print("Sauvegarde terminée.")
        print(f"Dossier : {dossier}")

    except (RuntimeError, OSError, subprocess.CalledProcessError) as erreur:
        print(f"Erreur : {erreur}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
