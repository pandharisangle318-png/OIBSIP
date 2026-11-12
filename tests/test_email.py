import smtplib
import socket
import unittest

from tests.helpers import EMAIL_ENV, FakeSMTP
from features.email_service import (EmailError, EmailService, is_valid_address, parse_spoken_address)


def service(**kw):
    FakeSMTP.reset()
    args = dict(address="sender@gmail.com", app_password="secret123", smtp_factory=FakeSMTP)
    args.update(kw)
    return EmailService(args.pop("address"), args.pop("app_password"), **args)


class EmailServiceTests(unittest.TestCase):
    def test_missing_credentials(self):
        """Missing credentials raise a friendly error and send nothing."""
        for addr, pw in ((None, None), ("a@gmail.com", None), (None, "x")):
            with self.assertRaises(EmailError) as ctx:
                service(address=addr, app_password=pw).send("b@x.com", "s", "b")
            self.assertEqual(ctx.exception.kind, "missing_credentials")
        self.assertEqual(FakeSMTP.sent, [])

    def test_invalid_recipient(self):
        """An invalid recipient is rejected before any connection is made."""
        for bad in ("", "nobody", "a@b", "a b@c.com", "a@@c.com"):
            with self.subTest(bad=bad), self.assertRaises(EmailError) as ctx:
                service().send(bad, "s", "b")
            self.assertEqual(ctx.exception.kind, "invalid_recipient")

    def test_auth_failure(self):
        """SMTPAuthenticationError becomes an 'auth' error that does not reveal the password."""
        svc = service()
        FakeSMTP.raise_on_login = smtplib.SMTPAuthenticationError(535, b"nope")
        with self.assertRaises(EmailError) as ctx:
            svc.send("b@x.com", "s", "b")
        self.assertEqual(ctx.exception.kind, "auth")
        self.assertNotIn("secret123", ctx.exception.user_message)

    def test_connection_failure(self):
        """Connection problems become a 'network' error."""
        svc = service()
        for exc in (ConnectionRefusedError(), socket.gaierror(), smtplib.SMTPServerDisconnected()):
            FakeSMTP.raise_on_connect = exc
            with self.assertRaises(EmailError) as ctx:
                svc.send("b@x.com", "s", "b")
            self.assertEqual(ctx.exception.kind, "network")

    def test_timeout(self):
        """Timeouts become a 'timeout' error (checked before generic OSError)."""
        svc = service()
        FakeSMTP.raise_on_connect = socket.timeout()
        with self.assertRaises(EmailError) as ctx:
            svc.send("b@x.com", "s", "b")
        self.assertEqual(ctx.exception.kind, "timeout")

    def test_generic_smtp_error(self):
        """Other SMTP errors become 'send_failed'."""
        svc = service()
        FakeSMTP.raise_on_login = smtplib.SMTPException("boom")
        with self.assertRaises(EmailError) as ctx:
            svc.send("b@x.com", "s", "b")
        self.assertEqual(ctx.exception.kind, "send_failed")

    def test_successful_send_is_mocked(self):
        """A valid email is built with EmailMessage and passed to the mocked SMTP server."""
        svc = service()
        svc.send("friend@example.org", "Hello\nthere", "Body text")
        msg = FakeSMTP.sent[0]
        self.assertEqual(msg["To"], "friend@example.org")
        self.assertEqual(msg["Subject"], "Hello there")  # newline cannot inject headers
        self.assertIn("Body text", msg.get_content())

    def test_uses_ssl_port_465_and_gmail_host(self):
        """Defaults match the specification: smtp.gmail.com on port 465."""
        svc = service()
        self.assertEqual((svc.host, svc.port), ("smtp.gmail.com", 465))

    def test_spoken_address_parsing(self):
        """Spoken addresses ('at', 'dot') and saved contacts are converted."""
        self.assertEqual(parse_spoken_address("john dot doe at gmail dot com"), "john.doe@gmail.com")
        self.assertEqual(parse_spoken_address("Sam@Example.com."), "sam@example.com")
        self.assertEqual(parse_spoken_address("mom", {"Mom": "mom@home.in"}), "mom@home.in")
        self.assertIsNone(parse_spoken_address("hello world"))
        self.assertTrue(is_valid_address("a.b+c@sub.domain.co.in"))

    def test_password_never_in_exception_text(self):
        """No error message contains the app password."""
        svc = service(app_password="TOPSECRETPW")
        FakeSMTP.raise_on_login = smtplib.SMTPAuthenticationError(535, b"bad TOPSECRETPW")
        with self.assertRaises(EmailError) as ctx:
            svc.send("b@x.com", "s", "b")
        self.assertNotIn("TOPSECRETPW", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
