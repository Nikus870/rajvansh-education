from typing import Any

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core.sitemaps import StaticViewSitemap
from apps.courses.sitemaps import CourseSitemap
from apps.universities.sitemaps import UniversitySitemap


sitemaps = {
    "static": StaticViewSitemap,
    "courses": CourseSitemap,
    "universities": UniversitySitemap,
}


urlpatterns = [
    path("admin/", admin.site.urls),

    path("", include("apps.core.urls")),
    path("courses/", include("apps.courses.urls")),
    path("universities/", include("apps.universities.urls")),
    path("inquiry/", include("apps.inquiries.urls")),
    path("franchise/", include("apps.franchise.urls")),
    path("content/", include("apps.content.urls")),

    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="sitemap",
    ),
]


urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT,
)