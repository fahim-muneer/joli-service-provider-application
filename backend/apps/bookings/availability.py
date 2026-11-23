"""What a customer can book: a month calendar (how free is each day) and the free start
times of one day. Built for the date picker. Public data: it only counts providers, never names them.

Every call costs a fixed number of queries (offers, schedules, bookings), however many providers
there are: the work is done in Python over those three result sets."""
import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from apps.providers import selectors as provider_selectors
from apps.providers.models import ProviderAvailability

from .models import Booking
from .services import MAX_DAYS_AHEAD, MIN_LEAD

GRID_FIRST_HOUR = 6    # start times are offered on the hour, from 06:00 ...
GRID_LAST_HOUR = 21    # ... to 21:00 (the job must still fit the provider's working hours)
LIMITED_BELOW = 4      # a day with fewer free start times than this is "limited"


def _aware(naive):
    return timezone.make_aware(naive)


def _load(service, city_id, area_id, first_day, last_day):
    """The three data sets everything below is computed from."""
    rows = list(
        provider_selectors.offers_for_service(service.pk, city_id=city_id, area_id=area_id)
        .values_list("provider_id", "estimated_duration_minutes")
    )
    ids = {provider_id for provider_id, _ in rows}
    windows, busy = defaultdict(list), defaultdict(list)
    if ids:
        for w in ProviderAvailability.objects.filter(provider_id__in=ids, available_date__range=(first_day, last_day)):
            windows[(w.provider_id, w.available_date)].append(w)
        low = _aware(datetime.combine(first_day, time.min))
        high = _aware(datetime.combine(last_day + timedelta(days=1), time.min))
        for provider_id, start, end in Booking.objects.filter(
            assigned_provider_id__in=ids, status__in=Booking.ACTIVE_STATUSES, scheduled_at__lt=high, ends_at__gt=low
        ).values_list("assigned_provider_id", "scheduled_at", "ends_at"):
            busy[provider_id].append((start, end))
    return rows, windows, busy


def _free_providers(rows, windows, busy, day, hour, cutoff):
    """How many providers could start a job at day/hour."""
    naive = datetime.combine(day, time(hour))
    start = _aware(naive)
    if start < cutoff:
        return 0
    free = 0
    for provider_id, minutes in rows:
        if not provider_selectors.window_fits(windows[(provider_id, day)], naive, minutes):
            continue
        end = start + timedelta(minutes=minutes)
        if any(b_start < end and b_end > start for b_start, b_end in busy[provider_id]):
            continue
        free += 1
    return free


def bookable_range(now=None):
    today = timezone.localdate(now or timezone.now())
    return today, today + timedelta(days=MAX_DAYS_AHEAD)


def month_calendar(service, year, month, *, city_id=None, area_id=None, now=None):
    now = now or timezone.now()
    today, last_bookable = bookable_range(now)
    last_day_number = calendar.monthrange(year, month)[1]
    low = max(date(year, month, 1), today)
    high = min(date(year, month, last_day_number), last_bookable)
    loaded = _load(service, city_id, area_id, low, high) if low <= high else ([], {}, {})
    cutoff = now + MIN_LEAD

    days = []
    for number in range(1, last_day_number + 1):
        day = date(year, month, number)
        if day < today:
            status, slots = "past", 0
        elif day > last_bookable:
            status, slots = "unavailable", 0
        else:
            slots = sum(
                1 for hour in range(GRID_FIRST_HOUR, GRID_LAST_HOUR + 1)
                if _free_providers(*loaded, day, hour, cutoff) > 0
            )
            status = "unavailable" if slots == 0 else "limited" if slots < LIMITED_BELOW else "available"
        days.append({
            "date": day.isoformat(), "status": status, "slots": slots,
            "price": str(service.base_price) if status in ("available", "limited") else None,
        })
    return days


def day_slots(service, day, *, city_id=None, area_id=None, now=None):
    now = now or timezone.now()
    loaded = _load(service, city_id, area_id, day, day)
    cutoff = now + MIN_LEAD
    slots = []
    for hour in range(GRID_FIRST_HOUR, GRID_LAST_HOUR + 1):
        providers = _free_providers(*loaded, day, hour, cutoff)
        if providers:
            start = datetime.combine(day, time(hour))
            slots.append({
                "start": f"{hour:02d}:00",
                "end": (start + timedelta(minutes=service.estimated_duration_minutes)).strftime("%H:%M"),
                "start_at": _aware(start).isoformat(),
                "providers": providers,
            })
    return slots