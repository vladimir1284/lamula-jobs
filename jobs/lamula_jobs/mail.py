"""Envío de correo por SMTP (Brevo en producción). Todo por entorno; `SMTP_HOST=console` solo vuelca a stderr."""

from __future__ import annotations

import smtplib
import sys
from dataclasses import dataclass, field
from email.message import EmailMessage

from .config import env


class EnvioFallido(RuntimeError):
    pass


@dataclass
class Mailer:
    host: str
    port: int
    user: str
    password: str
    remitente: str
    enviados: list[EmailMessage] = field(default_factory=list)  # solo se llena en modo console

    @classmethod
    def from_env(cls) -> "Mailer":
        host = env("SMTP_HOST")
        if host == "console":
            return cls("console", 0, "", "", env("MAIL_FROM", "demo@localhost"))
        return cls(host, int(env("SMTP_PORT", "587")), env("SMTP_USER"), env("SMTP_PASSWORD"), env("MAIL_FROM"))

    def enviar(self, para: str, asunto: str, texto: str, *, responder_a: str | None = None) -> None:
        m = EmailMessage()
        m["From"], m["To"], m["Subject"] = self.remitente, para, asunto
        if responder_a:
            m["Reply-To"] = responder_a
        m.set_content(texto)
        if self.host == "console":
            self.enviados.append(m)
            print(f"--- correo a {para}: {asunto}\n{texto}\n---", file=sys.stderr)
            return
        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as s:
                s.starttls()
                s.login(self.user, self.password)
                s.send_message(m)
        except (smtplib.SMTPException, OSError) as exc:
            raise EnvioFallido(f"{type(exc).__name__}: {exc}") from exc
