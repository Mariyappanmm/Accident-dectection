from app import db
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    vehicle_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    family_phone = db.Column(db.String(20), nullable=False)
    blood_group = db.Column(db.String(10), nullable=False)

    def __repr__(self):
        return f'<User {self.name} - {self.vehicle_id}>'

class Hospital(db.Model):
    __tablename__ = 'hospitals'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    phone = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return f'<Hospital {self.name}>'

class Accident(db.Model):
    __tablename__ = 'accidents'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Assuming vehicle_id references the users table
    vehicle_id = db.Column(db.String(50), db.ForeignKey('users.vehicle_id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    time = db.Column(db.DateTime, default=datetime.utcnow)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=True)
    status = db.Column(db.String(50), default='detected')

    def __repr__(self):
        return f'<Accident {self.id} for Vehicle {self.vehicle_id}>'
