# Kinobot

Aiogram-based Telegram movie bot.

Features:
- Admin panel
- Add movie to database
- Assign unique code to each movie
- User searches movie by code
- AIogram + SQLite storage

## Setup

1. Create a .env file:

   BOT_TOKEN=your_telegram_bot_token
   ADMIN_IDS=123456789,987654321

2. Install dependencies:

   pip install -r requirements.txt

3. Run:

   python main.py

## Docker

Build:

   docker build -t kinobot .

Run:

   docker run --rm -it -e BOT_TOKEN="your_token" -e ADMIN_IDS="123456789" kinobot

## Create ZIP locally

   zip -r kinobot.zip . -x ".git/*" "__pycache__/*" ".venv/*" "*.pyc" "movies.db"

