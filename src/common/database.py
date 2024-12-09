# standard imports
import shelve
import threading


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = threading.Lock()

    def __enter__(self):
        self.lock.acquire()
        self.db = shelve.open(self.db_path, writeback=True)
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sync()
        self.db.close()
        self.lock.release()

    def sync(self):
        self.db.sync()
