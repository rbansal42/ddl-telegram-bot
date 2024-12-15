from src.database.mongo_db import MongoDB
from src.services.google.drive_service import GoogleDriveService
from src.services.rclone.rclone_service import RcloneService

class ServiceContainer:
    def __init__(self):
        self.db = MongoDB()
        self.rclone_service = RcloneService()
        self.drive_service = GoogleDriveService(rclone_service=self.rclone_service)

    def close(self):
        """Close all service connections"""
        self.db.close() 