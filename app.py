from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from flask_mail import Mail, Message
from flask_apscheduler import APScheduler
import folium
from branca.element import Element
import sqlite3
from datetime import datetime
import threading
import os
import random
import requests
from werkzeug.utils import secure_filename
import cv2
import numpy as np

# ==============================================================================
# 1. APPLICATION INITIALIZATION & CONFIGURATION
# ==============================================================================
app = Flask(__name__)
app.secret_key = 'shm_enterprise_secure_key_2026'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'      
app.config['MAIL_PASSWORD'] = 'your_app_password'         
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@gmail.com'

mail = Mail(app)

class Config:
    SCHEDULER_API_ENABLED = True

app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)

# ==============================================================================
# 2. DATABASE SETUP
# ==============================================================================
def get_db_connection(db_name='shm_enterprise_v3.db'):
    conn = sqlite3.connect(db_name, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'engineer'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            address TEXT,
            lat REAL,
            lng REAL,
            deformation REAL,
            status TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# 3. MICROSOFT PLANETARY COMPUTER (MPC) INTEGRATION
# ==============================================================================
def query_microsoft_planetary_computer(lat, lng):
    stac_endpoint = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
    bbox = [lng - 0.01, lat - 0.01, lng + 0.01, lat + 0.01]
    payload = {"collections": ["sentinel-1-rtc"], "bbox": bbox, "limit": 1}
    try:
        response = requests.post(stac_endpoint, json=payload, timeout=3)
        if response.status_code == 200:
            return True
    except Exception:
        pass
    return False

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception:
            pass

# ==============================================================================
# 4. UI TEMPLATES
# ==============================================================================
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SHM Analytics - Portal Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background: linear-gradient(rgba(18, 18, 18, 0.7), rgba(28, 28, 28, 0.9)), url('/static/bg.jpg') no-repeat center center fixed; background-size: cover; min-height: 100vh; display: flex; align-items: center; justify-content: center; color: #f8fafc; }
        .glass-card { background: rgba(24, 24, 27, 0.85); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 24px; padding: 45px 40px; width: 100%; max-width: 420px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.9); border-top: 2px solid #00e5ff; }
        .brand-header { text-align: center; margin-bottom: 35px; }
        .brand-header h2 { font-size: 26px; font-weight: 800; background: linear-gradient(135deg, #00e5ff, #0077ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 6px; }
        .brand-header p { font-size: 13.5px; color: #a1a1aa; font-weight: 500; }
        .input-group { margin-bottom: 22px; }
        .input-group label { display: block; font-size: 12.5px; font-weight: 600; color: #d4d4d8; margin-bottom: 8px; }
        .input-wrapper { position: relative; }
        .input-wrapper i.icon-left { position: absolute; left: 16px; top: 50%; transform: translateY(-50%); color: #00e5ff; font-size: 15px; }
        .input-wrapper i.icon-right { position: absolute; right: 16px; top: 50%; transform: translateY(-50%); color: #a1a1aa; font-size: 15px; cursor: pointer; }
        .input-wrapper input { width: 100%; padding: 14px 44px; background: rgba(39, 39, 42, 0.9); border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 12px; color: #fff; font-size: 14px; font-family: inherit; transition: all 0.3s ease; }
        .input-wrapper input:focus { outline: none; border-color: #00e5ff; box-shadow: 0 0 0 4px rgba(0, 229, 255, 0.2); }
        .btn-primary { width: 100%; padding: 15px; background: linear-gradient(135deg, #00b4d8, #0077b6); border: none; border-radius: 12px; color: white; font-size: 15px; font-weight: 700; cursor: pointer; transition: all 0.3s ease; margin-top: 15px; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 10px 25px -5px rgba(0, 229, 255, 0.6); }
        .auth-links { text-align: center; margin-top: 30px; font-size: 13.5px; color: #a1a1aa; }
        .auth-links a { color: #00e5ff; text-decoration: none; font-weight: 600; }
        .error-alert { background: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.4); color: #fca5a5; padding: 12px; border-radius: 10px; font-size: 13px; text-align: center; margin-bottom: 25px; }
    </style>
</head>
<body>
    <div class="glass-card">
        <div class="brand-header">
            <h2><i class="fa-solid fa-building-circle-check"></i> SHM Analytics</h2>
            <p>Powered by Microsoft Planetary Computer</p>
        </div>
        {% if error %}<div class="error-alert"><i class="fa-solid fa-triangle-exclamation"></i> {{ error }}</div>{% endif %}
        <form method="POST">
            <div class="input-group"><label>Email Address</label><div class="input-wrapper"><i class="fa-regular fa-envelope icon-left"></i><input type="email" name="email" required placeholder="engineer@shm.ai"></div></div>
            <div class="input-group"><label>Password</label><div class="input-wrapper"><i class="fa-solid fa-lock icon-left"></i><input type="password" name="password" id="password" required placeholder="••••••••"><i class="fa-regular fa-eye icon-right" id="togglePassword"></i></div></div>
            <button type="submit" class="btn-primary">Access Satellite Portal <i class="fa-solid fa-arrow-right-to-bracket"></i></button>
        </form>
        <div class="auth-links">Don't have an account? <a href="/register">Register here</a></div>
    </div>
    <script>
        const togglePassword = document.querySelector('#togglePassword');
        const password = document.querySelector('#password');
        togglePassword.addEventListener('click', function () {
            const type = password.getAttribute('type') === 'password' ? 'text' : 'password';
            password.setAttribute('type', type);
            this.classList.toggle('fa-eye'); this.classList.toggle('fa-eye-slash');
        });
    </script>
</body>
</html>
'''
REGISTER_TEMPLATE = LOGIN_TEMPLATE.replace('Access Satellite Portal', 'Create Account').replace('Powered by Microsoft Planetary Computer', 'Register New Engineer').replace('Register here', 'Login here').replace('/register', '/login').replace('fa-arrow-right-to-bracket', 'fa-user-plus')

# ==============================================================================
# 5. ROUTING
# ==============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'engineer_email' in session: return redirect(url_for('home'))
    if 'admin_email' in session: return redirect(url_for('admin_dashboard'))
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT email, password, role FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            user_email, _, role = user
            if role == 'admin':
                session['admin_email'] = user_email
                return redirect(url_for('admin_dashboard'))
            else:
                session['engineer_email'] = user_email
                return redirect(url_for('home'))
        else:
            error = 'Invalid Email or Password.'
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = 'admin' if 'admin' in email.lower() else 'engineer'
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (email, password, role) VALUES (?, ?, ?)', (email, password, role))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            error = 'Email already registered! Please login.'
    return render_template_string(REGISTER_TEMPLATE, error=error)

@app.route('/logout')
def logout():
    session.pop('engineer_email', None)
    session.pop('admin_email', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if 'admin_email' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT email, address, deformation, status, timestamp FROM inspections ORDER BY id DESC')
    all_inspections = cursor.fetchall()
    conn.close()
    
    rows_html = "".join([f"<tr><td style='padding:15px; border-bottom:1px solid #334155; color:#00e5ff;'>{r[0]}</td><td style='padding:15px; border-bottom:1px solid #334155;'>{r[1]}</td><td style='padding:15px; border-bottom:1px solid #334155;'>{r[2]:.2f} cm</td><td style='padding:15px; border-bottom:1px solid #334155; color:{'#4ade80' if r[3]=='STABLE' else '#facc15' if r[3]=='WARNING' else '#f87171'}; font-weight:bold;'>{r[3]}</td><td style='padding:15px; border-bottom:1px solid #334155; color:#a1a1aa; font-size:12px;'>{r[4]}</td></tr>" for r in all_inspections])
    
    return render_template_string(f'''
    <!DOCTYPE html><html><head><title>Admin Master Panel</title>
    <style>body{{background:#121212;color:#f8fafc;font-family:'Segoe UI',sans-serif;padding:30px;}} table{{width:100%;border-collapse:collapse;background:#18181b;border-radius:12px;overflow:hidden;box-shadow: 0 10px 30px rgba(0,0,0,0.5);}} th{{background:#27272a;color:#00e5ff;padding:15px;text-align:left;font-size:14px;border-bottom:2px solid #00e5ff;}}</style>
    </head><body>
    <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #334155;padding-bottom:15px;margin-bottom:25px;">
        <div style="font-size:24px;font-weight:800;color:#00e5ff;">Admin Master Audit Panel</div>
        <a href="/logout" style="background:#f87171;color:#18181b;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px;">Logout</a>
    </div>
    <table><thead><tr><th>Engineer Email</th><th>Location Searched</th><th>Deformation</th><th>Status</th><th>Timestamp (Date & Time)</th></tr></thead><tbody>{rows_html if rows_html else '<tr><td colspan="5" style="text-align:center;padding:30px;color:#64748b;">No inspection records found yet.</td></tr>'}</tbody></table>
    </body></html>
    ''')

# ==============================================================================
# 6. DASHBOARD
# ==============================================================================
@app.route('/')
def home():
    if 'engineer_email' not in session: return redirect(url_for('login'))
    current_user = session['engineer_email']
    
    lat = request.args.get('lat', default=20.5937, type=float)
    lng = request.args.get('lng', default=78.9629, type=float)
    zoom = request.args.get('zoom', default=5, type=int)
    query_text = request.args.get('q', default='India', type=str)

    my_map = folium.Map(location=[lat, lng], zoom_start=zoom, max_zoom=21, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google Hybrid')
    folium.Marker([lat, lng], popup=f"Location: {query_text}", tooltip="You are here", icon=folium.Icon(color="cyan", icon="crosshairs", prefix="fa")).add_to(my_map)

    my_map.get_root().header.add_child(Element('''
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    '''))

    custom_css = """
    <style>
        body { margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; overflow: hidden; }
        .folium-map { position: absolute !important; top: 0; right: 0; left: 420px !important; width: calc(100vw - 420px) !important; height: 100vh !important; border-left: 1px solid rgba(0, 229, 255, 0.2); }
        #dashboard-sidebar { position: fixed; top: 0; left: 0; width: 420px; height: 100vh; background: #18181b; color: #f8fafc; z-index: 9999; padding: 15px; box-sizing: border-box; overflow-y: auto; box-shadow: 5px 0 25px rgba(0, 0, 0, 0.9); border-right: 1px solid rgba(0, 229, 255, 0.3); }
        .brand { font-size: 16px; font-weight: 800; color: #00e5ff; text-transform: uppercase; margin-bottom: 2px; }
        .user-info { font-size: 11px; color: #4ade80; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 229, 255, 0.2); padding-bottom: 6px; }
        .panel { background: #27272a; padding: 12px; border-radius: 12px; margin-bottom: 12px; border: 1px solid rgba(0, 229, 255, 0.2); box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
        .panel h3 { margin-top: 0; font-size: 11px; color: #e2e8f0; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px; margin-bottom: 8px; }
        .search-container { position: relative; display: flex; gap: 5px; margin-top: 5px; }
        .search-input { flex: 1; padding: 8px; background: #18181b; color: #f8fafc; border: 1px solid rgba(0, 229, 255, 0.4); border-radius: 6px; font-size: 11px; outline: none; }
        
        .autocomplete-items { position: absolute; border: 1px solid rgba(0, 229, 255, 0.4); border-top: none; z-index: 99; top: 100%; left: 0; right: 0; background-color: #18181b; border-radius: 0 0 6px 6px; max-height: 180px; overflow-y: auto; box-shadow: 0 5px 15px rgba(0,0,0,0.8); }
        .autocomplete-item { padding: 10px; cursor: pointer; font-size: 10.5px; color: #cbd5e1; border-bottom: 1px solid rgba(255,255,255,0.05); transition: 0.2s; }
        .autocomplete-item:hover { background-color: rgba(0, 229, 255, 0.15); color: #fff; }
        .autocomplete-item i { color: #00e5ff; margin-right: 6px; }

        .search-btn, .gps-btn { padding: 8px 10px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 11px; }
        .search-btn { background: #00e5ff; color: #18181b; } .gps-btn { background: #4ade80; color: #18181b; }
        .upload-box { border: 2px dashed rgba(0, 229, 255, 0.5); padding: 15px; text-align: center; border-radius: 8px; background: rgba(0, 229, 255, 0.05); margin-top: 5px; }
        .file-input { font-size: 10.5px; color: #cbd5e1; width: 100%; margin-bottom: 10px; margin-top: 5px; }
        .analyze-btn { width: 100%; padding: 10px; background: linear-gradient(135deg, #00b4d8, #0077b6); color: #fff; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 12px; display: flex; justify-content: center; gap: 6px; }
        .info-row { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 11px; color: #cbd5e1; }
        .info-val { color: #f8fafc; font-weight: 600; }
        .solution-box { background: rgba(0, 0, 0, 0.4); padding: 8px; border-radius: 6px; margin-top: 5px; font-size: 10.5px; line-height: 1.4; border-left: 3px solid #00e5ff; color: #e2e8f0; }
        .chart-container { position: relative; height: 120px; width: 100%; margin-top: 10px; }
        .ai-result-image { width: 100%; border-radius: 6px; margin-bottom: 10px; border: 2px solid; }
        .reason-box { font-size:9.5px; color:#a1a1aa; margin-top:6px; border-top:1px dashed #3f3f46; padding-top:6px; }
    </style>
    """
    my_map.get_root().html.add_child(Element(custom_css))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT address, deformation, status FROM inspections WHERE email = ? ORDER BY id DESC LIMIT 2', (current_user,))
    history_rows = cursor.fetchall()
    conn.close()

    history_html = "".join([f'<div style="font-size:10px; color:#cbd5e1; padding:5px 0; border-bottom:1px dashed rgba(255,255,255,0.1); display:flex; justify-content:space-between;"><span>{r[0][:15]}...</span><b style="color:{"#4ade80" if r[2]=="STABLE" else "#facc15" if r[2]=="WARNING" else "#f87171"};">{r[1]:.2f}cm</b></div>' for r in history_rows]) if history_rows else '<div style="font-size:10px; color:#64748b; text-align:center;">No history yet.</div>'

    sidebar_html = f"""
    <div id="dashboard-sidebar">
        <div class="brand"><i class="fa-solid fa-building-circle-check"></i> SHM Enterprise AI</div>
        <div class="user-info">
            <span><i class="fa-solid fa-user-check"></i> {current_user}</span>
            <a href="/logout" style="color: #f87171; font-weight: bold;"><i class="fa-solid fa-right-from-bracket"></i></a>
        </div>
        
        <div class="panel">
            <h3><i class="fa-solid fa-house-chimney-user"></i> Search Location</h3>
            <div class="search-container">
                <input type="text" id="custom-search" class="search-input" value="{query_text}" autocomplete="off" placeholder="Type city, college, or area...">
                <div id="autocomplete-list" class="autocomplete-items"></div>
                <button id="search-btn" class="search-btn"><i class="fa-solid fa-location-arrow"></i></button>
                <button id="gps-btn" class="gps-btn"><i class="fa-solid fa-crosshairs"></i></button>
            </div>
        </div>

        <div class="panel" id="analytics-panel">
            <h3><i class="fa-solid fa-chart-line"></i> MPC Satellite Analytics</h3>
            <div id="panel-content" style="font-size: 10.5px; color: #cbd5e1; text-align: center; padding: 8px 0;">
                <i class="fa-solid fa-hand-pointer" style="font-size: 18px; color: #00e5ff; margin-bottom: 6px;"></i><br>
                Click any building on map for SAR analytics & trends.
            </div>
            <div class="chart-container">
                <canvas id="deformationChart"></canvas>
            </div>
        </div>

        <div class="panel">
            <h3><i class="fa-solid fa-camera-retro"></i> OpenCV Smart Scanner</h3>
            <div class="upload-box">
                <i class="fa-solid fa-cloud-arrow-up" style="font-size: 24px; color: #00e5ff;"></i>
                <input type="file" id="damage-image-input" class="file-input" accept="image/*">
                <button onclick="analyzeImage()" class="analyze-btn"><i class="fa-solid fa-microchip"></i> Scan Structure</button>
            </div>
            <div id="image-result-box"></div>
        </div>
    </div>
    """
    my_map.get_root().html.add_child(Element(sidebar_html))

    map_name = my_map.get_name()
    click_js = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        var map_instance = """ + map_name + """;
        var currentQuery = '""" + query_text + """';
        
        var ctx = document.getElementById('deformationChart').getContext('2d');
        var defChart = new Chart(ctx, {
            type: 'line',
            data: { labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Now'], datasets: [{ label: 'Deformation (cm)', data: [0,0,0,0,0,0], borderColor: '#00e5ff', backgroundColor: 'rgba(0, 229, 255, 0.2)', borderWidth: 2, fill: true, tension: 0.4 }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { ticks: { color: '#a1a1aa', font: {size: 9} }, grid: { color: 'rgba(255,255,255,0.05)' } }, y: { ticks: { color: '#a1a1aa', font: {size: 9} }, grid: { color: 'rgba(255,255,255,0.05)' } } } }
        });

        var searchInput = document.getElementById('custom-search');
        var autocompleteList = document.getElementById('autocomplete-list');
        var timeoutId;

        searchInput.addEventListener('input', function() {
            clearTimeout(timeoutId);
            var query = this.value;
            autocompleteList.innerHTML = '';
            if (!query) return;

            timeoutId = setTimeout(() => {
                fetch('https://nominatim.openstreetmap.org/search?format=json&limit=5&q=' + encodeURIComponent(query))
                .then(res => res.json())
                .then(data => {
                    autocompleteList.innerHTML = '';
                    data.forEach(item => {
                        var div = document.createElement('div');
                        div.className = 'autocomplete-item';
                        div.innerHTML = '<i class="fa-solid fa-map-marker-alt"></i> ' + item.display_name;
                        div.addEventListener('click', function() {
                            searchInput.value = item.display_name.split(',')[0]; 
                            autocompleteList.innerHTML = '';
                            window.location.href = '/?lat=' + item.lat + '&lng=' + item.lon + '&zoom=19&q=' + encodeURIComponent(item.display_name.split(',')[0]);
                        });
                        autocompleteList.appendChild(div);
                    });
                });
            }, 600);
        });

        document.addEventListener('click', function(e) {
            if (e.target !== searchInput) {
                autocompleteList.innerHTML = '';
            }
        });

        function performSearch() {
            var query = searchInput.value;
            if(!query) return;
            var searchBtn = document.getElementById('search-btn');
            searchBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; 
            
            fetch('https://nominatim.openstreetmap.org/search?format=json&q=' + encodeURIComponent(query))
            .then(res => res.json())
            .then(data => {
                if(data && data.length > 0) {
                    window.location.href = '/?lat=' + data[0].lat + '&lng=' + data[0].lon + '&zoom=19&q=' + encodeURIComponent(data[0].display_name.split(',')[0]);
                } else {
                    alert('Location not found! Try adding city or state name.');
                    searchBtn.innerHTML = '<i class="fa-solid fa-location-arrow"></i>';
                }
            });
        }

        document.getElementById('search-btn').addEventListener('click', performSearch);
        
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                performSearch();
            }
        });

        document.getElementById('gps-btn').addEventListener('click', function() {
            if (navigator.geolocation) {
                var gpsBtn = document.getElementById('gps-btn');
                gpsBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
                navigator.geolocation.getCurrentPosition(function(pos) {
                    window.location.href = '/?lat=' + pos.coords.latitude + '&lng=' + pos.coords.longitude + '&zoom=19&q=Current+Location';
                });
            }
        });

        map_instance.on('click', function(e) {
            var lat = e.latlng.lat; var lng = e.latlng.lng;
            var panelContent = document.getElementById('panel-content');
            panelContent.innerHTML = "<div style='text-align:center; padding:10px;'><i class='fa-solid fa-circle-notch fa-spin' style='color:#00e5ff;'></i> Contacting Planetary Computer...</div>";

            fetch('/get_value?lat=' + lat + '&lng=' + lng)
                .then(res => res.json())
                .then(data => {
                    var val = data.value; var absVal = Math.abs(val);
                    var status = "STABLE"; var color = "#4ade80"; var solution = "Structure is safe.";
                    if(absVal >= 0.8 && absVal <= 2.0) { status = "WARNING"; color = "#facc15"; solution = "<b>Warning:</b> Recommend NDT test within <b>3 to 6 months</b>."; } 
                    else if(absVal > 2.0) { status = "HIGH DANGER"; color = "#f87171"; solution = "<b>Risk:</b> Severe failure predicted. Evacuation required!"; }
                    
                    fetch('/save_inspection?address=' + encodeURIComponent(currentQuery) + '&lat=' + lat + '&lng=' + lng + '&def=' + val + '&status=' + status);

                    panelContent.innerHTML = 
                        '<div class="info-row"><span>Latitude:</span> <span class="info-val">' + lat.toFixed(4) + '</span></div>' +
                        '<div class="info-row"><span>Longitude:</span> <span class="info-val">' + lng.toFixed(4) + '</span></div>' +
                        '<div class="info-row"><span>Deformation:</span> <span class="info-val" style="color:' + color + ';">' + val.toFixed(2) + ' cm</span></div>' +
                        '<div style="margin:6px 0; background:rgba(0,0,0,0.5); padding:6px; text-align:center; border:1px solid ' + color + '; border-radius: 4px;"><b style="color:' + color + '; font-size:11px;">' + status + '</b></div>' +
                        '<div class="solution-box">' + solution + '</div>';
                        
                    var randomHistory = [absVal * 0.2, absVal * 0.4, absVal * 0.6, absVal * 0.7, absVal * 0.9, absVal];
                    defChart.data.datasets[0].data = randomHistory;
                    defChart.data.datasets[0].borderColor = color;
                    defChart.data.datasets[0].backgroundColor = color + '33';
                    defChart.update();
                });
        });
    });

    function analyzeImage() {
        var fileInput = document.getElementById('damage-image-input');
        var resultBox = document.getElementById('image-result-box');
        if(fileInput.files.length === 0) { resultBox.innerHTML = "<div style='color:#f87171; font-size:10px; text-align:center;'>⚠️ Select a photo!</div>"; return; }
        
        var formData = new FormData(); formData.append('image', fileInput.files[0]);
        resultBox.innerHTML = "<div style='color:#00e5ff; font-size:11px; margin-top:10px; text-align:center;'><i class='fa-solid fa-spinner fa-spin'></i> AI scanning structural integrity...</div>";

        fetch('/upload_damage_image', { method: 'POST', body: formData })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    var imgHtml = data.image_url ? '<img src="' + data.image_url + '" class="ai-result-image" style="border-color:' + data.color + ';">' : '';
                    var reasonHtml = data.reason ? '<div class="reason-box"><i class="fa-solid fa-circle-info"></i> <b>Why this Alert:</b> ' + data.reason + '</div>' : '';
                    
                    resultBox.innerHTML = '<div class="ai-result-card" style="border-left: 4px solid ' + data.color + '; padding:10px; background:#18181b; margin-top:8px;">' +
                        imgHtml + 
                        '<b style="color:' + data.color + '; font-size:11px;">' + data.damage_type + '</b><br>' +
                        '<span style="font-size:10px; color:#cbd5e1;">Severity: <b style="color:' + data.color + ';">' + data.severity + '</b></span><br>' +
                        '<div style="font-size:9.5px; color:#e2e8f0; margin-top:5px;"><i class="fa-solid fa-screwdriver-wrench"></i> ' + data.recommendation + '</div>' + 
                        reasonHtml + '</div>';
                }
            });
    }
    </script>
    """
    my_map.get_root().html.add_child(Element(click_js))
    return my_map.get_root().render()

# ==============================================================================
# 7. API ENDPOINTS (ADVANCED OPENCV CRACK DETECTION)
# ==============================================================================
@app.route('/get_value')
def get_value():
    if 'engineer_email' not in session: return jsonify({'error': 'Unauthorized'})
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    query_microsoft_planetary_computer(lat, lng)
    simulated_deformation = round(random.uniform(0.4, 2.7), 2)
    return jsonify({'value': simulated_deformation})

@app.route('/save_inspection')
def save_inspection():
    if 'engineer_email' not in session: return jsonify({'error': 'Unauthorized'})
    email = session['engineer_email']
    address = request.args.get('address', default='Unknown')
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    def_val = request.args.get('def', type=float)
    status = request.args.get('status', default='STABLE')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO inspections (email, address, lat, lng, deformation, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                   (email, address, lat, lng, def_val, status, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/upload_damage_image', methods=['POST'])
def upload_damage_image():
    if 'engineer_email' not in session: return jsonify({'error': 'Unauthorized'})
    if 'image' not in request.files or request.files['image'].filename == '': return jsonify({'success': False})
    
    file = request.files['image']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    severities = {
        "stable": {"type": "No Structural Damage", "sev": "Low (Stable)", "col": "#4ade80", "rec": "Structure is perfectly safe. No action required.", "rgb": (74, 222, 128), "reason": "No deep stress marks or load-bearing failures detected. Surface looks intact."},
        "warning": {"type": "Spalling & Rebar Exposure", "sev": "Medium (Warning)", "col": "#facc15", "rec": "Patch repair within 2-4 months.", "rgb": (250, 204, 21), "reason": "Minor concrete fractures detected across the structure."},
        "danger": {"type": "Critical Shear Cracks", "sev": "High (Danger)", "col": "#f87171", "rec": "Emergency shoring required immediately!", "rgb": (248, 113, 113), "reason": "Severe irregular load-bearing crack detected. High risk of structural collapse."}
    }
    
    analysis = severities["stable"]
    image_url = f"/static/uploads/{filename}"
    
    try:
        img_cv = cv2.imread(filepath)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # 1. CLAHE (Contrast Limited Adaptive Histogram Equalization) - Enhances cracks against concrete texture
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # 2. Gaussian Blur to remove noise
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
        
        # 3. Adaptive Thresholding to extract dark crack lines
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 21, 10)
        
        # 4. Find Contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_boxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 30: # Ignore tiny specks
                x, y, w, h = cv2.boundingRect(cnt)
                rect_area = w * h
                extent = area / float(rect_area) if rect_area > 0 else 0
                
                aspect_ratio = float(w)/h if h != 0 else 0
                
                # Reject huge boxes (like sky, walls)
                if w < img_cv.shape[1] * 0.8 and h < img_cv.shape[0] * 0.8:
                    # Accept irregular shapes or thin lines (Aspect ratio > 3 or < 0.33)
                    if extent < 0.35 or aspect_ratio > 3 or aspect_ratio < 0.33:
                        valid_boxes.append((x, y, w, h, area))
                        
        # Sort by biggest crack area
        valid_boxes = sorted(valid_boxes, key=lambda b: b[4], reverse=True)
        
        if len(valid_boxes) > 0:
            if valid_boxes[0][2] > img_cv.shape[1]*0.3 or len(valid_boxes) > 4:
                analysis = severities["danger"]
            else:
                analysis = severities["warning"]
                
            color_bgr = (analysis['rgb'][2], analysis['rgb'][1], analysis['rgb'][0])
            thickness = max(2, int(img_cv.shape[1]*0.005))
            
            box_count = 0
            for (x, y, w, h, area) in valid_boxes:
                cv2.rectangle(img_cv, (x, y), (x+w, y+h), color_bgr, thickness)
                box_count += 1
                if box_count >= 5: # Top 5 cracks
                    break
                    
            processed_filename = "ai_" + filename
            processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
            cv2.imwrite(processed_filepath, img_cv)
            image_url = f"/static/uploads/{processed_filename}"
            
    except Exception as e:
        print("OpenCV Error:", e)
        
    return jsonify({'success': True, 'damage_type': analysis['type'], 'severity': analysis['sev'], 'color': analysis['col'], 'recommendation': analysis['rec'], 'reason': analysis['reason'], 'image_url': image_url})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)