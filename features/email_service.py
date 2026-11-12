"""Sending email through Gmail SMTP (SSL) with smtplib."""
from __future__ import annotations

import logging
import re
import smtplib
import socket
import ssl
from email.message import EmailMessage
from typing import Callable, Mapping, Optional

log = logging.getLogger(__name__)

ADDRESS_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")

MISSING_CREDENTIALS = (
    "Email is not set up yet. Add EMAIL_ADDRESS and EMAIL_APP_PASSWORD to the .env file "
    "(use a Gmail App Password, not your normal password) and restart VYOM. See the README."
)


class EmailError(Exception):
    def __init__(self, kind: str, user_message: str) -> None:
        super().__init__(user_message)
        self.kind = kind
        self.user_message = user_message


def is_valid_address(address: str) -> bool:
    return bool(address) and len(address) <= 254 and bool(ADDRESS_RE.match(address))


def parse_spoken_address(text: str, contacts: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """Turn 'john dot doe at gmail dot com' (or a saved contact name) into an address."""
    raw = (text or "").strip().lower()
    if not raw:
        return None
    if contacts:
        for name, address in contacts.items():
            if raw == str(name).strip().lower() and is_valid_address(str(address)):
                return str(address)
    candidate = raw.rstrip(".,!? ")
    candidate = re.sub(r"\s+at the rate of\s+|\s+at\s+", "@", candidate)
    candidate = re.sub(r"\s+dot\s+", ".", candidate)
    candidate = re.sub(r"\s+underscore\s+", "_", candidate)
    candidate = re.sub(r"\s+(dash|hyphen)\s+", "-", candidate)
    candidate = re.sub(r"\s+", "", candidate)
    return candidate if is_valid_address(candidate) else None


def speakable_address(address: str) -> str:
    return address.replace("@", " at ").replace(".", " dot ")


class EmailService:
    def __init__(
        self,
        address: Optional[str],
        app_password: Optional[str],
        host: str = "smtp.gmail.com",
        port: int = 465,
        timeout: float = 20,
        smtp_factory: Callable[..., smtplib.SMTP_SSL] = smtplib.SMTP_SSL,
    ) -> None:
        self._address = address
        self._password = app_password
        self.host = host
        self.port = int(port)
        self.timeout = timeout
        self._factory = smtp_factory

    @property
    def configured(self) -> bool:
        return bool(self._address and self._password)

    def credential_problem(self) -> Optional[str]:
        return None if self.configured else MISSING_CREDENTIALS

    def send(self, recipient: str, subject: str, body: str) -> None:
        """Send one email. Raises EmailError with a friendly message on failure."""
        if not self.configured:
            raise EmailError("missing_credentials", MISSING_CREDENTIALS)
        recipient = (recipient or "").strip()
        if not is_valid_address(recipient):
            raise EmailError("invalid_recipient", "That recipient address does not look valid.")
        subject = " ".join((subject or "").split()) or "(no subject)"
        body = (body or "").strip()
        if not body:
            raise EmailError("empty_body", "The message is empty, so I did not send it.")

        message = EmailMessage()
        message["From"] = self._address
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        try:
            context = ssl.create_default_context()
            with self._factory(self.host, self.port, timeout=self.timeout, context=context) as server:
                server.login(self._address, self._password)
                server.send_message(message)
        except smtplib.SMTPAuthenticationError:
            raise EmailError(
                "auth",
                "Gmail rejected the login. Check EMAIL_ADDRESS and that EMAIL_APP_PASSWORD is a valid "
                "16 character App Password with 2-Step Verification turned on.",
            )
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused):
            raise EmailError("invalid_recipient", "The mail server refused that address. Please check it and try again.")
        except (socket.timeout, TimeoutError):
            raise EmailError("timeout", "The mail server took too long to respond. Please try again.")
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError):
            raise EmailError("network", "I could not connect to the mail server. Please check your internet connection.")
        except smtplib.SMTPException as exc:  # note: SMTPException is an OSError subclass, so it must come first
            log.warning("SMTP error: %s", type(exc).__name__)
            raise EmailError("send_failed", "The email could not be sent because of a mail server error.")
        except (ConnectionError, socket.gaierror, ssl.SSLError, OSError):
            raise EmailError("network", "I could not connect to the mail server. Please check your internet connection.")
