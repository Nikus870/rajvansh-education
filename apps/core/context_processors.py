from .models import WebsiteSettings,AdmissionSettings
def site_context(request): return {"site_settings":WebsiteSettings.get_solo(),"admission_settings":AdmissionSettings.get_solo()}
