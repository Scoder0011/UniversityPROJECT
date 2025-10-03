# auth.py
import os
from datetime import datetime, timedelta

# optional dotenv (won't crash if not installed on the server)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId

# Config (override via environment variables)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret")
DB_NAME = os.environ.get("MONGO_DBNAME", "file_combiner")

def register_auth_routes(app: Flask):
    """
    Call this from your app.py after creating the Flask app:
        register_auth_routes(app)
    """

    # JWT setup
    app.config.setdefault("JWT_SECRET_KEY", JWT_SECRET_KEY)
    jwt = JWTManager(app)

    # Mongo client (reuse)
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    users_coll = db["users"]
    history_coll = db["history"]

    # Ensure unique username index
    try:
        users_coll.create_index("username", unique=True)
    except Exception:
        # ignore index errors in environments with limited privileges
        app.logger.debug("Could not create unique index on users.username (maybe already exists).")

    # --- Register ---
    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json(force=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify(error="username+password required"), 400

        hashed = generate_password_hash(password)
        user_doc = {
            "username": username,
            "password_hash": hashed,
            "created_at": datetime.utcnow()
        }

        try:
            res = users_coll.insert_one(user_doc)
        except DuplicateKeyError:
            return jsonify(error="user exists"), 400
        except Exception as e:
            app.logger.exception("DB error during register")
            return jsonify(error="internal error"), 500

        return jsonify(message="registered", user_id=str(res.inserted_id)), 201

    # --- Login ---
    @app.route("/auth/login", methods=["POST"])
    def login():
        data = request.get_json(force=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify(error="username+password required"), 400

        user = users_coll.find_one({"username": username})
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            return jsonify(error="invalid credentials"), 401

        access_token = create_access_token(identity=str(user["_id"]), expires_delta=timedelta(days=7))
        return jsonify(token=access_token, user_id=str(user["_id"]))

    # --- Me (protected) ---
    @app.route("/auth/me", methods=["GET"])
    @jwt_required()
    def me():
        uid = get_jwt_identity()
        try:
            user = users_coll.find_one({"_id": ObjectId(uid)}, {"password_hash": 0})
        except Exception:
            return jsonify(error="invalid user id"), 400

        if not user:
            return jsonify(error="not found"), 404

        user["_id"] = str(user["_id"])
        return jsonify(user=user)

    # --- helper: record history (optional) ---
    def record_history(user_id, filenames, output):
        try:
            history_coll.insert_one({
                "user_id": user_id,
                "filenames": filenames,
                "output": output,
                "created_at": datetime.utcnow()
            })
        except Exception:
            app.logger.exception("Failed to record history")

    # expose helper on app object if you want to call from other modules:
    app.record_history = record_history

    # done
    app.logger.info("Auth routes registered (/auth/register, /auth/login, /auth/me)")
