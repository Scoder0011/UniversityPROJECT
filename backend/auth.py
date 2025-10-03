import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from pymongo import MongoClient
from bson.objectid import ObjectId

load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret")

client = MongoClient(MONGO_URI)
db = client["file_combiner"]
users_coll = db["users"]
history_coll = db["history"]

def register_auth_routes(app: Flask):
    app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
    jwt = JWTManager(app)

    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json(force=True)
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return {"error": "username+password required"}, 400

        if users_coll.find_one({"username": username}):
            return {"error": "user exists"}, 400

        hashed = generate_password_hash(password)
        user_doc = {
            "username": username,
            "password_hash": hashed,
            "created_at": datetime.utcnow()
        }
        result = users_coll.insert_one(user_doc)
        return {"message": "registered", "user_id": str(result.inserted_id)}

    @app.route("/auth/login", methods=["POST"])
    def login():
        data = request.get_json(force=True)
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return {"error": "username+password required"}, 400

        user = users_coll.find_one({"username": username})
        if not user or not check_password_hash(user["password_hash"], password):
            return {"error": "invalid credentials"}, 401

        access_token = create_access_token(
            identity=str(user["_id"]),
            expires_delta=timedelta(days=7)
        )
        return {"token": access_token, "user_id": str(user["_id"])}

    @app.route("/auth/me", methods=["GET"])
    @jwt_required()
    def me():
        uid = get_jwt_identity()
        user = users_coll.find_one({"_id": ObjectId(uid)}, {"password_hash": 0})
        if not user:
            return {"error": "not found"}, 404
        user["_id"] = str(user["_id"])
        return {"user": user}
