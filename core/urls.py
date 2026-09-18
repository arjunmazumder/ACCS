from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AllCategoriesView, PolicyViewSet, AboutUsViewSet

router = DefaultRouter(trailing_slash=False)
router.register(r'policies', PolicyViewSet, basename='policy')
router.register(r'about-us', AboutUsViewSet, basename='about-us')

urlpatterns = [
    path('all-categories/', AllCategoriesView.as_view(), name='all-categories'),
    path('', include(router.urls)),
]
