from django.contrib.admin.apps import AdminConfig


class SuperuserOnlyAdminConfig(AdminConfig):
    default_site = "apps.core.admin_site.SuperuserOnlyAdminSite"
