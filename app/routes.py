from flask import Blueprint, jsonify, request, current_app
from app import db
from sqlalchemy import text
from app.models import User, Hospital, Accident
from geopy.distance import geodesic
from datetime import datetime
import sys
import os

# Windows Path Limit Workaround: load local vendor folder first
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'vendor')))
from twilio.rest import Client

main_bp = Blueprint('main', __name__)

def normalize_phone(phone):
    if not phone:
        return phone
    phone = str(phone).strip()
    # Remove any existing + to avoid double prefixing
    if phone.startswith('+'):
        phone = phone[1:]
    # If it's a 10 digit number, assume it's Indian (+91)
    if len(phone) == 10 and phone.isdigit():
        return "+91" + phone
    return "+" + phone

@main_bp.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "Welcome to the Smart Helmet API hosted on Render/Railway!",
        "status": "success"
    })

@main_bp.route('/health', methods=['GET'])
def health_check():
    # Attempt a simple db query to check connectivity
    try:
        db.session.execute(text('SELECT 1'))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        
    return jsonify({
        "status": "healthy",
        "database": db_status
    })

@main_bp.route('/accident-alert', methods=['POST'])
def accident_alert():
    data = request.get_json()
    
    # Verify we received the expected data fields
    if not data or not all(k in data for k in ("vehicle_id", "latitude", "longitude")):
        return jsonify({"error": "Missing required fields (vehicle_id, latitude, longitude)"}), 400
        
    vehicle_id = data['vehicle_id']
    try:
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
    except ValueError:
        return jsonify({"error": "Latitude and longitude must be numbers"}), 400
    
    # 1. Retrieve the user associated with the vehicle_id
    user = User.query.filter_by(vehicle_id=vehicle_id).first()
    if not user:
        return jsonify({"error": f"Vehicle ID {vehicle_id} not registered in the system"}), 404
        
    # 2. Find the nearest hospital using Geopy (Haversine distance)
    hospitals = Hospital.query.all()
    nearest_hospital = None
    min_distance = float('inf')
    
    accident_coords = (latitude, longitude)
    
    for hospital in hospitals:
        hospital_coords = (hospital.latitude, hospital.longitude)
        distance = geodesic(accident_coords, hospital_coords).km
        if distance < min_distance:
            min_distance = distance
            nearest_hospital = hospital
            
    hospital_id = nearest_hospital.id if nearest_hospital else None
    
    # 3. Insert accident record into the database
    new_accident = Accident(
        vehicle_id=vehicle_id,
        latitude=latitude,
        longitude=longitude,
        time=datetime.utcnow(),
        hospital_id=hospital_id,
        status="detected"
    )
    
    db.session.add(new_accident)
    db.session.commit()
    
    # 4. Send SMS notifications via Twilio
    twilio_client = Client(
        current_app.config['TWILIO_ACCOUNT_SID'],
        current_app.config['TWILIO_AUTH_TOKEN']
    )
    twilio_from = current_app.config['TWILIO_FROM_NUMBER']
    
    # Compose message to Family
    family_msg = f"EMERGENCY: Accident detected for {user.name} (Vehicle ID: {vehicle_id}). Location: Lat {latitude}, Lng {longitude}. Blood Group: {user.blood_group}. "
    if nearest_hospital:
        family_msg += f"Nearest Hospital: {nearest_hospital.name} (Phone: {nearest_hospital.phone})."
        
    twilio_error_msg = None
    notifications_sent = False
    try:
        # Send SMS to family
        if twilio_from and user.family_phone:
            to_number = normalize_phone(user.family_phone)
            twilio_client.messages.create(
                body=family_msg,
                from_=twilio_from,
                to=to_number
            )
            
        # Send SMS to Hospital
        if twilio_from and nearest_hospital and nearest_hospital.phone:
            to_number = normalize_phone(nearest_hospital.phone)
            hospital_msg = f"EMERGENCY INCOMING: Accident detected {min_distance:.2f}km away. Victim: {user.name}, Blood Group: {user.blood_group}. Contact Family: {user.family_phone}."
            twilio_client.messages.create(
                body=hospital_msg,
                from_=twilio_from,
                to=to_number
            )
        notifications_sent = True
    except Exception as e:
        twilio_error_msg = str(e)
        print(f"Failed to send Twilio SMS: {twilio_error_msg}")
        
    return jsonify({
        "status": "success",
        "message": "Accident alert processed and notifications dispatched." if notifications_sent else "Accident alert processed, but notifications failed.",
        "data": {
            "accident_id": new_accident.id,
            "vehicle_id": vehicle_id,
            "nearest_hospital": nearest_hospital.name if nearest_hospital else None,
            "distance_km": round(min_distance, 2) if nearest_hospital else None,
            "family_notified": notifications_sent,
            "twilio_error": twilio_error_msg
        }
    }), 201
