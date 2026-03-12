from flask import Blueprint, jsonify, request, current_app, render_template
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
    return render_template('dashboard.html')

@main_bp.route('/accidents-list', methods=['GET'])
def accidents_list():
    return render_template('accidents.html')

@main_bp.route('/hospitals-map', methods=['GET'])
def hospitals_map():
    return render_template('hospitals.html')

@main_bp.route('/management', methods=['GET'])
def management():
    return render_template('management.html')

# --- API Endpoints for Dashboard ---

@main_bp.route('/api/stats', methods=['GET'])
def get_stats():
    user_count = User.query.count()
    accident_count = Accident.query.count()
    hospital_count = Hospital.query.count()
    active_emergencies = Accident.query.filter_by(status='detected').count()
    
    return jsonify({
        "total_users": user_count,
        "total_accidents": accident_count,
        "total_hospitals": hospital_count,
        "active_emergencies": active_emergencies
    })

@main_bp.route('/api/hospitals', methods=['GET', 'POST'])
def handle_hospitals_list():
    if request.method == 'POST':
        data = request.get_json()
        new_h = Hospital(
            name=data['name'],
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            phone=data['phone']
        )
        db.session.add(new_h)
        db.session.commit()
        return jsonify({"message": "Hospital created", "id": new_h.id}), 201
        
    hospitals = Hospital.query.all()
    return jsonify([{
        "id": h.id,
        "name": h.name,
        "latitude": h.latitude,
        "longitude": h.longitude,
        "phone": h.phone
    } for h in hospitals])

@main_bp.route('/api/hospitals/<int:h_id>', methods=['PUT', 'DELETE'])
def handle_hospital(h_id):
    h = Hospital.query.get_or_404(h_id)
    if request.method == 'DELETE':
        db.session.delete(h)
        db.session.commit()
        return jsonify({"message": "Hospital deleted"})
        
    data = request.get_json()
    h.name = data.get('name', h.name)
    h.latitude = data.get('latitude', h.latitude)
    h.longitude = data.get('longitude', h.longitude)
    h.phone = data.get('phone', h.phone)
    db.session.commit()
    return jsonify({"message": "Hospital updated"})

@main_bp.route('/api/users', methods=['GET', 'POST'])
def handle_users_list():
    if request.method == 'POST':
        data = request.get_json()
        if User.query.filter_by(vehicle_id=data['vehicle_id']).first():
            return jsonify({"error": "Vehicle ID already exists"}), 400
        new_user = User(
            name=data['name'],
            vehicle_id=data['vehicle_id'],
            phone=data['phone'],
            family_phone=data['family_phone'],
            blood_group=data['blood_group']
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User created", "id": new_user.id}), 201
        
    users = User.query.all()
    return jsonify([{
        "id": u.id,
        "name": u.name,
        "vehicle_id": u.vehicle_id,
        "phone": u.phone,
        "family_phone": u.family_phone,
        "blood_group": u.blood_group
    } for u in users])

@main_bp.route('/api/users/<int:user_id>', methods=['PUT', 'DELETE'])
def handle_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'DELETE':
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted"})
        
    data = request.get_json()
    user.name = data.get('name', user.name)
    user.phone = data.get('phone', user.phone)
    user.family_phone = data.get('family_phone', user.family_phone)
    user.blood_group = data.get('blood_group', user.blood_group)
    db.session.commit()
    return jsonify({"message": "User updated"})

@main_bp.route('/api/accidents', methods=['GET'])
def get_accidents():
    accidents = db.session.query(Accident, User, Hospital).outerjoin(
        User, Accident.vehicle_id == User.vehicle_id
    ).outerjoin(
        Hospital, Accident.hospital_id == Hospital.id
    ).order_by(Accident.time.desc()).all()
    
    result = []
    for acc, user, hosp in accidents:
        result.append({
            "id": acc.id,
            "vehicle_id": acc.vehicle_id,
            "user_name": user.name if user else "Unknown",
            "latitude": acc.latitude,
            "longitude": acc.longitude,
            "time": acc.time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": acc.status,
            "hospital_name": hosp.name if hosp else "None"
        })
    return jsonify(result)


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
