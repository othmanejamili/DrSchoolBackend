"""
URL configuration for Drive project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from rest_framework.routers import DefaultRouter
from DriveApp.views import (UserViewSet, DrivingSchoolViewSet, StudentProfileViewSet,
                            LessonViewSet,AttendanceViewSet, FeedbackViewSet, VehicleViewSet,
                            ScheduleViewSet,AchievemtViewSet)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'drivingschool', DrivingSchoolViewSet, basename='drivingschool')
router.register(r'studentprofile', StudentProfileViewSet, basename='studentprofile')
router.register(r'lesson',LessonViewSet, basename='lesson')
router.register(r'attendance',AttendanceViewSet,basename='attendance')
router.register(r'feedback',FeedbackViewSet, basename='feedback')
router.register(r'vehicle',VehicleViewSet, basename='vehicle')
router.register(r'schedule',ScheduleViewSet,basename='schedule')
router.register(r'achievement',AchievemtViewSet, basename='achievement')
urlpatterns = [
    path('admin/', admin.site.urls),
]+ router.urls
