import os
import mysql.connector
from mysql.connector import Error

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "cabinet_medical"),
}

def get_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"[Erreur connexion DB] {e}")
        raise

def init_db():
    conn = get_connection()
    if conn.is_connected():
        print("Connexion a MySQL reussie.")
        conn.close()
