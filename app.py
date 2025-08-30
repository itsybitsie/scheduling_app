from flask import Flask, render_template, request, redirect, url_for, session
import json
import os
import calendar
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# -----------------------
# Flask App Setup
# -----------------------
app = Flask(__name__)

# -----------------------
# File Paths
# -----------------------
DATA_FILE = "jobs.json"
SETTINGS_FILE = "settings.json"

# -----------------------
# Jobs Persistence
# -----------------------
def load_jobs():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except json.JSONDecodeError:
            pass
    return []

def save_jobs(jobs):
    with open(DATA_FILE, "w") as f:
        json.dump(jobs, f, indent=4)

jobs = load_jobs()

# -----------------------
# Settings Persistence
# -----------------------
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"business_name": "My Business", "contact_email": ""}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

settings = load_settings()

# Authentication

app.secret_key = "supersecretkey" 

@app.route("/login", methods =["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == settings.get("login_username") and password == settings.get("login_password"):
            session["logged_in"] = True
            return redirect(url_for("schedule"))
        else:
            error = "Invalid Credentials"

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.before_request
def require_login():
    if request.endpoint not in ("login", "logout", "static") and not session.get("logged_in"):
        return redirect(url_for("login"))


@app.context_processor
def inject_settings():
    return dict(settings=settings)

# -----------------------
# Database Config (Clients)
# -----------------------
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'clients.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Client Model
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    notes = db.Column(db.Text)

    def __repr__(self):
        return f'<Client {self.name}>'

with app.app_context():
    db.create_all()

# -----------------------
# Routes
# -----------------------
@app.route('/')
def home():
    return redirect(url_for('schedule'))

@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    jobs = load_jobs()

    if request.method == "POST":
        customer = request.form.get("customer", "")
        description = request.form.get("description", "")
        date = request.form.get("date", "")
        time = request.form.get("time", "")

        if customer and date:
            job_id = len(jobs) + 1
            jobs.append({
                "id": job_id,
                "customer": customer,
                "description": description,
                "date": date,
                "time": time
            })
            save_jobs(jobs)

    now = datetime.now()
    year = request.args.get('year', default=now.year, type=int)
    month = request.args.get('month', default=now.month, type=int)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdayscalendar(year, month)

    jobs_by_date = {}
    for job in jobs:
        jobs_by_date.setdefault(job["date"], []).append(job)

    return render_template(
        "schedule.html",
        jobs=jobs,
        month_days=month_days,
        year=year,
        month=month,
        jobs_by_date=jobs_by_date,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year
    )

@app.route("/delete/<int:job_id>")
def delete_job(job_id):
    jobs = load_jobs()
    jobs = [job for job in jobs if job.get("id") != job_id]
    save_jobs(jobs)
    return redirect(url_for("schedule"))

@app.route("/edit/<int:job_id>", methods=["GET", "POST"])
def edit_job(job_id):
    jobs = load_jobs()
    job = next((job for job in jobs if job.get("id") == job_id), None)

    if not job:
        return redirect(url_for("schedule"))

    if request.method == "POST":
        job["customer"] = request.form.get("customer", "")
        job["description"] = request.form.get("description", "")
        job["date"] = request.form.get("date", "")
        job["time"] = request.form.get("time", "")
        save_jobs(jobs)
        return redirect(url_for("schedule"))

    return render_template("edit_job.html", job=job)

@app.route('/clients', methods=['GET', 'POST'])
def clients():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        address = request.form['address']
        notes = request.form['notes']

        new_client = Client(name=name, phone=phone, email=email, address=address, notes=notes)
        db.session.add(new_client)
        db.session.commit()

        return redirect(url_for('clients'))

    all_clients = Client.query.all()
    return render_template('clients.html', clients=all_clients)

@app.route('/edit_client/<int:id>', methods=['GET', 'POST'])
def edit_client(id):
    client = Client.query.get(id)
    if not client:
        return redirect(url_for('clients'))

    if request.method == 'POST':
        client.name = request.form['name']
        client.phone = request.form['phone']
        client.email = request.form['email']
        client.address = request.form['address']
        client.notes = request.form['notes']
        db.session.commit()
        return redirect(url_for('clients'))

    return render_template('edit_client.html', client=client, settings=settings)


@app.route('/delete_client/<int:id>', methods=['POST'])
def delete_client(id):
    client = Client.query.get(id)
    if client:
        db.session.delete(client)
        db.session.commit()
    return redirect(url_for('clients'))


@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    global settings
    if request.method == 'POST':
        settings['business_name'] = request.form.get('business_name', 'My Business')
        settings['contact_email'] = request.form.get('contact_email', '')
        settings['login_username'] = request.form.get('login_username', 'admin')
        settings['login_password'] = request.form.get('login_password', 'password')
        save_settings(settings)
        return redirect(url_for('settings_page'))

    return render_template('settings.html', settings=settings)

# -----------------------
# Run
# -----------------------
if __name__ == '__main__':
    app.run(debug=True)
