import logging, sys, os
from flask import Flask, session, redirect, url_for, render_template, request

app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET", os.urandom(50))

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
    return app.send_static_file("login.html")
    # return render_template("login.html")


@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username", None)
    return app.send_static_file("login.html")
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
    db.create_user(username, password)
    session["username"] = username
    return redirect(url_for("home"))


@app.route("/profile/<username>", methods=["GET"])
def profile():
    pass


@app.route("/post", methods=["POST"])
def post():
    pass
