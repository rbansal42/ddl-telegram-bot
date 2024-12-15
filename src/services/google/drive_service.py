from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
from typing import List, Dict, Optional, Tuple
from enum import Enum
from dotenv import load_dotenv
from pathlib import Path
from googleapiclient.http import MediaIoBaseUpload
import io

class DriveAccessLevel(Enum):
    NO_ACCESS = "no_access"
    READER = "reader"
    COMMENTER = "commenter"
    WRITER = "writer"
    ORGANIZER = "organizer"
    OWNER = "owner"

class GoogleDriveService:
    _instance = None
    _rclone_service = None

    def __new__(cls, rclone_service=None):
        if cls._instance is None:
            cls._instance = super(GoogleDriveService, cls).__new__(cls)
            cls._instance._initialized = False
            cls._rclone_service = rclone_service
        return cls._instance

    def __init__(self, rclone_service=None):
        if self._initialized:
            return
            
        # Load environment variables from .env file
        env_path = Path(__file__).parent.parent.parent.parent / '.env'
        load_dotenv(env_path)
        
        self.SCOPES = ['https://www.googleapis.com/auth/drive']  # Full access needed for Team Drive
        self.credentials = None
        self.service = None
        self.rclone_service = self._rclone_service or rclone_service
        
        # Get and validate environment variables
        self.team_drive_id = os.getenv('GDRIVE_TEAM_DRIVE_ID')
        self.root_folder_id = os.getenv('GDRIVE_ROOT_FOLDER_ID')
        
        # Debug prints
        print(f"Team Drive ID: {self.team_drive_id}")
        print(f"Root Folder ID: {self.root_folder_id}")
        
        # Validate required environment variables
        if not self.team_drive_id:
            raise ValueError("GDRIVE_TEAM_DRIVE_ID not set in environment variables")
        if not self.root_folder_id:
            raise ValueError("GDRIVE_ROOT_FOLDER_ID not set in environment variables")
            
        self._initialize_service()
        self.verify_drive_access()  # Verify access on initialization

        self._initialized = True

    def _initialize_service(self):
        """Initialize the Google Drive service with credentials"""
        try:
            credentials_path = os.path.join(
                os.path.dirname(__file__), 
                '../../credentials/service-account-key.json'
            )
            
            if not os.path.exists(credentials_path):
                raise Exception("Service account credentials file not found")

            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=self.SCOPES
            )
            self.service = build('drive', 'v3', credentials=self.credentials)
        except Exception as e:
            raise Exception(f"Failed to initialize Google Drive service: {str(e)}")

    def verify_drive_access(self) -> Tuple[bool, Dict[str, Dict]]:
        """
        Verify access levels for Team Drive and root folder
        Returns: Tuple of (success_status, {resource: {access_level, name, url}})
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
                access_level = DriveAccessLevel.OWNER
            elif capabilities.get('canAddChildren'):
                access_level = DriveAccessLevel.WRITER
            elif capabilities.get('canComment'):
                access_level = DriveAccessLevel.COMMENTER
            elif capabilities.get('canDownload'):
                access_level = DriveAccessLevel.READER
            else:
                access_level = DriveAccessLevel.NO_ACCESS
                raise Exception("Insufficient Team Drive access")

            access_info['team_drive'] = {
                'access_level': access_level,
                'name': drive_response.get('name', 'Unknown Drive'),
                'url': f"https://drive.google.com/drive/u/0/folders/{self.team_drive_id}"
            }

            # Check root folder access
            folder_response = self.service.files().get(
                fileId=self.root_folder_id,
                supportsAllDrives=True,
                fields='id, name, capabilities, webViewLink'
            ).execute()
            
            folder_capabilities = folder_response.get('capabilities', {})
            
            # Determine root folder access level
            if folder_capabilities.get('canEdit'):
                if folder_capabilities.get('canShare'):
                    access_level = DriveAccessLevel.ORGANIZER
                else:
                    access_level = DriveAccessLevel.WRITER
            elif folder_capabilities.get('canComment'):
                access_level = DriveAccessLevel.COMMENTER
            elif folder_capabilities.get('canReadRevisions'):
                access_level = DriveAccessLevel.READER
            else:
                access_level = DriveAccessLevel.NO_ACCESS
                raise Exception("Insufficient root folder access")

            access_info['root_folder'] = {
                'access_level': access_level,
                'name': folder_response.get('name', 'Unknown Folder'),
                'url': folder_response.get('webViewLink', 
                       f"https://drive.google.com/drive/u/0/folders/{self.root_folder_id}")
            }

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

    def list_files(self, folder_id: Optional[str] = None, recursive: bool = False) -> List[Dict]:
        """
        List all files and folders in the specified folder
        Args:
            folder_id: ID of the folder to list contents from (defaults to root folder)
            recursive: Whether to list contents of subfolders recursively
        """
        try:
            current_folder_id = folder_id or self.root_folder_id
            
            # Double check folder ID is available
            if not current_folder_id:
                raise ValueError("No folder ID provided and root folder ID not set")

            # Verify folder exists and is accessible
            try:
                self.service.files().get(
                    fileId=current_folder_id,
                    supportsAllDrives=True
                ).execute()
            except Exception as e:
                raise ValueError(f"Invalid or inaccessible folder ID: {current_folder_id}")

            query = [
                f"'{current_folder_id}' in parents",
                "trashed=false"
            ]

            results = self.service.files().list(
                q=" and ".join(query),
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora='drive',
                driveId=self.team_drive_id,
                fields='files(id, name, mimeType, createdTime, modifiedTime, webViewLink, size)',
                orderBy='name'
            ).execute()

            files = results.get('files', [])

            if recursive:
                for file in files:
                    if file['mimeType'] == 'application/vnd.google-apps.folder':
                        subfiles = self.list_files(file['id'], recursive=True)
                        file['children'] = subfiles

            return files

        except Exception as e:
            raise Exception(f"Failed to list files: {str(e)}")

    def list_drives(self) -> List[Dict]:
        """
        List all shared drives accessible to the service account
        Returns: List of drives with basic information
        """
        try:
            drives = []
            page_token = None
            
            while True:
                response = self.service.drives().list(
                    pageSize=100,
                    pageToken=page_token,
                    fields="nextPageToken, drives(id, name, kind)"
                ).execute()
                
                drives.extend(response.get('drives', []))
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
                    
            return [{
                'id': drive['id'],
                'name': drive['name'],
                'type': drive['kind']
            } for drive in drives]
            
        except Exception as e:
            raise Exception(f"Failed to list drives: {str(e)}")

    def list_team_drive_contents(self) -> List[Dict]:
        """
        List all files and folders at the root level of the Team Drive (non-recursive).
        
        Returns:
            List[Dict]: List of file/folder metadata dictionaries with name and webViewLink
        """
        try:
            # Query to get only root-level files and folders in the Team Drive
            query = [
                f"'{self.team_drive_id}' in parents",  # Only items in the specified root folder
                "trashed=false"                        # Only non-trashed items
            ]
            
            results = self.service.files().list(
                driveId=self.team_drive_id,
                corpora='drive',
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields='files(id, name, mimeType, webViewLink)',
                orderBy='name',
                q=" and ".join(query)
            ).execute()

            return results.get('files', [])

        except HttpError as error:
            print(f"Error listing Team Drive contents: {error}")
            raise Exception(f"Failed to list Team Drive contents: {str(error)}") 

    def set_folder_sharing_permissions(self, folder_id: str) -> str:
        """
        Set folder permissions to allow anyone with the link to add content
        Args:
            folder_id: ID of the folder
        Returns:
            str: The sharing URL
        """
        try:
            # Create sharing permission
            permission = {
                'type': 'anyone',
                'role': 'writer',
                'allowFileDiscovery': False
            }
            
            # Apply the permission
            self.service.permissions().create(
                fileId=folder_id,
                body=permission,
                supportsAllDrives=True,
                sendNotificationEmail=False
            ).execute()
            
            # Get sharing link
            file = self.service.files().get(
                fileId=folder_id,
                fields='webViewLink',
                supportsAllDrives=True
            ).execute()
            
            return file.get('webViewLink')
            
        except Exception as e:
            raise Exception(f"Failed to set folder permissions: {str(e)}")

    def upload_file(self, file_content: bytes, file_name: str, parent_folder_id: str) -> dict:
        """
        Upload a file to Google Drive using Google Drive API directly
        
        Args:
            file_content: The file content in bytes
            file_name: Name of the file
            parent_folder_id: ID of the parent folder
            
        Returns:
            dict: The uploaded file's metadata
        """
        try:
            print(f"[DEBUG] Starting file upload: {file_name} to folder: {parent_folder_id}")
            
            # Create file metadata
            file_metadata = {
                'name': file_name,
                'parents': [parent_folder_id]
            }
            
            # Create media content
            fh = io.BytesIO(file_content)
            media = MediaIoBaseUpload(
                fh,
                mimetype='application/octet-stream',
                chunksize=1024*1024,
                resumable=True
            )
            
            # Upload file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                supportsAllDrives=True,
                fields='id, name, mimeType, size, webViewLink'
            ).execute()
            
            print(f"[DEBUG] File uploaded successfully: {file.get('id')}")
            
            return {
                'id': file.get('id', ''),
                'name': file.get('name', file_name),
                'mimeType': file.get('mimeType', ''),
                'size': file.get('size', 0),
                'webViewLink': file.get('webViewLink', '')
            }
            
        except Exception as e:
            print(f"[DEBUG] Error in upload_file: {str(e)}")
            raise Exception(f"Failed to upload file: {str(e)}")

    def folder_exists(self, folder_name: str, parent_id: Optional[str] = None) -> bool:
        """Check if a folder with the given name exists in the specified parent folder"""
        try:
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            if parent_id:
                query += f" and '{parent_id}' in parents"
            else:
                query += f" and '{self.root_folder_id}' in parents"

            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                driveId=self.team_drive_id,
                corpora='drive'
            ).execute()

            return len(results.get('files', [])) > 0

        except Exception as e:
            print(f"Error checking folder existence: {str(e)}")
            return False
