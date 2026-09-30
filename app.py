from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///acc_consultation.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    course = db.Column(db.String(100))
    specialization = db.Column(db.String(120))
    active = db.Column(db.Boolean, default=True)

class Consultation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    expert_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    concern = db.Column(db.Text, nullable=False)
    schedule = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(30), default="Pending")
    response = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("You are not authorized to access that page.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.active and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            session["name"] = user.name
            session["role"] = user.role
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    role = session["role"]
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    if role == "expert":
        return redirect(url_for("expert_dashboard"))
    return redirect(url_for("student_dashboard"))

@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    users = User.query.order_by(User.name).all()
    consultations = Consultation.query.order_by(Consultation.created_at.desc()).all()
    experts = User.query.filter_by(role="expert").all()
    students = User.query.filter_by(role="student").all()
    return render_template("admin.html", users=users, consultations=consultations,
                           experts=experts, students=students)

@app.route("/admin/toggle/<int:user_id>")
@role_required("admin")
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != "admin":
        user.active = not user.active
        db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/expert")
@role_required("expert")
def expert_dashboard():
    consultations = Consultation.query.filter_by(expert_id=session["user_id"]).order_by(
        Consultation.created_at.desc()).all()
    students = {}
    for c in consultations:
        students[c.student_id] = User.query.get(c.student_id)
    return render_template("expert.html", consultations=consultations, students=students)

@app.route("/expert/update/<int:consultation_id>", methods=["POST"])
@role_required("expert")
def update_consultation(consultation_id):
    c = Consultation.query.get_or_404(consultation_id)
    if c.expert_id != session["user_id"]:
        flash("Unauthorized consultation.", "error")
        return redirect(url_for("expert_dashboard"))
    c.status = request.form.get("status", "Pending")
    c.response = request.form.get("response", "").strip()
    db.session.commit()
    flash("Consultation updated successfully.", "success")
    return redirect(url_for("expert_dashboard"))

@app.route("/student")
@role_required("student")
def student_dashboard():
    consultations = Consultation.query.filter_by(student_id=session["user_id"]).order_by(
        Consultation.created_at.desc()).all()
    experts = User.query.filter_by(role="expert", active=True).all()
    return render_template("student.html", consultations=consultations, experts=experts)

@app.route("/student/book", methods=["POST"])
@role_required("student")
def book():
    expert_id = request.form.get("expert_id", type=int)
    schedule = request.form.get("schedule", "").strip()
    concern = request.form.get("concern", "").strip()
    expert = User.query.filter_by(id=expert_id, role="expert", active=True).first()
    if not expert or not schedule or not concern:
        flash("Please complete all consultation fields.", "error")
        return redirect(url_for("student_dashboard"))
    c = Consultation(student_id=session["user_id"], expert_id=expert.id,
                     concern=concern, schedule=schedule)
    db.session.add(c)
    db.session.commit()
    flash("Consultation request submitted.", "success")
    return redirect(url_for("student_dashboard"))

def seed():
    db.create_all()
    if not User.query.filter_by(email="admin@acc.edu.ph").first():
        db.session.add(User(name="ACC Super Admin", email="admin@acc.edu.ph",
            password=generate_password_hash("Admin@12345"), role="admin"))
    if not User.query.filter_by(email="expert@acc.edu.ph").first():
        db.session.add(User(name="Dr. Maria Santos", email="expert@acc.edu.ph",
            password=generate_password_hash("Expert@12345"), role="expert",
            specialization="General Medicine"))
    if not User.query.filter_by(email="student@acc.edu.ph").first():
        db.session.add(User(name="Juan Dela Cruz", email="student@acc.edu.ph",
            password=generate_password_hash("Student@12345"), role="student",
            course="BS Information Technology"))
    db.session.commit()

if __name__ == "__main__":
    with app.app_context():
        seed()
    app.run(debug=True)
