from flask import Blueprint, jsonify, request
from models.db import get_connection

patients_bp = Blueprint("patients", __name__)

@patients_bp.route("/", methods=["GET"])
def get_patients():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM patients")
    patients = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(patients)

@patients_bp.route("/<int:id_patient>", methods=["GET"])
def get_patient(id_patient):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM patients WHERE id_patient = %s", (id_patient,))
    patient = cursor.fetchone()
    cursor.close()
    conn.close()
    if patient is None:
        return jsonify({"error": "Patient non trouve"}), 404
    return jsonify(patient)

@patients_bp.route("/", methods=["POST"])
def create_patient():
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO patients (nom, prenom, date_naissance, sexe, telephone, email, adresse) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            data.get("nom"),
            data.get("prenom"),
            data.get("date_naissance"),
            data.get("sexe"),
            data.get("telephone"),
            data.get("email"),
            data.get("adresse"),
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"message": "Patient cree", "id_patient": new_id}), 201
