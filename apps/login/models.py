from django.contrib.auth.models import User
from django.db import models

# Create your models here.

class UserIdentity(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.DO_NOTHING,
        db_column="user_id",
        related_name="oidc_identity",
    )

    subject = models.UUIDField(
        unique=True,
        editable=False,
    )

    class Meta:
        managed = False
        db_table = "identity_useridentity"

    def __str__(self):
        return f"{self.user.username} ({self.subject})"