import unittest
import asyncio
import tempfile
import os
import aiosqlite
from mutt.storage.database import Database
from mutt.storage.auth_failure_tracker import AuthFailureTracker


class TestAuthFailureTracker(unittest.IsolatedAsyncioTestCase):
    """Test AuthFailureTracker class."""

    async def asyncSetUp(self):
        """Set up test database and tracker."""
        # Create a temporary directory and database file
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')

        # Initialize database and tracker
        self.database = Database(self.db_path)
        await self.database.initialize()
        self.tracker = AuthFailureTracker(self.database)

    async def asyncTearDown(self):
        """Clean up test database."""
        if self.database.connection:
            await self.database.connection.close()

        # Clean up temporary directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    async def test_record_failure_new_user(self):
        """Test recording a failure for a new user."""
        await self.tracker.record_failure('testuser', 'testhost')

        # Verify the failure was recorded
        failures = await self.tracker.get_all_failures()
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['username'], 'testuser')
        self.assertEqual(failures[0]['hostname'], 'testhost')
        self.assertEqual(failures[0]['num_failures'], 1)
        self.assertIsNotNone(failures[0]['last_failure'])

    async def test_record_failure_existing_user(self):
        """Test recording multiple failures for the same user."""
        # Record first failure
        await self.tracker.record_failure('user1', 'host1')

        # Record second failure
        await self.tracker.record_failure('user1', 'host2')

        # Verify the count incremented
        failures = await self.tracker.get_all_failures()
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['username'], 'user1')
        self.assertEqual(failures[0]['num_failures'], 2)
        # Hostname should be updated to the latest
        self.assertEqual(failures[0]['hostname'], 'host2')

    async def test_record_failure_multiple_users(self):
        """Test recording failures for multiple different users."""
        await self.tracker.record_failure('user1', 'host1')
        await self.tracker.record_failure('user2', 'host2')
        await self.tracker.record_failure('user3', 'host3')

        failures = await self.tracker.get_all_failures()
        self.assertEqual(len(failures), 3)

        usernames = {f['username'] for f in failures}
        self.assertEqual(usernames, {'user1', 'user2', 'user3'})

    async def test_record_failure_increment_count(self):
        """Test that failure count increments correctly."""
        username = 'incrementuser'

        # Record 5 failures
        for i in range(5):
            await self.tracker.record_failure(username, f'host{i}')

        failures = await self.tracker.get_all_failures()
        user_failure = next(f for f in failures if f['username'] == username)

        self.assertEqual(user_failure['num_failures'], 5)

    async def test_clear_failure(self):
        """Test clearing failures for a specific user."""
        # Record failures for multiple users
        await self.tracker.record_failure('user1', 'host1')
        await self.tracker.record_failure('user2', 'host2')

        # Clear failures for user1
        await self.tracker.clear_failure('user1')

        # Verify only user2 remains
        failures = await self.tracker.get_all_failures()
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['username'], 'user2')

    async def test_clear_failure_nonexistent_user(self):
        """Test clearing failures for a user that doesn't exist."""
        # Should not raise an exception
        await self.tracker.clear_failure('nonexistent')

        failures = await self.tracker.get_all_failures()
        self.assertEqual(len(failures), 0)

    async def test_get_all_failures_empty(self):
        """Test getting all failures when there are none."""
        failures = await self.tracker.get_all_failures()
        self.assertEqual(len(failures), 0)
        self.assertIsInstance(failures, list)

    async def test_get_all_failures_sorted_by_count(self):
        """Test that failures are sorted by count (descending)."""
        # Record different numbers of failures for each user
        await self.tracker.record_failure('user_low', 'host1')

        await self.tracker.record_failure('user_high', 'host2')
        await self.tracker.record_failure('user_high', 'host2')
        await self.tracker.record_failure('user_high', 'host2')
        await self.tracker.record_failure('user_high', 'host2')
        await self.tracker.record_failure('user_high', 'host2')

        await self.tracker.record_failure('user_medium', 'host3')
        await self.tracker.record_failure('user_medium', 'host3')
        await self.tracker.record_failure('user_medium', 'host3')

        failures = await self.tracker.get_all_failures()

        # Should be sorted: user_high (5), user_medium (3), user_low (1)
        self.assertEqual(failures[0]['username'], 'user_high')
        self.assertEqual(failures[0]['num_failures'], 5)
        self.assertEqual(failures[1]['username'], 'user_medium')
        self.assertEqual(failures[1]['num_failures'], 3)
        self.assertEqual(failures[2]['username'], 'user_low')
        self.assertEqual(failures[2]['num_failures'], 1)

    async def test_record_failure_updates_hostname(self):
        """Test that recording failure updates the hostname to the latest."""
        username = 'testuser'

        # Record failures from different hosts
        await self.tracker.record_failure(username, 'host1')
        failures = await self.tracker.get_all_failures()
        self.assertEqual(failures[0]['hostname'], 'host1')

        await self.tracker.record_failure(username, 'host2')
        failures = await self.tracker.get_all_failures()
        self.assertEqual(failures[0]['hostname'], 'host2')

        await self.tracker.record_failure(username, 'host3')
        failures = await self.tracker.get_all_failures()
        self.assertEqual(failures[0]['hostname'], 'host3')

    async def test_record_failure_updates_timestamp(self):
        """Test that recording failure updates the timestamp."""
        username = 'timeuser'

        # Record first failure
        await self.tracker.record_failure(username, 'host1')
        failures = await self.tracker.get_all_failures()
        first_timestamp = failures[0]['last_failure']

        # Wait a tiny bit
        await asyncio.sleep(0.01)

        # Record second failure
        await self.tracker.record_failure(username, 'host1')
        failures = await self.tracker.get_all_failures()
        second_timestamp = failures[0]['last_failure']

        # Timestamps should be different
        self.assertNotEqual(first_timestamp, second_timestamp)

    async def test_tracker_integration_with_database(self):
        """Test that tracker properly integrates with the database."""
        # Record some failures
        await self.tracker.record_failure('integuser', 'integhost')

        # Query the database directly to verify
        query = "SELECT username, hostname, num_failures FROM snmpv3_auth_failures WHERE username = ?"
        cursor = await self.database.execute(query, ('integuser',))
        row = await cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], 'integuser')
        self.assertEqual(row[1], 'integhost')
        self.assertEqual(row[2], 1)

    async def test_clear_all_and_re_record(self):
        """Test clearing a user and then recording again."""
        username = 'clearuser'

        # Record failures
        await self.tracker.record_failure(username, 'host1')
        await self.tracker.record_failure(username, 'host1')

        failures = await self.tracker.get_all_failures()
        self.assertEqual(failures[0]['num_failures'], 2)

        # Clear the user
        await self.tracker.clear_failure(username)
        failures = await self.tracker.get_all_failures()
        self.assertEqual(len(failures), 0)

        # Record a new failure for the same user
        await self.tracker.record_failure(username, 'host2')
        failures = await self.tracker.get_all_failures()

        # Should start at 1 again
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['num_failures'], 1)
        self.assertEqual(failures[0]['hostname'], 'host2')


if __name__ == '__main__':
    unittest.main()
