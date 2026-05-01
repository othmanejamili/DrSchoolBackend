from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (UserViewSet, DrivingSchoolViewSet, StudentProfileViewSet,
                    LessonViewSet, AttendanceViewSet, FeedbackViewSet, VehicleViewSet,
                    ScheduleViewSet,AchievemtViewSet, CommunicationTemplateViewSet,
                    AutomatedMessageViewSet, SchoolAnalyticsViewSet, ReportViewSet,
                    DashboardViewSet,SubscriptionPlanViewSet,SchoolSubscriptionViewSet,
                    StudentDocumentViewSet, login_view, logout_view, register_view, verify_token,
                    PasswordResetRequestView,PasswordResetVerifyView,PasswordResetConfirmView,
                    RegisterView
                )

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'drivingschool', DrivingSchoolViewSet, basename='drivingschool')
router.register(r'studentprofile', StudentProfileViewSet, basename='studentprofile')
router.register(r'lesson',LessonViewSet, basename='lesson')
router.register(r'attendance',AttendanceViewSet, basename='attendance')
router.register(r'feedback',FeedbackViewSet, basename='feedback')
router.register(r'vehicle',VehicleViewSet, basename='vehicle')
router.register(r'schedule',ScheduleViewSet, basename='schedule')
router.register(r'achievement',AchievemtViewSet, basename='achievement')
router.register(r'communicationtemplate',CommunicationTemplateViewSet, basename='communicationtemplate')
router.register(r'automatedmessage',AutomatedMessageViewSet, basename='automatedmessage')
router.register(r'schoolanalytics',SchoolAnalyticsViewSet, basename='schoolanalytics')
router.register(r'report', ReportViewSet, basename='report')
router.register(r'dashboard',DashboardViewSet, basename='dashboard')
router.register(r'subscriptionplan',SubscriptionPlanViewSet, basename='subscriptionplan')
router.register(r'schoolsubscription',SchoolSubscriptionViewSet, basename='schoolsubscription')
router.register(r'studentdocument',StudentDocumentViewSet, basename='studentdocument')

urlpatterns = [
    path('admin/', admin.site.urls),
    # Authentication endpoints
    path('api/auth/login/', login_view, name='login'),
    path('api/auth/logout/', logout_view, name='logout'),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/verify/', verify_token, name='verify-token'),
    path('api/auth/password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('api/auth/password-reset/verify/',  PasswordResetVerifyView.as_view(),  name='password-reset-verify'),
    path('api/auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('api/', include(router.urls)), 
    path('api/drivingschool/<str:name>/', 
        DrivingSchoolViewSet.as_view({'get': 'retrieve'}),
        name='drivingschool-by-name'),
]+ router.urls

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]