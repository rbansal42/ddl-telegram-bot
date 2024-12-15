import os
import sys
import pytest
from dotenv import load_dotenv
from src.database.mongo_db import MongoDB
from src.utils.test_helpers import setup_test_environment

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load test environment variables
load_dotenv()

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup test environment variables"""
    os.environ['ADMIN_ID'] = '123456789'  # Test admin ID
    os.environ['ADMIN_IDS'] = '123456789,987654321'  # Test admin IDs list
    os.environ['MONGODB_HOST'] = 'mongodb://localhost:27017'
    os.environ['MONGODB_DB_NAME'] = 'test_ddl_bot_db'

@pytest.fixture(scope="function")
def test_mongo():
    """Fixture for MongoDB test database"""
    db = MongoDB()
    yield db
    # Cleanup: Drop test database
    db.client.drop_database('test_ddl_bot_db')
    db.close()