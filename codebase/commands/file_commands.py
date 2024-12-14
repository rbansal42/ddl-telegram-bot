from telebot import TeleBot

def register_file_handlers(bot: TeleBot):
    @bot.message_handler(commands=['upload'])
    def upload(message):
        bot.reply_to(message, "Please send me the file you want to upload.")

    @bot.message_handler(commands=['delete'])
    def delete(message):
        bot.reply_to(message, "Please specify which file you want to delete.")
