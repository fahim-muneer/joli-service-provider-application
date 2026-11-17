from django.http import FileResponse, Http404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.locations.pagination import StandardPagination
from apps.users.permissions import IsAdminRole, IsProviderRole

from . import selectors, services
from .models import ProviderDocument, ProviderProfile
from .serializers import (
    AdminProviderDetailSerializer,
    AdminProviderDocumentSerializer,
    AdminProviderListSerializer,
    DocumentReviewSerializer,
    NoteSerializer,
    ProviderAreasUpdateSerializer,
    ProviderAreaSerializer,
    ProviderDocumentSerializer,
    ProviderDocumentUploadSerializer,
    ProviderProfileSerializer,
    ProviderServiceCreateSerializer,
    ProviderServiceSerializer,
    ProviderServiceUpdateSerializer,
    ReasonSerializer,
)


def serve_document(document):
    """Stream a private file. Callers must already have checked permission."""
    try:
        handle = document.document_file.open("rb")
    except FileNotFoundError:
        raise Http404("File not found.")
    response = FileResponse(handle, filename=document.original_name or "document", as_attachment=False)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


# =========================== provider self-service ===========================

class _ProviderView(APIView):
    permission_classes = [IsProviderRole]

    def get_profile(self):
        profile = selectors.get_provider_profile(self.request.user)
        if profile is None:
            raise NotFound("This account has no provider profile.")
        return profile


class ProviderProfileView(_ProviderView):
    """GET / PATCH the provider's own profile."""

    def get(self, request):
        return Response(ProviderProfileSerializer(self.get_profile()).data)

    def patch(self, request):
        serializer = ProviderProfileSerializer(self.get_profile(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ProviderSubmitView(_ProviderView):
    """POST: send the application for admin review."""

    def post(self, request):
        profile = services.submit_for_review(profile=self.get_profile(), user=request.user)
        return Response(ProviderProfileSerializer(profile).data)


class ProviderDocumentListCreateView(_ProviderView):
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        documents = selectors.list_own_documents(self.get_profile())
        return Response(ProviderDocumentSerializer(documents, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = ProviderDocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        document = services.add_document(
            profile=self.get_profile(),
            document_type=data["document_type"],
            file=data["file"],
            expires_at=data.get("expires_at"),
        )
        return Response(
            ProviderDocumentSerializer(document, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class _OwnDocumentMixin:
    def get_document(self):
        document = selectors.get_own_document(self.get_profile(), self.kwargs["pk"])
        if document is None:
            raise NotFound("Document not found.")
        return document


class ProviderDocumentDetailView(_OwnDocumentMixin, _ProviderView):
    def get(self, request, pk):
        return Response(ProviderDocumentSerializer(self.get_document(), context={"request": request}).data)

    def delete(self, request, pk):
        services.delete_document(document=self.get_document())
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProviderDocumentFileView(_OwnDocumentMixin, _ProviderView):
    def get(self, request, pk):
        return serve_document(self.get_document())


class ProviderServiceListCreateView(_ProviderView):
    def get(self, request):
        return Response(ProviderServiceSerializer(selectors.list_own_services(self.get_profile()), many=True).data)

    def post(self, request):
        serializer = ProviderServiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider_service, created = services.set_provider_service(
            profile=self.get_profile(), **serializer.validated_data
        )
        return Response(
            ProviderServiceSerializer(provider_service).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ProviderServiceDetailView(_ProviderView):
    def get_object(self):
        provider_service = selectors.get_own_service(self.get_profile(), self.kwargs["pk"])
        if provider_service is None:
            raise NotFound("Service not found.")
        return provider_service

    def get(self, request, pk):
        return Response(ProviderServiceSerializer(self.get_object()).data)

    def patch(self, request, pk):
        provider_service = self.get_object()
        serializer = ProviderServiceUpdateSerializer(provider_service, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProviderServiceSerializer(provider_service).data)

    def delete(self, request, pk):
        services.deactivate_provider_service(provider_service=self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProviderAreasView(_ProviderView):
    """GET the covered areas; PUT {"areas": [ids]} replaces the whole selection."""

    def _response(self, profile):
        return Response(ProviderAreaSerializer(selectors.list_own_areas(profile), many=True).data)

    def get(self, request):
        return self._response(self.get_profile())

    def put(self, request):
        serializer = ProviderAreasUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = self.get_profile()
        services.replace_areas(profile=profile, area_ids=serializer.validated_data["areas"])
        return self._response(profile)


# =========================== admin portal ===========================

class AdminProviderListView(generics.ListAPIView):
    """GET ?status=under_review&search=..."""

    serializer_class = AdminProviderListSerializer
    permission_classes = [IsAdminRole]
    pagination_class = StandardPagination

    def get_queryset(self):
        wanted = self.request.query_params.get("status")
        if wanted and wanted not in ProviderProfile.ApprovalStatus.values:
            raise ValidationError({"status": f"Must be one of {ProviderProfile.ApprovalStatus.values}."})
        return selectors.list_providers(status=wanted, search=self.request.query_params.get("search"))


class _AdminProviderMixin:
    permission_classes = [IsAdminRole]

    def get_profile(self):
        profile = selectors.provider_detail_queryset().filter(pk=self.kwargs["pk"]).first()
        if profile is None:
            raise NotFound("Provider not found.")
        return profile

    def respond(self, profile):
        fresh = selectors.provider_detail_queryset().get(pk=profile.pk)
        return Response(AdminProviderDetailSerializer(fresh, context={"request": self.request}).data)


class AdminProviderDetailView(_AdminProviderMixin, APIView):
    def get(self, request, pk):
        return self.respond(self.get_profile())


class AdminProviderApproveView(_AdminProviderMixin, APIView):
    def post(self, request, pk):
        s = NoteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        profile = services.approve_provider(profile=self.get_profile(), admin=request.user, note=s.validated_data["note"])
        return self.respond(profile)


class AdminProviderRejectView(_AdminProviderMixin, APIView):
    def post(self, request, pk):
        s = ReasonSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        profile = services.reject_provider(profile=self.get_profile(), admin=request.user, reason=s.validated_data["reason"])
        return self.respond(profile)


class AdminProviderSuspendView(_AdminProviderMixin, APIView):
    def post(self, request, pk):
        s = ReasonSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        profile = services.suspend_provider(profile=self.get_profile(), admin=request.user, reason=s.validated_data["reason"])
        return self.respond(profile)


class AdminProviderReinstateView(_AdminProviderMixin, APIView):
    def post(self, request, pk):
        s = NoteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        profile = services.reinstate_provider(profile=self.get_profile(), admin=request.user, note=s.validated_data["note"])
        return self.respond(profile)


class _AdminDocumentMixin:
    permission_classes = [IsAdminRole]

    def get_document(self):
        document = ProviderDocument.objects.filter(pk=self.kwargs["pk"]).first()
        if document is None:
            raise NotFound("Document not found.")
        return document


class AdminDocumentReviewView(_AdminDocumentMixin, APIView):
    def post(self, request, pk):
        s = DocumentReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        document = services.review_document(
            document=self.get_document(), admin=request.user,
            decision=s.validated_data["decision"], reason=s.validated_data["reason"], remark=s.validated_data["remark"],
        )
        return Response(AdminProviderDocumentSerializer(document, context={"request": request}).data)


class AdminDocumentFileView(_AdminDocumentMixin, APIView):
    def get(self, request, pk):
        return serve_document(self.get_document())
