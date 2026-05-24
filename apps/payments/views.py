import json

import stripe
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.payments.services import process_webhook_event


@csrf_exempt
@require_POST
def stripe_webhook(request) -> HttpResponse:
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")
    process_webhook_event(json.loads(payload))
    return HttpResponse(status=200)
