from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """
    Authenticate against settings.AUTH_USER_MODEL using either
    email or username (case-insensitive).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get("email") or kwargs.get(UserModel.USERNAME_FIELD)

        if not username or not password:
            return None

        username = str(username).strip()
        try:
            user = UserModel.objects.filter(
                Q(email__iexact=username) | Q(username__iexact=username)
            ).order_by("id").first()
        except Exception:
            return None

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
