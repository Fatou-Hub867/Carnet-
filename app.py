from flask import Flask, jsonify

def create_app():
    app = Flask(__name__)

    from routes.patients import patients_bp
    app.register_blueprint(patients_bp, url_prefix="/api/patients")

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "message": "API cabinet medical en ligne"})

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
