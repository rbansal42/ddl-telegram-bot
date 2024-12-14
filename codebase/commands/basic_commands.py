from telebot import TeleBot
import os

def register_basic_handlers(bot: TeleBot):
    def is_admin(user_id):
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
        return user_id in admin_ids

    @bot.message_handler(commands=['start'])
    def start(message):
        bot.reply_to(message, "Hello! I am your bot.")

    @bot.message_handler(commands=['help'])
    def help_command(message):
        help_text = """Available commands:
/start - Start the bot
/help - Show this help message
/upload - Upload a file to storage
/events - List your stored files
/newevent - Creates a folder for an event
/delete - Delete a stored file
/cat - Get a random cat GIF
/dog - Get a random dog GIF
/space - Get a random space GIF
/meme - Get a random meme GIF
/funny - Get a random funny GIF"""
        bot.reply_to(message, help_text)

    @bot.message_handler(commands=['setphoto'])
    def set_bot_photo(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "Sorry, only administrators can change the bot's profile picture.")
            return
        bot.reply_to(message, "Please send me the new profile picture.")

    @bot.message_handler(content_types=['photo'], func=lambda message: message.caption == '/setphoto')
    def handle_photo(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "Sorry, only administrators can change the bot's profile picture.")
            return
        try:
            # Get the file ID of the largest photo size
            file_id = message.photo[-1].file_id
            # Download the file
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Set the bot's profile photo
            bot.set_chat_photo(message.chat.id, downloaded_file)
            bot.reply_to(message, "Profile picture updated successfully! ✅")
        except Exception as e:
            bot.reply_to(message, "Sorry, I couldn't update the profile picture. Make sure you have the right permissions.")

    @bot.message_handler(commands=['myid'])
    def get_user_id(message):
        bot.reply_to(message, f"Your Telegram ID is: {message.from_user.id}")
