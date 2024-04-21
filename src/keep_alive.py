from flask import Flask
from threading import Thread
import os

app = Flask('')


@app.route('/')
def main():
    return f"{os.environ['REPL_SLUG']} is live!"


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    server = Thread(name="Flask", target=run)
    server.setDaemon(daemonic=True)
    server.start()
