# VYOM - Intelligent Personal Voice Assistant

**Oasis Infobyte - Python Programming Internship - Task 1: Voice Assistant**

VYOM is a desktop voice assistant for Windows 10/11 written in Python 3.12 with a dark purple PySide6 interface. You can talk to it with a microphone or type to it. It tells the time and date, searches Google, reports live weather, sends emails by voice (always asking for confirmation first), sets timed reminders, tells jokes, answers general-knowledge questions from an offline knowledge base, and runs your own custom commands.

> **Testing status:** The project's automated test suite completed successfully: **124 tests passed** (see `docs/QA_REPORT.md`). In addition, the project owner manually tested the desktop GUI, microphone/voice interaction, weather lookup using an active OpenWeatherMap key, and Gmail email sending using a Google App Password. Automated tests do not send real emails, call the live weather service, or access the microphone; those integrations were checked separately through manual testing.

---

## 1. Project objectives
1. Capture voice with SpeechRecognition, answer with pyttsx3.
2. Understand natural questions, not just exact phrases.
3. Provide the Oasis Infobyte beginner and advanced voice-assistant features.
4. Stay responsive (no freezing), safe (no secrets in code, email only after confirmation) and easy to install.

## 2. Oasis Infobyte requirement checklist

| Requirement | Where it is implemented | Needs your setup? |
|---|---|---|
| Capture voice with SpeechRecognition + microphone | `core/listener.py` | Microphone + internet (Google web recognizer) |
| Respond to "Hello" with a predefined greeting | `core/command_handler.py` | No |
| Current time and date | `core/command_handler.py` (Python `datetime`) | No, works offline |
| Web search on a spoken topic | `features/search_service.py` | Internet browser |
| Handle recognition errors and ask to repeat | `core/listener.py`, `core/voice_session.py` | No |
| Voice responses with pyttsx3 | `core/text_to_speech.py` | Windows voice (built in) |
| NLP (normalising, intents, topics, fuzzy matching) | `core/nlp.py` | No, offline |
| Send email by voice with smtplib | `features/email_service.py` + dialogue in `core/command_handler.py` | **Gmail address + App Password** |
| Timed reminders with audible alerts | `features/reminder_service.py` | No |
| Live weather from an API | `features/weather_service.py` | **OpenWeatherMap API key** |
| General knowledge (knowledge base / QA source) | `data/knowledge_base.json` (offline, 20 topics) + optional Wikipedia in `features/online_lookup.py` | Offline works without setup |
| Custom commands from a configuration file | `data/custom_commands.json`, `features/custom_commands.py` | No |
| Jokes (extra) | `features/joke_service.py` | No |

## 3. Features in detail
- **Speech recognition with separate outcomes.** Unintelligible speech -> VYOM says "Sorry, I didn't understand that. Could you please repeat?". No speech before the timeout -> silently keeps listening (nothing is spoken, nothing is treated as a command). Recognised but unsupported -> "Sorry, I am not sure how to help with that. Say help to hear what I can do." Microphone problem and network problem each get their own clear message, never an endless loop: after 3 unintelligible attempts in a row the assistant stops and asks you to check the microphone or type.
- **Natural language understanding.** Text normalising, stop-word removal, intent rules, topic extraction, exact + fuzzy knowledge-base matching with a confidence threshold. All ten phrasings of the machine-learning question (for example "Can you explain machine learning in simple words?", "What is ML?") return the Machine Learning answer. Unrelated questions never get a weak, wrong match.
- **Email.** "Send an email" -> recipient -> subject -> message -> VYOM reads all three back -> asks "Would you like me to send this email?" -> sends only after "yes". "No" or "cancel" stops it. You can say addresses like "john dot doe at gmail dot com".
- **Reminders.** "Remind me after 5 minutes to drink water", "set a reminder for 10 minutes", "cancel my reminders", "what are my reminders". Several can run at once; each plays a beep (Windows), speaks and shows the message.
- **Weather.** Temperature, feels-like, description, humidity, wind speed and city.
- **Custom commands.** Only two safe types: `reply` (VYOM says something) and `open_url` (opens an http/https address). Nothing from the file or from speech is ever run as a program or shell command.
- **Typed commands** work even with no microphone. **Mute** button silences spoken replies.

## 4. Technologies
Python 3.12 - PySide6 (GUI) - SpeechRecognition + PyAudio (microphone, Google web speech recognizer) - pyttsx3 (Windows SAPI5 voices) - requests - python-dotenv - smtplib/ssl (Gmail SMTP over SSL, port 465) - difflib (fuzzy matching) - `unittest` (tests).

## 5. Architecture
```
GUI thread (PySide6)  <-- signals -->  Workers  --> Assistant --> CommandHandler --> features
 main_window.py                        VoiceWorker (QThread)       |                 weather / email / search /
                                       CommandTask (thread pool)   +--> NLP (nlp.py)  reminders / jokes / custom
                                                                   +--> Speaker (own thread + queue)
```
- The GUI never listens, speaks or uses the network itself. `VoiceWorker` runs the listen -> understand -> respond loop (`core/voice_session.py`); typed commands run in a one-thread pool, so they cannot overlap. A lock makes sure voice and typed commands never mix up an email dialogue.
- Only one `VoiceWorker` can exist: Start does nothing while one runs. Stop sets an event that is checked every second while listening; closing the window stops the worker, cancels reminders and shuts the speech thread down.
- `core/` and `features/` contain no GUI code, which is why they could be tested without a screen. `python main.py --cli` uses them in a plain console.
- Spoken output uses one queue and a fresh pyttsx3 engine per sentence in a dedicated thread, which avoids the well-known "second sentence is silent" problem on Windows.

## 6. Folder structure
```
Python_Task1_VoiceAssistant/
|-- main.py                  start the app (GUI, or --cli)
|-- requirements.txt  .env.example  .gitignore  LICENSE  config.json
|-- setup.bat  run.bat  test.bat  diagnose.bat
|-- core/      assistant.py  command_handler.py  nlp.py  listener.py  text_to_speech.py
|              voice_session.py  config.py  logging_setup.py  messages.py
|-- features/  email_service.py  weather_service.py  search_service.py  reminder_service.py
|              joke_service.py  custom_commands.py  online_lookup.py
|-- gui/       main_window.py  workers.py  styles.py
|-- data/      knowledge_base.json  custom_commands.json
|-- tests/     (unit tests + run_qa.py)      tools/diagnose.py
|-- docs/      QA_REPORT.md  DEMO_VIDEO_SCRIPT.md  LINKEDIN_POST.md  SUBMISSION_CHECKLIST.md
|-- assets/  screenshots/  logs/
```
Note: the speech-recognition module is called `core/listener.py` (not `speech_recognition.py`) so that it can never clash with the real `speech_recognition` package.

## 7-12. Install and launch (Windows 10/11)
1. Install **Python 3.12 (64-bit)** from python.org. Tick **"Add python.exe to PATH"**.
2. Extract the ZIP anywhere (for example your Desktop) and open the folder.
3. Double-click **`setup.bat`**. It checks Python, creates a `.venv` virtual environment, upgrades pip, installs `requirements.txt`, and creates `.env` from `.env.example`.
4. (Optional) Open `.env` in Notepad and add your keys (sections 17-19).
5. Double-click **`run.bat`** to start VYOM.

Manual equivalent (Command Prompt inside the project folder):
```
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
python main.py
```
Text-only mode without PySide6 or a microphone: `python main.py --cli`.

## 13. Using voice commands
Press **Start Assistant**, wait for the green "Listening" status, then speak. Examples:

| Say | Result |
|---|---|
| "Hello" / "Hey VYOM" / "Good morning" | Greeting |
| "What can you do?" / "Help" | Feature list |
| "What is the time?" / "What is today's date?" / "What day is today?" | Time, date, weekday |
| "Search for Python programming" / "Google machine learning" | Opens Google in your browser |
| "What is the weather in Pune?" | Live weather (needs API key) |
| "Remind me after 5 minutes to drink water" | Background reminder |
| "Send an email" | Guided email with confirmation |
| "Explain machine learning" / "What is SQL?" / "Tell me about Python" | Knowledge-base answer |
| "Tell me a joke" | A joke |
| "Open YouTube" | Custom command |
| "Stop listening" | Back to standby |
| "Exit assistant" | Closes VYOM |

## 14. Using text commands
Type in the box at the bottom and press Enter or **Send**. The quick buttons (Time, Date, Help, Weather, Search, Email) send ready-made commands; Weather and Search first ask for the city or topic.

## 15. Microphone setup
Windows Settings -> Privacy & security -> Microphone: turn on "Microphone access" and "Let desktop apps access your microphone". Set your microphone as the default input device in Settings -> System -> Sound. Run `diagnose.bat` to check it.

## 16. Speech recognition troubleshooting
- **"I cannot use the microphone"** - the microphone is off/blocked, PyAudio is not installed, or another app has exclusive control. Run `diagnose.bat`.
- **"I could not reach the speech recognition service"** - the Google web recognizer needs internet. Press Start again later, or type.
- **VYOM often says "didn't understand"** - speak closer to the microphone, reduce noise, or raise `listen_timeout`/`phrase_time_limit` in `config.json`. Change `language` (for example `en-US`) if your accent is recognised better.
- **PyAudio will not install** - use Python 3.12 64-bit (PyAudio 0.2.14 has a ready-made wheel for it).

## 17. Email configuration and Gmail App Password
VYOM never needs your normal Gmail password.
1. Open your Google Account -> **Security** and turn on **2-Step Verification**.
2. Open https://myaccount.google.com/apppasswords (search "App passwords" in your account if the link does not open).
3. Create an app password (name it "VYOM"). Google shows 16 characters.
4. In `.env` set:
```
EMAIL_ADDRESS=yourname@gmail.com
EMAIL_APP_PASSWORD=abcd efgh ijkl mnop
```
(spaces in the password are fine). Restart VYOM. Without these values email is simply disabled and everything else works. Never share or upload `.env`.

## 18. Weather API setup
Create a free account at https://openweathermap.org, copy your API key, and set `OPENWEATHER_API_KEY=...` in `.env`. **New keys can take up to a couple of hours to activate**; until then VYOM reports that the key was rejected. Optionally set `assistant.default_city` in `config.json`.

## 19. Optional settings (`config.json`)
Voice `rate`, `volume`, `voice_index` (0, 1, ... picks another installed Windows voice), `muted`; speech `language`, `listen_timeout`, `phrase_time_limit`, `calibration_seconds`, `max_consecutive_failures`; `assistant.user_name` (used in greetings), `assistant.default_city`, `assistant.online_lookup` (true/false); `email.contacts` (for example `{"mom": "mom@example.com"}` so you can say "mom"); `weather.units` (`metric` or `imperial`). Missing or broken settings fall back to safe defaults. The **Settings** button shows what is configured (never the secrets).

## 20. Custom commands (`data/custom_commands.json`)
```json
{"phrases": ["open youtube", "launch youtube"], "type": "open_url", "url": "https://www.youtube.com", "response": "Opening YouTube."}
{"phrases": ["who is my best friend"], "type": "reply", "response": "Your best friend is Rahul."}
```
Rules: `type` is `reply` or `open_url`; URLs must start with http:// or https://. Invalid entries are skipped and written to `logs/vyom.log`. Restart VYOM after editing. Edit the "best friend" example to your own answer.

## 21. Editing the knowledge base (`data/knowledge_base.json`)
Each topic has a `name`, a list of `aliases` (other ways to say it, including short forms such as "ml") and an `answer`. Add a new object to the `topics` list; matching works on whole words, so use specific aliases. Restart VYOM afterwards.

General-knowledge questions that are not in the knowledge base are tried against Wikipedia (online, clearly labelled "From Wikipedia, online"). If you are offline or nothing relevant is found, VYOM says so honestly. Turn this off with `"online_lookup": false`.

## 22. Running automated tests
Double-click `test.bat`, or in the activated environment run `python tests\run_qa.py` (or `python -m unittest discover -s tests -t .`). The run rewrites `docs\QA_REPORT.md`. No real email is ever sent, no real weather request is made, and no microphone is used by the tests. The GUI tests run when PySide6 is installed (they use Qt's offscreen mode).

**Manual integration testing:** The project owner separately tested the GUI, microphone/voice interaction, weather lookup with the configured OpenWeatherMap API key, and Gmail email sending with a Google App Password. These are manual checks and are intentionally separate from the automated test suite. If you set up VYOM on another computer or with different accounts/devices, repeat the relevant checks using your own configuration.

## 23. Troubleshooting
| Problem | Fix |
|---|---|
| `setup.bat` says Python not found | Reinstall Python 3.12 with "Add to PATH" ticked |
| `run.bat` says virtual environment not found | Run `setup.bat` first |
| No voice output | Check Windows volume/voice; try the Mute button state; try `voice_index` 1 |
| Weather says key rejected | Wait up to 2 hours after creating the key; check for typos in `.env` |
| Email says login rejected | Use an App Password (16 characters) with 2-Step Verification on |
| Anything else | Run `diagnose.bat`, then read `logs\vyom.log` (secrets are masked there) |

## 24. Known limitations
- Google's free web speech recognizer needs internet; there is no offline speech recognition.
- There is no wake word: while the assistant is started it listens continuously until you press Stop or say "stop listening".
- The waveform animates according to the assistant state (listening, thinking, speaking); it does not display the live microphone level.
- Reminders live in memory and are lost when VYOM closes. Maximum is 24 hours.
- The knowledge base has 20 topics; online answers come from Wikipedia summaries and are only as good as the title match.
- Only Gmail SMTP is configured by default (other providers can be set in `config.json`, but only Gmail was considered).
- Designed and written for Windows; the console mode runs elsewhere.

## 25. Privacy, data processing and security

VYOM is a local desktop application, but some optional features communicate with external services when you use them. The following describes what information is involved:

- **Microphone and speech recognition:** When microphone mode is active, VYOM captures speech for the command you speak. The configured Google web speech recognizer processes the audio for transcription, so audio is sent to that external speech-recognition service. Use typed-command mode if you do not want to use the microphone or send audio for online recognition.
- **Text commands and local processing:** Commands typed into the GUI, intent matching, and answers from the bundled knowledge base are processed locally by the application. If optional Wikipedia lookup is enabled and a question is not answered locally, a search request is sent online.
- **Email:** When you request an email, VYOM collects the recipient address, subject and message. It reads the details back and sends the email only after you confirm. The email content and recipient are transmitted to the configured SMTP email provider (Gmail by default). Do not send confidential information unless you are comfortable using that email service.
- **Weather:** A weather request sends the requested city/location and API request information to OpenWeatherMap. The API key is read from the local `.env` file.
- **Credentials and configuration:** Gmail App Passwords and API keys are stored in the local `.env` file, not hard-coded in the source code. Keep `.env` private, do not commit it to GitHub, and do not share it in screenshots or messages. Use `.env.example` as the safe template.
- **Reminders and logs:** Reminders are held in application memory and are cleared when VYOM closes. Diagnostic logs are written locally under `logs/`; review them before sharing, even though the application is designed to mask secrets.

VYOM does not intentionally upload the local knowledge-base or custom-command files. Network access occurs only for features that need an external service, such as speech recognition, optional Wikipedia lookup, weather, web search, and sending email. You can avoid optional online features by not invoking them; use typed mode to avoid microphone-based recognition.

## 26. Submission
See `docs/SUBMISSION_CHECKLIST.md`, `docs/DEMO_VIDEO_SCRIPT.md` and `docs/LINKEDIN_POST.md`. GitHub upload, LinkedIn post, peer evaluation (if required) and the official submission form are separate actions for you to complete.

License: MIT (see `LICENSE`).
