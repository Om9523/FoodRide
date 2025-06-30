from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from flask_pymongo import PyMongo 
from bson.objectid import ObjectId
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json
import logging, os

# ------------------- Flask Setup -------------------
app = Flask(__name__)
app.secret_key = "supersecretkey"

# MongoDB connection (local)
app.config["MONGO_URI"] = "mongodb://localhost:27017/foodride"
mongo = PyMongo(app)

donations_col = mongo.db.donations
ngos_col = mongo.db.ngos
rider_col = mongo.db.rider

# ------------------- IP Logging Setup -------------------
LOG_FILE = "access.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def get_client_ip(req):
    """Get real visitor IP even behind proxy/CDN like Cloudflare"""
    ip = req.headers.get('CF-Connecting-IP') or \
         req.headers.get('X-Forwarded-For', '').split(',')[0].strip() or \
         req.remote_addr or 'Unknown'
    return ip

@app.before_request
def log_ip():
    ip = get_client_ip(request)
    logging.info(f"Visitor IP: {ip} | Path: {request.path}")

# ---------------------- Routes ----------------------

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/donate', methods=['GET', 'POST'])
def donate():
    if request.method == 'POST':
        data = {
            'donor_name': request.form['donor_name'],
            'food_type': request.form['food_type'],
            'quantity': int(request.form['quantity']),
            'pickup_location': request.form['pickup_location'],
            'status': 'Pending',
            'timestamp': datetime.now()
        }
        donations_col.insert_one(data)
        return render_template("thankyou.html")
    return render_template("donate.html")

# ---------------------- NGO Registration/Login ----------------------

@app.route('/ngo/register', methods=['GET', 'POST'])
def ngo_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        lat_str = request.form.get('lat', '').strip()
        lng_str = request.form.get('lng', '').strip()

        if not lat_str or not lng_str:
            return "Latitude and Longitude are required", 400

        try:
            lat = float(lat_str)
            lng = float(lng_str)
        except ValueError:
            return "Invalid coordinates format", 400

        ngo = {
            "name": name,
            "email": email,
            "password": password,
            "lat": lat,
            "lng": lng
        }
        mongo.db.ngos.insert_one(ngo)
        return redirect('/ngo/login')

    return render_template('ngo_register.html')

@app.route('/ngo/login', methods=['GET', 'POST'])
def ngo_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        ngo = ngos_col.find_one({'email': email})

        if ngo and check_password_hash(ngo['password'], password):
            session['ngo_id'] = str(ngo['_id'])
            session['ngo_name'] = ngo['name']
            return redirect(url_for('ngo_dashboard'))
        return "Invalid credentials"
    return render_template('ngo_login.html')

@app.route('/ngo/logout')
def ngo_logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/ngo/dashboard')
def ngo_dashboard():
    if 'ngo_id' not in session:
        return redirect('/ngo/login')

    ngo_id = session['ngo_id']
    ngo = mongo.db.ngos.find_one({'_id': ObjectId(ngo_id)})

    donations = list(mongo.db.donations.find({'status': 'Pending'}))

    donations_for_map = [{
        'lat': d.get('lat', 0),
        'lng': d.get('lng', 0)
    } for d in donations]

    return render_template(
        'ngo_dashboard.html',
        ngo_name=ngo['name'],
        ngo=ngo,
        donations=donations,
        donations_json=donations_for_map
    )

@app.route('/ngo/accept/<donation_id>')
def accept_donation(donation_id):
    if 'ngo_id' not in session:
        return redirect(url_for('ngo_login'))
    donations_col.update_one({'_id': ObjectId(donation_id)}, {'$set': {'status': 'Accepted by NGO'}})
    return redirect(url_for('ngo_dashboard'))

@app.route('/rider/register', methods=['GET', 'POST'])
def register_rider():
    if request.method == 'POST':
        data = {
            "name": request.form['name'],
            "email": request.form['email'],
            "phone": request.form['phone'],
            "vehicle_type": request.form['vehicle_type'],
            "vehicle_number": request.form['vehicle_number'],
            "location": request.form['location'],
            "password": generate_password_hash(request.form['password']),
        }
        rider_col.insert_one(data)
        return redirect('/rider/register')
    return render_template('rider_register.html')

# ---------------------- Run App ----------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
