from setuptools import setup, find_packages

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