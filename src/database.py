from pymongo import MongoClient

from src.config import DB_NAME, MONGODB_URI, verifier_configuration


def connexion():
    """Ouvre une connexion MongoDB Atlas et renvoie le client et la base."""
    verifier_configuration()

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")

    return client, client[DB_NAME]
