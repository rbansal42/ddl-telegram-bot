from setuptools import setup, find_packages
import subprocess
import platform
import os
from pathlib import Path
import json
import sys
from dotenv import load_dotenv
import shutil

def get_rclone_path():
    """Get full path to rclone executable"""
    rclone_path = shutil.which('rclone')
    if not rclone_path:
        raise FileNotFoundError("Rclone executable not found in PATH")
    return rclone_path

def run_rclone_command(cmd, env=None):
    """Run rclone command with full path"""
    rclone_path = get_rclone_path()
    full_cmd = [rclone_path] + cmd[1:]  # Replace 'rclone' with full path
    return subprocess.run(full_cmd, env=env, capture_output=True, text=True)

def setup_rclone():
    """Setup rclone with service account"""
    print("🚀 Setting up rclone...")
    
    # Load environment variables
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
    
    if not all([os.getenv('GDRIVE_TEAM_DRIVE_ID'), os.getenv('GDRIVE_ROOT_FOLDER_ID')]):
        print("❌ Missing required environment variables: GDRIVE_TEAM_DRIVE_ID or GDRIVE_ROOT_FOLDER_ID")
        return False

    # Get paths
    project_root = Path(__file__).parent
    credentials_path = project_root / 'src' / 'credentials'
    service_account_path = credentials_path / 'service-account-key.json'
    rclone_config_path = credentials_path / 'rclone.conf'
    
    # Check service account exists
    if not service_account_path.exists():
        print("❌ Service account key not found in credentials folder")
        return False
    
    # Verify rclone installation
    try:
        result = run_rclone_command(["rclone", "version"])
        print("✅ Rclone is installed and working")
    except Exception as e:
        print(f"❌ Rclone verification failed: {str(e)}")
        return False
        
    # Create rclone config
    try:
        config_content = f"""[gdrive]
type = drive
service_account_file = {service_account_path}
team_drive = true
team_drive_id = {os.getenv('GDRIVE_TEAM_DRIVE_ID')}
root_folder_id = {os.getenv('GDRIVE_ROOT_FOLDER_ID')}
"""
        # Ensure credentials directory exists
        credentials_path.mkdir(exist_ok=True)
        rclone_config_path.write_text(config_content)
        print("✅ Rclone configuration created")
        
        # Test configuration
        result = run_rclone_command(
            ["rclone", "lsd", "gdrive:", 
             "--drive-shared-with-me",
             "--drive-team-drive",
             f"--drive-team-drive-id={os.getenv('GDRIVE_TEAM_DRIVE_ID')}"],
            env={"RCLONE_CONFIG": str(rclone_config_path.resolve())}
        )
        
        if result.returncode != 0:
            print(f"❌ Failed to verify rclone configuration: {result.stderr}")
            return False
            
        print("✅ Rclone setup completed successfully!")
        return True
            
    except Exception as e:
        print(f"❌ Error creating rclone config: {str(e)}")
        return False

if __name__ == "__main__":
    # Run rclone setup
    if not setup_rclone():
        sys.exit(1)
    
    # Run package setup if install command is given
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        setup(
            name="telegram_drive",
            version="0.1.0",
            packages=find_packages(),
            install_requires=[
                "python-telegram-bot",
                "pymongo",
                "python-dotenv",
                "google-auth",
                "google-api-python-client"
            ],
        ) 