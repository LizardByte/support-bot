# standard imports
import logging
import os
from pathlib import Path
import shelve
import shutil
import threading
from typing import Union

# lib imports
import git
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

# local imports
from src.common.common import data_dir

# Get logger for this module
logger = logging.getLogger(__name__)

# Constants
DATA_REPO_LOCK = threading.Lock()
GIT_ENABLED = True  # disable to pause pushing to git, useful for heavy db operations


class Database:
    def __init__(self, db_name: str, db_dir: Union[str, Path] = data_dir, use_git: bool = True):
        self.db_name = db_name
        self.db_dir = db_dir
        self.repo = None

        # Check for CI environment
        is_ci = os.environ.get('GITHUB_PYTEST', '').lower() == 'true'

        self.use_git = use_git and not is_ci

        self.repo_url = None
        self.repo_branch = None
        if self.use_git:
            self._setup_git_repository()

        self.json_path = os.path.join(self.db_dir, f"{self.db_name}.json")
        self.shelve_path = os.path.join(db_dir, self.db_name)  # Shelve adds its own extensions
        self.lock = threading.Lock()

        # Check if migration is needed before creating TinyDB instance
        self._check_for_migration()

        # Initialize the TinyDB instance with CachingMiddleware
        self.tinydb = TinyDB(
            self.json_path,
            storage=CachingMiddleware(JSONStorage),
            indent=4,
        )

    def _setup_git_repository(self):
        """Initialize or open the backing git repository used for database persistence."""
        self.repo_url = os.getenv("DATA_REPO", "https://github.com/LizardByte/support-bot-data")
        self.repo_branch = os.getenv("DATA_REPO_BRANCH", "master")
        self.db_dir = os.path.join(self.db_dir, "support-bot-data")

        # Get Git user configuration from environment variables
        self.git_user_name = os.environ["GIT_USER_NAME"]
        self.git_user_email = os.environ["GIT_USER_EMAIL"]

        # Git credentials for authentication (required for private repo)
        self.git_token = os.getenv("GIT_TOKEN") or os.getenv("GITHUB_TOKEN")
        if not self.git_token:
            raise ValueError("GIT_TOKEN or GITHUB_TOKEN must be provided for private repository access")

        clone_url = self._authenticated_repo_url()
        if os.path.exists(self.db_dir):
            self._open_existing_repo()
        else:
            self._clone_repo(clone_url=clone_url)

    def _authenticated_repo_url(self) -> str:
        """Build a repository URL with credentials for private repo access."""
        protocol, repo_path = self.repo_url.split("://", 1)
        return f"{protocol}://{self.git_user_name}:{self.git_token}@{repo_path}"

    def _clone_repo(self, clone_url: str):
        logger.info(f"Cloning repository {self.repo_url} to {self.db_dir}")
        try:
            self.repo = git.Repo.clone_from(clone_url, self.db_dir, branch=self.repo_branch)
            self._configure_repo()
        except git.exc.GitCommandError as e:
            if not self._is_missing_remote_branch(error=e):
                raise

            logger.info(f"Branch '{self.repo_branch}' not found in remote. Creating a new empty branch.")
            self.repo = git.Repo.clone_from(clone_url, self.db_dir)
            self._configure_repo()
            self._initialize_orphan_branch(clean_worktree=True)
            self._push_new_branch(log_errors=True)

    def _open_existing_repo(self):
        self.repo = git.Repo(self.db_dir)
        self._configure_repo()

        if self._has_local_branch():
            self.repo.git.checkout(self.repo_branch)
            return

        self._checkout_or_create_branch()

    def _checkout_or_create_branch(self):
        try:
            self.repo.git.fetch('origin')
            if self._has_remote_branch():
                self.repo.git.checkout(self.repo_branch)
                return

            self._initialize_orphan_branch(clean_worktree=False)
            self._push_new_branch(log_errors=False)
        except git.exc.GitCommandError:
            logger.warning(f"Failed to work with branch '{self.repo_branch}'. Using current branch instead.")

    @staticmethod
    def _is_missing_remote_branch(error: git.exc.GitCommandError) -> bool:
        error_message = str(error)
        return "Remote branch" in error_message and "not found in upstream origin" in error_message

    def _has_local_branch(self) -> bool:
        local_branches = [ref.name.split('/')[-1] for ref in self.repo.refs]
        return self.repo_branch in local_branches

    def _has_remote_branch(self) -> bool:
        remote_branches = [ref.name.split('/')[-1] for ref in self.repo.remote().refs]
        return self.repo_branch in remote_branches

    def _initialize_orphan_branch(self, clean_worktree: bool):
        self.repo.git.checkout('--orphan', self.repo_branch)
        self._clear_repo_index()

        if clean_worktree:
            self._clear_data_repo_worktree()

        self._commit_gitkeep()

    def _clear_repo_index(self):
        try:
            self.repo.git.rm('-rf', '.', '--cached')
        except git.exc.GitCommandError:
            logger.debug("No tracked files to remove from the new branch index")

    def _clear_data_repo_worktree(self):
        for item in Path(self.db_dir).iterdir():
            if item.name == '.git':
                continue

            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    def _commit_gitkeep(self):
        gitkeep_path = os.path.join(self.db_dir, '.gitkeep')
        Path(gitkeep_path).touch()
        self.repo.git.add(gitkeep_path)
        self.repo.git.commit('-m', f"Initialize empty branch '{self.repo_branch}'")

    def _push_new_branch(self, log_errors: bool):
        try:
            self.repo.git.push('--set-upstream', 'origin', self.repo_branch)
            logger.info(f"Created and pushed new empty branch '{self.repo_branch}'")
        except git.exc.GitCommandError:
            if log_errors:
                logger.exception("Failed to push new branch")
            else:
                raise

    def _configure_repo(self):
        """Configure the Git repository with user identity from environment variables."""
        if self.repo:
            with self.repo.config_writer() as config:
                # Set user name and email for this repository
                config.set_value("user", "name", self.git_user_name)
                config.set_value("user", "email", self.git_user_email)

                # Configure credentials for private repo access
                domain = self.repo_url.split("://")[-1].split("/")[0]

                # Set credential store helper
                config.set_value("credential", "helper", "store")

                # Set credential helper specific to this domain
                if self.git_user_name and self.git_token:
                    config.set_value(f"credential \"{domain}\"", "username", self.git_user_name)

            # Update origin URL with credentials to ensure push works
            protocol, repo_path = self.repo_url.split("://", 1)
            new_url = f"{protocol}://{self.git_user_name}:{self.git_token}@{repo_path}"
            try:
                origin = self.repo.remote('origin')
                origin.set_url(new_url)
            except git.exc.GitCommandError:
                logger.exception("Failed to update remote URL")
                # Continue anyway, might work with stored credentials

    def _check_for_migration(self):
        # Check if migration is needed (shelve exists but json doesn't)
        # No extension is used on Linux
        shelve_exists = os.path.exists(f"{self.shelve_path}.dat") or os.path.exists(self.shelve_path)
        json_exists = os.path.exists(self.json_path)

        if shelve_exists and not json_exists:
            logger.info(f"Migrating database from shelve to TinyDB: {self.shelve_path}")
            self._migrate_from_shelve()

    def _migrate_from_shelve(self):
        try:
            # Create a temporary database just for migration
            migration_db = self._open_tinydb()

            # Determine if this is the Reddit database
            is_reddit_db = "reddit_bot" in self.db_name

            # Open the shelve database
            with shelve.open(self.shelve_path) as shelve_db:
                self._migrate_shelve_tables(
                    migration_db=migration_db,
                    shelve_db=shelve_db,
                    is_reddit_db=is_reddit_db,
                )

                # Flush changes to disk
                migration_db.storage.flush()
                migration_db.close()

            logger.info(f"Migration completed successfully: {self.json_path}")
        except Exception:
            logger.exception("Migration failed")

    def _migrate_shelve_tables(self, migration_db: TinyDB, shelve_db: shelve.Shelf, is_reddit_db: bool):
        # Process each key in the shelve database
        for key in shelve_db.keys():
            value = shelve_db[key]

            # If value is a dict and looks like a collection of records
            if not self._is_record_collection(value=value):
                continue

            table = migration_db.table(key)
            for record_id, record_data in value.items():
                self._insert_migrated_record(
                    table=table,
                    record_id=record_id,
                    record_data=record_data,
                    is_reddit_db=is_reddit_db,
                )

    @staticmethod
    def _is_record_collection(value) -> bool:
        return isinstance(value, dict) and all(isinstance(k, str) for k in value.keys())

    def _insert_migrated_record(self, table, record_id: str, record_data: dict, is_reddit_db: bool):
        if not isinstance(record_data, dict):
            return

        if is_reddit_db:
            table.insert(self._simplify_reddit_record(record_id=record_id, record_data=record_data))
            return

        # Non-Reddit databases keep original structure
        record_data['id'] = record_id
        table.insert(record_data)

    def _simplify_reddit_record(self, record_id: str, record_data: dict) -> dict:
        if 'body' in record_data:
            return self._simplify_reddit_comment(record_id=record_id, record_data=record_data)

        return self._simplify_reddit_submission(record_id=record_id, record_data=record_data)

    @staticmethod
    def _simplify_reddit_comment(record_id: str, record_data: dict) -> dict:
        return {
            'reddit_id': record_data.get('id', record_id),
            'author': record_data.get('author'),
            'body': record_data.get('body'),
            'created_utc': record_data.get('created_utc', 0),
            'processed': record_data.get('processed', False),
            'slash_command': record_data.get('slash_command', {
                'project': None,
                'command': None,
            }),
        }

    @staticmethod
    def _simplify_reddit_submission(record_id: str, record_data: dict) -> dict:
        return {
            'reddit_id': record_data.get('id', record_id),
            'title': record_data.get('title'),
            'selftext': record_data.get('selftext'),
            'author': str(record_data.get('author')),
            'created_utc': record_data.get('created_utc', 0),
            'permalink': record_data.get('permalink'),
            'url': record_data.get('url'),
            'link_flair_text': record_data.get('link_flair_text'),
            'link_flair_background_color': record_data.get('link_flair_background_color'),
            'bot_discord': record_data.get('bot_discord', {
                'sent': False,
                'sent_utc': None,
            }),
        }

    def __enter__(self):
        self.lock.acquire()
        return self.tinydb

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.sync()
        finally:
            self.lock.release()

    def sync(self):
        try:
            # Flush changes to disk if possible
            self._close_tinydb_for_sync()

            # Git operations with closed file
            self._sync_git_repo()
        finally:
            # Ensure database is ready for next use
            if self.tinydb is None:
                self.tinydb = self._open_tinydb()

    def _close_tinydb_for_sync(self):
        if self.tinydb and hasattr(self.tinydb.storage, 'flush'):
            self.tinydb.storage.flush()

        # Close the database to ensure file is available for Git operations
        if self.tinydb is not None:
            self.tinydb.close()
            self.tinydb = None

    def _sync_git_repo(self):
        with DATA_REPO_LOCK:
            if not self._should_sync_git():
                return

            try:
                self._commit_and_push_changes()
            except Exception:
                logger.exception("Git operation failed")

    def _should_sync_git(self) -> bool:
        return self.use_git and self.repo is not None and GIT_ENABLED

    def _commit_and_push_changes(self):
        # Check for untracked database files and tracked files with changes
        if not self.repo.git.status('--porcelain'):
            return

        # Add ALL json files in the directory to ensure we track all databases
        json_files = self._json_files_to_sync()
        for file_path in json_files:
            self.repo.git.add(file_path)

        if not json_files or not self.repo.git.status('--porcelain'):
            return

        # Ensure the repository is configured with user identity
        self._configure_repo()

        # Commit all changes at once with a general message
        self.repo.git.commit('-m', "Update database files")
        logger.info("Committed changes to git data repository")
        self._push_database_changes()

    def _json_files_to_sync(self) -> list[str]:
        return [
            os.path.join(self.db_dir, json_file)
            for json_file in os.listdir(self.db_dir)
            if json_file.endswith('.json')
        ]

    def _push_database_changes(self):
        try:
            push_url = self._authenticated_repo_url()
            self.repo.git.push(push_url, self.repo_branch)
            logger.info("Pushed changes to remote git data repository")
        except git.exc.GitCommandError:
            logger.exception("Failed to push changes")

    def _open_tinydb(self) -> TinyDB:
        return TinyDB(
            self.json_path,
            storage=CachingMiddleware(JSONStorage),
            indent=4,
        )

    @staticmethod
    def query():
        """
        Get the TinyDB Query object for constructing database queries.

        This is a helper method to avoid importing the Query class directly
        in modules that use the Database class.

        Returns
        -------
        Query
            A TinyDB Query object for constructing queries.
        """
        return Query()
