import logging
import requests
import mysql.connector
import os
import base64
import json
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# 🔑 Replace with your credentials
TOKEN = "7740960213:AAHBdZeBV8ehuWx8fn0djt4JulZXa3OqBVU"
GOOGLE_API_KEY = "AIzaSyAT4gTEN6-V7YRjVGwMfj-xFuGHyVIYlWA"
GENAI_API_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"

# MySQL Database Configuration
DB_HOST = "blg3gddyoqm11t50miod-mysql.services.clever-cloud.com"
DB_USER = "uwrexml3vanwh8gr"
DB_PASSWORD = "hgzWYeOmQYPHfWzFoOU1"
DB_NAME = "blg3gddyoqm11t50miod"

# Logging
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

async def start(update: Update, context):
    await update.message.reply_text("Send me a photo, and I'll process it!")

async def handle_photo(update: Update, context):
    """Handles the uploaded photo, processes it with AI, and stores it in MySQL."""
    photo = update.message.photo[-1]  # Get the highest resolution image
    file = await context.bot.get_file(photo.file_id)
    file_path = "photo.jpg"
    await file.download_to_drive(file_path)

    await update.message.reply_text("Processing your image using AI...")

    # Process the image using Generative AI
    features = process_image(file_path)

    if features:
        await update.message.reply_text("Uploading image and features to the database...")
        success = upload_to_database(file_path, features)

        if success:
            await update.message.reply_text("✅ Image and features stored in the database successfully!")
        else:
            await update.message.reply_text("❌ Failed to upload image to the database.")
    else:
        await update.message.reply_text("❌ AI processing failed. Try again.")

import re

def process_image(image_path):
    """Send the image to Generative AI API and get structured features."""
    time.sleep(2)  # Wait 2 seconds before sending a request

    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    url = f"{GENAI_API_URL}?key={GOOGLE_API_KEY}"
    headers = {"Content-Type": "application/json"}

    prompt = """
You are an AI system analyzing an image of a person for police reporting.  
Extract and return the following **27 attributes** in **strict JSON format** without explanations, markdown, or additional text.

{
  "General Description": "Overall appearance summary",
  "Properties": ["A list of observed characteristics"],
  "Estimated Age": "Numeric age or age range",
  "Gender": "Male/Female/Unknown",
  "Hair Color": "Observed hair color",
  "Eye Color": "Observed eye color",
  "Height (cm)": "Estimated height",
  "Weight (kg)": "Estimated weight",
  "Facial Hair Type": "Beard, mustache, none",
  "Skin Tone": "Fair, medium, dark, etc.",
  "Body Build": "Slim, muscular, overweight, etc.",
  "Clothing Type (upper body)": "Shirt, jacket, hoodie, etc.",
  "Clothing Color (upper body)": "Red, blue, black, etc.",
  "Clothing Type (lower body)": "Pants, shorts, skirt, etc.",
  "Clothing Color (lower body)": "Blue, black, white, etc.",
  "Footwear Type": "Shoes, sandals, boots, etc.",
  "Footwear Color": "Color of footwear",
  "Headwear": "Hat, cap, none",
  "Glasses": "Sunglasses, prescription, none",
  "Tattoo/Scar Marks": "Yes/No + description",
  "Bag/Backpack": "Yes/No + type",
  "Jewelry": "Earrings, necklace, bracelet, etc.",
  "Wristwatch": "Yes/No",
  "Pose/Posture": "Standing, sitting, walking",
  "Walking/Standing/Sitting": "Current motion or posture",
  "Emotional Expression": "Happy, neutral, angry, etc.",
  "Any distinguishing feature": "Birthmark, missing limb, etc.",
  "Nearby objects or context": "Details about surroundings"
}

Ensure that all **27 attributes** are always present in the output, even if some values are 'Unknown' or 'None'.
"""


    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": "image/jpeg", "data": encoded_image}}
                ]
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        try:
            text_response = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            # ✅ Remove Markdown-style JSON formatting (` ```json ... ``` `)
            clean_json = re.sub(r"```json\n|\n```", "", text_response).strip()

            print("🔹 Extracted JSON:", clean_json)  # Debugging

            return json.loads(clean_json)  # Convert to dictionary

        except json.JSONDecodeError:
            print("❌ Error: AI response is not in valid JSON format.")
            return None
    else:
        print("❌ GenAI Processing Failed:", response.text)
        return None


def upload_to_database(image_path, features):
    """Insert or update image and AI-extracted features into MySQL."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        with open(image_path, "rb") as file:
            binary_data = file.read()

        # Convert 'Properties' list to a JSON string
        properties = json.dumps(features.get("Properties", [])) if isinstance(features.get("Properties"), list) else "Unknown"

        query = """
        INSERT INTO images (
            image_data, description, properties, age_estimate, hair_color, eye_color, height_cm, weight_kg, facial_hair, skin_tone, body_build,
            clothing_upper, clothing_upper_color, clothing_lower, clothing_lower_color, footwear, footwear_color, headwear, glasses,
            tattoo_scar, bag_backpack, jewelry, wristwatch, pose, movement, emotion, distinguishing_feature, context
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        );
        """

        values = (
            binary_data,
            features.get("General Description", "Unknown"),
            properties,
            features.get("Estimated Age", "Unknown"),
            features.get("Hair Color", "Unknown"),
            features.get("Eye Color", "Unknown"),
            features.get("Height (cm)", "Unknown"),
            features.get("Weight (kg)", "Unknown"),
            features.get("Facial Hair Type", "Unknown"),
            features.get("Skin Tone", "Unknown"),
            features.get("Body Build", "Unknown"),
            features.get("Clothing Type (upper body)", "Unknown"),
            features.get("Clothing Color (upper body)", "Unknown"),
            features.get("Clothing Type (lower body)", "Unknown"),
            features.get("Clothing Color (lower body)", "Unknown"),
            features.get("Footwear Type", "Unknown"),
            features.get("Footwear Color", "Unknown"),
            features.get("Headwear", "Unknown"),
            features.get("Glasses", "Unknown"),
            features.get("Tattoo/Scar Marks", "Unknown"),
            features.get("Bag/Backpack", "Unknown"),
            features.get("Jewelry", "Unknown"),
            features.get("Wristwatch", "Unknown"),
            features.get("Pose/Posture", "Unknown"),
            features.get("Walking/Standing/Sitting", "Unknown"),
            features.get("Emotional Expression", "Unknown"),
            features.get("Any distinguishing feature", "Unknown"),
            features.get("Nearby objects or context", "Unknown"),
        )

        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Image successfully inserted into database!")
        return True

    except Exception as e:
        print("❌ Database Insert Error:", e)
        return False

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()

if __name__ == "__main__":
    main()
