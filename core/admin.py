from django.contrib import admin
from .models import BroadcastAnnouncement, Policy, AboutUs

@admin.register(BroadcastAnnouncement)
class BroadcastAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'target_audience', 'created_at')
    list_filter = ('target_audience',)
    search_fields = ('title', 'message')

@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'updated_at')
    search_fields = ('title',)

@admin.register(AboutUs)
class AboutUsAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'updated_at')
    search_fields = ('title',)
