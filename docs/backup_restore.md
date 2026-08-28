# Sauvegarde et restauration MongoDB

Le projet utilise les outils officiels `mongodump` et `mongorestore` via deux scripts Python simples et multiplateformes.

## Prérequis

Installer **MongoDB Database Tools** et vérifier que les commandes suivantes sont disponibles dans le terminal :

```bash
mongodump --version
mongorestore --version
```

Le fichier `.env.local` doit contenir la connexion Atlas habituelle. La variable suivante peut aussi être définie :

```env
RESTORE_DB_NAME=irve_restore_demo
```

La restauration est volontairement faite dans une base de démonstration distincte afin de ne pas écraser la base `irve` utilisée par le projet.

---

## Sauvegarde

Commande :

```bash
python scripts/backup.py
```

Le script crée un dossier horodaté dans `backups/`, par exemple :

```text
backups/20260828_113000/irve/
```

`backups/` est ignoré par Git car les dumps peuvent être volumineux et contiennent les données de la base.

---

## Restauration

Commande :

```bash
python scripts/restore.py
```

Le script :

1. sélectionne la sauvegarde locale la plus récente ;
2. lit les collections de la base sauvegardée `irve` ;
3. les restaure dans `irve_restore_demo` ;
4. utilise `--drop` uniquement sur les collections de cette base de démonstration pour rendre le test reproductible.

La base principale `irve` n'est donc pas supprimée ou écrasée par le script de démonstration.

Après restauration, la vérification peut être faite dans Atlas en comparant le nombre de documents des collections restaurées avec les collections d'origine.

---

## Pourquoi cette méthode ?

`mongodump` et `mongorestore` sont les outils d'administration demandés dans le sujet. Les scripts Python servent uniquement à rendre les commandes reproductibles sur Windows, macOS et Linux sans dépendre d'un script PowerShell.
