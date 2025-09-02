from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret_key_for_demo"

##Postgres接続
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:postgres@localhost:5432/comm_site"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "User"
    user_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)  
    password_hash = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    school_id = db.Column(db.Integer, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.department_id"), nullable=True)
    role = db.Column(db.String(20), nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    year = db.Column(db.Integer, nullable=True)
    
    department = db.relationship("Department", backref="users")

class Department(db.Model):
    __tablename__ = "department"
    department_id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, nullable=False)
    department_name = db.Column(db.String(100), nullable=False)

class School(db.Model):
    __tablename__ = "school"
    school_id = db.Column(db.Integer, primary_key=True)
    school_name = db.Column(db.String(100), nullable=False)

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        student_id = request.form["username"]   
        password = request.form["password"]

        user = User.query.filter_by(student_id=student_id).first()
        if user and user.password_hash == password:  
            session["student_id"] = user.student_id
            session["role"] = user.role
            session["name"] = user.name

            user.last_login = datetime.now()
            db.session.commit()

            if user.role == "student":
                return redirect(url_for("home"))
            elif user.role == "admin":
                return redirect(url_for("admin_dashboard"))

        return render_template("login.html", error="ユーザー名またはパスワードが違います")

    return render_template("login.html")


@app.route("/home")
def home():
    if "role" in session and session["role"] == "student":
        return render_template("home.html", user=session["name"])
    return redirect(url_for("login"))

@app.route("/admin")
def admin_dashboard():
    if "role" in session and session["role"] == "admin":
        return render_template("admin_dashboard.html", user=session["name"])
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/user_management/select", methods=["GET", "POST"])
def user_management_select():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))


    schools = School.query.all()

    if request.method == "POST":
        school_id = request.form.get("school_id")
        department_id = request.form.get("department_id")
        year = request.form.get("year")

        return redirect(url_for("user_management", 
                                school_id=school_id, 
                                department_id=department_id, 
                                year=year))
    return render_template("user_management_select.html", schools=schools)


@app.route("/user_management")
def user_management():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    school_id = request.args.get("school_id", type=int)
    department_id = request.args.get("department_id", type=int)
    year = request.args.get("year", type=int)

    query = User.query.filter(User.role == "student")

    if school_id and school_id != -1:   # -1 = 吉田学園グループ全体
        query = query.filter_by(school_id=school_id)
    if department_id and department_id != -1:  # -1 = 全校
        query = query.filter_by(department_id=department_id)
    if year and year != -1:  # -1 = 全学年
        query = query.filter_by(year=year)

    users = query.all()
    return render_template("user_management.html", users=users)

@app.route("/api/departments")
def api_departments():
    school_id = request.args.get("school_id", type=int)
    departments = Department.query.filter_by(school_id=school_id).all()
    return [{"department_id": d.department_id, "department_name": d.department_name} for d in departments]

if __name__ == "__main__":
    app.run(debug=True)