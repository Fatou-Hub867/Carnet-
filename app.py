from flask import Flask, jsonify

def create_app():
    app = Flask(__name__)

    from routes.patients import patients_bp
    from routes.medecins import medecins_bp
    from routes.rendez_vous import rdv_bp
    from routes.consultations import consultations_bp

    app.register_blueprint(patients_bp, url_prefix="/api/patients")
    app.register_blueprint(medecins_bp, url_prefix="/api/medecins")
    app.register_blueprint(rdv_bp, url_prefix="/api/rendez_vous")
    app.register_blueprint(consultations_bp, url_prefix="/api/consultations")

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "message": "API cabinet medical en ligne"})

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
