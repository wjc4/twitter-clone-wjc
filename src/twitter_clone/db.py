import redis
import flask
import time
from distutils import util


class DB:
    def __init__(self):
        try:
            self.db = redis.StrictRedis(host="127.0.0.1", port=6379, db=0, password="")
            flask.current_app.logger.debug("Connected to Redis")
        except:
            flask.current_app.logger.error("Failed to connect to Redis")

    # @TODO make this atomic
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
                sso=str(int(sso)),
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
            sso=util.strtobool(undecoded_user[b"sso"].decode("utf-8")),
        )
        return user

    def get_all_user_id(self):
        user_list = self.db.hgetall("users")
        user_ids = []
        for key in user_list:
            user_ids.append(user_list[key].decode("utf-8"))
        return user_ids

    def get_all_user_details(self, user_ids):
        users = []
        for user_id in user_ids:
            users.append(self.get_user(user_id))
        return users

    def existing_username(self, username):
        return self.db.hexists("users", username)

    def existing_user_id(self, user_id):
        return self.db.exists("user:" + user_id)

    def validate_user(self, username, password):
        # @TODO not hashed yet. pls check
        # @TODO raise exceptions for login failures. eg. invalid user, invalid password
        user_id = self.get_user_id(username)
        sso = util.strtobool(str(self.db.hget("user:" + user_id, "sso"), "utf-8"))
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

    def get_followings(self, username):
        user_id = self.get_user_id(username)
        following = self.db.smembers("following:" + user_id)
        following_list = []
        for item in following:
            following_list.append(item.decode("utf-8"))
        return following_list

    def get_followers(self, username):
        user_id = self.get_user_id(username)
        follower = self.db.smembers("follower:" + user_id)
        follower_list = []
        for item in follower:
            follower_list.append(item.decode("utf-8"))
        return follower_list

    def get_followings_num(self, username):
        user_id = self.get_user_id(username)
        following_num = self.db.scard("following:" + user_id)
        return following_num

    def get_followers_num(self, username):
        user_id = self.get_user_id(username)
        follower_num = self.db.scard("follower:" + user_id)
        return follower_num

    def put_follow(self, follower, following):
        follower_id = self.get_user_id(follower)
        following_id = self.get_user_id(following)
        if follower_id == following_id:
            raise Exception("Cannot follow yourself")
        self.db.sadd("following:" + follower_id, following_id)
        self.db.sadd("follower:" + following_id, follower_id)

        following_posts = self.db.lrange("posts:" + str(following_id), 0, 200)
        for post_id in following_posts:
            post = self.get_post(post_id)
            self.db.zadd(
                "timeline:" + str(follower_id),
                {str(post_id, "utf-8"): post["time_stamp"]},
            )
        self.db.zremrangebyrank("timeline:" + str(follower_id), 0, -201)

        return following

    def delete_follow(self, follower, following):
        follower_id = self.get_user_id(follower)
        following_id = self.get_user_id(following)
        self.db.srem("following:" + follower_id, following_id)
        self.db.srem("follower" + following_id, follower_id)

        follower_timeline = self.db.zrevrange("timeline:" + str(follower_id), 0, -1)
        following_posts = self.db.lrange("posts:" + str(following_id), 0, 200)
        for post_id in following_posts:
            if post_id in follower_timeline:
                self.db.zrem("timeline:" + follower_id, post_id)

        # @TODO add back

        return following

    def existing_following(self, follower, following):
        follower_id = self.get_user_id(follower)
        following_id = self.get_user_id(following)
        return self.db.sismember("following:" + follower_id, following_id)

    def existing_post(self, post_id):
        # @TODO check this. its weird
        if type(post_id) != str:
            post_id = str(post_id, "utf-8")
        return self.db.exists("post:" + post_id)

    def get_post(self, post_id):
        if not self.existing_post(post_id):
            raise Exception("Post not found")
        if type(post_id) != str:
            post_id = str(post_id, "utf-8")
        post = self.db.hgetall("post:" + post_id)
        user_id = post[b"user_id"].decode("utf-8")
        user = self.get_user(user_id)
        item = dict(
            id=post_id,
            user_id=user_id,
            username=user["username"],
            display_name=user["display_name"],
            time_stamp=post[b"time_stamp"].decode("utf-8"),
            text=post[b"text"].decode("utf-8"),
            image=util.strtobool(post[b"image"].decode("utf-8")),
        )
        if item["image"]:
            item["image_id"] = post[b"image_id"].decode("utf-8")
        return item

    def get_user_timeline(self, username):
        # return all(?) user's post
        user_id = self.get_user_id(username)
        display_name = self.get_user(user_id)["display_name"]
        posts = self.db.lrange("posts:" + str(user_id), 0, -1)
        user_posts = []
        for post_id in posts:
            post = self.db.hgetall("post:" + str(post_id, "utf-8"))
            item = dict(
                id=str(post_id, "utf-8"),
                username=username,
                display_name=display_name,
                time_stamp=post[b"time_stamp"].decode("utf-8"),
                text=post[b"text"].decode("utf-8"),
                image=util.strtobool(post[b"image"].decode("utf-8")),
            )
            if item["image"]:
                item["image_id"] = post[b"image_id"].decode("utf-8")
            user_posts.append(item)
        return user_posts

    def get_home_timeline(self, username):
        user_id = self.get_user_id(username)
        display_name = self.get_user(user_id)["display_name"]
        posts = self.db.zrevrange("timeline:" + str(user_id), 0, -1)
        user_timeline = []
        users = {}
        for post_id in posts:
            post = self.db.hgetall("post:" + str(post_id, "utf-8"))
            user_id = post[b"user_id"].decode("utf-8")
            if user_id not in users:
                user = self.get_user(user_id)
                users[user_id] = dict(
                    username=user["username"], display_name=user["display_name"]
                )

            item = dict(
                id=str(post_id, "utf-8"),
                username=users[user_id]["username"],
                display_name=users[user_id]["display_name"],
                time_stamp=post[b"time_stamp"].decode("utf-8"),
                text=post[b"text"].decode("utf-8"),
                image=util.strtobool(post[b"image"].decode("utf-8")),
            )
            if item["image"]:
                item["image_id"] = post[b"image_id"].decode("utf-8")
            user_timeline.append(item)
        return user_timeline

    def get_global_timeline(self):
        posts = self.db.lrange("gtimeline", 0, -1)
        all_posts = []
        users = {}
        for post_id in posts:
            post = self.db.hgetall("post:" + str(post_id, "utf-8"))
            user_id = post[b"user_id"].decode("utf-8")
            # prevent requerying for user details again
            if user_id not in users:
                user = self.get_user(user_id)
                users[user_id] = dict(
                    username=user["username"], display_name=user["display_name"]
                )

            item = dict(
                id=str(post_id, "utf-8"),
                username=users[user_id]["username"],
                display_name=users[user_id]["display_name"],
                time_stamp=post[b"time_stamp"].decode("utf-8"),
                text=post[b"text"].decode("utf-8"),
                image=util.strtobool(post[b"image"].decode("utf-8")),
            )
            if item["image"]:
                item["image_id"] = post[b"image_id"].decode("utf-8")
            all_posts.append(item)
        return all_posts

    def put_user_post(self, username, text, image_id=None):
        # only trims timeline currently.
        user_id = self.get_user_id(username)
        post_id = str(self.db.incr("next_post_id"))
        time_stamp = int(time.time())
        if image_id is None:
            item = dict(
                user_id=user_id, time_stamp=time_stamp, text=text, image=str(False)
            )
        else:
            item = dict(
                user_id=user_id,
                time_stamp=time_stamp,
                text=text,
                image=str(True),
                image_id=image_id,
            )
        # post details
        self.db.hmset("post:" + post_id, item)

        # userid to posts
        self.db.lpush("posts:" + str(user_id), str(post_id))

        # user timeline
        # push to own timeline
        # zadd(key, {'value':score})
        self.db.zadd("timeline:" + str(user_id), {str(post_id): time_stamp})
        self.db.zremrangebyrank("timeline:" + str(user_id), 0, -201)
        # TO DELETE
        # self.db.lpush("timeline:" + str(user_id), str(post_id))
        # self.db.ltrim("timeline:" + str(user_id), 0, 200)
        # END DELETE

        # push to follower's timeline
        followers = self.get_followers(username)
        for follower_id in followers:
            self.db.zadd("timeline:" + str(follower_id), {str(post_id): time_stamp})
            self.db.zremrangebyrank("timeline:" + str(follower_id), 0, -201)

        # global timeline
        self.db.lpush("gtimeline", str(post_id))
        self.db.ltrim("gtimeline", 0, 500)
        # @TODO get user's followers and push this tweet to their timeline.

    def edit_post(self, post):
        post_id = post["id"]
        if not self.existing_post(post_id):
            raise Exception("Post not found")
        if "image_id" in post:
            item = dict(
                user_id=post["user_id"],
                time_stamp=post["time_stamp"],
                text=post["text"],
                image=str(True),
                image_id=post["image_id"],
            )
        else:
            item = dict(
                user_id=post["user_id"],
                time_stamp=post["time_stamp"],
                text=post["text"],
                image=str(False),
            )
        # post details
        self.db.hmset("post:" + post_id, item)

    def delete_post(self, username, post_id):
        if not self.existing_post(post_id):
            raise Exception("Post not found")
        user_id = self.get_user_id(username)
        self.db.delete("post:" + post_id)
        self.db.lrem("posts:" + str(user_id), 1, post_id)
        self.db.zrem("timeline:" + str(user_id), post_id)

        # @TODO delete post from followers timeline
        # get followers
        # iterate
        followers = self.get_followers(username)
        for follower_id in followers:
            self.db.zrem("timeline:" + follower_id, post_id)

        # delete from gtimeline
        self.db.lrem("gtimeline", 1, post_id)

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
