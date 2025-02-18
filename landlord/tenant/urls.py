from tenant.views import CreateTenantView, TenantView, StaticViewSitemap, RobotsView
from django.contrib.sitemaps.views import sitemap
from django.urls import path

app_name = "tenant"
sitemaps = {
    'static': StaticViewSitemap
}

urlpatterns = [
    path("tenant/<int:pk>", TenantView.as_view(), name="view"),
    path("", CreateTenantView.as_view(), name="create"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path('robots.txt', RobotsView.as_view(), name='robots'),
]