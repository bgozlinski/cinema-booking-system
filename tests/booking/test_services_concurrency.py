"""Concurrency proof for create_booking row-locking (US-20 / §5.2).

Requires a real DB transaction (transaction=True) + Postgres row locks; SQLite
won't truly serialize. Each thread uses its own connection and must close it.
"""

import threading

import pytest
from django.db import connection

from apps.booking.models import Booking, BookingStatus
from apps.booking.services import NotEnoughSeatsError, create_booking
from tests.accounts.factories import UserFactory
from tests.cinema.factories import HallFactory, ScreeningFactory


@pytest.mark.django_db(transaction=True)
def test_concurrent_booking_no_overbooking():
    screening = ScreeningFactory(hall=HallFactory(capacity=5))
    users = [UserFactory(), UserFactory()]
    barrier = threading.Barrier(2)
    results: dict[int, str] = {}

    def worker(idx: int) -> None:
        barrier.wait()  # release both threads together to maximize contention
        try:
            create_booking(user=users[idx], screening=screening, seats_count=3)
            results[idx] = "ok"
        except NotEnoughSeatsError:
            results[idx] = "rejected"
        finally:
            connection.close()  # close this thread's connection

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # capacity 5, both want 3 → exactly one wins, the other is rejected
    assert sorted(results.values()) == ["ok", "rejected"]
    booked = sum(
        b.seats_count
        for b in Booking.objects.filter(screening=screening, status=BookingStatus.PENDING)
    )
    assert booked == 3
    assert booked <= 5
