"""User-facing messages that are part of the specification."""

UNINTELLIGIBLE = "Sorry, I didn't understand that. Could you please repeat?"
UNKNOWN_COMMAND = "Sorry, I am not sure how to help with that. Say help to hear what I can do."
TROUBLE_HEARING = (
    "I am having trouble understanding you. Please check your microphone, "
    "or type your command in the box below. Press Start Assistant to try again."
)
MIC_UNAVAILABLE = (
    "I cannot use the microphone right now. Check that it is connected, allowed in "
    "Windows privacy settings, and that PyAudio is installed. You can still type commands."
)
NETWORK_SPEECH = (
    "I could not reach the speech recognition service. Please check your internet "
    "connection, then press Start Assistant to retry, or type your command."
)
HELP = (
    "I can greet you, tell the time and date, search Google, report live weather for a city, "
    "send an email by voice with confirmation, set timed reminders, tell jokes, explain topics "
    "such as machine learning or Python, and run your custom commands such as opening YouTube. "
    "Try: what is the time, weather in Pune, remind me in 5 minutes to drink water, "
    "or explain machine learning."
)
