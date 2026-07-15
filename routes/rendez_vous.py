from flask import Blueprint, jsonify, request
from models.db import get_connection

rdv_bp = Blueprint("rendez_vous", __name__)

@rdv_bp.route("/", methods=["GET"])
def get_rendez_vous():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rendez_vous")
    rdvs = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rdvs)

@rdv_bp.route("/<int:id_rdv>", methods=["GET"])
def get_rendez_vous_by_id(id_rdv):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rendez_vous WHERE id_rdv = %s", (id_rdv,))
    rdv = cursor.fetchone()
    cursor.close()
    conn.close()
    if rdv is None:
        return jsonify({"error": "Rendez-vous non trouve"}), 404
    return jsonify(rdv)

@rdv_bp.route("/", methods=["POST"])
def create_rendez_vous():
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO rendez_vous (id_patient, id_medecin, date_heure, motif, statut) VALUES (%s, %s, %s, %s, %s)",
        (
            data.get("id_patient"),
            data.get("id_medecin"),
            data.get("date_heure"),
            data.get("motif"),
            data.get("statut", "en_attente"),
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"message": "Rendez-vous cree", "id_rdv": new_id}), 201

@rdv_bp.route("/<int:id_rdv>", methods=["PUT"])
def update_rendez_vous(id_rdv):
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE rendez_vous SET date_heure = %s, motif = %s, statut = %s WHERE id_rdv = %s",
        (data.get("date_heure"), data.get("motif"), data.get("statut"), id_rdv),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Rendez-vous mis a jour"})

@rdv_bp.route("/<int:id_rdv>", methods=["DELETE"])
def delete_rendez_vous(id_rdv):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rendez_vous WHERE id_rdv = %s", (id_rdv,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Rendez-vous supprime"})
