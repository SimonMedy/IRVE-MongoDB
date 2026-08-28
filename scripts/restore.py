import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import DB_NAME, MONGODB_URI, verifier_configuration


BACKUPS_DIR = ROOT_DIR / "backups"
RESTORE_DB_NAME = os.environ.get("RESTORE_DB_NAME", "irve_restore_demo")


def verifier_mongorestore():
    if shutil.which("mongorestore") is None:
        raise RuntimeError(
            "mongorestore est introuvable. Installez MongoDB Database Tools "
            "et vérifiez que mongorestore est disponible dans le PATH."
        )


def derniere_sauvegarde():
    if not BACKUPS_DIR.exists():
        raise RuntimeError("Aucune sauvegarde trouvée dans le dossier backups/.")

    dossiers = sorted(
        [chemin for chemin in BACKUPS_DIR.iterdir() if chemin.is_dir()],
        reverse=True,
    )

    if not dossiers:
        raise RuntimeError("Aucune sauvegarde trouvée dans le dossier backups/.")

    return dossiers[0]


def main():
    try:
        verifier_configuration()
        verifier_mongorestore()

        sauvegarde = derniere_sauvegarde()
        source = sauvegarde / DB_NAME

        if not source.exists():
            raise RuntimeError(
                f"Le dossier attendu est introuvable dans la sauvegarde : {source}"
            )

        commande = [
            "mongorestore",
            "--uri",
            MONGODB_URI,
            "--drop",
            "--nsFrom",
            f"{DB_NAME}.*",
            "--nsTo",
            f"{RESTORE_DB_NAME}.*",
            "--dir",
            str(sauvegarde),
        ]

        print(f"Sauvegarde utilisée : {sauvegarde.name}")
        print(f"Restauration vers la base de démonstration '{RESTORE_DB_NAME}'...")
        subprocess.run(commande, check=True)

        print("Restauration terminée avec succès.")
        print(f"Base restaurée : {RESTORE_DB_NAME}")

    except (RuntimeError, OSError, subprocess.CalledProcessError) as erreur:
        print(f"Erreur : {erreur}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
