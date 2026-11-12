import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import FakeOnline, FakeSMTP, OpenerRecorder, make_handler
from core import messages
from features.online_lookup import LookupError_


def say(handler, text):
    return handler.handle(text)[0].text


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.h, self.parts = make_handler()

    def tearDown(self):
        self.parts["reminders"].shutdown()

    def test_hello(self):
        """'Hello' returns the predefined greeting."""
        self.assertIn("Hello! I am VYOM", say(self.h, "Hello"))

    def test_other_greetings_and_identity(self):
        """Hi, Hey VYOM, time-of-day greetings, how are you, name and who are you all answer naturally."""
        for text in ("Hi", "Hey VYOM"):
            self.assertIn("VYOM", say(self.h, text))
        self.assertTrue(say(self.h, "Good morning").startswith("Good morning!"))
        self.assertTrue(say(self.h, "Good afternoon").startswith("Good afternoon!"))
        self.assertTrue(say(self.h, "Good evening").startswith("Good evening!"))
        self.assertIn("doing great", say(self.h, "How are you?"))
        self.assertIn("I am VYOM", say(self.h, "What is your name?"))
        self.assertIn("I am VYOM", say(self.h, "Who are you?"))

    def test_help(self):
        """Help and 'what can you do' list the features."""
        self.assertEqual(say(self.h, "help"), messages.HELP)
        self.assertEqual(say(self.h, "What can you do?"), messages.HELP)

    def test_stop_listening_and_exit_actions(self):
        """Stop listening / exit produce the right action."""
        self.assertEqual(self.h.handle("Stop listening")[0].action, "stop_listening")
        self.assertEqual(self.h.handle("Exit assistant")[0].action, "exit")

    def test_time(self):
        """Current time is spoken from the clock (offline)."""
        self.assertEqual(say(self.h, "What is the time?"), "The time is 3:05 PM.")
        self.assertEqual(say(self.h, "Tell me the current time."), "The time is 3:05 PM.")

    def test_date_and_day(self):
        """Date and weekday are spoken from the clock (offline)."""
        self.assertEqual(say(self.h, "What is today's date?"), "Today's date is Wednesday, 11 November 2026.")
        self.assertEqual(say(self.h, "What day is today?"), "Today is Wednesday.")

    def test_search_opens_safe_google_url(self):
        """Search opens a URL-encoded Google link; never a shell command."""
        say(self.h, "Search for Python programming & more")
        self.assertEqual(self.parts["opener"].urls, ["https://www.google.com/search?q=Python+programming+%26+more"])

    def test_search_without_topic_asks_then_searches(self):
        """'search' alone asks for a topic, the next message is the query."""
        self.assertIn("What would you like me to search", say(self.h, "search"))
        self.assertTrue(self.h.expects_reply)
        say(self.h, "artificial intelligence")
        self.assertIn("q=artificial+intelligence", self.parts["opener"].urls[0])
        self.assertFalse(self.h.expects_reply)

    def test_search_browser_failure(self):
        """A browser that fails to open gives a friendly message."""
        h, _ = make_handler(opener=OpenerRecorder(result=False))
        self.assertIn("could not open your web browser", say(h, "google machine learning"))

    def test_weather_without_key_is_friendly(self):
        """Weather without an API key explains how to configure it."""
        self.assertIn("OPENWEATHER_API_KEY", say(self.h, "What is the weather in Mumbai?"))

    def test_joke_offline(self):
        """Jokes work offline and do not repeat back-to-back."""
        first, second = say(self.h, "Tell me a joke"), say(self.h, "Make me laugh")
        self.assertTrue(first and second and first != second)

    def test_reminder_command(self):
        """A reminder command schedules a background reminder."""
        reply = say(self.h, "Remind me after 5 minutes to drink water")
        self.assertEqual(reply, "Okay, I will remind you to drink water in 5 minutes.")
        self.assertEqual(len(self.parts["reminders"].active()), 1)
        self.assertIn("Cancelled 1 reminder", say(self.h, "cancel my reminders"))

    def test_reminder_invalid(self):
        """A reminder without a time is rejected politely."""
        self.assertIn("could not understand when", say(self.h, "remind me to drink water"))

    def test_custom_commands(self):
        """Custom commands open URLs or reply from the JSON file."""
        say(self.h, "Open YouTube")
        self.assertEqual(self.parts["opener"].urls, ["https://www.youtube.com"])
        self.assertIn("best friend", say(self.h, "Who is my best friend?"))

    def test_custom_commands_validation(self):
        """Unsafe or malformed custom commands are rejected, not executed."""
        bad = {"commands": [
            {"phrases": ["run it"], "type": "shell", "response": "x"},
            {"phrases": ["open file"], "type": "open_url", "url": "file:///C:/Windows/system32/cmd.exe"},
            {"phrases": ["js"], "type": "open_url", "url": "javascript:alert(1)"},
            {"phrases": [], "type": "reply", "response": "x"},
            {"phrases": ["good one"], "type": "reply", "response": "fine"},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps(bad))
            h, parts = make_handler(custom_json=path)
            self.assertEqual(len(parts["custom"].commands), 1)
            self.assertEqual(len(parts["custom"].problems), 4)
            self.assertEqual(say(h, "good one"), "fine")
            self.assertEqual(say(h, "run it"), messages.UNKNOWN_COMMAND)
            parts["reminders"].shutdown()

    def test_unknown_command(self):
        """CASE 3: an unsupported command gets the exact unknown-command sentence."""
        self.assertEqual(say(self.h, "blah blah blah"), messages.UNKNOWN_COMMAND)

    def test_knowledge_answers_in_handler(self):
        """The ML question from the failed project now gets the Machine Learning answer."""
        reply = say(self.h, "Can you explain machine learning in simple words?")
        self.assertIn("Machine Learning is a branch of Artificial Intelligence", reply)

    def test_unrelated_question_falls_back_safely(self):
        """Unknown topics with online lookup off give an honest offline fallback."""
        h, parts = make_handler()
        reply = say(h, "What is the capital of France?")
        self.assertIn("do not have that in my offline knowledge base", reply)
        parts["reminders"].shutdown()

    def test_online_lookup_used_and_labelled(self):
        """Online answers are labelled as online and use the topic words only."""
        online = FakeOnline(answer="Paris is the capital of France.")
        h, parts = make_handler(online=online)
        reply = say(h, "What is the capital of France?")
        self.assertTrue(reply.startswith("From Wikipedia, online:"))
        self.assertEqual(online.queries, ["capital france"])
        parts["reminders"].shutdown()

    def test_online_failure_never_crashes(self):
        """Network failure or empty results in the online source fall back gracefully."""
        for online in (FakeOnline(error=LookupError_("timeout")), FakeOnline(answer=None)):
            h, parts = make_handler(online=online)
            reply = say(h, "What is the capital of France?")
            self.assertIn("could not find an answer", reply)
            parts["reminders"].shutdown()

    def test_offline_kb_wins_over_online(self):
        """A topic in the local knowledge base never triggers an online request."""
        online = FakeOnline(answer="should not be used")
        h, parts = make_handler(online=online)
        say(h, "What is Python?")
        self.assertEqual(online.queries, [])
        parts["reminders"].shutdown()

    def test_empty_input(self):
        """Empty or whitespace input produces no reply."""
        self.assertEqual(self.h.handle("   "), [])


class EmailDialogueTests(unittest.TestCase):
    def setUp(self):
        from tests.helpers import EMAIL_ENV
        self.h, self.parts = make_handler(env=EMAIL_ENV)

    def tearDown(self):
        self.parts["reminders"].shutdown()

    def start_to_confirm(self):
        self.assertIn("Who should I send", say(self.h, "Send an email"))
        self.assertIn("subject", say(self.h, "john dot doe at gmail dot com"))
        self.assertIn("What should the message say", say(self.h, "Meeting tomorrow"))
        return self.h.handle("Please join the meeting at ten")[0]

    def test_workflow_reads_back_and_waits_for_confirmation(self):
        """The assistant reads back recipient, subject and message and asks before sending."""
        reply = self.start_to_confirm()
        for part in ("john.doe@gmail.com", "Meeting tomorrow", "Please join the meeting at ten", "Would you like me to send this email?"):
            self.assertIn(part, reply.text)
        self.assertIn("john dot doe at gmail dot com", reply.speech)
        self.assertEqual(FakeSMTP.sent, [])  # nothing sent before confirmation

    def test_explicit_yes_sends(self):
        """Saying yes sends exactly one email through the (mocked) SMTP server."""
        self.start_to_confirm()
        self.assertIn("has been sent", say(self.h, "Yes"))
        self.assertEqual(len(FakeSMTP.sent), 1)
        msg = FakeSMTP.sent[0]
        self.assertEqual((msg["To"], msg["From"], msg["Subject"]), ("john.doe@gmail.com", "sender@gmail.com", "Meeting tomorrow"))

    def test_no_cancels(self):
        """Saying no cancels; nothing is sent."""
        self.start_to_confirm()
        self.assertIn("cancelled", say(self.h, "No"))
        self.assertEqual(FakeSMTP.sent, [])
        self.assertFalse(self.h.expects_reply)

    def test_unclear_answer_does_not_send(self):
        """An unclear answer re-asks instead of sending."""
        self.start_to_confirm()
        self.assertIn("yes to send", say(self.h, "maybe later"))
        self.assertEqual(FakeSMTP.sent, [])
        self.assertTrue(self.h.expects_reply)

    def test_cancel_anytime(self):
        """'cancel' at any step aborts the workflow."""
        say(self.h, "send an email")
        self.assertEqual(say(self.h, "cancel"), "Okay, cancelled.")
        self.assertFalse(self.h.expects_reply)

    def test_invalid_recipient_asks_again_then_gives_up(self):
        """An invalid address is re-asked; repeated failures cancel safely."""
        say(self.h, "send an email")
        self.assertIn("valid email address", say(self.h, "not an address"))
        self.assertIn("valid email address", say(self.h, "still not"))
        self.assertIn("cancelled", say(self.h, "nope nope"))
        self.assertFalse(self.h.expects_reply)

    def test_send_failure_reported(self):
        """An SMTP failure after confirmation is reported to the user."""
        import smtplib
        self.start_to_confirm()
        FakeSMTP.raise_on_login = smtplib.SMTPAuthenticationError(535, b"bad")
        self.assertIn("Gmail rejected the login", say(self.h, "yes"))

    def test_missing_credentials_blocks_workflow_only(self):
        """Without credentials the email flow explains setup and other features still work."""
        h, parts = make_handler()
        self.assertIn("EMAIL_APP_PASSWORD", say(h, "send an email"))
        self.assertFalse(h.expects_reply)
        self.assertIn("3:05 PM", say(h, "what is the time"))
        parts["reminders"].shutdown()

    def test_exit_during_dialogue(self):
        """'exit assistant' during a dialogue exits instead of being taken as an answer."""
        say(self.h, "send an email")
        self.assertEqual(self.h.handle("exit assistant")[0].action, "exit")


if __name__ == "__main__":
    unittest.main()
