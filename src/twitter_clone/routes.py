import logging, sys, os, uuid, json
from flask import Flask, session, redirect, url_for, render_template, request

from . import google_auth

from . import upload

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", os.urandom(50))

app.register_blueprint(google_auth.app)

from .db import DB

with app.app_context():
    # maybe consider opening and closing per request
    db = DB()


@app.route("/hello", methods=["GET"])
def hello_world():
    app.logger.debug("Saying Hello!")
    return "Hello"


@app.route("/", methods=["GET"])
def home():
    return app.send_static_file("index.html")
    # return render_template("login.html")


@app.route("/login", methods=["GET"])
def login():
    error = None
    if is_logged_in():
        return redirect(url_for("home"))
    else:
        return app.send_static_file("login.html")
        # return render_template("login.html", error=error)


@app.route("/redirect", methods=["GET"])
def redirection():
    error = None
    if google_auth.is_logged_in():
        return check_google_session()
    if is_logged_in():
        return redirect(url_for("home"))
    else:
        return redirect(url_for("login"))
        # return render_template("login.html", error=error)


@app.route("/login", methods=["POST"])
def create_user():
    username = request.form["username"]
    password = request.form["password"]
    try:
        create_user_session(db.validate_user(username, password))
    except:
        # @TODO failed login
        return "failed login"
    return redirect(url_for("home"))


@app.route("/logout", methods=["GET"])
def logout():
    if "session_id" in session:
        db.delete_session(session["session_id"])
    flush_session()
    return redirect(url_for("login"))
    # return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "GET":
        return app.send_static_file("register.html")
        # return render_template("signup.html", error=error)
    # @TODO enforce valid username
    app.logger.debug(dict(request.form))
    username = request.form["username"]
    password = request.form["password"]
    display_name = request.form["display_name"]
    # @TODO catch errors
    user_id = db.create_user(username, password, display_name)

    create_user_session(user_id)

    return redirect(url_for("home"))


@app.route("/signup2", methods=["GET", "POST"])
def signup_google():
    error = None
    if not google_auth.is_logged_in():
        return "Error 401: Unauthorised"
    else:
        google_id = session["google_id"]
        app.logger.debug(
            "checking if gid:"
            + str(google_id)
            + " of type "
            + str(type(google_id))
            + " exists"
        )
        if db.existing_google_id(google_id):
            app.logger.debug("google_id alr exists")
            return check_google_session()
    if request.method == "GET":
        return app.send_static_file("register_google.html")
    # @TODO enforce valid username
    app.logger.debug(dict(request.form))
    username = request.form["username"]
    password = request.form["username"]
    display_name = request.form["display_name"]
    # @TODO catch errors
    user_id = db.create_user(username, password, display_name)
    db.create_google_user(session["google_id"], user_id, username)
    create_user_session(user_id)

    return redirect(url_for("home"))


def create_user_session(user_id):
    session_id = uuid.uuid4().hex
    session["session_id"] = session_id
    session["user_id"] = user_id  # DELETE AFTER DEPRECATION
    session.permanent = True
    db.put_session(session_id, user_id)


def is_logged_in():
    status = False
    if "session_id" in session:
        status = db.existing_session(session["session_id"])
        if not status:
            flush_session()
    return status


def check_google_session():
    if "google_id" not in session:
        raise Exception("No google SSO found!")
    google_id = session["google_id"]
    if not db.existing_google_id(google_id):
        return redirect(url_for("signup_google"))
    if not is_logged_in():
        user_id = db.get_user_id_from_google_id(google_id)
        create_user_session(user_id)
    return redirect(url_for("home"))


def flush_session():
    [session.pop(key) for key in list(session.keys()) if key != "_flashes"]


@app.route("/profile", methods=["GET"])
def profile():
    if not is_logged_in():
        app.logger.debug("not logged in")
        return redirect(url_for("login"))

    user_id = db.get_session(session["session_id"])
    username = db.get_username(user_id)

    timeline = db.get_user_timeline(username)
    return render_template("timeline.html", timeline=timeline, username=username)
    # return render_template("profile.html", timeline=timeline)


@app.route("/post", methods=["POST"])
def post():
    if not is_logged_in():
        return redirect(url_for("login"))
    session_id = session["session_id"]
    if not db.existing_session(session_id):
        return redirect(url_for("logout"))
    user_id = db.get_session(session["session_id"])
    username = db.get_username(user_id)

    tweet = request.form["tweet"]
    referrer = request.referrer
    db.put_user_post(username, tweet)
    return redirect(referrer)


@app.route("/googleinfo")
def google_debug():
    if google_auth.is_logged_in():
        user_info = google_auth.get_user_info()
        return (
            "<div>You are currently logged in as "
            + user_info["given_name"]
            + "<div><pre>"
            + json.dumps(user_info, indent=4)
            + "</pre>"
        )

    return "You are not currently logged in."


@app.route("/upload", methods=["POST"])
def upload_file():
    app.logger.debug(dict(request.files))
    # A
    if "user_file" not in request.files:
        return "No user_file key in request.files"

    # B
    file = request.files["user_file"]

    """
        These attributes are also available

        file.filename               # The actual name of the file
        file.content_type
        file.content_length
        file.mimetype

    """

    # C.
    if file.filename == "":
        return "Please select a file"

    # D.
    if file and upload.allowed_file(file.filename):
        output = upload.upload_file_to_s3(file)
        # return str(output)
        return upload.create_presigned_url(output)

    else:
        return redirect("/")
