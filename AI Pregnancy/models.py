# models.py
import datetime
from werkzeug.security import generate_password_hash

class User:
    def __init__(self, collection):
        self.collection = collection

    def find_by_email(self, email):
        return self.collection.find_one({'email': email})

    def find_by_username(self, username):
        return self.collection.find_one({'username': username})

    def create_user(self, email, username, password):
        hashed_password = generate_password_hash(password)
        user_data = {
            'email': email,
            'username': username,
            'password': hashed_password,
            'created_at': datetime.utcnow()
        }
        print("Attempting to insert:", user_data)
        return self.collection.insert_one(user_data)

doctor_schema = {
    "name": "string",
    "specialization": "string",
    "location": "string",
    "availability": "boolean"
}

appointment_schema = {
    "doctorId": "ObjectId",
    "patientName": "string",
    "date": "string",
    "notes": "string"
}
