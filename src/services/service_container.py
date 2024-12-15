from src.database.mongo_db import MongoDB
from src.services.google.drive_service import GoogleDriveService

class ServiceContainer:
    def __init__(self):
        self.db = MongoDB()
        self.drive_service = GoogleDriveService()

    def close(self):
        """Close all service connections"""
        self.db.close() 