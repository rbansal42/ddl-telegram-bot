import os
import requests
from telebot import TeleBot

def register_cat_handlers(bot: TeleBot):
    @bot.message_handler(commands=['cat'])
    def send_cat_gif(message):
        try:
            url = "https://api.giphy.com/v1/gifs/random"
            params = {
                "api_key": os.getenv("GIPHY_API_KEY"),
                "tag": "cat",
                "rating": "g"
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            gif_url = response.json()["data"]["images"]["original"]["url"]
            bot.send_animation(message.chat.id, gif_url, caption="Here's your random cat GIF! 🐱")
        
        except requests.RequestException as e:
            bot.reply_to(message, "Sorry, I couldn't fetch a cat GIF right now. Try again later! 😿")
        except Exception as e:
            bot.reply_to(message, "Oops! Something went wrong. Try again later! 😿")
