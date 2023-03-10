import smtplib
from email.message import EmailMessage
from logging.handlers import SMTPHandler
from typing import Optional


class SMTPConnectionWrapper:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl = True
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.from_address = None
        self.connection = None

    def open(self):
        from icbot.config import settings, ConfigurationError

        if not self.host and not settings.SMTP_HOST:
            raise ConfigurationError(
                "No SMTP hostname provided (did you forget to set the SMTP_HOST setting?)"
            )
        if self.connection:
            return
        self.from_address = settings.EMAIL_FROM_ADDRESS
        connection_class = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
        self.connection = connection_class(
            self.host or settings.SMTP_HOST,
            self.port or settings.SMTP_PORT
        )
        username = self.username or settings.SMTP_USERNAME
        password = self.password or settings.SMTP_PASSWORD
        if username is not None and password is not None:
            self.connection.login(username, password)

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
        message["From"] = from_addr or self.from_address
        message["To"] = ", ".join(to_addrs)
        self.send_email(message)


class SMTPSSLHandler(SMTPHandler):
    def __init__(self, *args, **kwargs):
        self.retries = kwargs.pop("retries", 1)
        super().__init__(*args, **kwargs)
        self.connection_wrapper = SMTPConnectionWrapper(
            self.mailhost,
            self.mailport,
            self.username,
            self.password
        )

    def emit(self, record):
        for i in range(self.retries):
            try:
                self.connection_wrapper.make_and_send_email(
                    self.toaddrs,
                    self.getSubject(record),
                    self.format(record)
                )
            except Exception:
                if i + 1 < self.retries:
                    continue
                self.handleError(record)
            break
