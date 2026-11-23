from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .factories import make_provider
from .models import ProviderAvailability, ProviderProfile
from .selectors import is_within_availability

User = get_user_model()
Status = ProviderProfile.ApprovalStatus


def day(n):
    return timezone.localdate() + timedelta(days=n)


class AvailabilityTestCase(APITestCase):
    def setUp(self):
        self.profile = make_provider("+919500000001", status=Status.APPROVED)
        self.user = self.profile.user
        self.client.force_authenticate(self.user)
        self.schedule = reverse("provider-schedule-list")

    def add(self, date=None, start="09:00", end="17:00", **extra):
        body = {"date": (date or day(2)).isoformat(), "start_time": start, "end_time": end, **extra}
        return self.client.post(self.schedule, body, format="json")


class OnlineSwitchTests(AvailabilityTestCase):
    url_name = "provider-online"

    def test_roles(self):
        url = reverse(self.url_name)
        self.assertEqual(APIClient().get(url).status_code, 401)
        for phone, role in (("+919500000010", User.Role.CUSTOMER), ("+919500000011", User.Role.ADMIN)):
            self.client.force_authenticate(User.objects.create_user(phone=phone, password="x" * 12, full_name="T", role=role))
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_approved_provider_toggles(self):
        url = reverse(self.url_name)
        self.assertEqual(self.client.get(url).data, {"is_available": False, "approval_status": "approved"})
        self.assertTrue(self.client.patch(url, {"is_available": True}, format="json").data["is_available"])
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_available)
        self.assertFalse(self.client.patch(url, {"is_available": False}, format="json").data["is_available"])

    def test_only_approved_providers_can_go_online(self):
        url = reverse(self.url_name)
        for status in (Status.PENDING, Status.UNDER_REVIEW, Status.REJECTED, Status.SUSPENDED):
            ProviderProfile.objects.update(approval_status=status, is_available=False)
            self.assertEqual(self.client.patch(url, {"is_available": True}, format="json").status_code, 400, status)
        ProviderProfile.objects.update(is_available=True)               # offline is always allowed
        self.assertEqual(self.client.patch(url, {"is_available": False}, format="json").status_code, 200)

    def test_bad_payload(self):
        self.assertEqual(self.client.patch(reverse(self.url_name), {}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(reverse(self.url_name), {"is_available": "maybe"}, format="json").status_code, 400)


class ScheduleTests(AvailabilityTestCase):
    def test_roles(self):
        self.assertEqual(APIClient().get(self.schedule).status_code, 401)
        self.client.force_authenticate(User.objects.create_user(phone="+919500000010", password="x" * 12, full_name="T", role=User.Role.CUSTOMER))
        self.assertEqual(self.client.get(self.schedule).status_code, 403)

    def test_add_one_day(self):
        res = self.add()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["date"], day(2).isoformat())
        self.assertEqual((res.data[0]["start_time"], res.data[0]["end_time"], res.data[0]["is_available"]), ("09:00:00", "17:00:00", True))

    def test_add_several_days_at_once_and_duplicates_collapse(self):
        res = self.client.post(
            self.schedule,
            {"dates": [day(2).isoformat(), day(3).isoformat(), day(2).isoformat()], "start_time": "10:00", "end_time": "18:00"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual([w["date"] for w in res.data], [day(2).isoformat(), day(3).isoformat()])

    def test_send_exactly_one_of_date_or_dates(self):
        both = {"date": day(2).isoformat(), "dates": [day(3).isoformat()], "start_time": "09:00", "end_time": "10:00"}
        neither = {"start_time": "09:00", "end_time": "10:00"}
        for body in (both, neither):
            self.assertEqual(self.client.post(self.schedule, body, format="json").status_code, 400)

    def test_time_and_date_rules(self):
        cases = {
            "end before start": dict(start="17:00", end="09:00"),
            "end equals start": dict(start="09:00", end="09:00"),
            "past date": dict(date=day(-1)),
            "too far ahead": dict(date=day(91)),
        }
        for label, kw in cases.items():
            self.assertEqual(self.add(**kw).status_code, 400, label)
        self.assertEqual(self.add(date=day(90)).status_code, 201)          # the last allowed day
        self.assertEqual(self.add(date=day(0), start="00:00", end="23:00").status_code, 201)  # today is allowed
        bad = self.client.post(self.schedule, {"date": "tomorrow", "start_time": "9am", "end_time": "5pm"}, format="json")
        self.assertEqual(bad.status_code, 400)

    def test_overlap_rules(self):
        self.add(start="09:00", end="12:00")
        self.assertEqual(self.add(start="11:00", end="13:00").status_code, 400)   # overlaps
        self.assertEqual(self.add(start="08:00", end="09:30").status_code, 400)
        self.assertEqual(self.add(start="09:30", end="10:30").status_code, 400)   # inside
        self.assertEqual(self.add(start="12:00", end="15:00").status_code, 201)   # back to back is fine
        self.assertEqual(self.add(date=day(3), start="09:00", end="12:00").status_code, 201)  # other day is fine

    def test_a_blocked_window_may_sit_inside_working_hours(self):
        self.add(start="09:00", end="17:00")
        self.assertEqual(self.add(start="13:00", end="14:00", is_available=False).status_code, 201)
        self.assertEqual(self.add(start="13:30", end="15:00", is_available=False).status_code, 400)  # two blocks overlap

    def test_bulk_add_is_all_or_nothing(self):
        self.add(date=day(3), start="09:00", end="17:00")
        res = self.client.post(
            self.schedule,
            {"dates": [day(2).isoformat(), day(3).isoformat(), day(-1).isoformat()], "start_time": "10:00", "end_time": "12:00"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(len(res.data["dates"]), 2)                               # overlap + past, both reported
        self.assertEqual(ProviderAvailability.objects.count(), 1)

    def test_list_defaults_to_today_onwards_and_filters(self):
        ProviderAvailability.objects.create(provider=self.profile, available_date=day(-5), start_time="09:00", end_time="10:00")
        for n in (1, 5, 10):
            self.add(date=day(n))
        dates = lambda res: [w["date"] for w in res.data]
        self.assertEqual(dates(self.client.get(self.schedule)), [day(1).isoformat(), day(5).isoformat(), day(10).isoformat()])
        res = self.client.get(self.schedule, {"from": day(2).isoformat(), "to": day(6).isoformat()})
        self.assertEqual(dates(res), [day(5).isoformat()])
        self.assertEqual(self.client.get(self.schedule, {"from": "yesterday"}).status_code, 400)

    def test_edit_window(self):
        window_id = self.add().data[0]["id"]
        url = reverse("provider-schedule-detail", args=[window_id])
        res = self.client.patch(url, {"end_time": "18:00"}, format="json")
        self.assertEqual((res.data["start_time"], res.data["end_time"]), ("09:00:00", "18:00:00"))
        self.assertEqual(self.client.patch(url, {"start_time": "19:00"}, format="json").status_code, 400)   # start after end
        self.assertFalse(self.client.patch(url, {"is_available": False}, format="json").data["is_available"])

    def test_edit_cannot_create_an_overlap_or_touch_the_past(self):
        a = self.add(start="09:00", end="12:00").data[0]["id"]
        self.add(start="13:00", end="15:00")
        self.assertEqual(self.client.patch(reverse("provider-schedule-detail", args=[a]), {"end_time": "14:00"}, format="json").status_code, 400)
        old = ProviderAvailability.objects.create(provider=self.profile, available_date=day(-1), start_time="09:00", end_time="10:00")
        self.assertEqual(self.client.patch(reverse("provider-schedule-detail", args=[old.pk]), {"end_time": "11:00"}, format="json").status_code, 400)

    def test_delete_window(self):
        window_id = self.add().data[0]["id"]
        url = reverse("provider-schedule-detail", args=[window_id])
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(self.schedule).data, [])

    def test_other_providers_windows_are_404(self):
        other = make_provider("+919500000002")
        theirs = ProviderAvailability.objects.create(provider=other, available_date=day(2), start_time="09:00", end_time="10:00")
        url = reverse("provider-schedule-detail", args=[theirs.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {"end_time": "11:00"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(self.client.get(self.schedule).data, [])

    def test_providers_can_prepare_their_schedule_before_approval(self):
        ProviderProfile.objects.update(approval_status=Status.PENDING)
        self.assertEqual(self.add().status_code, 201)

    def test_database_rejects_inverted_times(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProviderAvailability.objects.create(provider=self.profile, available_date=day(2), start_time="12:00", end_time="09:00")


class IsWithinAvailabilityTests(AvailabilityTestCase):
    def at(self, hour, minute=0, n=2):
        naive = datetime.combine(day(n), datetime.min.time()).replace(hour=hour, minute=minute)
        return timezone.make_aware(naive)

    def setUp(self):
        super().setUp()
        self.add(start="09:00", end="17:00")
        self.add(start="13:00", end="14:00", is_available=False)       # lunch

    def test_inside_working_hours(self):
        self.assertTrue(is_within_availability(self.profile, self.at(9), 60))
        self.assertTrue(is_within_availability(self.profile, self.at(10, 30), 90))
        self.assertTrue(is_within_availability(self.profile, self.at(16), 60))      # ends exactly at closing

    def test_outside_or_partly_outside(self):
        self.assertFalse(is_within_availability(self.profile, self.at(8), 60))
        self.assertFalse(is_within_availability(self.profile, self.at(16, 30), 60))  # runs past closing
        self.assertFalse(is_within_availability(self.profile, self.at(8, 30), 60))   # starts before opening

    def test_blocked_time_wins(self):
        self.assertFalse(is_within_availability(self.profile, self.at(13), 30))
        self.assertFalse(is_within_availability(self.profile, self.at(12, 30), 60))  # touches lunch
        self.assertTrue(is_within_availability(self.profile, self.at(11), 120))      # ends as lunch starts
        self.assertTrue(is_within_availability(self.profile, self.at(14), 60))       # starts as lunch ends

    def test_day_without_windows_and_overnight(self):
        self.assertFalse(is_within_availability(self.profile, self.at(10, n=5), 60))
        self.assertFalse(is_within_availability(self.profile, self.at(23), 120))

    def test_other_providers_windows_do_not_count(self):
        other = make_provider("+919500000002")
        self.assertFalse(is_within_availability(other, self.at(10), 60))
