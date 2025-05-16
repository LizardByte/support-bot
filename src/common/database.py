# standard imports
import os
from pathlib import Path
import shelve
import threading
import traceback
from typing import Union

# lib imports
import git
from tinydb import TinyDB
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

# local imports
from src.common.common import data_dir

# Constants
DATA_REPO_LOCK = threading.Lock()


class Database:
    def __init__(self, db_name: str, db_dir: Union[str, Path] = data_dir, use_git: bool = True):
        self.db_name = db_name
        self.db_dir = db_dir

        # Check for CI environment
        is_ci = os.environ.get('GITHUB_PYTEST', '').lower() == 'true'

        self.use_git = use_git and not is_ci

        self.repo_url = None
        self.repo_branch = None
        if self.use_git:
            self.repo_url = os.getenv("DATA_REPO", "https://github.com/LizardByte/support-bot-data")
            self.repo_branch = os.getenv("DATA_REPO_BRANCH", "master")
            self.db_dir = os.path.join(self.db_dir, "support-bot-data")

            if not os.path.exists(self.db_dir):
                # Clone repo if it doesn't exist
                print(f"Cloning repository {self.repo_url} to {self.db_dir}")
                try:
                    # Try cloning with the specified branch
                    self.repo = git.Repo.clone_from(self.repo_url, self.db_dir, branch=self.repo_branch)
                except git.exc.GitCommandError as e:
                    # Check if the error is due to branch not found
                    if "Remote branch" in str(e) and "not found in upstream origin" in str(e):
                        print(f"Branch '{self.repo_branch}' not found in remote. Creating a new empty branch.")
                        # Clone with default branch first
                        self.repo = git.Repo.clone_from(self.repo_url, self.db_dir)

                        # Create a new orphan branch (not based on any other branch)
                        self.repo.git.checkout('--orphan', self.repo_branch)

                        # Clear the index and working tree
                        try:
                            self.repo.git.rm('-rf', '.', '--cached')
                        except git.exc.GitCommandError:
                            # This might fail if there are no files yet, which is fine
                            pass

                        # Remove all files in the directory except .git
                        for item in os.listdir(self.db_dir):
                            if item != '.git':
                                item_path = os.path.join(self.db_dir, item)
                                if os.path.isdir(item_path):
                                    import shutil
                                    shutil.rmtree(item_path)
                                else:
                                    os.remove(item_path)

                        # Create empty .gitkeep file to ensure the branch can be committed
                        gitkeep_path = os.path.join(self.db_dir, '.gitkeep')
                        with open(gitkeep_path, 'w'):
                            pass

                        # Add and commit the .gitkeep file
                        self.repo.git.add(gitkeep_path)
                        self.repo.git.commit('-m', f"Initialize empty branch '{self.repo_branch}'")

                        # Push the new branch to remote
                        try:
                            self.repo.git.push('--set-upstream', 'origin', self.repo_branch)
                            print(f"Created and pushed new empty branch '{self.repo_branch}'")
                        except git.exc.GitCommandError as e:
                            print(f"Failed to push new branch: {str(e)}")
                            # Continue anyway - we might not have push permissions
                    else:
                        # Re-raise if it's a different error
                        raise
            else:
                # Use existing repo
                self.repo = git.Repo(self.db_dir)

                # Make sure the correct branch is checked out
                if self.repo_branch not in [ref.name.split('/')[-1] for ref in self.repo.refs]:
                    # Branch doesn't exist locally, check if it exists remotely
                    try:
                        self.repo.git.fetch('origin')
                        remote_branches = [ref.name.split('/')[-1] for ref in self.repo.remote().refs]

                        if self.repo_branch in remote_branches:
                            # Checkout existing remote branch
                            self.repo.git.checkout(self.repo_branch)
                        else:
                            # Create new orphan branch
                            self.repo.git.checkout('--orphan', self.repo_branch)
                            self.repo.git.rm('-rf', '.', '--cached')

                            # Create empty .gitkeep file
                            gitkeep_path = os.path.join(self.db_dir, '.gitkeep')
                            with open(gitkeep_path, 'w'):
                                pass

                            self.repo.git.add(gitkeep_path)
                            self.repo.git.commit('-m', f"Initialize empty branch '{self.repo_branch}'")
                            self.repo.git.push('--set-upstream', 'origin', self.repo_branch)
                            print(f"Created and pushed new empty branch '{self.repo_branch}'")
                    except git.exc.GitCommandError:
                        print(f"Failed to work with branch '{self.repo_branch}'. Using current branch instead.")
                else:
                    # Branch exists locally, make sure it's checked out
                    self.repo.git.checkout(self.repo_branch)

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

    def _check_for_migration(self):
        # Check if migration is needed (shelve exists but json doesn't)
        # No extension is used on Linux
        shelve_exists = os.path.exists(f"{self.shelve_path}.dat") or os.path.exists(self.shelve_path)
        json_exists = os.path.exists(self.json_path)

        if shelve_exists and not json_exists:
            print(f"Migrating database from shelve to TinyDB: {self.shelve_path}")
            self._migrate_from_shelve()

    def _migrate_from_shelve(self):
        try:
            # Create a temporary database just for migration
            migration_db = TinyDB(
                self.json_path,
                storage=CachingMiddleware(JSONStorage),
                indent=4,
            )

            # Determine if this is the Reddit database
            is_reddit_db = "reddit_bot" in self.db_name

            # Open the shelve database
            with shelve.open(self.shelve_path) as shelve_db:
                # Process each key in the shelve database
                for key in shelve_db.keys():
                    value = shelve_db[key]

                    # If value is a dict and looks like a collection of records
                    if isinstance(value, dict) and all(isinstance(k, str) for k in value.keys()):
                        table = migration_db.table(key)

                        # Insert each record into TinyDB with proper fields
                        for record_id, record_data in value.items():
                            if isinstance(record_data, dict):
                                if is_reddit_db:
                                    # Check if it's a comment or submission
                                    is_comment = 'body' in record_data

                                    if is_comment:
                                        # For comments
                                        simplified_record = {
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
                                    else:
                                        # For submissions
                                        simplified_record = {
                                            'reddit_id': record_data.get('id', record_id),
                                            'title': record_data.get('title'),
                                            'selftext': record_data.get('selftext'),
                                            'author': str(record_data.get('author')),
                                            'created_utc': record_data.get('created_utc', 0),
                                            'permalink': record_data.get('permalink'),
                                            'url': record_data.get('url'),
                                            'link_flair_text': record_data.get('link_flair_text'),
                                            'link_flair_background_color': record_data.get(
                                                'link_flair_background_color'),
                                            'bot_discord': record_data.get('bot_discord', {
                                                'sent': False,
                                                'sent_utc': None,
                                            }),
                                        }

                                    table.insert(simplified_record)
                                else:
                                    # Non-Reddit databases keep original structure
                                    record_data['id'] = record_id
                                    table.insert(record_data)

                # Flush changes to disk
                migration_db.storage.flush()
                migration_db.close()

            print(f"Migration completed successfully: {self.json_path}")
        except Exception as e:
            print(f"Migration failed: {str(e)}")
            traceback.print_exc()

    def __enter__(self):
        self.lock.acquire()
        return self.tinydb

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sync()
        self.lock.release()

    def sync(self):
        # Only call flush if using CachingMiddleware
        if hasattr(self.tinydb.storage, 'flush'):
            self.tinydb.storage.flush()

        # Git operations - commit and push changes if using git
        with DATA_REPO_LOCK:
            if self.use_git and self.repo is not None:
                try:
                    # Check for untracked database files and tracked files with changes
                    status = self.repo.git.status('--porcelain')

                    # If there are any changes or untracked files
                    if status:
                        # Add ALL json files in the directory to ensure we track all databases
                        json_files = [f for f in os.listdir(self.db_dir) if f.endswith('.json')]
                        if json_files:
                            for json_file in json_files:
                                file_path = os.path.join(self.db_dir, json_file)
                                self.repo.git.add(file_path)

                        # Check if we have anything to commit after adding
                        if self.repo.git.status('--porcelain'):
                            # Commit all changes at once with a general message
                            commit_message = "Update database files"
                            self.repo.git.commit('-m', commit_message)
                            print("Committed changes to git data repository")

                            # Push to remote
                            try:
                                origin = self.repo.remote('origin')
                                origin.push()
                                print("Pushed changes to remote git data repository")
                            except git.exc.GitCommandError as e:
                                print(f"Failed to push changes: {str(e)}")

                except Exception as e:
                    print(f"Git operation failed: {str(e)}")
                    traceback.print_exc()
