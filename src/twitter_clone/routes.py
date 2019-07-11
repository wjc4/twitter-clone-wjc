import logging, sys, os, uuid, json, re
from distutils import util

from flask import (
    Flask,
    session,
    redirect,
    url_for,
    render_template,
    request,
    send_from_directory,
)

import google_auth

import upload

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", os.urandom(50))

app.register_blueprint(google_auth.app)

from db import DB

with app.app_context():
    # maybe consider opening and closing per request
    db = DB()


@app.route("/hello", methods=["GET"])
def hello_world():
    app.logger.debug("Saying Hello!")
    return "Hello"


@app.route("/", methods=["GET"])
def home():
    if is_logged_in():
        return home_timeline()
    return global_timeline()
    #     return redirect(url_for("home_timeline"))
    # return redirect(url_for("global_timeline"))
    # return app.send_static_file("index.html")
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
    flush_session()
    username = request.form["username"]
    password = request.form["password"]
    try:
        create_user_session(db.validate_user(username, password))
    except Exception as e:
        # @TODO failed login
        return str(e)
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
    app.logger.debug(dict(request.form))
    username = request.form["username"]
    # check username
    user_pattern = re.compile("^[a-z0-9_]{3,15}$")
    if not bool(user_pattern.match(username)):
        return "invalid username. username must match ^[a-z0-9_]{3,15}$"
    password = request.form["password"]
    repeat_password = request.form["repeat_password"]
    if password != repeat_password:
        return "passwords does not match"
    password_pattern = re.compile("^[A-Za-z0-9!@#$%^&+=]{3,15}$")
    if not bool(password_pattern.match(password)):
        return "invalid password. password must match ^[A-Za-z0-9!@#$%^&+=]{3,15}$"
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
    user_pattern = re.compile("^[a-z0-9_]{3,15}$")
    if not bool(user_pattern.match(username)):
        return "invalid username. username must match ^[a-z0-9_]{3,15}$"
    password = request.form["username"]
    display_name = request.form["display_name"]
    # @TODO catch errors
    user_id = db.create_user(username, password, display_name, True)
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
    user = db.get_user(user_id)
    app.logger.debug(user)
    user["followers"] = db.get_followers_num(username)
    user["followings"] = db.get_followings_num(username)

    timeline = db.get_user_timeline(username)

    timeline = update_timeline(timeline, username)

    return render_template(
        "timeline.html",
        timeline=timeline,
        page_title="Your Tweets",
        logged_in=user,
        user=user,
    )
    # return render_template("profile.html", timeline=timeline)


@app.route("/global", methods=["GET"])
def global_timeline():
    user = False
    username = None
    if is_logged_in():
        logged_in = True
        user_id = db.get_session(session["session_id"])
        username = db.get_username(user_id)
        user = db.get_user(user_id)

    # user_id = db.get_session(session["session_id"])
    # username = db.get_username(user_id)

    timeline = db.get_global_timeline()

    timeline = update_timeline(timeline, username)
    app.logger.debug(timeline)
    return render_template(
        "timeline.html", timeline=timeline, page_title="Global Tweets", logged_in=user
    )


@app.route("/home", methods=["GET"])
def home_timeline():
    if not is_logged_in():
        app.logger.debug("not logged in")
        return redirect(url_for("login"))

    user_id = db.get_session(session["session_id"])
    username = db.get_username(user_id)
    user = db.get_user(user_id)

    timeline = db.get_home_timeline(username)

    timeline = update_timeline(timeline, username)
    app.logger.debug(timeline)
    return render_template(
        "timeline.html", timeline=timeline, page_title="Your Timeline", logged_in=user
    )


def update_timeline(timeline, username=None):
    for post in timeline:
        if "image_id" in post:
            post["image_url"] = upload.create_presigned_url(post["image_id"])
        if username is not None:
            post["editable"] = username == post["username"]

    return timeline


@app.route("/post", methods=["POST"])
def post():
    app.logger.debug("received a post submission")
    if not is_logged_in():
        return redirect(url_for("login"))
    session_id = session["session_id"]
    if not db.existing_session(session_id):
        return redirect(url_for("logout"))
    user_id = db.get_session(session["session_id"])
    username = db.get_username(user_id)
    uploadImage = False

    try:
        if "pic" in request.files:
            image = request.files["pic"]
            if image.filename != "":
                uploadImage = True
                image_id = upload_file(image)
    except:
        # upload failed
        uploadImage = False

    tweet = request.form["tweet"]
    referrer = request.referrer
    if uploadImage:
        db.put_user_post(username, tweet, image_id)
    else:
        db.put_user_post(username, tweet)

    followers = db.get_followers(username)
    app.logger.debug(followers)

    return redirect(referrer)


@app.route("/post/<post_id>", methods=["GET"])
def get_post(post_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    session_id = session["session_id"]
    if not db.existing_session(session_id):
        return redirect(url_for("logout"))
    user_id = db.get_session(session["session_id"])
    username = db.get_username(user_id)
    post = db.get_post(post_id)

    if post["user_id"] != user_id:
        raise Exception("Unauthorized")
    if "image_id" in post:
        post["image_url"] = upload.create_presigned_url(post["image_id"])
    return render_template(
        "post.html", post=post, page_title="Edit Tweet", current_user=username
    )


@app.route("/post/<post_id>", methods=["PUT"])
@app.route("/post/<post_id>/edit", methods=["POST"])
def edit_post(post_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    session_id = session["session_id"]
    if not db.existing_session(session_id):
        return redirect(url_for("logout"))
    user_id = db.get_session(session["session_id"])
    username = db.get_username(user_id)
    post = db.get_post(post_id)

    if post["user_id"] != user_id:
        raise Exception("Unauthorized")

    if util.strtobool(request.form["new_image"]):
        uploadImage = False

        try:
            # Delete Old Image
            if "image_id" in post:
                upload.delete_file_from_s3(post["image_id"])
                del post["image_id"]
            # Upload new Image
            if "pic" in request.files:
                image = request.files["pic"]
                if image.filename != "":
                    uploadImage = True
                    image_id = upload_file(image)
                    post["image_id"] = image_id
        except Exception as e:
            # upload failed
            app.logger.error(e)

    post["text"] = request.form["tweet"]
    db.edit_post(post)

    return redirect(url_for("profile"))


@app.route("/post/<post_id>", methods=["DELETE"])
@app.route("/post/<post_id>/delete", methods=["GET"])
def delete_post(post_id):
    if not is_logged_in():
        return redirect(url_for("login"))
    session_id = session["session_id"]
    if not db.existing_session(session_id):
        return redirect(url_for("logout"))
    user_id = db.get_session(session["session_id"])
    username = db.get_username(user_id)
    post = db.get_post(post_id)

    if post["user_id"] != user_id:
        raise Exception("Unauthorized")
    if "image_id" in post:
        upload.delete_file_from_s3(post["image_id"])

    db.delete_post(username, post_id)
    referrer = request.referrer
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


def upload_file(image):
    app.logger.debug("Attempting to upload image")
    if image and upload.allowed_file(image.filename):
        output = upload.upload_file_to_s3(image)
        app.logger.debug("Upload success")
        return str(output)
        # return upload.create_presigned_url(output)

    else:
        app.logger.debug("Upload failed due to invalid image")
        raise Exception("upload failed")


@app.route("/users")
def get_userbase():
    logged_in = False
    user = False
    if is_logged_in():
        session_id = session["session_id"]
        if db.existing_session(session_id):
            logged_in = True

    user_ids = db.get_all_user_id()
    users = db.get_all_user_details(user_ids)

    if logged_in:
        user_id = db.get_session(session["session_id"])
        username = db.get_username(user_id)
        following = db.get_followings(username)
        current_user = db.get_user(user_id)
        for user in users:
            if user["user_id"] in following:
                user["following"] = True
            else:
                user["following"] = False
        return render_template(
            "users.html",
            logged_in=current_user,
            users=users,
            page_title="All Users",
            current_user=username,
        )
    app.logger.debug(users)
    return render_template(
        "users.html", logged_in=logged_in, users=users, page_title="All Users"
    )


@app.route("/user/<username>", methods=["GET"])
def get_user_profile(username):
    logged_in = False  # or same user
    user = False
    current_user = False

    timeline = db.get_user_timeline(username)
    timeline = update_timeline(timeline)
    user_id = db.get_user_id(username)
    user = db.get_user(user_id)
    user["followers"] = db.get_followers_num(username)
    user["followings"] = db.get_followings_num(username)

    following = False
    if is_logged_in():
        session_id = session["session_id"]
        if db.existing_session(session_id):
            logged_in = True
            user_id = db.get_session(session["session_id"])
            current_username = db.get_username(user_id)
            current_user = db.get_user(user_id)
            following = db.existing_following(current_username, username)

            if current_username == username:
                logged_in = False

    return render_template(
        "user.html",
        logged_in=current_user,
        timeline=timeline,
        page_title=username + "'s Tweets",
        following=following,
        user=user,
    )


@app.route("/user/<username>/follower", methods=["GET"])
def get_user_follower(username):
    logged_in = False
    if is_logged_in():
        session_id = session["session_id"]
        if db.existing_session(session_id):
            logged_in = True

    user_ids = db.get_followers(username)
    users = db.get_all_user_details(user_ids)

    if logged_in:
        current_user_id = db.get_session(session["session_id"])
        current_username = db.get_username(current_user_id)
        current_user = db.get_user(current_user_id)
        following = db.get_followings(current_username)
        for user in users:
            if user["user_id"] in following:
                user["following"] = True
            else:
                user["following"] = False
        return render_template(
            "list_users.html",
            logged_in=current_user,
            users=users,
            page_title="@" + username + "'s Followers",
            current_user=username,
        )

    return render_template(
        "list_users.html",
        logged_in=logged_in,
        users=users,
        page_title="@" + username + "'s Followers",
    )


@app.route("/user/<username>/following", methods=["GET"])
def get_user_following(username):
    logged_in = False
    if is_logged_in():
        session_id = session["session_id"]
        if db.existing_session(session_id):
            logged_in = True

    user_ids = db.get_followings(username)
    users = db.get_all_user_details(user_ids)

    if logged_in:
        current_user_id = db.get_session(session["session_id"])
        current_username = db.get_username(current_user_id)
        current_user = db.get_user(current_user_id)
        following = db.get_followings(current_username)
        for user in users:
            if user["user_id"] in following:
                user["following"] = True
            else:
                user["following"] = False
        return render_template(
            "list_users.html",
            logged_in=current_user,
            users=users,
            page_title="@" + username + "'s Followings",
            current_user=username,
        )

    return render_template(
        "list_users.html",
        logged_in=logged_in,
        users=users,
        page_title="@" + username + "'s Followings",
    )


@app.route("/follow/<following_username>", methods=["POST"])
def follow(following_username):
    if not is_logged_in():
        return redirect(url_for("login"))
    session_id = session["session_id"]
    if not db.existing_session(session_id):
        return redirect(url_for("logout"))
    user_id = db.get_session(session["session_id"])
    username = db.get_username(user_id)

    # following_username = request.form["following_username"]
    referrer = request.referrer
    db.put_follow(username, following_username)
    return redirect(referrer)


# html forms does not support DELETE
@app.route("/follow//<following_username>", methods=["DELETE"])
@app.route("/unfollow/<following_username>", methods=["POST"])
def unfollow(following_username):
    if not is_logged_in():
        return redirect(url_for("login"))
    session_id = session["session_id"]
    if not db.existing_session(session_id):
        return redirect(url_for("logout"))
    user_id = db.get_session(session["session_id"])
    username = db.get_username(user_id)

    # following_username = request.form["following_username"]
    referrer = request.referrer
    db.delete_follow(username, following_username)
    return redirect(referrer)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )
