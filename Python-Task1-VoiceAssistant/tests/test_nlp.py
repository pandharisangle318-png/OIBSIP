import unittest

from tests.helpers import make_kb
from core.nlp import detect_intent, normalize

ML_QUESTIONS = [
    "What is Machine Learning?",
    "Explain Machine Learning.",
    "Can you explain machine learning in simple words?",
    "Tell me about Machine Learning.",
    "What do you mean by Machine Learning?",
    "Give me a simple explanation of Machine Learning.",
    "Explain ML.",
    "What is ML?",
    "I want to learn about machine learning.",
    "Tell me something about machine learning.",
]


class NlpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = make_kb()

    def assertTopic(self, question, name):
        match = self.kb.find_topic(question)
        self.assertIsNotNone(match, question)
        self.assertEqual(match.topic["name"], name, question)

    def test_all_ten_machine_learning_variations(self):
        """All ten Machine Learning question variations return the Machine Learning answer."""
        for question in ML_QUESTIONS:
            with self.subTest(question=question):
                self.assertTopic(question, "Machine Learning")
                self.assertIn("Machine Learning is a branch", self.kb.answer(question))

    def test_artificial_intelligence_variations(self):
        """AI question variations return the Artificial Intelligence answer."""
        for q in ["What is Artificial Intelligence?", "Explain AI", "Can you explain artificial intelligence in simple words?",
                  "Tell me about AI", "I want to learn about artificial intelligence", "What do you mean by AI?"]:
            with self.subTest(q=q):
                self.assertTopic(q, "Artificial Intelligence")

    def test_python_variations(self):
        """Python question variations return the Python answer."""
        for q in ["What is Python?", "Explain Python programming", "Tell me about the Python language",
                  "Can you explain python in simple words?", "I want to learn about python"]:
            with self.subTest(q=q):
                self.assertTopic(q, "Python")

    def test_other_required_topics(self):
        """Deep Learning, SQL, MySQL, Java and JavaScript are not confused with each other."""
        self.assertTopic("What is deep learning?", "Deep Learning")
        self.assertTopic("Explain SQL", "SQL")
        self.assertTopic("What is MySQL?", "MySQL")
        self.assertTopic("What is Java?", "Java")
        self.assertTopic("What is JavaScript?", "JavaScript")
        self.assertTopic("Explain cloud computing", "Cloud Computing")
        self.assertTopic("What is an operating system?", "Operating System")

    def test_every_listed_topic_exists(self):
        """The knowledge base contains all 20 required topics."""
        names = {t["name"].lower() for t in self.kb.topics}
        required = ["artificial intelligence", "machine learning", "deep learning", "python", "java", "programming",
                    "computer science", "internet", "database", "sql", "mysql", "data science", "cyber security",
                    "cloud computing", "html", "css", "javascript", "computer networks", "operating system",
                    "software engineering"]
        for name in required:
            self.assertIn(name, names)

    def test_fuzzy_typos_still_match(self):
        """Minor misspellings still find the right topic."""
        self.assertTopic("what is machin learnin", "Machine Learning")
        self.assertTopic("explain artifical intelligence", "Artificial Intelligence")

    def test_unrelated_questions_do_not_match(self):
        """Unrelated questions never return a weak, wrong topic."""
        for q in ["What is the capital of France?", "Tell me about quantum chromodynamics", "who won the world cup",
                  "explain photosynthesis", "what is love"]:
            with self.subTest(q=q):
                self.assertIsNone(self.kb.find_topic(q))

    def test_normalize(self):
        """Normalisation lower-cases, expands contractions and strips punctuation."""
        self.assertEqual(normalize("What's  ML?!"), "what is ml")
        self.assertEqual(normalize(None), "")

    def test_intents(self):
        """Core intents are recognised from natural phrasing."""
        cases = {
            "Hello": "greeting", "Hey VYOM": "greeting", "Good morning": "greeting", "How are you?": "how_are_you",
            "What is your name?": "identity", "Who are you?": "identity", "What can you do?": "help", "Help": "help",
            "Stop listening": "stop_listening", "Exit assistant": "exit",
            "What is the time?": "time", "Tell me the current time.": "time", "What is today's date?": "date",
            "What day is today?": "day", "Search for Python programming": "search", "Google machine learning": "search",
            "Send an email": "email", "Remind me after 5 minutes to drink water": "reminder_set",
            "Set a reminder for 10 minutes": "reminder_set", "Tell me a joke": "joke", "Say something funny": "joke",
            "Make me laugh": "joke", "What is the weather in Mumbai?": "weather", "Explain machine learning": "unknown",
        }
        for text, intent in cases.items():
            with self.subTest(text=text):
                self.assertEqual(detect_intent(text).name, intent)

    def test_weather_city_and_search_query_extraction(self):
        """City and search topic are extracted from the sentence."""
        self.assertEqual(detect_intent("What is the weather in Mumbai?").params["city"], "Mumbai")
        self.assertEqual(detect_intent("Tell me the weather in Pune").params["city"], "Pune")
        self.assertEqual(detect_intent("weather in navi mumbai today").params["city"], "Navi Mumbai")
        self.assertEqual(detect_intent("Search for latest technology news").params["query"], "latest technology news")
        self.assertEqual(detect_intent("Google machine learning").params["query"], "machine learning")
        self.assertEqual(detect_intent("search for artificial intelligence on google").params["query"], "artificial intelligence")


if __name__ == "__main__":
    unittest.main()
