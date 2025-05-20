# standard imports
import inspect
import os
import shelve
import threading
from unittest.mock import patch

# lib imports
import pytest
from tinydb import JSONStorage, TinyDB
from tinydb.middlewares import CachingMiddleware

# local imports
from src.common.database import Database


class TestDatabase:
    @pytest.fixture
    def test_dir(self, tmp_path):
        """Create a temporary directory for database files."""
        return tmp_path

    @pytest.fixture
    def db_init(self, test_dir):
        """Create a database path for testing."""
        return {
            "db_dir": test_dir,
            "use_git": False
        }

    @pytest.fixture
    def cleanup_files(self, db_init):
        """Clean up database files after tests."""
        yield

        db_name = f'db_{inspect.currentframe().f_code.co_name}'

        # Clean up known database files
        for file_path in [f"{db_name}.json", f"{db_name}.db", f"{db_name}.dat",
                          f"{db_name}.bak", f"{db_name}.dir", db_name]:
            if os.path.exists(os.path.join(db_init['db_dir'], file_path)):
                try:
                    os.remove(file_path)
                    print(f"Removed {file_path}")
                except Exception as e:
                    print(f"Could not remove {file_path}: {e}")

    def test_init_new_database(self, db_init, cleanup_files):
        """Test creating a new database."""
        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=db_init['use_git'],
        )
        assert os.path.exists(os.path.join(db_init['db_dir'], f'db_{inspect.currentframe().f_code.co_name}.json'))
        assert hasattr(db, "tinydb")
        assert hasattr(db, "lock")

    def test_context_manager(self, db_init, cleanup_files):
        """Test database context manager functionality."""
        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=db_init['use_git'],
        )

        with db as tinydb:
            tinydb.insert({"test": "data"})

        # Reopen to verify data was saved
        db2 = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=db_init['use_git'],
        )
        with db2 as tinydb:
            data = tinydb.all()
            assert len(data) == 1
            assert data[0]["test"] == "data"

    def test_sync_method(self, db_init, cleanup_files):
        """Test sync method flushes data to disk, closes and reopens database."""
        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=db_init['use_git'],
        )

        # Get the original TinyDB instance
        original_tinydb = db.tinydb

        # Create a test record to verify persistence
        with db as tinydb:
            tinydb.insert({"test_before_sync": "data"})

        # Create a real TinyDB instance to return from the mock
        new_db = TinyDB(
            db.json_path,
            storage=CachingMiddleware(JSONStorage),
            indent=4,
        )

        # Setup the mocks - correctly patching the TinyDB constructor
        with patch.object(db.tinydb.storage, 'flush') as mock_flush:
            with patch.object(db.tinydb, 'close') as mock_close:
                # Use __name__ to get the fully qualified name including module
                with patch('src.common.database.TinyDB', return_value=new_db) as mock_tinydb:
                    # Call sync method
                    db.sync()

                    # Verify the sequence of operations
                    mock_flush.assert_called_once()
                    mock_close.assert_called_once()
                    mock_tinydb.assert_called_once()

        # Verify database is still usable after sync
        assert db.tinydb is not None
        assert db.tinydb is not original_tinydb

        # Verify we can still use the database and data persisted
        with db as tinydb:
            existing_data = tinydb.all()
            assert any(record.get("test_before_sync") == "data" for record in existing_data)

            # Add new data to verify database is functional
            tinydb.insert({"test_after_sync": "new_data"})

    @staticmethod
    def create_test_shelve(shelve_path):
        """Helper to create a test shelve database."""
        # Close the shelve db properly to ensure it's written to disk
        shelve_db = shelve.open(shelve_path)

        # Add a comments table with records
        shelve_db["comments"] = {
            "abc123": {"author": "user1", "body": "test comment", "processed": True},
            "def456": {"author": "user2", "body": "another comment", "processed": False}
        }
        # Add submissions table
        shelve_db["submissions"] = {
            "xyz789": {"author": "user3", "title": "Test post", "processed": True}
        }

        # Explicitly sync and close
        shelve_db.sync()
        shelve_db.close()

    def test_migrate_from_shelve(self, db_init, cleanup_files):
        """Test migration from shelve to TinyDB."""
        # Create a shelve database first
        self.create_test_shelve(os.path.join(db_init['db_dir'], f'db_{inspect.currentframe().f_code.co_name}'))
        print("Files in db_dir before migration:", os.listdir(db_init['db_dir']))

        # Try to create the database (it should migrate if possible)
        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=db_init['use_git'],
        )

        # If migration didn't happen on this platform, create the tables manually for test
        with db as tinydb:
            comments = tinydb.table("comments").all()
            submissions = tinydb.table("submissions").all()

            # Now verify the data exists one way or another
            assert len(comments) == 2
            assert len(submissions) == 1

            # Find records by attributes since order may vary
            user1_comment = next((c for c in comments if c["author"] == "user1"), None)
            user2_comment = next((c for c in comments if c["author"] == "user2"), None)

            assert user1_comment is not None, "Couldn't find user1's comment"
            assert user2_comment is not None, "Couldn't find user2's comment"
            assert user1_comment["body"] == "test comment"
            assert user1_comment["processed"] is True
            assert user2_comment["body"] == "another comment"
            assert user2_comment["processed"] is False

            assert submissions[0]["author"] == "user3"
            assert submissions[0]["title"] == "Test post"

    def test_migrate_from_shelve_reddit_db(self, db_init, cleanup_files):
        """Test migration from shelve to TinyDB for Reddit database specifically."""
        # Create a shelve path with reddit in the name to trigger special handling
        reddit_db_name = f'reddit_bot_{inspect.currentframe().f_code.co_name}'
        shelve_path = os.path.join(db_init['db_dir'], reddit_db_name)

        # Create a test shelve with Reddit-specific data structures
        shelve_db = shelve.open(shelve_path)

        # Add comments with different structures
        shelve_db["comments"] = {
            "abc123": {
                "author": "user1",  # comment authors are strings
                "body": "test comment",
                "created_utc": 1625097600,
                "processed": True,
                "slash_command": "/help",
            },
            "def456": {
                "author": "user2",
                "body": "another comment",
                "created_utc": 1625184000,
                "processed": False,
            },
            "ghi789": {
                "author": None,  # Edge case with None author
                "body": "deleted comment",
                "created_utc": 1625270400,
            }
        }

        # Add submissions with different structures
        shelve_db["submissions"] = {
            "xyz789": {
                "id": "xyz789",
                "title": "Test post",
                "selftext": "Post content",
                "author": "user3",
                "created_utc": 1625356800,
                "permalink": "/r/test/comments/xyz789/",
                "url": "https://reddit.com/r/test/comments/xyz789/",
                "link_flair_text": "Help",
                "link_flair_background_color": "#ff0000",
                "bot_discord": {"message_id": "123456789"}
            },
            "uvw456": {
                "id": "uvw456",
                "title": "Another post",
                "selftext": "",
                "author": "user4",
                "created_utc": 1625443200,
                "permalink": "/r/test/comments/uvw456/",
                "url": "https://reddit.com/r/test/comments/uvw456/"
                # Missing some fields intentionally
            }
        }

        # Explicitly sync and close
        shelve_db.sync()
        shelve_db.close()

        # Create the database (it should trigger migration)
        db = Database(
            db_name=reddit_db_name,
            db_dir=db_init['db_dir'],
            use_git=db_init['use_git'],
        )

        # Verify the migrated data
        with db as tinydb:
            # Check comments
            comments_table = tinydb.table("comments")
            comments = comments_table.all()
            assert len(comments) == 3

            # Find specific comments by ID to verify consistent order
            comment1 = next((c for c in comments if c["reddit_id"] == "abc123"), None)
            comment2 = next((c for c in comments if c["reddit_id"] == "def456"), None)
            comment3 = next((c for c in comments if c["reddit_id"] == "ghi789"), None)

            # Verify comment 1
            assert comment1 is not None
            assert comment1["author"] == "user1"
            assert comment1["body"] == "test comment"
            assert comment1["created_utc"] == 1625097600
            assert comment1["processed"] is True
            assert comment1["slash_command"] == "/help"

            # Verify comment 2
            assert comment2 is not None
            assert comment2["author"] == "user2"
            assert comment2["body"] == "another comment"
            assert comment2["created_utc"] == 1625184000
            assert comment2["processed"] is False
            assert comment2["slash_command"]["command"] is None
            assert comment2["slash_command"]["project"] is None

            # Verify comment 3 - None author
            assert comment3 is not None
            assert comment3["author"] is None
            assert comment3["body"] == "deleted comment"
            assert comment3["created_utc"] == 1625270400

            # Check submissions
            submissions_table = tinydb.table("submissions")
            submissions = submissions_table.all()
            assert len(submissions) == 2

            # Find specific submissions
            submission1 = next((s for s in submissions if s["reddit_id"] == "xyz789"), None)
            submission2 = next((s for s in submissions if s["reddit_id"] == "uvw456"), None)

            # Verify submission 1 - full fields
            assert submission1 is not None
            assert submission1["title"] == "Test post"
            assert submission1["selftext"] == "Post content"
            assert submission1["author"] == "user3"
            assert submission1["created_utc"] == 1625356800
            assert submission1["permalink"] == "/r/test/comments/xyz789/"
            assert submission1["url"] == "https://reddit.com/r/test/comments/xyz789/"
            assert submission1["link_flair_text"] == "Help"
            assert submission1["link_flair_background_color"] == "#ff0000"
            assert submission1["bot_discord"]["message_id"] == "123456789"

            # Verify submission 2 - missing some fields
            assert submission2 is not None
            assert submission2["title"] == "Another post"
            assert submission2["selftext"] == ""
            assert submission2["author"] == "user4"
            assert submission2["created_utc"] == 1625443200
            assert submission2["permalink"] == "/r/test/comments/uvw456/"
            assert submission2["url"] == "https://reddit.com/r/test/comments/uvw456/"
            assert submission2["link_flair_text"] is None
            assert submission2["link_flair_background_color"] is None
            assert submission2["bot_discord"]["sent"] is False
            assert submission2["bot_discord"]["sent_utc"] is None

    def test_migration_error_handling(self, db_init, cleanup_files):
        """Test error handling during migration."""
        # Create a shelve database first
        self.create_test_shelve(os.path.join(db_init['db_dir'], f'db_{inspect.currentframe().f_code.co_name}'))

        # Instead of testing print output, check that the database still initializes
        # even when shelve migration fails
        with patch('shelve.open', side_effect=Exception("Test error")):
            db = Database(
                db_name=f'db_{inspect.currentframe().f_code.co_name}',
                db_dir=db_init['db_dir'],
                use_git=db_init['use_git'],
            )

            # Check database was initialized with empty tables
            with db as tinydb:
                comments = tinydb.table("comments").all()
                submissions = tinydb.table("submissions").all()
                assert len(comments) == 0
                assert len(submissions) == 0

    def test_thread_safety(self, db_init, cleanup_files):
        """Test thread safety with multiple threads accessing database."""
        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=db_init['use_git'],
        )
        results = []

        def worker(worker_id):
            with db as tinydb:
                # Simulate some work
                table = tinydb.table(f"worker_{worker_id}")
                table.insert({"id": worker_id})
                results.append(worker_id)

        # Create and start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Verify all workers processed
        assert len(results) == 5
        assert set(results) == set(range(5))

        # Verify database has all tables
        with db as tinydb:
            for i in range(5):
                table = tinydb.table(f"worker_{i}")
                assert len(table.all()) == 1
                assert table.all()[0]["id"] == i
