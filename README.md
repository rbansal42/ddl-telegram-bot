# Telegram Drive Bot

A Telegram bot that manages Google Drive access and provides various utility functions for managing files, folders, and user permissions.

## Features

- **Google Drive Integration**
  - Create and manage folders in Team Drive
  - Set folder permissions
  - List files and folders
  - Share folder access

- **User Management**
  - Role-based access control (Owner, Admin, Manager, Member)
  - Registration system with admin approval
  - User activity logging

- **Fun Commands**
  - Random GIFs (cats, dogs, space, memes, funny)
  - Interactive responses

## Prerequisites

- Python 3.8+
- MongoDB
- Google Drive API credentials
- Telegram Bot Token

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd telegram_drive
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```


4. Set up environment variables:
Create a `.env` file in the root directory with the following variables:

```
TELEGRAM_BOT_TOKEN=your_bot_token
OWNER_ID=your_telegram_id
OWNER_USERNAME=your_username
OWNER_NAME=Your Full Name
OWNER_EMAIL=your@email.com
ADMIN_IDS=comma,separated,ids
MONGODB_HOST=mongodb://localhost:27017
MONGODB_DB_NAME=ddl_bot_db
GDRIVE_TEAM_DRIVE_ID=your_team_drive_id
GDRIVE_ROOT_FOLDER_ID=your_root_folder_id
```

5. Set up Google Drive credentials:
- Place your `service-account.json` file in `src/credentials/`

```bash
git add README.md
git commit -m "docs: add installation instructions to README"
```

6. Run the bot:

```bash
python main.py
```

## Usage
Start the bot: `python src/bot.py`

For development with auto-reload:
`nodemon`


## Available Commands

### Public Commands
- `/start` - Start the bot
- `/help` - Show available commands
- `/register` - Request access to the bot
- `/cat` - Get a random cat GIF
- `/dog` - Get a random dog GIF
- `/space` - Get a random space GIF
- `/meme` - Get a random meme GIF
- `/funny` - Get a random funny GIF

### Member Commands
- `/neweventfolder` - Create a new editable folder in Google Drive
- `/listfolders` - List all folders with their indexes
- `/getlink` - Get a link to a folder using its index

### Admin Commands
- `/listmembers` - List all registered members
- `/removemember` - Remove a member from the system
- `/pending` - List and manage pending registration requests
- `/adminhelp` - Show admin-level commands

### Owner Commands
- `/addadmin` - Add a new admin user
- `/removeadmin` - Remove an admin user
- `/listadmins` - List all admin users
- `/ownerhelp` - Show owner-level commands

git add README.md
git commit -m "docs: add usage instructions and command list to README"

## Testing

Run tests with coverage:
``` bash
pytest --cov=src tests/
```

## Project Structure

├── src/
│ ├── bot.py # Main bot file
│ ├── commands/ # Command handlers
│ ├── database/ # Database models
│ ├── middleware/ # Auth middleware
│ ├── services/ # External services
│ └── utils/ # Helper functions
├── tests/ # Test files
├── requirements.txt # Dependencies
└── setup.py # Package setup
