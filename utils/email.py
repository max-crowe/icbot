import smtplib
from email.message import EmailMessage
from typing import Optional

from icbot.config import settings
from icbot.settings import ConfigurationError


class SMTPConnectionWrapper:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        self.host = host or settings.SMTP_HOST
        self.port = port or settings.SMTP_PORT
        self.username = username or settings.SMTP_USERNAME
        self.password = password or settings.SMTP_PASSWORD
        if not self.host:
            raise ConfigurationError(
                "No SMTP hostname provided (did you forget to set the SMTP_HOST setting?)"
            )
        self.connection = None

    def open(self):
        if self.connection:
            return
        self.connection = smtplib.SMTP(self.host, self.port)
        if self.username:
            self.connection.login(self.username, self.password)

    def close(self):
        if self.connection:
            try:
                self.connection.quit()
            except smtplib.SMTPServerDisconnected:
                self.connection.close()
        self.connection = None

    def send_email(self, email_message: EmailMessage):
        self.open()
        self.connection.send_message(email_message)

    def make_and_send_email(
        self,
        to_addrs: list[str],
        subject: str,
        body: str,
        from_addr: Optional[str] = None
    ):
        message = EmailMessage()
        message.set_content(body)
        message["Subject"] = subject
        message["From"] = from_addr or settings.EMAIL_FROM_ADDRESS
        message["To"] = ", ".join(to_addrs)
        self.send_email(message)
