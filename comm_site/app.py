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

@app.route("/admin/users")
def user_management():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    users = User.query.all()
    return render_template("user_management.html", users=users)

if __name__ == "__main__":
    app.run(debug=True)