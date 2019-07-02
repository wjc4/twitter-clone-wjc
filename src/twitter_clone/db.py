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

    def create_user(self, username, password):
        if self.existing_user(username):
            raise Exception("User already exists")
        user_id = str(self.db.incrby("next_user_id", 1000))
        # @TODO hash password
        self.db.hmset("user:" + user_id, dict(username=username, password=password))
        self.db.hset("users", username, user_id)
        return username

    def get_user_id(self, username):
        if not self.existing_user(username):
            raise Exception("User not found")
        return str(self.db.hget("users", username), "utf-8")

    def existing_user(self, username):
        return self.db.hexists("users", username)

    def validate_user(self, username, password):
        # @TODO not hashed yet. pls check
        stored_hash = str(
            self.db.hget("user:" + self.get_user_id(username), "password"), "utf-8"
        )
        return password == stored_hash

    def existing_post(self, post_id):
        # @TODO check this. its weird
        return self.db.exists("post:" + post_id)

    def get_post(self, post_id):
        if not self.existing_post(post_id):
            raise Exception("Post not found")
        return self.db.hgetall("post:" + str(post_id, "utf-8"))

    def get_user_timeline(self, username):
        # return all(?) user's post
        user_id = self.get_user_id(username)
        posts = self.db.lrange("posts:" + str(user_id), 0, -1)
        user_posts = []
        for post_id in posts:
            post = self.db.hgetall("post:" + str(post_id, "utf-8"))
            user_posts.append(
                dict(username=username, time_stamp=post[b"ts"], text=post[b"text"])
            )
        return user_posts

    def get_home_timeline(self, username):
        pass

    def put_user_posts(self, username, text):
        # only trims timeline currently.
        user_id = self.get_user_id(username)
        post_id = str(self.db.incr("next_post_id"))
        self.db.hmset(
            "post:" + post_id, dict(user_id=user_id, time_stamp=time.time(), text=text)
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
