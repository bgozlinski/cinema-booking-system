"""factory_boy factories for the payments app."""

import factory
from factory.django import DjangoModelFactory


class StripeEventFactory(DjangoModelFactory):
    """Default factory creates a checkout.session.completed event with mock payload."""

    class Meta:
        model = "payments.StripeEvent"

    event_id = factory.Sequence(lambda n: f"evt_test_{n}")
    event_type = "checkout.session.completed"
    payload = factory.LazyAttribute(
        lambda obj: {
            "id": obj.event_id,
            "type": obj.event_type,
            "data": {"object": {"client_reference_id": "1"}},
        }
    )
    # processed_at default None (raw event, not yet processed by webhook handler)
