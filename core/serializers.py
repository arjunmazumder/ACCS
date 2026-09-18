from rest_framework import serializers
from .models import Policy, AboutUs, BroadcastAnnouncement
from django.contrib.auth import get_user_model

User = get_user_model()

class BroadcastAnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = BroadcastAnnouncement
        fields = '__all__'
        read_only_fields = ['created_at']

class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = '__all__'

class AboutUsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AboutUs
        fields = '__all__'

