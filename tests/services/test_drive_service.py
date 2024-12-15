import unittest
from unittest.mock import patch, MagicMock
from src.services.google.drive_service import GoogleDriveService, DriveAccessLevel
import os

class TestGoogleDriveService(unittest.TestCase):
    def setUp(self):
        self.mock_env_vars = {
            'GDRIVE_TEAM_DRIVE_ID': 'test_team_drive_id',
            'GDRIVE_ROOT_FOLDER_ID': 'test_root_folder_id'
        }
        self.patcher = patch.dict(os.environ, self.mock_env_vars)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch('src.services.google.drive_service.build')
    @patch('src.services.google.drive_service.service_account.Credentials')
    def test_list_folders(self, mock_credentials, mock_build):
        # Mock response data
        mock_folders = {
            'files': [
                {
                    'id': '1',
                    'name': 'Test Folder 1',
                    'createdTime': '2024-01-01T00:00:00.000Z',
                    'modifiedTime': '2024-01-01T00:00:00.000Z'
                }
            ]
        }

        # Setup mock service
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files
        mock_list = MagicMock()
        mock_files.list.return_value = mock_list
        mock_list.execute.return_value = mock_folders

        # Initialize service and test
        drive_service = GoogleDriveService()
        folders = drive_service.list_folders()

        # Verify results
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0]['name'], 'Test Folder 1')

        # Verify correct query parameters for Team Drive
        mock_files.list.assert_called_with(
            q="'test_root_folder_id' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora='drive',
            driveId='test_team_drive_id',
            fields='files(id, name, createdTime, modifiedTime)',
            orderBy='name'
        )

    @patch('src.services.google.drive_service.build')
    @patch('src.services.google.drive_service.service_account.Credentials')
    def test_verify_drive_access(self, mock_credentials, mock_build):
        # Mock drive response
        mock_drive_response = {
            'id': 'test_team_drive_id',
            'name': 'Test Team Drive',
            'capabilities': {
                'canAddChildren': True,
                'canComment': True,
                'canDownload': True,
                'canManageTeamDrives': False
            }
        }
        
        # Mock folder response
        mock_folder_response = {
            'id': 'test_root_folder_id',
            'name': 'Test Root Folder',
            'capabilities': {
                'canEdit': True,
                'canShare': True,
                'canComment': True,
                'canReadRevisions': True
            }
        }
        
        # Setup mock service
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        
        # Mock drives API
        mock_drives = MagicMock()
        mock_service.drives.return_value = mock_drives
        mock_drives.get.return_value.execute.return_value = mock_drive_response
        
        # Mock files API
        mock_files = MagicMock()
        mock_service.files.return_value = mock_files
        mock_files.get.return_value.execute.return_value = mock_folder_response
        
        # Initialize service and test
        drive_service = GoogleDriveService()
        success, access_info = drive_service.verify_drive_access()
        
        # Verify results
        self.assertTrue(success)
        self.assertEqual(access_info['team_drive'], DriveAccessLevel.WRITER)
        self.assertEqual(access_info['root_folder'], DriveAccessLevel.ORGANIZER)
        
        # Verify API calls
        mock_drives.get.assert_called_with(
            driveId='test_team_drive_id',
            fields='id, name, capabilities'
        )
        
        mock_files.get.assert_called_with(
            fileId='test_root_folder_id',
            supportsAllDrives=True,
            fields='id, name, capabilities, permissions'
        )