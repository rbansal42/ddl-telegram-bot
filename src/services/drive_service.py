# Standard library imports
import os
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path
import io
import logging

# Third-party imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Disable connection logs
logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
logging.getLogger('pymongo.topology').setLevel(logging.WARNING)
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.WARNING)
logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)

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
        env_path = Path(__file__).parent.parent.parent / '.env'
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
                '../credentials/service-account-key.json'
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
            logger.info(f"Setting sharing permissions for folder: {folder_id}")
            
            # Create sharing permission
            permission = {
                'type': 'anyone',
                'role': 'writer',
                'allowFileDiscovery': False
            }
            logger.debug(f"Permission configuration: {permission}")
            
            # Apply the permission
            logger.debug("Applying permissions...")
            self.service.permissions().create(
                fileId=folder_id,
                body=permission,
                supportsAllDrives=True,
                sendNotificationEmail=False
            ).execute()
            logger.debug("Permissions applied successfully")
            
            # Get sharing link
            logger.debug("Retrieving sharing link...")
            file = self.service.files().get(
                fileId=folder_id,
                fields='webViewLink',
                supportsAllDrives=True
            ).execute()
            
            sharing_url = file.get('webViewLink', f'https://drive.google.com/drive/folders/{folder_id}')
            logger.info(f"Sharing URL generated: {sharing_url}")
            return sharing_url
            
        except Exception as e:
            logger.error(f"Failed to set folder permissions: {str(e)}", exc_info=True)
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
            logger.info(f"Starting file upload: {file_name} to folder: {parent_folder_id}")
            
            # Create file metadata
            file_metadata = {
                'name': file_name,
                'parents': [parent_folder_id]
            }
            logger.debug(f"File metadata: {file_metadata}")
            
            # Create media content
            fh = io.BytesIO(file_content)
            media = MediaIoBaseUpload(
                fh,
                mimetype='application/octet-stream',
                chunksize=1024*1024,
                resumable=True
            )
            logger.debug("Media upload object created")
            
            # Upload file
            logger.debug("Starting file upload to Drive...")
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                supportsAllDrives=True,
                fields='id, name, mimeType, size, webViewLink'
            ).execute()
            
            logger.info(f"File uploaded successfully. File ID: {file.get('id')}")
            
            result = {
                'id': file.get('id', ''),
                'name': file.get('name', file_name),
                'mimeType': file.get('mimeType', ''),
                'size': file.get('size', 0),
                'webViewLink': file.get('webViewLink', '')
            }
            logger.debug(f"Upload result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to upload file {file_name}: {str(e)}", exc_info=True)
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

    def list_events(self) -> List[Dict]:
        """List all event folders in the root folder"""
        try:
            logger.info("Listing event folders from root folder")
            query = [
                f"'{self.root_folder_id}' in parents",
                "mimeType='application/vnd.google-apps.folder'",
                "trashed=false"
            ]
            logger.debug(f"Query parameters: {query}")

            results = self.service.files().list(
                q=" and ".join(query),
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora='drive',
                driveId=self.team_drive_id,
                fields='files(id, name)',
                orderBy='name'
            ).execute()

            events = results.get('files', [])
            logger.info(f"Found {len(events)} event folders")
            logger.debug(f"Event folders: {events}")
            return events
            
        except Exception as e:
            logger.error(f"Error listing events: {str(e)}", exc_info=True)
            return []

    def get_folder_stats(self, folder_id: str) -> dict:
        """
        Get statistics about media files in a folder
        Returns: dict with total count and size of media files
        """
        try:
            # List of media MIME types to copy
            MEDIA_MIME_TYPES = [
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'video/mp4', 'video/quicktime', 'video/x-msvideo',
                'audio/mpeg', 'audio/mp4', 'audio/wav'
            ]
            
            def list_all_files(folder_id: str, page_token=None):
                """Recursively list all files in a folder"""
                files = []
                total_size = 0
                while True:
                    # Query for files in the folder
                    results = self.service.files().list(
                        q=f"'{folder_id}' in parents and trashed=false",
                        pageSize=1000,
                        fields="nextPageToken, files(id, name, mimeType, size)",
                        pageToken=page_token,
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        corpora='drive',
                        driveId=self.team_drive_id
                    ).execute()
                    
                    for item in results.get('files', []):
                        if item['mimeType'] == 'application/vnd.google-apps.folder':
                            # Recursively get files from subfolders
                            sub_files, sub_size = list_all_files(item['id'])
                            files.extend(sub_files)
                            total_size += sub_size
                        elif item['mimeType'] in MEDIA_MIME_TYPES:
                            files.append(item)
                            total_size += int(item.get('size', 0))
                    
                    page_token = results.get('nextPageToken')
                    if not page_token:
                        break
                        
                return files, total_size

            # Get all media files and their total size
            files, total_size = list_all_files(folder_id)
            
            return {
                'success': True,
                'total_files': len(files),
                'total_size': total_size,
                'files': files
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def copy_media_files(self, source_folder_id: str, target_folder_id: str, progress_callback=None) -> dict:
        """
        Copy all media files from source folder to target folder, flattening the structure
        Args:
            source_folder_id: ID of source folder
            target_folder_id: ID of target folder
            progress_callback: Optional callback function to report progress
        Returns: dict with success status and additional info
        """
        try:
            # Get all media files using get_folder_stats
            source_stats = self.get_folder_stats(source_folder_id)
            if not source_stats['success']:
                return {
                    'success': False,
                    'error': source_stats['error']
                }

            all_files = source_stats['files']
            if not all_files:
                return {
                    'success': False,
                    'error': 'No media files found in the source folder'
                }

            # Copy each file to the target folder
            copied_count = 0
            total_files = len(all_files)
            cancelled = False
            
            try:
                for file in all_files:
                    try:
                        # Create a copy of the file
                        copied_file = self.service.files().copy(
                            fileId=file['id'],
                            body={
                                'name': file['name'],
                                'parents': [target_folder_id]
                            },
                            supportsAllDrives=True
                        ).execute()
                        copied_count += 1
                        
                        # Call progress callback if provided
                        if progress_callback:
                            try:
                                progress = (copied_count / total_files) * 100
                                progress_callback(copied_count, total_files, progress)
                            except Exception as e:
                                if str(e) == "Process cancelled by user":
                                    cancelled = True
                                    break
                                else:
                                    logger.warning(f"Error in progress callback: {str(e)}")
                            
                    except Exception as e:
                        logger.warning(f"Error copying file {file['name']}: {str(e)}")
                        continue
                        
                    if cancelled:
                        break
                        
            except Exception as e:
                logger.error(f"Error during file copy process: {str(e)}")
                if not cancelled:
                    raise

            if cancelled:
                # Clean up copied files
                logger.info("Process cancelled, cleaning up copied files...")
                for i in range(copied_count):
                    try:
                        file = all_files[i]
                        # Search for the copied file in the target folder
                        results = self.service.files().list(
                            q=f"name='{file['name']}' and '{target_folder_id}' in parents",
                            fields="files(id)",
                            supportsAllDrives=True
                        ).execute()
                        
                        # Delete the copied file
                        for copied_file in results.get('files', []):
                            self.service.files().delete(
                                fileId=copied_file['id'],
                                supportsAllDrives=True
                            ).execute()
                    except Exception as e:
                        logger.warning(f"Error cleaning up file {file['name']}: {str(e)}")
                        continue
                
                return {
                    'success': False,
                    'error': 'Process cancelled by user',
                    'copied_files': copied_count,
                    'total_files': total_files
                }

            return {
                'success': True,
                'copied_files': copied_count,
                'total_files': total_files
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_folder_size(self, folder_id: str) -> int:
        """Get total size of all files in a folder in bytes"""
        try:
            # Query for all files in the folder
            query = f"'{folder_id}' in parents and trashed = false"
            files = self.service.files().list(
                q=query,
                fields="files(size)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()

            # Sum up the sizes of all files
            total_size = 0
            for file in files.get('files', []):
                if 'size' in file:  # Some items like folders don't have size
                    total_size += int(file['size'])

            return total_size

        except Exception as e:
            logger.error(f"Error getting folder size: {str(e)}", exc_info=True)
            raise 