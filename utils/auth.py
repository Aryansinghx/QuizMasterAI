import firebase_admin
from firebase_admin import credentials, firestore
from datetime import date
import hashlib
import os

def init_db():
    if not firebase_admin._apps:
        # You'll download this JSON from Firebase Console > Project Settings
        cred = credentials.Certificate("firebase-sdk.json")
        firebase_admin.initialize_app(cred)
    return firestore.client()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()


def register_user(db, email: str, password: str):
    user_ref = db.collection('users').document(email)
    if user_ref.get().exists:
        return False, "A user with that email already exists."

    salt = os.urandom(16).hex()
    password_hash = _hash_password(password, salt)
    new_user = {
        "xp": 0,
        "level": 1,
        "streak": 1,
        "last_played": str(date.today()),
        "password_hash": password_hash,
        "password_salt": salt
    }
    user_ref.set(new_user)
    return True, "Registration successful."


def authenticate_user(db, email: str, password: str):
    user_ref = db.collection('users').document(email)
    doc = user_ref.get()
    if not doc.exists:
        return False, "No account found for that email."

    user_data = doc.to_dict()
    salt = user_data.get('password_salt')
    stored_hash = user_data.get('password_hash')
    if not salt or not stored_hash:
        return False, "This account does not support password login."

    if _hash_password(password, salt) == stored_hash:
        return True, "Login successful."

    return False, "Incorrect password."


def get_user_stats(db, email):
    user_ref = db.collection('users').document(email)
    doc = user_ref.get()
    if doc.exists:
        return doc.to_dict()
    else:
        # Initial stats for new users [cite: 18, 50]
        new_user = {
            "xp": 0,
            "level": 1,
            "streak": 1,
            "last_played": str(date.today())
        }
        user_ref.set(new_user)
        return new_user
    

def update_user_xp(db,email,earned_xp):
    user_ref = db.collection('users').document(email)
    user_ref.update({"xp": firestore.Increment(earned_xp)})