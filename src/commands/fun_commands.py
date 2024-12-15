# Standard library imports
import os
from typing import Optional

# Third-party imports
import requests
from telebot import TeleBot

# Local application imports
from src.commands.constants import (
    CMD_CAT,
    CMD_DOG,
    CMD_FUNNY,
    CMD_MEME,
    CMD_SPACE
)
from src.utils.user_actions import log_action, ActionType

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

    @bot.message_handler(commands=[CMD_DOG])
    def send_dog_gif(message):
        try:
            gif_url = _fetch_random_gif("dog", "Sorry, couldn't fetch a dog GIF! 🐕")
            if gif_url:
                log_action(
                    ActionType.COMMAND_SUCCESS,
                    message.from_user.id,
                    metadata={
                        'command': 'dog',
                        'chat_id': message.chat.id
                    }
                )
                bot.send_animation(message.chat.id, gif_url, caption="Here's your random dog GIF! 🐕")
            else:
                log_action(
                    ActionType.COMMAND_FAILED,
                    message.from_user.id,
                    error_message="Failed to fetch GIF",
                    metadata={'command': 'dog'}
                )
                bot.reply_to(message, "Sorry, couldn't fetch a dog GIF! 🐕")
        except Exception as e:
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={'command': 'dog'}
            )
            bot.reply_to(message, "Sorry, couldn't fetch a dog GIF! 🐕")

    @bot.message_handler(commands=[CMD_SPACE])
    def send_space_gif(message):
        gif_url = _fetch_random_gif("space", "Sorry, couldn't fetch a space GIF! 🚀")
        if gif_url:
            bot.send_animation(message.chat.id, gif_url, caption="Here's your random space GIF! 🚀")
        else:
            bot.reply_to(message, "Sorry, couldn't fetch a space GIF! 🚀")

    @bot.message_handler(commands=[CMD_MEME])
    def send_meme_gif(message):
        gif_url = _fetch_random_gif("meme", "Sorry, couldn't fetch a meme GIF! 😅")
        if gif_url:
            bot.send_animation(message.chat.id, gif_url, caption="Here's your random meme GIF! 😄")
        else:
            bot.reply_to(message, "Sorry, couldn't fetch a meme GIF! 😅")

    @bot.message_handler(commands=[CMD_FUNNY])
    def send_funny_gif(message):
        gif_url = _fetch_random_gif("funny", "Sorry, couldn't fetch a funny GIF! 😅")
        if gif_url:
            bot.send_animation(message.chat.id, gif_url, caption="Here's your random funny GIF! 😂")
        else:
            bot.reply_to(message, "Sorry, couldn't fetch a funny GIF! 😅") 
            
    @bot.message_handler(commands=[CMD_CAT])
    def send_cat_gif(message):
        try:
            # Call cat API
            response = requests.get('https://api.thecatapi.com/v1/images/search')
            if response.status_code == 200:
                cat_url = response.json()[0]['url']
                
                log_action(
                    ActionType.COMMAND_CAT,
                    message.from_user.id,
                    metadata={
                        'chat_id': message.chat.id,
                        'success': True
                    }
                )
                bot.send_photo(message.chat.id, cat_url)
            else:
                raise Exception("Failed to fetch cat image")
                
        except Exception as e:
            log_action(
                ActionType.COMMAND_FAILED,
                message.from_user.id,
                error_message=str(e),
                metadata={
                    'command': 'cat',
                    'chat_id': message.chat.id
                }
            )
            bot.reply_to(message, "😿 Failed to fetch a cat picture. Try again later!")
