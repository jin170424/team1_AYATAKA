from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "secret_key_for_demo"

users = {
    "0241101": {"password": "123", "role": "student"},
    "0241102": {"password": "123", "role": "student"},
    "admin": {"password": "admin", "role": "admin"}
}

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users.get(username)
        if user and user["password"] == password:
            session["username"] = username
            session["role"] = user["role"]

            if user["role"] == "student":
                return redirect(url_for("home"))
            elif user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

        return render_template("login.html", error="ユーザー名またはパスワードが違います")

    return render_template("login.html")

@app.route("/home")
def home():
    if "role" in session and session["role"] == "student":
        return render_template("home.html", user=session["username"])
    return redirect(url_for("login"))

@app.route("/admin")
def admin_dashboard():
    if "role" in session and session["role"] == "admin":
        return render_template("admin_dashboard.html", user=session["username"])
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)