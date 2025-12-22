from django.contrib import admin
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (UserViewSet, DrivingSchoolViewSet, StudentProfileViewSet,
                    LessonViewSet, AttendanceViewSet, FeedbackViewSet, VehicleViewSet,
                    ScheduleViewSet)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'drivingschool', DrivingSchoolViewSet, basename='drivingschool')
router.register(r'studentprofile', StudentProfileViewSet, basename='studentprofile')
router.register(r'lesson',LessonViewSet, basename='lesson')
router.register(r'attendance',AttendanceViewSet, basename='attendance')
router.register(r'feedback',FeedbackViewSet, basename='feedback')
router.register(r'vehicle',VehicleViewSet, basename='vehicle')
router.register(r'schedule',ScheduleViewSet, basename='schedule')
urlpatterns = [
    path('admin/', admin.site.urls),
    
]+ router.urls