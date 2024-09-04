from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    is_seller = models.BooleanField(default=False)
    is_venue_vendor = models.BooleanField(default=False)