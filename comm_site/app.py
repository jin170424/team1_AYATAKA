from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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

    school_id = db.Column(db.Integer, db.ForeignKey("school.school_id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    posts = db.relationship("Post", backref="author", lazy=True)
    # SchoolとDepartmentとのリレーションシップを定義
    school = db.relationship("School", backref="users", lazy=True)

    department_id = db.Column(db.Integer, db.ForeignKey("department.department_id"), nullable=True)
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

class Post(db.Model):
    __tablename__ = "post"
    post_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scope = db.Column(db.String(50), nullable=False)

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        student_id = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(student_id=student_id).first()
        # stored password is hashed; verify using check_password_hash
        if user and check_password_hash(user.password_hash, password) or user and user.password_hash == password:
            school_info = School.query.filter_by(school_id=user.school_id).first()
            department_info = Department.query.filter_by(department_id=user.department_id).first()

            session["user_id"] = user.user_id
            session["student_id"] = user.student_id
            session["role"] = user.role
            session["name"] = user.name
            session["school_id"] = user.school_id
            session["school_name"] = school_info.school_name if school_info else "不明"
            session["department_name"] = department_info.department_name if department_info else "不明"
            session["year"] = user.year

            # student_idの1桁目を校舎識別子としてセッションに保存
            session["school_identifier"] = student_id[0]

            user.last_login = datetime.now()
            db.session.commit()

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
    return redirect(url_for("school_specific_board"))

@app.route("/home/school_wide")
def school_wide_board():
    if "role" in session and session["role"] == "student":
        # 公開範囲が'public'の投稿をすべて取得
        posts = Post.query.filter_by(scope="public").order_by(Post.created_at.desc()).all()
        return render_template("home.html", user=session["name"], posts=posts, board_title="校舎間掲示板")
    return redirect(url_for("login"))


@app.route("/home/school_specific")
def school_specific_board():
    if "role" in session and session["role"] == "student":
        user_school_id = session.get("school_id")
        if user_school_id is None:
            return redirect(url_for("login"))

        # スコープを'school' + school_idの形式で設定
        school_scope = f"school{user_school_id}"

        # 指定されたスコープの投稿を取得
        posts = Post.query.filter_by(scope=school_scope).order_by(Post.created_at.desc()).all()

        # 掲示板タイトル用にschool_nameを取得
        school_info = School.query.filter_by(school_id=user_school_id).first()
        board_title = f"{school_info.school_name} 掲示板" if school_info else "校舎別掲示板"

        return render_template("home.html", user=session["name"], posts=posts, board_title=board_title)
    return redirect(url_for("login"))


@app.route("/home/notice_board")
def notice_board():
    if "role" in session and session["role"] == "student":
        # 'notice0'から'notice8'までのスコープに合致する投稿を取得
        notice_scopes = [f'notice{i}' for i in range(9)]
        posts = Post.query.filter(Post.scope.in_(notice_scopes)).order_by(Post.created_at.desc()).all()
        return render_template("home.html", user=session["name"], posts=posts, board_title="通知用掲示板")
    return redirect(url_for("login"))


#プロフィール確認画面
@app.route("/profile")
def profile_view():
    # ユーザーがログインしているか確認
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    # セッション情報からユーザー情報を取得
    user = User.query.get(session["user_id"])
    
    if not user:
        return redirect(url_for("logout"))
        
    return render_template("profile.html", user=user)

#設定画面
@app.route("/settings")
def settings():
    # ユーザーがログインしているか確認
    if "user_id" not in session:
        return redirect(url_for("login"))
        
    # 必要に応じて設定ページ用のロジックを追加
    return render_template("settings.html")

@app.route("/settings/change_password", methods=["GET", "POST"])
def change_password():
    # ユーザーがログインしているか確認
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user:
        return redirect(url_for("logout"))

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # 現在のパスワードが正しいか検証
        if not check_password_hash(user.password_hash, current_password):
            flash("現在のパスワードが正しくありません。", "error")
            return redirect(url_for("change_password"))
            
        # 新しいパスワードと確認用パスワードが一致するか検証
        if new_password != confirm_password:
            flash("新しいパスワードが一致しません。", "error")
            return redirect(url_for("change_password"))

        # 新しいパスワードをハッシュ化して保存
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        # 成功メッセージ
        flash("パスワードが正常に変更されました。", "success")
        return redirect(url_for("settings"))

    # GETリクエストの場合、フォームを表示
    return render_template("change_password.html")

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
        name = request.form["name"]
        student_id = request.form["student_id"]
        school_id = request.form["school"]
        department_id = request.form["department"]
        password = request.form["password"]
        year = request.form["year"]
        
        hashed_password = generate_password_hash(password)

        new_user = User(
            name=name,
            student_id=student_id,
            school_id=school_id,
            department_id=department_id,
            password_hash=hashed_password,
            year=year,
            role="student"
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("user_management"))  

    
    schools = School.query.all()
    departments = Department.query.all()
    return render_template(
        "Create_Account.html",
        schools=schools,
        departments=departments
    )

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
    
    school_name = "吉田学園グループ全体"
    if school_id is not None and school_id != -1:
        query = query.filter_by(school_id=school_id)
        school = School.query.get(school_id)
        if school:
            school_name = school.school_name
    if department_id and department_id != -1:
        query = query.filter_by(department_id=department_id)
    if year and year != -1:
        query = query.filter_by(year=year)

    users = query.order_by(User.student_id).all()
    return render_template("user_management.html", users=users, school_name=school_name)


@app.route("/user_management/delete/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    # 管理者権限チェック
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    user = User.query.get(user_id)
    if not user:
        return redirect(url_for("user_management"))

    # 自分自身のアカウントは削除させない
    if session.get("user_id") == user.user_id:
        return redirect(url_for("user_management"))

    # 関連する投稿を先に削除（外部キー制約を回避）
    Post.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()

    return redirect(url_for("user_management"))


@app.route("/user_management/reset_password/<int:user_id>", methods=["POST"])
def reset_password(user_id):
    # 管理者のみ実行可
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    user = User.query.get(user_id)
    if not user:
        return redirect(url_for("user_management", msg="ユーザーが見つかりません"))

    temp_password = user.student_id
    user.password_hash = generate_password_hash(temp_password)
    db.session.commit()

    return redirect(url_for("user_management", msg=f"ユーザー {user.student_id} のパスワードをリセットしました（新しいパスワード: {temp_password}）"))


@app.route("/user_management/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    # 管理者権限チェック
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    user = User.query.get(user_id)
    if not user:
        return redirect(url_for("user_management", msg="ユーザーが見つかりません"))

    if request.method == "POST":
        # フォーム入力を更新
        user.name = request.form.get("name")
        student_id = request.form.get("student_id")
        school_id = request.form.get("school")
        department_id = request.form.get("department") or None
        year = request.form.get("year")

        if student_id and school_id:
            if len(student_id) > 1:
                student_id = str(school_id) + student_id[1:]
                
        user.student_id = student_id
        user.school_id = int(school_id) if school_id else user.school_id
        user.department_id = int(department_id) if department_id else None
        user.year = int(year) if year else None

        db.session.commit()

        return redirect(url_for("user_management", msg=f"ユーザー {user.student_id} を更新しました"))

    # GET: 編集フォーム表示
    schools = School.query.all()
    departments = Department.query.filter_by(school_id=user.school_id).all()
    return render_template("edit_user.html", user=user, schools=schools, departments=departments)

@app.route("/api/departments")
def api_departments():
    school_id = request.args.get("school_id", type=int)
    departments = Department.query.filter_by(school_id=school_id).all()
    return [{"department_id": d.department_id, "department_name": d.department_name} for d in departments]

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)