import os
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.locations.models import Area, City
from apps.services.models import Category, Service

from .factories import make_provider
from .models import (
    ProviderArea,
    ProviderDocument,
    ProviderProfile,
    ProviderService,
    ProviderStatusHistory,
)

User = get_user_model()
PW = "Str0ng-Passw0rd!"
Status = ProviderProfile.ApprovalStatus

_PRIVATE_ROOT = tempfile.mkdtemp(prefix="joli-private-")


def tearDownModule():
    shutil.rmtree(_PRIVATE_ROOT, ignore_errors=True)


def pdf(name="id.pdf", size=100):
    return SimpleUploadedFile(name, b"%PDF-1.4\n" + b"0" * size, content_type="application/pdf")


def png(name="id.png"):
    return SimpleUploadedFile(name, b"\x89PNG\r\n\x1a\n" + b"0" * 50, content_type="image/png")


def make_user(role, phone, verified=True):
    return User.objects.create_user(
        phone=phone, password=PW, full_name="Test", role=role, is_phone_verified=verified
    )


@override_settings(PRIVATE_MEDIA_ROOT=_PRIVATE_ROOT)
class ProviderTestCase(APITestCase):
    """Shared fixtures: one verified provider (pending), one admin, one customer."""

    def setUp(self):
        self.profile = make_provider("+919200000001", status=Status.PENDING)
        self.provider_user = self.profile.user
        self.provider_user.is_phone_verified = True
        self.provider_user.save()
        self.admin = make_user(User.Role.ADMIN, "+919111111111")
        self.customer = make_user(User.Role.CUSTOMER, "+919333333333")

        self.city = City.objects.create(name="Bengaluru", state="Karnataka")
        self.area = Area.objects.create(city=self.city, name="Indiranagar", pincode="560038")
        self.category = Category.objects.create(name="Plumbing")
        self.tap = Service.objects.create(category=self.category, name="Tap repair", base_price=299)

    def as_user(self, user):
        self.client = APIClient()
        self.client.force_authenticate(user)

    def upload(self, file=None, document_type="id_proof", **extra):
        return self.client.post(
            reverse("provider-document-list"),
            {"document_type": document_type, "file": file or pdf(), **extra},
            format="multipart",
        )


class ProviderProfileTests(ProviderTestCase):
    def test_roles_are_enforced(self):
        url = reverse("provider-profile")
        self.assertEqual(APIClient().get(url).status_code, 401)
        for user in (self.customer, self.admin):
            self.as_user(user)
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_provider_without_profile_gets_404(self):
        orphan = make_user(User.Role.PROVIDER, "+919200000099")
        self.as_user(orphan)
        self.assertEqual(self.client.get(reverse("provider-profile")).status_code, 404)

    def test_view_and_edit_profile(self):
        self.as_user(self.provider_user)
        res = self.client.get(reverse("provider-profile"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["approval_status"], "pending")
        self.assertEqual(res.data["phone"], "+919200000001")

        res = self.client.patch(
            reverse("provider-profile"),
            {"business_name": "Fix It Fast", "bio": "10 years", "experience_years": 10, "languages": ["English", "Hindi"]},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.business_name, "Fix It Fast")
        self.assertEqual(self.profile.languages, ["English", "Hindi"])

    def test_status_and_availability_cannot_be_set_by_the_provider(self):
        self.as_user(self.provider_user)
        self.client.patch(
            reverse("provider-profile"),
            {"approval_status": "approved", "is_available": True, "rejection_reason": "x", "internal_admin_note": "x"},
            format="json",
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, "pending")
        self.assertFalse(self.profile.is_available)
        self.assertEqual(self.profile.internal_admin_note, "")

    def test_language_validation(self):
        self.as_user(self.provider_user)
        url = reverse("provider-profile")
        self.assertEqual(self.client.patch(url, {"languages": ["x"] * 11}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"languages": ["x" * 31]}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"experience_years": -1}, format="json").status_code, 400)

    def test_internal_admin_note_is_never_shown_to_the_provider(self):
        self.profile.internal_admin_note = "secret"
        self.profile.save()
        self.as_user(self.provider_user)
        self.assertNotIn("internal_admin_note", self.client.get(reverse("provider-profile")).data)


class ProviderDocumentTests(ProviderTestCase):
    def setUp(self):
        super().setUp()
        self.as_user(self.provider_user)

    def test_upload_list_and_download(self):
        res = self.upload()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "pending")
        self.assertEqual(res.data["original_name"], "id.pdf")
        self.assertNotIn("document_file", res.data)          # stored path never exposed
        self.assertTrue(res.data["download_url"].endswith(f"/{res.data['id']}/file/"))

        listing = self.client.get(reverse("provider-document-list"))
        self.assertEqual(len(listing.data), 1)

        file_res = self.client.get(reverse("provider-document-file", args=[res.data["id"]]))
        self.assertEqual(file_res.status_code, 200)
        self.assertEqual(file_res["Content-Type"], "application/pdf")
        self.assertEqual(file_res["X-Content-Type-Options"], "nosniff")
        self.assertTrue(b"".join(file_res.streaming_content).startswith(b"%PDF-"))

    def test_stored_file_is_private_and_randomly_named(self):
        res = self.upload(file=pdf("my-aadhaar-card.pdf"))
        document = ProviderDocument.objects.get(pk=res.data["id"])
        self.assertTrue(document.document_file.path.startswith(os.path.abspath(_PRIVATE_ROOT)))
        self.assertNotIn("aadhaar", document.document_file.name)
        with self.assertRaises(ValueError):
            document.document_file.url                         # no public URL exists

    def test_png_accepted(self):
        self.assertEqual(self.upload(file=png()).status_code, 201)

    def test_bad_uploads_are_rejected(self):
        cases = {
            "wrong extension": SimpleUploadedFile("x.exe", b"MZ" + b"0" * 50),
            "html renamed to pdf": SimpleUploadedFile("x.pdf", b"<html><script>alert(1)</script></html>"),
            "empty": SimpleUploadedFile("x.pdf", b""),
            "too large": SimpleUploadedFile("x.pdf", b"%PDF-" + b"0" * (5 * 1024 * 1024)),
        }
        for label, file in cases.items():
            res = self.upload(file=file)
            self.assertEqual(res.status_code, 400, label)
        self.assertFalse(ProviderDocument.objects.exists())

    def test_bad_type_and_expired_date_rejected(self):
        self.assertEqual(self.upload(document_type="selfie").status_code, 400)
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.assertEqual(self.upload(expires_at=yesterday).status_code, 400)
        tomorrow = (timezone.localdate() + timedelta(days=30)).isoformat()
        self.assertEqual(self.upload(expires_at=tomorrow).status_code, 201)

    def test_providers_only_see_their_own_documents(self):
        mine = self.upload().data["id"]
        other = make_provider("+919200000002")
        other_doc = ProviderDocument.objects.create(provider=other, document_type="id_proof", document_file=pdf())
        self.assertEqual(len(self.client.get(reverse("provider-document-list")).data), 1)
        for name in ("provider-document-detail", "provider-document-file"):
            self.assertEqual(self.client.get(reverse(name, args=[other_doc.pk])).status_code, 404)
            self.assertEqual(self.client.get(reverse(name, args=[mine])).status_code, 200)
        self.assertEqual(self.client.delete(reverse("provider-document-detail", args=[other_doc.pk])).status_code, 404)

    def test_delete_removes_row_and_file_but_not_approved_documents(self):
        doc_id = self.upload().data["id"]
        document = ProviderDocument.objects.get(pk=doc_id)
        path = document.document_file.path
        self.assertTrue(os.path.exists(path))
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.delete(reverse("provider-document-detail", args=[doc_id]))
        self.assertEqual(res.status_code, 204)
        self.assertFalse(ProviderDocument.objects.filter(pk=doc_id).exists())
        self.assertFalse(os.path.exists(path))

        approved_id = self.upload().data["id"]
        ProviderDocument.objects.filter(pk=approved_id).update(status="approved")
        res = self.client.delete(reverse("provider-document-detail", args=[approved_id]))
        self.assertEqual(res.status_code, 400)

    def test_only_providers_can_upload(self):
        for user in (self.customer, self.admin):
            self.as_user(user)
            self.assertEqual(self.upload().status_code, 403)
        self.assertEqual(APIClient().post(reverse("provider-document-list")).status_code, 401)


class SubmissionTests(ProviderTestCase):
    def setUp(self):
        super().setUp()
        self.as_user(self.provider_user)

    def submit(self):
        return self.client.post(reverse("provider-submit"))

    def test_blockers_are_listed_and_block_submission(self):
        self.provider_user.is_phone_verified = False
        self.provider_user.save()
        profile = self.client.get(reverse("provider-profile")).data
        self.assertFalse(profile["can_submit"])
        self.assertEqual(profile["submission_blockers"], ["Verify your phone number.", "Upload an ID proof."])

        res = self.submit()
        self.assertEqual(res.status_code, 400)
        self.assertEqual(len(res.data["detail"]), 2)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, "pending")

    def test_a_non_id_document_does_not_satisfy_the_requirement(self):
        self.upload(document_type="address_proof")
        res = self.submit()
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["detail"], ["Upload an ID proof."])

    def test_a_rejected_id_proof_does_not_count(self):
        doc = self.upload().data["id"]
        ProviderDocument.objects.filter(pk=doc).update(status="rejected")
        self.assertEqual(self.submit().status_code, 400)

    def test_successful_submission_moves_to_under_review_and_is_logged(self):
        self.upload()
        res = self.submit()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["approval_status"], "under_review")
        self.assertFalse(res.data["can_submit"])
        history = ProviderStatusHistory.objects.get()
        self.assertEqual((history.from_status, history.to_status), ("pending", "under_review"))
        self.assertEqual(history.changed_by, self.provider_user)

    def test_cannot_submit_twice_or_when_approved(self):
        self.upload()
        self.submit()
        self.assertEqual(self.submit().status_code, 400)
        ProviderProfile.objects.update(approval_status="approved")
        self.assertEqual(self.submit().status_code, 400)

    def test_admins_and_customers_cannot_submit(self):
        for user in (self.admin, self.customer):
            self.as_user(user)
            self.assertEqual(self.submit().status_code, 403)


class ProviderServiceTests(ProviderTestCase):
    def setUp(self):
        super().setUp()
        self.as_user(self.provider_user)
        self.url = reverse("provider-service-list")

    def test_offer_a_service_with_defaults_from_the_catalogue(self):
        res = self.client.post(self.url, {"service": self.tap.pk}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["custom_price"], "299.00")
        self.assertEqual(res.data["pricing_type"], "fixed")
        self.assertEqual(res.data["estimated_duration_minutes"], 60)
        self.assertEqual(res.data["service_name"], "Tap repair")
        self.assertEqual(res.data["category_name"], "Plumbing")

    def test_offer_with_own_price_and_validation(self):
        res = self.client.post(self.url, {"service": self.tap.pk, "custom_price": "349.50", "estimated_duration_minutes": 90}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["custom_price"], "349.50")
        other = Service.objects.create(category=self.category, name="Other", base_price=100)
        for bad in ({"service": other.pk, "custom_price": "-5"}, {"service": other.pk, "estimated_duration_minutes": 0},
                    {"service": other.pk, "pricing_type": "nope"}, {"service": 9999}, {}):
            self.assertEqual(self.client.post(self.url, bad, format="json").status_code, 400, bad)

    def test_inactive_service_or_category_cannot_be_offered(self):
        self.tap.is_active = False
        self.tap.save()
        self.assertEqual(self.client.post(self.url, {"service": self.tap.pk}, format="json").status_code, 400)
        self.tap.is_active = True
        self.tap.save()
        self.category.is_active = False
        self.category.save()
        self.assertEqual(self.client.post(self.url, {"service": self.tap.pk}, format="json").status_code, 400)

    def test_offering_again_reactivates_and_keeps_the_price(self):
        first = self.client.post(self.url, {"service": self.tap.pk, "custom_price": "400"}, format="json")
        self.client.delete(reverse("provider-service-detail", args=[first.data["id"]]))
        self.assertFalse(ProviderService.objects.get().is_active)
        again = self.client.post(self.url, {"service": self.tap.pk}, format="json")
        self.assertEqual(again.status_code, 200)                  # not a new row
        self.assertTrue(again.data["is_active"])
        self.assertEqual(again.data["custom_price"], "400.00")    # earlier price kept
        self.assertEqual(ProviderService.objects.count(), 1)

    def test_patch_and_delete_deactivates(self):
        pk = self.client.post(self.url, {"service": self.tap.pk}, format="json").data["id"]
        detail = reverse("provider-service-detail", args=[pk])
        res = self.client.patch(detail, {"custom_price": "450.00"}, format="json")
        self.assertEqual(res.data["custom_price"], "450.00")
        self.assertEqual(self.client.patch(detail, {"custom_price": "-1"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(detail, {"is_active": False}, format="json").data["is_active"], False)
        self.assertEqual(self.client.delete(detail).status_code, 204)
        self.assertEqual(self.client.delete(detail).status_code, 204)   # idempotent
        self.assertEqual(len(self.client.get(self.url).data), 1)        # inactive rows still listed

    def test_cannot_touch_another_providers_service(self):
        other = make_provider("+919200000002")
        theirs = ProviderService.objects.create(
            provider=other, service=self.tap, custom_price=1, pricing_type="fixed", estimated_duration_minutes=60
        )
        detail = reverse("provider-service-detail", args=[theirs.pk])
        for call in (self.client.get, self.client.delete):
            self.assertEqual(call(detail).status_code, 404)
        self.assertEqual(self.client.patch(detail, {"custom_price": "9"}, format="json").status_code, 404)
        self.assertEqual(self.client.get(self.url).data, [])


class ProviderAreaTests(ProviderTestCase):
    def setUp(self):
        super().setUp()
        self.as_user(self.provider_user)
        self.url = reverse("provider-areas")
        self.area2 = Area.objects.create(city=self.city, name="Koramangala", pincode="560034")

    def test_replace_the_selection(self):
        res = self.client.put(self.url, {"areas": [self.area.pk, self.area2.pk]}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([a["name"] for a in res.data], ["Indiranagar", "Koramangala"])
        self.assertEqual(res.data[0]["city_name"], "Bengaluru")
        self.assertEqual(res.data[0]["id"], self.area.pk)

        res = self.client.put(self.url, {"areas": [self.area2.pk]}, format="json")
        self.assertEqual([a["name"] for a in res.data], ["Koramangala"])
        self.assertEqual(ProviderArea.objects.count(), 1)

        self.assertEqual(self.client.put(self.url, {"areas": []}, format="json").data, [])
        self.assertEqual(self.client.get(self.url).data, [])

    def test_duplicates_in_the_request_are_fine(self):
        res = self.client.put(self.url, {"areas": [self.area.pk, self.area.pk]}, format="json")
        self.assertEqual(len(res.data), 1)

    def test_unknown_or_inactive_areas_are_rejected_without_changes(self):
        self.client.put(self.url, {"areas": [self.area.pk]}, format="json")
        inactive = Area.objects.create(city=self.city, name="Old", pincode="560001", is_active=False)
        hidden_city = City.objects.create(name="Hidden", state="X", is_active=False)
        in_hidden = Area.objects.create(city=hidden_city, name="Z", pincode="111111")
        for bad in ([9999], [inactive.pk], [in_hidden.pk], [self.area2.pk, 9999]):
            res = self.client.put(self.url, {"areas": bad}, format="json")
            self.assertEqual(res.status_code, 400, bad)
            self.assertIn("areas", res.data)
        self.assertEqual([a["name"] for a in self.client.get(self.url).data], ["Indiranagar"])  # unchanged

    def test_bad_payloads(self):
        for bad in ({}, {"areas": "1"}, {"areas": [0]}, {"areas": ["a"]}):
            self.assertEqual(self.client.put(self.url, bad, format="json").status_code, 400, bad)


class AdminReviewTests(ProviderTestCase):
    """The approval workflow, end to end, ending in customer-visible availability."""

    def setUp(self):
        super().setUp()
        self.as_user(self.provider_user)
        self.doc_id = self.upload().data["id"]
        self.client.post(reverse("provider-service-list"), {"service": self.tap.pk}, format="json")
        self.client.put(reverse("provider-areas"), {"areas": [self.area.pk]}, format="json")
        self.client.post(reverse("provider-submit"))
        self.as_user(self.admin)

    def catalogue(self):
        return APIClient().get(reverse("service-list"), {"city": self.city.pk}).data["results"]

    def act(self, name, body=None, pk=None):
        return self.client.post(reverse(name, args=[pk or self.profile.pk]), body or {}, format="json")

    def approve_document(self):
        return self.act("admin-document-review", {"decision": "approved"}, pk=self.doc_id)

    def test_permissions(self):
        for user in (self.customer, self.provider_user):
            self.as_user(user)
            for name, args in (("admin-provider-list", []), ("admin-provider-detail", [self.profile.pk]),
                               ("admin-provider-document-file", [self.doc_id])):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 403, name)
        self.assertEqual(APIClient().get(reverse("admin-provider-list")).status_code, 401)

    def test_list_filters_and_counts(self):
        make_provider("+919200000002", status=Status.APPROVED, business_name="Other Co")
        res = self.client.get(reverse("admin-provider-list"))
        self.assertEqual(res.data["count"], 2)
        res = self.client.get(reverse("admin-provider-list"), {"status": "under_review"})
        self.assertEqual(res.data["count"], 1)
        row = res.data["results"][0]
        self.assertEqual((row["documents_count"], row["pending_documents_count"]), (1, 1))
        self.assertEqual(self.client.get(reverse("admin-provider-list"), {"search": "other co"}).data["count"], 1)
        self.assertEqual(self.client.get(reverse("admin-provider-list"), {"status": "bogus"}).status_code, 400)

    def test_detail_shows_documents_services_areas_and_history(self):
        res = self.client.get(reverse("admin-provider-detail", args=[self.profile.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["documents"]), 1)
        self.assertIn("admin_remark", res.data["documents"][0])
        self.assertEqual(res.data["services"][0]["service_name"], "Tap repair")
        self.assertEqual(res.data["areas"][0]["name"], "Indiranagar")
        self.assertEqual(res.data["status_history"][0]["to_status"], "under_review")
        self.assertEqual(self.client.get(reverse("admin-provider-detail", args=[9999])).status_code, 404)

    def test_admin_can_download_a_document(self):
        res = self.client.get(reverse("admin-provider-document-file", args=[self.doc_id]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")

    def test_cannot_approve_without_an_approved_id_proof(self):
        res = self.act("admin-provider-approve")
        self.assertEqual(res.status_code, 400)
        self.assertIn("ID proof", res.data["detail"])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, "under_review")

    def test_document_review_rules(self):
        self.assertEqual(self.act("admin-document-review", {"decision": "rejected"}, pk=self.doc_id).status_code, 400)  # reason needed
        self.assertEqual(self.act("admin-document-review", {"decision": "maybe"}, pk=self.doc_id).status_code, 400)
        res = self.act("admin-document-review", {"decision": "rejected", "reason": "Blurry", "remark": "ask again"}, pk=self.doc_id)
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data["status"], res.data["rejection_reason"]), ("rejected", "Blurry"))
        res = self.approve_document()                                   # a re-review is allowed
        self.assertEqual(res.data["status"], "approved")
        self.assertEqual(res.data["rejection_reason"], "")
        document = ProviderDocument.objects.get(pk=self.doc_id)
        self.assertEqual(document.reviewed_by, self.admin)

    def test_approval_makes_the_service_visible_to_customers(self):
        self.assertEqual(self.catalogue(), [])
        self.approve_document()
        res = self.act("admin-provider-approve", {"note": "Checked ID"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["approval_status"], "approved")
        self.assertEqual(res.data["reviewed_by_name"], "Test")
        self.assertEqual([s["name"] for s in self.catalogue()], ["Tap repair"])
        latest = ProviderStatusHistory.objects.first()
        self.assertEqual((latest.to_status, latest.internal_note, latest.changed_by), ("approved", "Checked ID", self.admin))

    def test_rejection_needs_a_reason_and_allows_resubmission(self):
        self.assertEqual(self.act("admin-provider-reject", {"reason": "  "}).status_code, 400)
        self.assertEqual(self.act("admin-provider-reject").status_code, 400)
        res = self.act("admin-provider-reject", {"reason": "ID unreadable"})
        self.assertEqual(res.data["approval_status"], "rejected")
        self.assertEqual(res.data["rejection_reason"], "ID unreadable")
        self.assertEqual(self.catalogue(), [])

        self.as_user(self.provider_user)                                 # provider sees why and resubmits
        mine = self.client.get(reverse("provider-profile")).data
        self.assertEqual(mine["rejection_reason"], "ID unreadable")
        self.upload()
        res = self.client.post(reverse("provider-submit"))
        self.assertEqual(res.data["approval_status"], "under_review")
        self.assertEqual(res.data["rejection_reason"], "")

    def test_suspend_hides_services_and_reinstate_restores_them(self):
        self.approve_document()
        self.act("admin-provider-approve")
        ProviderProfile.objects.update(is_available=True)

        self.assertEqual(self.act("admin-provider-suspend").status_code, 400)               # reason needed
        res = self.act("admin-provider-suspend", {"reason": "Fake completions reported"})
        self.assertEqual(res.data["approval_status"], "suspended")
        self.assertFalse(res.data["is_available"])                                          # forced offline
        self.assertEqual(self.catalogue(), [])

        res = self.act("admin-provider-reinstate", {"note": "Cleared after review"})
        self.assertEqual(res.data["approval_status"], "approved")
        self.assertEqual([s["name"] for s in self.catalogue()], ["Tap repair"])
        statuses = list(ProviderStatusHistory.objects.order_by("id").values_list("to_status", flat=True))
        self.assertEqual(statuses, ["under_review", "approved", "suspended", "approved"])

    def test_invalid_transitions_are_refused(self):
        self.approve_document()
        self.assertEqual(self.act("admin-provider-suspend", {"reason": "x"}).status_code, 400)   # not approved yet
        self.assertEqual(self.act("admin-provider-reinstate").status_code, 400)
        self.act("admin-provider-approve")
        self.assertEqual(self.act("admin-provider-approve").status_code, 400)                    # already approved
        self.assertEqual(self.act("admin-provider-reject", {"reason": "x"}).status_code, 400)
        self.act("admin-provider-suspend", {"reason": "x"})
        self.assertEqual(self.act("admin-provider-approve").status_code, 400)                    # suspended -> use reinstate
        self.assertEqual(self.act("admin-provider-suspend", {"reason": "x"}).status_code, 400)   # already suspended
        pending = make_provider("+919200000003", status=Status.PENDING)
        self.assertEqual(self.act("admin-provider-approve", pk=pending.pk).status_code, 400)     # never submitted
        self.assertEqual(self.act("admin-provider-approve", pk=9999).status_code, 404)

    def test_reinstate_cannot_be_used_to_skip_the_review(self):
        self.approve_document()                                      # documents fine, but still under review
        res = self.act("admin-provider-reinstate")
        self.assertEqual(res.status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.approval_status, "under_review")

    def test_expired_id_proof_cannot_be_used_for_approval(self):
        self.approve_document()
        ProviderDocument.objects.filter(pk=self.doc_id).update(expires_at=timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.act("admin-provider-approve").status_code, 400)
