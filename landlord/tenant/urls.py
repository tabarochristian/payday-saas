from tenant.views import CreateTenantView, TenantView
from django.urls import path

app_name = "tenant"

urlpatterns = [
    path("tenant/<int:pk>", TenantView.as_view(), name="tenant"),
    path("", CreateTenantView.as_view(), name="create-tenant"),
    path('sitemap.xml', views.sitemap, name='sitemap'),
]