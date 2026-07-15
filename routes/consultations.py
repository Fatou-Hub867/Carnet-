from flask import Blueprint, jsonify, request
from models.db import get_connection

consultations_bp = Blueprint("consultations", __name__)

@consultations_bp.route("/", methods=["GET"])
def get_consultations():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM consultations")
    consultations = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(consultations)

@consultations_bp.route("/<int:id_consultation>", methods=["GET"])
def get_consultation_by_id(id_consultation):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM consultations WHERE id_consultation = %s", (id_consultation,))
    consultation = cursor.fetchone()
    cursor.close()
    conn.close()
    if consultation is None:
        return jsonify({"error": "Consultation non trouvee"}), 404
    return jsonify(consultation)

@consultations_bp.route("/patient/<int:id_patient>", methods=["GET"])
def get_consultations_by_patient(id_patient):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM consultations WHERE id_patient = %s ORDER BY date_consultation DESC", (id_patient,))
    consultations = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(consultations)

@consultations_bp.route("/", methods=["POST"])
def create_consultation():
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO consultations (id_rdv, id_patient, id_medecin, symptomes, diagnostic, notes) VALUES (%s, %s, %s, %s, %s, %s)",
        (
            data.get("id_rdv"),
            data.get("id_patient"),
            data.get("id_medecin"),
            data.get("symptomes"),
            data.get("diagnostic"),
            data.get("notes"),
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"message": "Consultation creee", "id_consultation": new_id}), 201

@consultations_bp.route("/<int:id_consultation>", methods=["PUT"])
def update_consultation(id_consultation):
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE consultations SET symptomes = %s, diagnostic = %s, notes = %s WHERE id_consultation = %s",
        (data.get("symptomes"), data.get("diagnostic"), data.get("notes"), id_consultation),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Consultation mise a jour"})
