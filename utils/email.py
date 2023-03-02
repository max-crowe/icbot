import smtplib
from email.message import EmailMessage
from logging.handlers import SMTPHandler
from typing import Optional

from icbot.config import settings
from icbot.settings import ConfigurationError


class SMTPConnectionWrapper:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl = True
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
        connection_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        self.connection = connection_class(self.host, self.port)
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


class SMTPSSLHandler(SMTPHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection_wrapper = SMTPConnectionWrapper()

    def emit(self, record):
        try:
            self.connection_wrapper.make_and_send_email(
                self.toaddrs,
                self.getSubject(record),
                self.format(record)
            )
        except Exception:
            self.handleError(record)
