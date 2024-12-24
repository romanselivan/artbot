import os
import requests
import telebot
import logging
import time
from flask import Flask
import threading
from dotenv import load_dotenv

# Загрузить переменные из .env файла
load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Initialize Telegram bot with API token
TELEGRAM_API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
bot = telebot.TeleBot(TELEGRAM_API_TOKEN)

# OpenRouter API settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3.2-3b-instruct:free"

# System prompt for the AI model
SYSTEM_PROMPT = """You're an expert art consultant.
You know both classical and contemporary art like the back of your hand.
Keep responses extremely short, punchy, and casual with occasional art world jargon.
Format answers for Telegram chat:
- Use emojis
- Break text into short paragraphs
- Add links to images or galleries if relevant

Answer directly to the user's question without extra commentary or explanations about the question itself."""

# Memory for chat history
chat_memory = {}

# Function to query OpenRouter API with retries
def query_openrouter(chat_id, user_message, retries=3):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    # Prepare the chat history for the API call
    history = chat_memory.get(chat_id, [])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": user_message}]

    payload = {
        "model": MODEL,
        "messages": messages
    }

    for attempt in range(retries):
        try:
            response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
            response.raise_for_status()  # Check for HTTP errors
            result = response.json()

            # Check if 'choices' key is in the response and has content
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                logging.error("OpenRouter response doesn't contain 'choices' or it's empty.")
                return "Sorry, something went wrong. Try again later."

        except requests.exceptions.RequestException as e:
            logging.error(f"Error with OpenRouter request: {e}")
            if attempt < retries - 1:
                logging.info(f"Retrying in 3 seconds (attempt {attempt + 1})")
                time.sleep(3)  # Wait for 3 seconds before retrying
            else:
                return "Sorry, something went wrong. Try again later."

# Message handler for the bot
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, "Hey 👋 Art’s my thing. Got a question? I’ll give you the real deal, no fluff 😉")

# Message handler for all other messages
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_input = message.text.strip().lower()

    # Initialize chat history for the user if it doesn't exist
    if chat_id not in chat_memory:
        chat_memory[chat_id] = []

    # Add the user message to the chat history
    chat_memory[chat_id].append({"role": "user", "content": message.text})

    # Keep only the last 20 messages in the history
    chat_memory[chat_id] = chat_memory[chat_id][-20:]

    try:
        logging.info(f"Received message from user: {user_input}")

        # Special handling for "Who are you?" or similar questions
        if "who are you" in user_input or "what are you" in user_input:
            response = (
                "I'm an expert in art, trained by Vladislav Sludsky and Roman Selivan. 🎨 "
                "Ask me anything about classical or contemporary art!"
            )
        else:
            # Send typing action
            bot.send_chat_action(chat_id, 'typing')

            # Get response from OpenRouter
            response = query_openrouter(chat_id, message.text)

        # Add the bot response to the chat history
        chat_memory[chat_id].append({"role": "assistant", "content": response})

        # Keep only the last 20 messages in the history
        chat_memory[chat_id] = chat_memory[chat_id][-20:]

        # Send response to the user
        bot.reply_to(message, response)
    except Exception as e:
        logging.error(f"Error while processing message: {e}")
        bot.reply_to(message, "Sorry, something went wrong. Try again later.")

# Flask server to keep Replit alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running and connected to UptimeRobot!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()

# Start the bot and web server
if __name__ == "__main__":
    keep_alive()
    while True:
        try:
            bot.polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logging.error(f"Bot polling failed: {e}")
            time.sleep(15)