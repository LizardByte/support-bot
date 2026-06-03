# standard imports
import inspect
import os
import shelve
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# lib imports
import git
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

    def test_sync_with_git_enabled_no_changes(self, db_init, cleanup_files):
        """Test sync with git enabled but no changes to commit."""
        from unittest.mock import MagicMock

        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=False,
        )

        # Enable git and mock the repo
        db.use_git = True
        db.repo = MagicMock()
        db.repo.git.status.return_value = ""  # No changes

        # Call sync
        db.sync()

        # Verify status was checked but nothing was committed
        db.repo.git.status.assert_called_with('--porcelain')
        db.repo.git.add.assert_not_called()
        db.repo.git.commit.assert_not_called()

    def test_sync_with_git_enabled_with_changes(self, db_init, cleanup_files):
        """Test sync with git enabled and changes to commit."""
        from unittest.mock import MagicMock
        import src.common.database as db_module

        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=False,
        )

        # Enable git and mock the repo
        db.use_git = True
        db.repo = MagicMock()
        db.repo_url = "https://github.com/test/repo"
        db.repo_branch = "main"
        db.git_user_name = "testuser"
        db.git_token = "testtoken"

        # Mock _configure_repo to avoid actual git config operations
        db._configure_repo = MagicMock()

        # Mock git operations
        db.repo.git.status.side_effect = [
            "M db_test.json",  # First call - changes exist
            "M db_test.json",  # Second call - still changes after add
        ]

        # Mock os.listdir to return a json file
        with patch('os.listdir', return_value=['db_test.json']):
            # Mock GIT_ENABLED
            with patch.object(db_module, 'GIT_ENABLED', True):
                # Call sync
                db.sync()

        # Verify git operations were called
        assert db.repo.git.status.call_count == 2
        db.repo.git.add.assert_called_once()
        db._configure_repo.assert_called_once()
        db.repo.git.commit.assert_called_once_with('-m', 'Update database files')
        db.repo.git.push.assert_called_once()

    def test_sync_with_git_multiple_json_files(self, db_init, cleanup_files):
        """Test sync with git adds multiple json files."""
        from unittest.mock import MagicMock
        import src.common.database as db_module

        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=False,
        )

        # Enable git and mock the repo
        db.use_git = True
        db.repo = MagicMock()
        db.repo_url = "https://github.com/test/repo"
        db.repo_branch = "main"
        db.git_user_name = "testuser"
        db.git_token = "testtoken"

        # Mock git operations
        db.repo.git.status.side_effect = [
            "M db_test.json",  # First call
            "M db_test.json",  # Second call
        ]

        # Mock os.listdir to return multiple json files
        with patch('os.listdir', return_value=['db1.json', 'db2.json', 'db3.json']):
            with patch.object(db_module, 'GIT_ENABLED', True):
                db.sync()

        # Verify all json files were added
        assert db.repo.git.add.call_count == 3

    def test_sync_with_git_push_failure(self, db_init, cleanup_files):
        """Test sync handles git push failures gracefully."""
        from unittest.mock import MagicMock
        import git
        import src.common.database as db_module

        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=False,
        )

        # Enable git and mock the repo
        db.use_git = True
        db.repo = MagicMock()
        db.repo_url = "https://github.com/test/repo"
        db.repo_branch = "main"
        db.git_user_name = "testuser"
        db.git_token = "testtoken"

        # Mock _configure_repo to avoid actual git config operations
        db._configure_repo = MagicMock()

        # Mock git operations - push fails
        db.repo.git.status.side_effect = [
            "M db_test.json",
            "M db_test.json",
        ]
        db.repo.git.push.side_effect = git.exc.GitCommandError("push", "Failed to push")

        with patch('os.listdir', return_value=['db_test.json']):
            with patch.object(db_module, 'GIT_ENABLED', True):
                # Should not raise exception
                db.sync()

        # Verify commit was made but push failed
        db.repo.git.commit.assert_called_once()
        db.repo.git.push.assert_called_once()

    def test_sync_with_git_operation_exception(self, db_init, cleanup_files):
        """Test sync handles general git exceptions gracefully."""
        from unittest.mock import MagicMock
        import src.common.database as db_module

        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=False,
        )

        # Enable git and mock the repo
        db.use_git = True
        db.repo = MagicMock()

        # Mock git status to raise exception
        db.repo.git.status.side_effect = Exception("Git error")

        with patch.object(db_module, 'GIT_ENABLED', True):
            # Should not raise exception
            db.sync()

        # Database should still be usable after error
        with db as tinydb:
            tinydb.insert({'after_error': 'works'})
            assert len(tinydb.all()) >= 1

    def test_sync_with_git_disabled_by_flag(self, db_init, cleanup_files):
        """Test sync with git disabled by GIT_ENABLED flag."""
        from unittest.mock import MagicMock
        import src.common.database as db_module

        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=False,
        )

        # Enable git but disable GIT_ENABLED flag
        db.use_git = True
        db.repo = MagicMock()

        with patch.object(db_module, 'GIT_ENABLED', False):
            db.sync()

        # Verify no git operations were performed
        db.repo.git.status.assert_not_called()

    def test_sync_with_no_json_files(self, db_init, cleanup_files):
        """Test sync with changes but no json files to add."""
        from unittest.mock import MagicMock
        import src.common.database as db_module

        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=False,
        )

        # Enable git and mock the repo
        db.use_git = True
        db.repo = MagicMock()
        db.repo.git.status.return_value = "M some_file.txt"

        # Mock os.listdir to return no json files
        with patch('os.listdir', return_value=['other_file.txt']):
            with patch.object(db_module, 'GIT_ENABLED', True):
                db.sync()

        # Verify no files were added since no json files exist
        db.repo.git.add.assert_not_called()

    def test_sync_with_changes_but_empty_after_add(self, db_init, cleanup_files):
        """Test sync when status shows changes but nothing after git add."""
        from unittest.mock import MagicMock
        import src.common.database as db_module

        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=False,
        )

        # Enable git and mock the repo
        db.use_git = True
        db.repo = MagicMock()

        # Mock git operations - changes initially but nothing after add
        db.repo.git.status.side_effect = [
            "M db_test.json",  # First call - changes exist
            "",  # Second call - nothing to commit after add
        ]

        with patch('os.listdir', return_value=['db_test.json']):
            with patch.object(db_module, 'GIT_ENABLED', True):
                db.sync()

        # Verify add was called but not commit
        db.repo.git.add.assert_called_once()
        db.repo.git.commit.assert_not_called()

    def test_sync_url_split_and_push_url_construction(self, db_init, cleanup_files):
        """Test that sync correctly constructs push URL with credentials."""
        from unittest.mock import MagicMock
        import src.common.database as db_module

        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=False,
        )

        # Enable git and mock the repo
        db.use_git = True
        db.repo = MagicMock()
        db.repo_url = "https://github.com/LizardByte/support-bot-data"
        db.repo_branch = "master"
        db.git_user_name = "myuser"
        db.git_token = "mytoken123"

        # Mock _configure_repo to avoid actual git config operations
        db._configure_repo = MagicMock()

        # Mock git operations
        db.repo.git.status.side_effect = [
            "M db_test.json",
            "M db_test.json",
        ]

        with patch('os.listdir', return_value=['db_test.json']):
            with patch.object(db_module, 'GIT_ENABLED', True):
                db.sync()

        # Verify push was called with correctly formatted URL
        expected_url = "https://myuser:mytoken123@github.com/LizardByte/support-bot-data"  # NOSONAR(S2068) just a test
        db.repo.git.push.assert_called_once_with(expected_url, "master")

    def test_configure_repo_called_during_sync(self, db_init, cleanup_files):
        """Test that _configure_repo is called during sync when committing."""
        from unittest.mock import MagicMock
        import src.common.database as db_module

        db = Database(
            db_name=f'db_{inspect.currentframe().f_code.co_name}',
            db_dir=db_init['db_dir'],
            use_git=False,
        )

        # Enable git and mock the repo
        db.use_git = True
        db.repo = MagicMock()
        db.repo_url = "https://github.com/test/repo"
        db.repo_branch = "main"
        db.git_user_name = "testuser"
        db.git_token = "testtoken"

        # Mock _configure_repo
        configure_repo_called = []

        def mock_configure():
            configure_repo_called.append(True)
            # Don't actually call original to avoid git operations

        db._configure_repo = mock_configure

        # Mock git operations
        db.repo.git.status.side_effect = [
            "M db_test.json",
            "M db_test.json",
        ]

        with patch('os.listdir', return_value=['db_test.json']):
            with patch.object(db_module, 'GIT_ENABLED', True):
                db.sync()

        # Verify _configure_repo was called
        assert len(configure_repo_called) == 1

    def test_init_runs_git_setup_when_enabled(self, tmp_path, mocker):
        git_setup = mocker.patch.object(Database, '_setup_git_repository')

        with patch.dict(os.environ, {'GITHUB_PYTEST': 'false'}):
            db = Database(
                db_name='git_enabled',
                db_dir=tmp_path,
                use_git=True,
            )

        git_setup.assert_called_once()
        db.tinydb.close()

    @staticmethod
    def bare_database(tmp_path):
        db = Database.__new__(Database)
        db.db_name = 'test'
        db.db_dir = str(tmp_path)
        db.repo = MagicMock()
        db.repo_url = 'https://github.com/test/repo'
        db.repo_branch = 'local-test'
        db.git_user_name = 'user'
        db.git_user_email = 'user@example.com'
        db.git_token = 'token'
        db.json_path = os.path.join(str(tmp_path), 'test.json')
        db.shelve_path = os.path.join(str(tmp_path), 'test')
        db.use_git = True
        db.tinydb = None
        return db

    def test_setup_git_repository_uses_existing_repo(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        db._authenticated_repo_url = mocker.Mock(return_value='https://token-url')
        db._open_existing_repo = mocker.Mock()
        db._clone_repo = mocker.Mock()

        with patch.dict(os.environ, {
            'DATA_REPO_BRANCH': 'master',
            'GIT_USER_NAME': 'env-user',
            'GIT_USER_EMAIL': 'env-user@example.com',
            'GIT_TOKEN': 'env-token',
        }):
            with patch('os.path.exists', return_value=True):
                db._setup_git_repository()

        assert db.repo_url == 'https://github.com/LizardByte/support-bot-data'
        assert db.repo_branch == 'master'
        assert db.git_user_name == 'env-user'
        assert db.git_user_email == 'env-user@example.com'
        assert db.git_token == 'env-token'
        db._open_existing_repo.assert_called_once()
        db._clone_repo.assert_not_called()

    def test_setup_git_repository_clones_missing_repo(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        db._authenticated_repo_url = mocker.Mock(return_value='https://token-url')
        db._open_existing_repo = mocker.Mock()
        db._clone_repo = mocker.Mock()

        with patch.dict(os.environ, {
            'DATA_REPO': 'https://example.com/repo',
            'DATA_REPO_BRANCH': 'branch',
            'GIT_USER_NAME': 'env-user',
            'GIT_USER_EMAIL': 'env-user@example.com',
            'GITHUB_TOKEN': 'github-token',
        }, clear=False):
            with patch.dict(os.environ, {'GIT_TOKEN': ''}, clear=False):
                with patch('os.path.exists', return_value=False):
                    db._setup_git_repository()

        assert db.repo_url == 'https://example.com/repo'
        assert db.repo_branch == 'branch'
        assert db.git_token == 'github-token'
        db._clone_repo.assert_called_once_with(clone_url='https://token-url')
        db._open_existing_repo.assert_not_called()

    def test_setup_git_repository_requires_token(self, tmp_path):
        db = self.bare_database(tmp_path)

        with patch.dict(os.environ, {
            'GIT_USER_NAME': 'env-user',
            'GIT_USER_EMAIL': 'env-user@example.com',
            'GIT_TOKEN': '',
            'GITHUB_TOKEN': '',
        }, clear=False):
            with pytest.raises(ValueError, match='GIT_TOKEN or GITHUB_TOKEN'):
                db._setup_git_repository()

    def test_authenticated_repo_url(self, tmp_path):
        db = self.bare_database(tmp_path)

        authenticated_url = db._authenticated_repo_url()

        assert authenticated_url.startswith('https://')
        assert authenticated_url.endswith('@github.com/test/repo')
        assert db.git_user_name in authenticated_url
        assert db.git_token in authenticated_url

    def test_clone_repo_success(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        repo = MagicMock()
        clone_from = mocker.patch('src.common.database.git.Repo.clone_from', return_value=repo)
        db._configure_repo = mocker.Mock()

        db._clone_repo(clone_url='https://token-url')

        clone_from.assert_called_once_with('https://token-url', db.db_dir, branch='local-test')
        assert db.repo is repo
        db._configure_repo.assert_called_once()

    def test_clone_repo_creates_missing_branch(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        repo = MagicMock()
        missing_branch = git.exc.GitCommandError(
            'clone',
            'Remote branch local-test not found in upstream origin',
        )
        mocker.patch('src.common.database.git.Repo.clone_from', side_effect=[missing_branch, repo])
        db._configure_repo = mocker.Mock()
        db._initialize_orphan_branch = mocker.Mock()
        db._push_new_branch = mocker.Mock()

        db._clone_repo(clone_url='https://token-url')

        assert db.repo is repo
        assert db._configure_repo.call_count == 1
        db._initialize_orphan_branch.assert_called_once_with(clean_worktree=True)
        db._push_new_branch.assert_called_once_with(log_errors=True)

    def test_clone_repo_reraises_unexpected_error(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        clone_error = git.exc.GitCommandError('clone', 'different failure')
        mocker.patch('src.common.database.git.Repo.clone_from', side_effect=clone_error)

        with pytest.raises(git.exc.GitCommandError):
            db._clone_repo(clone_url='https://token-url')

    def test_open_existing_repo_checks_out_local_branch(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        repo = MagicMock()
        mocker.patch('src.common.database.git.Repo', return_value=repo)
        db._configure_repo = mocker.Mock()
        db._has_local_branch = mocker.Mock(return_value=True)
        db._checkout_or_create_branch = mocker.Mock()

        db._open_existing_repo()

        assert db.repo is repo
        repo.git.checkout.assert_called_once_with('local-test')
        db._checkout_or_create_branch.assert_not_called()

    def test_open_existing_repo_creates_missing_branch(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        repo = MagicMock()
        mocker.patch('src.common.database.git.Repo', return_value=repo)
        db._configure_repo = mocker.Mock()
        db._has_local_branch = mocker.Mock(return_value=False)
        db._checkout_or_create_branch = mocker.Mock()

        db._open_existing_repo()

        db._checkout_or_create_branch.assert_called_once()

    def test_checkout_or_create_branch_uses_remote_branch(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        db._has_remote_branch = mocker.Mock(return_value=True)
        db._initialize_orphan_branch = mocker.Mock()
        db._push_new_branch = mocker.Mock()

        db._checkout_or_create_branch()

        db.repo.git.fetch.assert_called_once_with('origin')
        db.repo.git.checkout.assert_called_once_with('local-test')
        db._initialize_orphan_branch.assert_not_called()

    def test_checkout_or_create_branch_initializes_orphan(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        db._has_remote_branch = mocker.Mock(return_value=False)
        db._initialize_orphan_branch = mocker.Mock()
        db._push_new_branch = mocker.Mock()

        db._checkout_or_create_branch()

        db._initialize_orphan_branch.assert_called_once_with(clean_worktree=False)
        db._push_new_branch.assert_called_once_with(log_errors=False)

    def test_checkout_or_create_branch_warns_on_git_error(self, tmp_path):
        db = self.bare_database(tmp_path)
        db.repo.git.fetch.side_effect = git.exc.GitCommandError('fetch', 'failed')

        db._checkout_or_create_branch()

    def test_branch_detection_helpers(self, tmp_path):
        db = self.bare_database(tmp_path)
        db.repo.refs = [
            SimpleNamespace(name='refs/heads/main'),
            SimpleNamespace(name='refs/heads/local-test'),
        ]
        db.repo.remote.return_value.refs = [
            SimpleNamespace(name='origin/main'),
            SimpleNamespace(name='origin/local-test'),
        ]

        assert db._has_local_branch() is True
        assert db._has_remote_branch() is True
        assert Database._is_missing_remote_branch(
            git.exc.GitCommandError('clone', 'Remote branch x not found in upstream origin')
        ) is True
        assert Database._is_missing_remote_branch(git.exc.GitCommandError('clone', 'different')) is False

    def test_initialize_orphan_branch_cleans_worktree_when_requested(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        db._clear_repo_index = mocker.Mock()
        db._clear_data_repo_worktree = mocker.Mock()
        db._commit_gitkeep = mocker.Mock()

        db._initialize_orphan_branch(clean_worktree=True)

        db.repo.git.checkout.assert_called_once_with('--orphan', 'local-test')
        db._clear_repo_index.assert_called_once()
        db._clear_data_repo_worktree.assert_called_once()
        db._commit_gitkeep.assert_called_once()

    def test_initialize_orphan_branch_can_keep_worktree(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        db._clear_repo_index = mocker.Mock()
        db._clear_data_repo_worktree = mocker.Mock()
        db._commit_gitkeep = mocker.Mock()

        db._initialize_orphan_branch(clean_worktree=False)

        db._clear_data_repo_worktree.assert_not_called()

    def test_clear_repo_index_handles_empty_index(self, tmp_path):
        db = self.bare_database(tmp_path)
        db.repo.git.rm.side_effect = git.exc.GitCommandError('rm', 'empty')

        db._clear_repo_index()

    def test_clear_data_repo_worktree_removes_only_non_git_items(self, tmp_path):
        db = self.bare_database(tmp_path)
        git_dir = tmp_path / '.git'
        data_dir = tmp_path / 'nested'
        data_file = tmp_path / 'data.json'
        git_dir.mkdir()
        data_dir.mkdir()
        data_file.write_text('{}')

        db._clear_data_repo_worktree()

        assert git_dir.exists()
        assert not data_dir.exists()
        assert not data_file.exists()

    def test_commit_gitkeep(self, tmp_path):
        db = self.bare_database(tmp_path)

        db._commit_gitkeep()

        gitkeep_path = tmp_path / '.gitkeep'
        assert gitkeep_path.exists()
        db.repo.git.add.assert_called_once_with(str(gitkeep_path))
        db.repo.git.commit.assert_called_once_with('-m', "Initialize empty branch 'local-test'")

    def test_push_new_branch_success(self, tmp_path):
        db = self.bare_database(tmp_path)

        db._push_new_branch(log_errors=True)

        db.repo.git.push.assert_called_once_with('--set-upstream', 'origin', 'local-test')

    def test_push_new_branch_logs_or_raises_errors(self, tmp_path):
        db = self.bare_database(tmp_path)
        db.repo.git.push.side_effect = git.exc.GitCommandError('push', 'failed')

        db._push_new_branch(log_errors=True)

        with pytest.raises(git.exc.GitCommandError):
            db._push_new_branch(log_errors=False)

    def test_migrate_shelve_tables_skips_invalid_collections(self, tmp_path):
        db = self.bare_database(tmp_path)
        migration_db = MagicMock()
        shelve_db = {
            'metadata': 'not records',
            'bad_keys': {1: {'value': 'bad'}},
            'comments': {
                'abc': {'body': 'hello'},
                'ignored': 'not a record',
            },
        }

        db._migrate_shelve_tables(migration_db=migration_db, shelve_db=shelve_db, is_reddit_db=True)

        migration_db.table.assert_called_once_with('comments')
        table = migration_db.table.return_value
        assert table.insert.call_count == 1

    def test_insert_migrated_record_handles_non_reddit_and_non_dict(self, tmp_path):
        db = self.bare_database(tmp_path)
        table = MagicMock()

        db._insert_migrated_record(table=table, record_id='ignored', record_data='not dict', is_reddit_db=False)
        db._insert_migrated_record(table=table, record_id='abc', record_data={'value': 1}, is_reddit_db=False)

        table.insert.assert_called_once_with({'value': 1, 'id': 'abc'})

    def test_simplify_reddit_records(self, tmp_path):
        db = self.bare_database(tmp_path)

        comment = db._simplify_reddit_record(record_id='comment-id', record_data={'body': 'hello'})
        submission = db._simplify_reddit_record(record_id='submission-id', record_data={'title': 'Title'})

        assert comment == {
            'reddit_id': 'comment-id',
            'author': None,
            'body': 'hello',
            'created_utc': 0,
            'processed': False,
            'slash_command': {'project': None, 'command': None},
        }
        assert submission['reddit_id'] == 'submission-id'
        assert submission['title'] == 'Title'
        assert submission['bot_discord'] == {'sent': False, 'sent_utc': None}

    def test_sync_git_repo_skips_or_logs_errors(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        db._should_sync_git = mocker.Mock(return_value=False)
        db._commit_and_push_changes = mocker.Mock()

        db._sync_git_repo()

        db._commit_and_push_changes.assert_not_called()

        db._should_sync_git.return_value = True
        db._commit_and_push_changes.side_effect = Exception('boom')
        db._sync_git_repo()

    def test_commit_and_push_changes_paths(self, tmp_path, mocker):
        db = self.bare_database(tmp_path)
        db._json_files_to_sync = mocker.Mock(return_value=[])
        db._configure_repo = mocker.Mock()
        db._push_database_changes = mocker.Mock()
        db.repo.git.status.return_value = ''

        db._commit_and_push_changes()

        db._json_files_to_sync.assert_not_called()

        db.repo.git.status.return_value = 'M other.txt'
        db._commit_and_push_changes()

        db._configure_repo.assert_not_called()

        json_file = os.path.join(str(tmp_path), 'test.json')
        db._json_files_to_sync.return_value = [json_file]
        db.repo.git.status.side_effect = ['M test.json', 'M test.json']
        db._commit_and_push_changes()

        db.repo.git.add.assert_called_once_with(json_file)
        db._configure_repo.assert_called_once()
        db.repo.git.commit.assert_called_once_with('-m', 'Update database files')
        db._push_database_changes.assert_called_once()

    def test_json_files_to_sync(self, tmp_path):
        db = self.bare_database(tmp_path)
        (tmp_path / 'one.json').write_text('{}')
        (tmp_path / 'two.txt').write_text('skip')

        assert db._json_files_to_sync() == [os.path.join(str(tmp_path), 'one.json')]

    def test_push_database_changes_success_and_failure(self, tmp_path):
        db = self.bare_database(tmp_path)

        db._push_database_changes()

        db.repo.git.push.assert_called_once_with(db._authenticated_repo_url(), 'local-test')

        db.repo.git.push.side_effect = git.exc.GitCommandError('push', 'failed')
        db._push_database_changes()

    def test_open_tinydb(self, tmp_path):
        db = self.bare_database(tmp_path)
        tinydb = db._open_tinydb()

        try:
            tinydb.insert({'value': 1})
            assert tinydb.all() == [{'value': 1}]
        finally:
            tinydb.close()
