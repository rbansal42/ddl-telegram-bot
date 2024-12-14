from src.database.mongo_db import MongoDB

def test_connection():
    try:
        db = MongoDB()
        # Try to ping the database
        db.client.admin.command('ping')
        print("✅ Successfully connected to MongoDB")
        
        # Test collection access
        print("\nTesting collections access:")
        print(f"Users collection: {db.users}")
        print(f"Registration requests collection: {db.registration_requests}")
        print(f"Folders collection: {db.folders}")
        print(f"User actions collection: {db.user_actions}")
        
        db.close()
        print("\n✅ Connection closed successfully")
        
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")

if __name__ == "__main__":
    test_connection() 