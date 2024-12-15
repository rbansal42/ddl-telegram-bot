from pathlib import Path
import subprocess
import json
import os
from typing import Dict, List
from dotenv import load_dotenv
import shutil

class RcloneService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RcloneService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        # Load environment variables
        env_path = Path(__file__).parent.parent.parent.parent / '.env'
        load_dotenv(env_path)
        
        self.team_drive_id = os.getenv('GDRIVE_TEAM_DRIVE_ID')
        self.root_folder_id = os.getenv('GDRIVE_ROOT_FOLDER_ID')
        self.rclone_remote = os.getenv('RCLONE_REMOTE_NAME', 'gdrive')
        self.config_path = Path(__file__).parent.parent.parent / 'credentials' / 'rclone.conf'
        
        if not all([self.team_drive_id, self.root_folder_id, self.rclone_remote]):
            raise ValueError("Missing required environment variables")
        
        if not self.config_path.exists():
            raise ValueError("Rclone configuration not found. Please run setup.py first")
            
        self._verify_rclone()
        self._initialized = True

    def get_rclone_path(self):
        """Get full path to rclone executable"""
        rclone_path = shutil.which('rclone')
        if not rclone_path:
            raise FileNotFoundError("Rclone executable not found in PATH")
        return rclone_path

    def run_rclone_command(self, cmd, env=None):
        """Run rclone command with full path"""
        rclone_path = self.get_rclone_path()
        full_cmd = [rclone_path] + cmd[1:]
        return subprocess.run(full_cmd, env=env, capture_output=True, text=True)

    def _verify_rclone(self):
        """Verify rclone installation and configuration"""
        try:
            env = {"RCLONE_CONFIG": str(self.config_path)}
            result = self.run_rclone_command(
                ["rclone", "lsd", f"{self.rclone_remote}:",
                 "--drive-shared-with-me",
                 "--drive-team-drive",
                 f"--drive-team-drive-id={self.team_drive_id}"],
                env=env
            )
            if result.returncode != 0:
                raise Exception(f"Failed to verify rclone: {result.stderr}")
            
            print(f"✅ Rclone verified with team drive: {self.team_drive_id}")
        except FileNotFoundError:
            raise Exception("Rclone is not installed or not in PATH")
        
    def upload_to_folder(self, source_dir: str, destination_folder: str) -> List[Dict]:
        """Upload all files from a directory to Google Drive using rclone"""
        try:
            print(f"[DEBUG] Uploading files from {source_dir} to {destination_folder}")
            
            env = {"RCLONE_CONFIG": str(self.config_path)}
            
            # Upload entire directory
            result = self.run_rclone_command([
                "rclone", "copy",
                source_dir,
                f"{self.rclone_remote}:/{destination_folder}",
                "--drive-server-side-across-configs",
                "--drive-shared-with-me",
                "--drive-team-drive",
                f"--drive-team-drive-id={self.team_drive_id}",
                "-P",  # Show progress
                "--stats-one-line"
            ], env=env)
            
            if result.returncode != 0:
                raise Exception(f"Upload failed: {result.stderr}")
            
            # Get info for all uploaded files
            uploaded_files = self._list_folder_contents(destination_folder)
            return uploaded_files
            
        except Exception as e:
            raise Exception(f"Failed to upload files: {str(e)}")

    def _list_folder_contents(self, folder_path: str) -> List[Dict]:
        """Get information about all files in a folder"""
        try:
            env = {"RCLONE_CONFIG": str(self.config_path)}
            result = self.run_rclone_command([
                "rclone", "lsf",
                f"{self.rclone_remote}:{folder_path}",
                "--format", "id,size,mime,path",  # Include path in output
                "--drive-shared-with-me",
                "--drive-team-drive",
                f"--drive-team-drive-id={self.team_drive_id}",
                "-R"  # Recursive listing
            ], env=env)
            
            if result.returncode != 0:
                raise Exception(f"Failed to list files: {result.stderr}")
                
            files = []
            for line in result.stdout.splitlines():
                if line.strip():
                    file_id, size, mime, path = line.split(',')
                    files.append({
                        'id': file_id,
                        'size': size,
                        'mimeType': mime,
                        'name': os.path.basename(path)
                    })
            
            return files
            
        except Exception as e:
            raise Exception(f"Failed to get file info: {str(e)}")

    def _get_file_info(self, file_path: str) -> Dict:
        """Get information about an uploaded file"""
        try:
            env = {"RCLONE_CONFIG": str(self.config_path)}
            result = self.run_rclone_command([
                "rclone", "lsf",
                f"{self.rclone_remote}:{file_path}",
                "--format", "id,size,mime",  # Specify exact format
                "--drive-shared-with-me",
                "--drive-team-drive",
                f"--drive-team-drive-id={self.team_drive_id}"
            ], env=env)
            
            if result.returncode != 0:
                raise Exception(f"Failed to get file info: {result.stderr}")
            
            # Parse the lsf output (format: id,size,mime)
            file_data = result.stdout.strip().split(',')
            if len(file_data) != 3:
                raise Exception("Invalid file info format")
            
            file_id, size, mime = file_data
            
            return {
                'name': os.path.basename(file_path),
                'size': int(size),
                'mimeType': mime,
                'id': file_id,
                'webViewLink': f"https://drive.google.com/file/d/{file_id}/view"
            }
        except Exception as e:
            print(f"[WARNING] Failed to get file info: {str(e)}")
            return {
                'name': os.path.basename(file_path),
                'size': 0,
                'mimeType': '',
                'id': '',
                'webViewLink': ''
            }

    def _get_web_link(self, file_id: str) -> str:
        """Generate web view link for file"""
        return f"https://drive.google.com/file/d/{file_id}/view"