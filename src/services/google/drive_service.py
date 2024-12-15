from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
from typing import List, Dict, Optional, Tuple
from enum import Enum

class DriveAccessLevel(Enum):
    NO_ACCESS = "no_access"
    READER = "reader"
    COMMENTER = "commenter"
    WRITER = "writer"
    ORGANIZER = "organizer"
    OWNER = "owner"

class GoogleDriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive']  # Full access needed for Team Drive
        self.credentials = None
        self.service = None
        self.team_drive_id = os.getenv('GDRIVE_TEAM_DRIVE_ID')
        self.root_folder_id = os.getenv('GDRIVE_ROOT_FOLDER_ID')
        self._initialize_service()
        self.verify_drive_access()  # Verify access on initialization

    def _initialize_service(self):
        """Initialize the Google Drive service with credentials"""
        try:
            credentials_path = os.path.join(
                os.path.dirname(__file__), 
                '../../credentials/service_account.json'
            )
            
            if not os.path.exists(credentials_path):
                raise Exception("Service account credentials file not found")

            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=self.SCOPES
            )
            self.service = build('drive', 'v3', credentials=self.credentials)
        except Exception as e:
            raise Exception(f"Failed to initialize Google Drive service: {str(e)}")

    def verify_drive_access(self) -> Tuple[bool, Dict[str, DriveAccessLevel]]:
        """
        Verify access levels for Team Drive and root folder
        Returns: Tuple of (success_status, {resource: access_level})
        """
        try:
            access_info = {}
            
            # Check Team Drive access
            drive_response = self.service.drives().get(
                driveId=self.team_drive_id,
                fields='id, name, capabilities'
            ).execute()
            
            capabilities = drive_response.get('capabilities', {})
            
            # Determine Team Drive access level
            if capabilities.get('canManageTeamDrives'):
                access_info['team_drive'] = DriveAccessLevel.OWNER
            elif capabilities.get('canAddChildren'):
                access_info['team_drive'] = DriveAccessLevel.WRITER
            elif capabilities.get('canComment'):
                access_info['team_drive'] = DriveAccessLevel.COMMENTER
            elif capabilities.get('canDownload'):
                access_info['team_drive'] = DriveAccessLevel.READER
            else:
                access_info['team_drive'] = DriveAccessLevel.NO_ACCESS
                raise Exception("Insufficient Team Drive access")

            # Check root folder access
            folder_response = self.service.files().get(
                fileId=self.root_folder_id,
                supportsAllDrives=True,
                fields='id, name, capabilities, permissions'
            ).execute()
            
            folder_capabilities = folder_response.get('capabilities', {})
            
            # Determine root folder access level
            if folder_capabilities.get('canEdit'):
                if folder_capabilities.get('canShare'):
                    access_info['root_folder'] = DriveAccessLevel.ORGANIZER
                else:
                    access_info['root_folder'] = DriveAccessLevel.WRITER
            elif folder_capabilities.get('canComment'):
                access_info['root_folder'] = DriveAccessLevel.COMMENTER
            elif folder_capabilities.get('canReadRevisions'):
                access_info['root_folder'] = DriveAccessLevel.READER
            else:
                access_info['root_folder'] = DriveAccessLevel.NO_ACCESS
                raise Exception("Insufficient root folder access")

            return True, access_info

        except HttpError as e:
            if e.resp.status == 404:
                return False, {"error": "Resource not found"}
            elif e.resp.status == 403:
                return False, {"error": "Access denied"}
            else:
                return False, {"error": f"HTTP error occurred: {str(e)}"}
        except Exception as e:
            return False, {"error": str(e)}

    def list_folders(self, parent_folder_id: Optional[str] = None) -> List[Dict]:
        """List all folders in the specified parent folder within Team Drive"""
        try:
            folder_id = parent_folder_id or self.root_folder_id
            if not folder_id:
                raise Exception("No folder ID provided and no root folder ID set")

            query = [
                f"'{folder_id}' in parents",
                "mimeType='application/vnd.google-apps.folder'",
                "trashed=false"
            ]

            results = self.service.files().list(
                q=" and ".join(query),
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora='drive',
                driveId=self.team_drive_id,
                fields='files(id, name, createdTime, modifiedTime)',
                orderBy='name'
            ).execute()

            return results.get('files', [])

        except Exception as e:
            raise Exception(f"Failed to list folders: {str(e)}")

    def get_folder_details(self, folder_id: str) -> Dict:
        """Get details of a specific folder in Team Drive"""
        try:
            return self.service.files().get(
                fileId=folder_id,
                supportsAllDrives=True,
                fields='id, name, createdTime, modifiedTime, parents',
            ).execute()
        except Exception as e:
            raise Exception(f"Failed to get folder details: {str(e)}")

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Dict:
        """Create a new folder in Team Drive"""
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id or self.root_folder_id],
                'driveId': self.team_drive_id
            }

            folder = self.service.files().create(
                body=file_metadata,
                supportsAllDrives=True,
                fields='id, name, createdTime, modifiedTime, webViewLink'
            ).execute()

            return folder
        except Exception as e:
            raise Exception(f"Failed to create folder: {str(e)}") 