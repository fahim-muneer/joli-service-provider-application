from django.urls import path

from . import views

urlpatterns = [
    # ---- the logged-in provider ----
    path("me/", views.ProviderProfileView.as_view(), name="provider-profile"),
    path("me/submit/", views.ProviderSubmitView.as_view(), name="provider-submit"),
    path("me/documents/", views.ProviderDocumentListCreateView.as_view(), name="provider-document-list"),
    path("me/documents/<int:pk>/", views.ProviderDocumentDetailView.as_view(), name="provider-document-detail"),
    path("me/documents/<int:pk>/file/", views.ProviderDocumentFileView.as_view(), name="provider-document-file"),
    path("me/services/", views.ProviderServiceListCreateView.as_view(), name="provider-service-list"),
    path("me/services/<int:pk>/", views.ProviderServiceDetailView.as_view(), name="provider-service-detail"),
    path("me/areas/", views.ProviderAreasView.as_view(), name="provider-areas"),
    # ---- admin portal ----
    path("admin/providers/", views.AdminProviderListView.as_view(), name="admin-provider-list"),
    path("admin/providers/<int:pk>/", views.AdminProviderDetailView.as_view(), name="admin-provider-detail"),
    path("admin/providers/<int:pk>/approve/", views.AdminProviderApproveView.as_view(), name="admin-provider-approve"),
    path("admin/providers/<int:pk>/reject/", views.AdminProviderRejectView.as_view(), name="admin-provider-reject"),
    path("admin/providers/<int:pk>/suspend/", views.AdminProviderSuspendView.as_view(), name="admin-provider-suspend"),
    path("admin/providers/<int:pk>/reinstate/", views.AdminProviderReinstateView.as_view(), name="admin-provider-reinstate"),
    path("admin/documents/<int:pk>/review/", views.AdminDocumentReviewView.as_view(), name="admin-document-review"),
    path("admin/documents/<int:pk>/file/", views.AdminDocumentFileView.as_view(), name="admin-provider-document-file"),
]
