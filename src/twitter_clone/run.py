from routes import app
import logging


def main():
    app.logger.setLevel(logging.DEBUG)
    app.run(debug=True)


application = app
if __name__ == "__main__":
    app.run()

if __name__ != "__main__":
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
