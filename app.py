from flask import Flask, render_template, request, session, url_for, redirect, flash
from flask_session import Session
import mysql.connector
import os
import requests

app = Flask(__name__)
app.secret_key = "pass123"
app.config["SESSION_PERMANENT"] = False

Session()


DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'test1_users'),
}


@app.route("/", methods=["GET", "POST"])
def index():
    if is_logged_in():
        profile_data : dict = get_user_profile_data(session["logged_in_username"])
        return render_template("index.html",
                                is_logged_in = True,
                                name = profile_data["name"],
                                fave_color = profile_data["fave_color"])

    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return redirect(url_for("index"))
    
    # verify with user database
    correct_creds : bool = verify_login_creds(request.form.get("username", ""), request.form.get("password", ""))

    # update cookies
    if correct_creds:
        set_login_cookies(request.form["username"])
    else:
        flash("Incorrect login credentials")
        clear_login_cookies()
    
    return redirect(url_for("index"))

@app.route("/logout", methods=["GET"])
def logout():
    clear_login_cookies()
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    created_user : bool = create_new_user(
        request.form.get("username"),
        request.form.get("password"),
        request.form.get("name"),
        request.form.get("email"))

    if created_user:
        return redirect(url_for("index"))
    else:
        return redirect(url_for("signup"))

@app.route("/set_fave_color", methods=["GET", "POST"])
def set_fave_color():
    if request.method == "POST" and is_logged_in():
        color = request.form.get("color", "")

        conn = get_db_conn()
        cursor = conn.cursor()
        print(f"setting color {color} as fave for {session['logged_in_username']}")

        cursor.execute(f"UPDATE users SET fave_color='{color}' WHERE username='{session['logged_in_username']}'")
        conn.commit()
        
        cursor.close()
        conn.close()

        flash("Set favorite color")

    return redirect(url_for("index"))

@app.route("/color_tally", methods = ["GET"])
def color_tally():
    color_dict = get_color_tally()
    return render_template("color_tally.html", color_dict=color_dict)

def get_db_conn() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(**DB_CONFIG)

def is_logged_in() -> bool:
    return bool(session.get("logged_in_username", ""))

def verify_login_creds(username : str, password : str) -> bool:
    if username == "" or password == "":
        return False

    # setup db connection
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)

    # get the user credentials from the given username
    cursor.execute(f"SELECT username, password FROM users WHERE username='{username}'; ")
    user_creds : dict = cursor.fetchone()

    # close db connection
    cursor.close()
    conn.close()

    # check wether the user exists and if so compare passwords
    user_exists : bool = bool(user_creds)
    password_correct : bool = user_creds["password"] == password if user_exists else False
    
    return user_exists and password_correct

def create_new_user(username : str, password : str, name : str, email : str) -> bool:
    """Create new user. Returns wether the given username was taken"""
    
    # if any of the fields is missing data
    if any(field == "" for field in [username, password, name, email]):
        flash("Please fill all fields")
        return False

    conn = get_db_conn()
    cursor = conn.cursor()

    # check the username availability
    cursor.execute(f"SELECT username FROM users WHERE username='{username}'")
    username_taken : bool = len(cursor.fetchall()) != 0

    if username_taken:
        flash("Username taken")
        cursor.close()
        conn.close()
        return False

    # check the email availability
    cursor.execute(f"SELECT email FROM users WHERE email='{email}'")
    email_taken : bool = len(cursor.fetchall()) != 0

    if email_taken:
        flash("Email taken")
        cursor.close()
        conn.close()
        return False
    
    
    # if neither username or email is taken
    cursor.execute(f"INSERT INTO users (username, password, name, email) VALUES ('{username}', '{password}', '{name}', '{email}')")
    conn.commit()

    flash("Created user")
    cursor.close()
    conn.close()
    return True

def set_login_cookies(username : str) -> None:
    session["logged_in_username"] = username

def clear_login_cookies() -> None:
    set_login_cookies("")

def get_user_profile_data(username : str) -> dict:
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(f"SELECT name,fave_color FROM users WHERE username='{username}'")
    profile_data = cursor.fetchone()

    cursor.close()
    conn.close()

    return profile_data

def get_color_tally() -> dict[str, int]:
    conn = get_db_conn()
    cursor = conn.cursor(dictionary=False)

    cursor.execute("SELECT fave_color,count(*) as color_count FROM users GROUP BY fave_color ORDER BY color_count DESC LIMIT 5")
    color_dict = dict(cursor.fetchall())

    cursor.close()
    conn.close()

    return color_dict


if __name__ == "__main__":
    app.run(debug=True)