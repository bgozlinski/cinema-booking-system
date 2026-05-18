"""Email composition helpers for the accounts app.

`send_activation_email` is the single seam for activation emails — views call
this; tests mock or inspect `mail.outbox` after it runs.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def send_activation_email(user, request: HttpRequest) -> None:
    """Send an account-activation email to `user`.
    Composes an absolute URL pointing at the `accounts:activate` view,
    using Django's HMAC-based `default_token_generator` (the same one used
    for password reset). The hash includes `is_active` and `password`, so
    once the user activates or changes their password the token auto-invalidates.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    relative_path = reverse(
        "accounts:activate",
        kwargs={"uidb64": uidb64, "token": token},
    )
    activation_url = request.build_absolute_uri(relative_path)

    subject = render_to_string("accounts/emails/activation_subject.txt").strip()
    body = render_to_string(
        "accounts/emails/activation_body.txt",
        context={"activation_url": activation_url, "user": user},
    )

    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
