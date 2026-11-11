from django.urls import path, include
from rest_framework.routers import DefaultRouter
<<<<<<< HEAD
from .views import AllCategoriesView, PolicyViewSet, AboutUsViewSet, PublicBroadcastAnnouncementViewSet
=======
from .views import AllCategoriesView, PolicyViewSet, AboutUsViewSet, MyAnnouncementsAPIView
>>>>>>> d3f86bdf3dac8fc402d56ff1ebace7e1271c6a92

router = DefaultRouter(trailing_slash=False)
router.register(r'policies', PolicyViewSet, basename='policy')
router.register(r'about-us', AboutUsViewSet, basename='about-us')
router.register(r'announcements', PublicBroadcastAnnouncementViewSet, basename='announcements')

urlpatterns = [
    path('all-categories/', AllCategoriesView.as_view(), name='all-categories'),
    path('announcements/', MyAnnouncementsAPIView.as_view(), name='my-announcements'),
    path('', include(router.urls)),
]
