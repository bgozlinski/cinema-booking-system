"""Email composition helpers for the accounts app.

`send_activation_email` is the single seam for activation emails — views call
this; tests mock or inspect `mail.outbox` after it runs.
"""

from __future__ import annotations

import sys

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def send_activation_email(user, request: HttpRequest) -> None:
    """Send an account-activation email to `user`."""
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

    # Dev convenience: Django's console email backend wraps long lines via
    # MIME quoted-printable ("=\n" soft-breaks), which breaks copy-paste of
    # the activation URL from the terminal. In DEBUG mode, print the clean
    # URL on its own line for easy grabbing. Production (DEBUG=False) is
    # unaffected — real email clients handle quoted-printable correctly.
    if settings.DEBUG:
        print(
            f"\n=== ACTIVATION LINK (dev convenience, copy-paste) ===\n"
            f"{activation_url}\n"
            f"=====================================================\n",
            file=sys.stderr,
        )
