from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext as _
from django.templatetags.static import static
import secrets


class Profile(models.Model):
    GENDER_MALE = 1
    GENDER_FEMALE = 2
    GENDER_CHOICES = [
        (GENDER_MALE, _("Male")),
        (GENDER_FEMALE, _("Female")),
    ]

    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to="customers/profiles/avatars/", null=True, blank=True)
    birthday = models.DateField(null=True, blank=True)
    gender = models.PositiveSmallIntegerField(choices=GENDER_CHOICES, null=True, blank=True)
    phone = models.CharField(max_length=32, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    number = models.CharField(max_length=32, null=True, blank=True)
    city = models.CharField(max_length=50, null=True, blank=True)
    zip = models.CharField(max_length=30, null=True, blank=True)
    
    # API Key cho MQTT và device connection
    api_key = models.CharField(
        _('API Key'),
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        help_text=_('API Key dùng để kết nối thiết bị qua MQTT')
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Profile')
        verbose_name_plural = _('Profiles')

    @property
    def get_avatar(self):
        return self.avatar.url if self.avatar else static('assets/img/team/default-profile-picture.png')
    
    def generate_api_key(self):
        """Tạo API key mới 64 ký tự"""
        self.api_key = secrets.token_hex(32)  # 32 bytes = 64 hex characters
        self.save()
        return self.api_key
    
    def save(self, *args, **kwargs):
        # Tự động tạo API key nếu chưa có
        if not self.api_key:
            self.api_key = secrets.token_hex(32)
        super().save(*args, **kwargs)
