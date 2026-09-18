from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()


class BroadcastAnnouncement(models.Model):
    TARGET_CHOICES = (
        ('ALL', 'All Users'),
        ('BUYERS', 'Only Buyers'),
        ('VENDORS', 'Only Vendors'),
        ('STAFF', 'Only Staff'),
        ('SPECIFIC_USERS', 'Specific Users'),
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    target_audience = models.CharField(max_length=20, choices=TARGET_CHOICES, default='ALL')
    specific_targets = models.ManyToManyField(User, blank=True, related_name='targeted_announcements')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.target_audience})"


class Policy(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Policies"

    def __str__(self):
        return self.title


class AboutUs(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "About Us"

    def __str__(self):
        return self.title

