from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from models.db import get_connection

medecins_bp = Blueprint("medecins", __name__)

@medecins_bp.route("/", methods=["GET"])
def get_medecins():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_medecin, nom, prenom, specialite, email FROM medecins")
    medecins = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(medecins)

@medecins_bp.route("/inscription", methods=["POST"])
def inscription():
    data = request.get_json()
    nom = data.get("nom")
    prenom = data.get("prenom")
    specialite = data.get("specialite")
    email = data.get("email")
    mot_de_passe = data.get("mot_de_passe")

    if not all([nom, prenom, email, mot_de_passe]):
        return jsonify({"error": "Champs obligatoires manquants"}), 400

    hash_mdp = generate_password_hash(mot_de_passe)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO medecins (nom, prenom, specialite, email, mot_de_passe) VALUES (%s, %s, %s, %s, %s)",
            (nom, prenom, specialite, email, hash_mdp),
        )
        conn.commit()
        new_id = cursor.lastrowid
        return jsonify({"message": "Medecin cree", "id_medecin": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        cursor.close()
        conn.close()

@medecins_bp.route("/connexion", methods=["POST"])
def connexion():
    data = request.get_json()
    email = data.get("email")
    mot_de_passe = data.get("mot_de_passe")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM medecins WHERE email = %s", (email,))
    medecin = cursor.fetchone()
    cursor.close()
    conn.close()

    if medecin is None:
        return jsonify({"error": "Identifiants incorrects"}), 401

    if not check_password_hash(medecin["mot_de_passe"], mot_de_passe):
        return jsonify({"error": "Identifiants incorrects"}), 401

    return jsonify({
        "message": "Connexion reussie",
        "id_medecin": medecin["id_medecin"],
        "nom": medecin["nom"],
        "prenom": medecin["prenom"]
    })
