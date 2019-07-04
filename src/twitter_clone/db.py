import redis
import flask
import time


class DB:
    def __init__(self):
        try:
            self.db = redis.StrictRedis(host="127.0.0.1", port=6379, db=0, password="")
            flask.current_app.logger.debug("Connected to Redis")
        except:
            flask.current_app.logger.error("Failed to connect to Redis")

    def create_user(self, username, password, display_name, sso=False):
        if self.existing_username(username):
            raise Exception("User already exists")
        user_id = str(self.db.incrby("next_user_id", 1000))
        # @TODO hash password
        self.db.hmset(
            "user:" + user_id,
            dict(
                username=username,
                password=password,
                display_name=display_name,
                sso=str(sso),
            ),
        )
        self.db.hset("users", username, user_id)
        return user_id

    def get_user_id(self, username):
        if not self.existing_username(username):
            raise Exception("User not found")
        return str(self.db.hget("users", username), "utf-8")

    def get_username(self, user_id):
        return str(self.db.hget("user:" + user_id, "username"), "utf-8")

    def get_user(self, user_id):
        undecoded_user = self.db.hgetall("user:" + str(user_id))
        user = dict(
            user_id=user_id,
            username=undecoded_user[b"username"].decode("utf-8"),
            display_name=undecoded_user[b"display_name"].decode("utf-8"),
            sso=bool(undecoded_user[b"sso"].decode("utf-8")),
        )
        return user

    def existing_username(self, username):
        return self.db.hexists("users", username)

    def existing_user_id(self, user_id):
        return self.db.exists("user:" + user_id)

    def validate_user(self, username, password):
        # @TODO not hashed yet. pls check
        # @TODO raise exceptions for login failures. eg. invalid user, invalid password
        user_id = self.get_user_id(username)
        sso = bool(self.db.hget("user:" + user_id, "sso"))
        if sso:
            raise Exception("Account needs to be logged in through SSO")
        stored_hash = str(self.db.hget("user:" + user_id, "password"), "utf-8")
        if password != stored_hash:
            raise Exception("Wrong Password")
        return user_id

    def create_google_user(self, google_id, user_id, username):
        if self.existing_google_id(google_id):
            raise Exception("Account already exists")
        self.db.hset("googlers", google_id, user_id)
        return google_id

    def get_user_id_from_google_id(self, google_id):
        if not self.existing_google_id(google_id):
            raise Exception("Google id not found")
        return str(self.db.hget("googlers", google_id), "utf-8")

    def existing_google_id(self, google_id):
        return self.db.hexists("googlers", str(google_id))

    def existing_post(self, post_id):
        # @TODO check this. its weird
        return self.db.exists("post:" + post_id)

    def get_post(self, post_id):
        if not self.existing_post(post_id):
            raise Exception("Post not found")
        post = self.db.hgetall("post:" + str(post_id, "utf-8"))
        return dict(
            username=post[b"username"].decode("utf-8"),
            time_stamp=post[b"time_stamp"].decode("utf-8"),
            text=post[b"text"].decode("utf-8"),
        )

    def get_user_timeline(self, username):
        # return all(?) user's post
        user_id = self.get_user_id(username)
        display_name = self.get_user(user_id)["display_name"]
        posts = self.db.lrange("posts:" + str(user_id), 0, -1)
        user_posts = []
        for post_id in posts:
            post = self.db.hgetall("post:" + str(post_id, "utf-8"))
            user_posts.append(
                dict(
                    username=username,
                    display_name=display_name,
                    time_stamp=post[b"time_stamp"].decode("utf-8"),
                    text=post[b"text"].decode("utf-8"),
                )
            )
        return user_posts

    def get_home_timeline(self, username):
        pass

    def get_global_timeline(self):
        pass

    def put_user_post(self, username, text):
        # only trims timeline currently.
        user_id = self.get_user_id(username)
        post_id = str(self.db.incr("next_post_id"))
        self.db.hmset(
            "post:" + post_id,
            dict(user_id=user_id, time_stamp=int(time.time()), text=text),
        )
        self.db.lpush("posts:" + str(user_id), str(post_id))
        self.db.lpush("timeline:" + str(user_id), str(post_id))
        self.db.ltrim("timeline:" + str(user_id), 0, 200)
        # @TODO get user's followers and push this tweet to their timeline.

    def delete_post(self, username, post_id):
        if not self.existing_post(post_id):
            raise Exception("Post not found")
        user_id = self.get_user_id(username)
        self.db.delete("post:" + post_id)
        self.db.lrem("posts:" + str(user_id), 1, post_id)
        self.db.lrem("timeline:" + str(user_id), 1, post_id)
        # @TODO delete post from followers timeline

    def existing_session(self, session_id):
        return self.db.exists("session:" + session_id)

    def put_session(self, session_id, user_id):
        if self.existing_session(session_id):
            raise Exception("Existing session. Do check for collision")
        self.db.hmset(
            "session:" + session_id, dict(user_id=user_id, time_stamp=time.time())
        )
        self.db.hset("sessions", session_id, user_id)

    def get_session(self, session_id):
        if not self.existing_session(session_id):
            raise Exception("Session not found")
        # @TODO check for expiration
        user_id = str(self.db.hget("session:" + session_id, "user_id"), "utf-8")
        return user_id

    def delete_session(self, session_id):
        if not self.existing_session(session_id):
            raise Exception("Session not found")
        self.db.delete("session:" + session_id)
        self.db.hdel("sessions", session_id)
