import os
import requests
from telebot import TeleBot
from commands.basic_commands import register_basic_handlers
from commands.cat_command import register_cat_handlers
from commands.event_commands import register_event_handlers
from commands.file_commands import register_file_handlers

def register_fun_handlers(bot: TeleBot):
    def _fetch_random_gif(tag: str, message_on_error: str):
        try:
            url = "https://api.giphy.com/v1/gifs/random"
            params = {
                "api_key": os.getenv("GIPHY_API_KEY"),
                "tag": tag,
                "rating": "g"
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            return response.json()["data"]["images"]["original"]["url"]
        except (requests.RequestException, KeyError, Exception) as e:
            return None

    @bot.message_handler(commands=['dog'])
    def send_dog_gif(message):
        gif_url = _fetch_random_gif("dog", "Sorry, couldn't fetch a dog GIF! 🐕")
        if gif_url:
            bot.send_animation(message.chat.id, gif_url, caption="Here's your random dog GIF! 🐕")
        else:
            bot.reply_to(message, "Sorry, couldn't fetch a dog GIF! 🐕")

    @bot.message_handler(commands=['space'])
    def send_space_gif(message):
        gif_url = _fetch_random_gif("space", "Sorry, couldn't fetch a space GIF! 🚀")
        if gif_url:
            bot.send_animation(message.chat.id, gif_url, caption="Here's your random space GIF! 🚀")
        else:
            bot.reply_to(message, "Sorry, couldn't fetch a space GIF! 🚀")

    @bot.message_handler(commands=['meme'])
    def send_meme_gif(message):
        gif_url = _fetch_random_gif("meme", "Sorry, couldn't fetch a meme GIF! 😅")
        if gif_url:
            bot.send_animation(message.chat.id, gif_url, caption="Here's your random meme GIF! 😄")
        else:
            bot.reply_to(message, "Sorry, couldn't fetch a meme GIF! 😅")

    @bot.message_handler(commands=['funny'])
    def send_funny_gif(message):
        gif_url = _fetch_random_gif("funny", "Sorry, couldn't fetch a funny GIF! 😅")
        if gif_url:
            bot.send_animation(message.chat.id, gif_url, caption="Here's your random funny GIF! 😂")
        else:
            bot.reply_to(message, "Sorry, couldn't fetch a funny GIF! 😅") 