import os
import sys
import pytest
from dotenv import load_dotenv
from src.database.db import BotDB
from src.database.mongo_db import MongoDB

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load test environment variables
load_dotenv()

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup test environment variables"""
    os.environ['ADMIN_ID'] = '123456789'  # Test admin ID
    os.environ['ADMIN_IDS'] = '123456789,987654321'  # Test admin IDs list
    os.environ['MONGODB_URI'] = 'mongodb://localhost:27017/test_telegram_bot_db'

@pytest.fixture(scope="function")
def test_db():
    """Fixture for SQLite test database"""
    test_db_file = 'test_bot.db'
    db = BotDB(db_file=test_db_file)
    yield db
    db.close()
    # Cleanup
    if os.path.exists(test_db_file):
        os.remove(test_db_file)

@pytest.fixture(scope="function")
def test_mongo():
    """Fixture for MongoDB test database"""
    db = MongoDB()
    yield db
    # Cleanup: Drop test database
    db.client.drop_database('test_telegram_bot_db')
    db.close() 