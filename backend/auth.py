# auth.py
import os
from datetime import datetime, timedelta
from typing import Any

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# Lazy import for extensions that might not be present at import-time in some environments
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from pymongo import MongoClient
from bson.objectid import ObjectId

# Load .env in development
load_dotenv()

# --- Configuration (read from env) ---
MONGO_URI = os.environ.get("MONGO_URI")  # required
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret")  # set in production

if not MONGO_URI:
    # don't crash the importer with obscure traceback — fail fast with helpful message
    raise RuntimeError("MONGO_URI environment variable is not set. Set it in Render/your host.")

# Create a single Mongo client for the process (safe to create at import-time)
client = MongoClient(MONGO_URI)
db = client.get_database("file_combiner")
users_coll = db.get_collection("users")
history_coll = db.get_collection("history")


def register_auth_routes(app: Flask) -> None:
    """
    Register auth routes on the given Flask app.
    Call from your app.py as:
        from auth import register_auth_routes
        register_auth_routes(app)
    """

    # Configure JWT for this Flask app
    app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
    jwt = JWTManager(app)

    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json(force=True) or {}
        username = (data.get("username") or data.get("email") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify({"error": "username+password required"}), 400

        # check for existing user (username unique)
        if users_coll.find_one({"username": username}):
            return jsonify({"error": "user exists"}), 400

        hashed = generate_password_hash(password)
        user_doc = {"username": username, "password_hash": hashed, "created_at": datetime.utcnow()}
        result = users_coll.insert_one(user_doc)
        return jsonify({"message": "registered", "user_id": str(result.inserted_id)}), 201

    @app.route("/auth/login", methods=["POST"])
    def login():
        data = request.get_json(force=True) or {}
        username = (data.get("username") or data.get("email") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify({"error": "username+password required"}), 400

        user = users_coll.find_one({"username": username})
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            return jsonify({"error": "invalid credentials"}), 401

        access_token = create_access_token(identity=str(user["_id"]), expires_delta=timedelta(days=7))
        return jsonify({"token": access_token, "user_id": str(user["_id"])}), 200

    @app.route("/auth/me", methods=["GET"])
    @jwt_required()
    def me():
        uid = get_jwt_identity()
        try:
            user = users_coll.find_one({"_id": ObjectId(uid)}, {"password_hash": 0})
        except Exception:
            return jsonify({"error": "invalid user id"}), 400

        if not user:
            return jsonify({"error": "not found"}), 404

        user["_id"] = str(user["_id"])
        return jsonify({"user": user}), 200

    # optional helper to record combine history (call from your combine route)
    def record_history(user_id: str, filenames: list[str], output: str) -> None:
        history_coll.insert_one({
            "user_id": user_id,
            "filenames": filenames,
            "output": output,
            "created_at": datetime.utcnow()
        })

    # attach helper to app for convenience (optional)
    app.record_history = record_history  # type: ignore[attr-defined]

    # nothing to return — routes registered in-place
