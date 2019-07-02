from .routes import app
import logging


def main():
    app.logger.setLevel(logging.DEBUG)
    app.run(debug=True)


if __name__ == "__main__":
    app.run()
