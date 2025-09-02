from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "secret_key_for_demo"

##Postgres接続
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:postgres@localhost:5432/comm_site"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# users = {
#     "0241101": {"password": "123", "role": "student"},
#     "0241102": {"password": "123", "role": "student"},
#     "admin": {"password": "admin", "role": "admin"}
# }

class User(db.Model):
    __tablename__ = "User"
    user_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)  
    password_hash = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    school_id = db.Column(db.Integer, nullable=False)
    department_id = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(20), nullable=False)


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

if __name__ == "__main__":
    app.run(debug=True)