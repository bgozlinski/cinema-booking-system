from django.urls import path

from apps.payments.views import stripe_webhook

app_name = "payments"

urlpatterns = [
    path("webhooks/stripe/", stripe_webhook, name="stripe_webhook"),
]
