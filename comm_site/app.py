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
    school_id = db.Column(db.Integer, db.ForeignKey("School.school_id"), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("Department.department_id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    # Postモデルとのリレーションシップを定義
    posts = db.relationship("Post", backref="author", lazy=True)
    # SchoolとDepartmentとのリレーションシップを定義
    school = db.relationship("School", backref="users", lazy=True)
    department = db.relationship("Department", backref="users", lazy=True)


class Post(db.Model):
    __tablename__ = "Post"
    post_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scope = db.Column(db.String(50), nullable=False)

class School(db.Model):
    __tablename__ = "School"
    school_id = db.Column(db.Integer, primary_key=True)
    school_name = db.Column(db.String(100), nullable=False)
    departments = db.relationship("Department", backref="school", lazy=True)

class Department(db.Model):
    __tablename__ = "Department"
    department_id = db.Column(db.Integer, primary_key=True)
    department_name = db.Column(db.String(100), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("School.school_id"), nullable=False)

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
            school_info = School.query.filter_by(school_id=user.school_id).first()
            department_info = Department.query.filter_by(department_id=user.department_id).first()
            
            session["user_id"] = user.user_id 
            session["student_id"] = user.student_id
            session["role"] = user.role
            session["name"] = user.name
            session["school_name"] = school_info.school_name if school_info else "不明"
            session["department_name"] = department_info.department_name if department_info else "不明"
            session["year"] = user.year 
            
            # student_idの1桁目を校舎識別子としてセッションに保存
            session["school_identifier"] = student_id[0]

            if user.role == "student":
                return redirect(url_for("home"))
            elif user.role == "admin":
                return redirect(url_for("admin_dashboard"))

        return render_template("login.html", error="ユーザー名またはパスワードが違います")
    return render_template("login.html")

# 既存の/homeルートは削除または変更
# ユーザーをデフォルトの掲示板にリダイレクトするダミールート
@app.route("/home")
def home():
    return redirect(url_for("school_wide_board"))

@app.route("/home/school_wide")
def school_wide_board():
    if "role" in session and session["role"] == "student":
        # 公開範囲が'school_wide'の投稿をすべて取得
        posts = Post.query.filter_by(scope="school_wide").order_by(Post.created_at.desc()).all()
        return render_template("home.html", user=session["name"], posts=posts, board_title="校舎間掲示板")
    return redirect(url_for("login"))

@app.route("/home/school_specific")
def school_specific_board():
    if "role" in session and session["role"] == "student":
        school_identifier = session.get("school_identifier")
        # 投稿者のstudent_idがログインユーザーの校舎識別子と一致する投稿を取得
        # Joinを使用してPostとUserテーブルを結合し、Userのstudent_idをフィルタリング
        posts = db.session.query(Post).join(User).filter(
            Post.scope == "school_specific",
            User.student_id.like(school_identifier + "%")
        ).order_by(Post.created_at.desc()).all()
        return render_template("home.html", user=session["name"], posts=posts, board_title="校舎別掲示板")
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
    with app.app_context():
        db.create_all()
    app.run(debug=True)