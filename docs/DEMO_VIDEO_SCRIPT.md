# VYOM - Demo Video Script (about 3 minutes)

Record the screen and your voice with any recorder (Xbox Game Bar: Win + G, or OBS). Speak clearly and keep the microphone close.

## 0:00 - 0:02 Title card (required: opening 2 seconds)
Show a plain slide or text overlay:

- **Full Name:** Pandharinath Dnyaneshwar Sangle
- **Track Name:** Python Programming (Oasis Infobyte)
- **Task Title:** Task 1 - Voice Assistant (VYOM)

## 0:02 - 0:20 Introduction
"Hello, this is VYOM, a Python voice assistant I built for my Oasis Infobyte Python Programming internship. It has a PySide6 interface, speech recognition, text to speech and a natural language knowledge base."

## 0:20 - 0:50 Basics (click Start Assistant, say each phrase)
1. "Hello"  -> greeting
2. "What is the time?"  -> time
3. "What is today's date?"  -> date
4. Say something unclear or mumble once -> VYOM asks you to repeat

## 0:50 - 1:20 Search and knowledge
1. "Search for Python programming" -> browser opens Google
2. "Can you explain machine learning in simple words?" -> knowledge base answer
3. "What is SQL?"

## 1:20 - 1:50 Weather and reminder (needs the keys in .env)
1. "What is the weather in Pune?"
2. "Remind me after 1 minute to drink water" -> wait for the spoken alert

## 1:50 - 2:30 Email with confirmation (use your own test address)
1. Say "Send an email" -> give recipient, subject, message
2. Show that VYOM reads everything back and asks for confirmation
3. Say "Yes" -> show the sent confirmation (or say "No" to show cancellation)

## 2:30 - 2:50 Extras
1. "Tell me a joke"
2. "Open YouTube" (custom command from data/custom_commands.json)
3. Type a command in the text box to show typed input works

## 2:50 - 3:00 Closing
"Thank you for watching. The code, README and tests are on my GitHub. #oasisinfobyte"

### Before you record
- Close private tabs, notifications and anything showing personal data. Never show the contents of your `.env` file.
- Do a dry run so the first take is smooth.
