from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret_key_for_demo"

# ====== 既存の設定 ======
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:postgres@localhost:5432/comm_site"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ====== 既存のモデル ======
class User(db.Model):
    __tablename__ = "User"
    user_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)  
    password_hash = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    school_id = db.Column(db.Integer, nullable=False)
    department_id = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(20), nullable=False)
    posts = db.relationship("Post", backref="author", lazy=True)

class Post(db.Model):
    __tablename__ = "Post"
    post_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scope = db.Column(db.String(50), nullable=False)

# ====== 追加: School モデル ======
class School(db.Model):
    __tablename__ = "school"   # pgAdmin のテーブルと一致させる
    school_id = db.Column(db.Integer, primary_key=True)
    school_name = db.Column(db.String(100), nullable=False)

# ====== 追加: Department モデル ======
class Department(db.Model):
    __tablename__ = "department"   # pgAdmin のテーブルと一致させる
    department_id = db.Column(db.Integer, primary_key=True)
    department_name = db.Column(db.String(100), nullable=False)

# ====== 既存ルート ======
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
            session["user_id"] = user.user_id
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
        posts = Post.query.filter_by(scope="home").order_by(Post.created_at.desc()).all()
        return render_template("home.html", user=session["name"], posts=posts)
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

# ====== 追加: アカウント作成用ルート ======
@app.route("/create_account", methods=["GET", "POST"])
def create_account():
    if request.method == "POST":
        student_id = request.form["student_id"]
        name = request.form["full_name"]
        password = request.form["password"]
        school_id = request.form["school"]
        department_id = request.form["department"]

        new_user = User(
            student_id=student_id,
            password_hash=password,   # 本番環境ではハッシュ化する
            name=name,
            school_id=school_id,
            department_id=department_id,
            role="student"
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))


    schools = School.query.all()
    departments = Department.query.all()
    return render_template("Create_Account.html", schools=schools, departments=departments)

# ====== 既存のエントリーポイント ======
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
