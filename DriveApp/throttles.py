"""
Custom throttle classes for rate limiting.
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, SimpleRateThrottle
from rest_framework.response import Response

import logging
logger = logging.getLogger(__name__)


# ============================================
# USER MANAGEMENT THROTTLES
# ============================================

class LoginRateThrottle(AnonRateThrottle):
    """Rate limit for login attempts to prevent brute force"""
    scope = 'login'


class RegisterStudentThrottle(UserRateThrottle):
    """Rate limit for student registration"""
    scope = 'register'


class StatsThrottle(UserRateThrottle):
    """Rate limit for statistics endpoints"""
    scope = 'stats'


class SchoolUsersThrottle(UserRateThrottle):
    """Limit school user listing"""
    scope = 'school_users'


# ============================================
# SCHOOL MANAGEMENT THROTTLES
# ============================================

class SchoolListThrottle(UserRateThrottle):
    """Limit school listing for authenticated users"""
    scope = 'school_list'


class SchoolCreateThrottle(UserRateThrottle):
    """Limit school creation (admins only)"""
    scope = 'school_create'


# ============================================
# STUDENT PROFILE THROTTLES
# ============================================

class StudentProgressThrottle(UserRateThrottle):
    """Limit student progress viewing for authenticated users"""
    scope = 'student_progress'  # ✅ FIXED: was 'scop'


class StudentProgressUpdateThrottle(UserRateThrottle):
    """Limit student progress updates (instructors only)"""
    scope = 'student_progress_update'  # ✅ FIXED: was 'scop'


class StudentPerformancePredictionThrottle(UserRateThrottle):
    """Limit student performance prediction queries (computationally expensive)"""
    scope = 'student_performance_prediction'  # ✅ FIXED: was 'scop' and renamed class

# ============================================
# LESSON MANAGEMENT THROTTLES
# ============================================
    
class LessonListThrottle(UserRateThrottle):
    """Limit lesson lissting"""
    scope = 'lesson_list'

class LessonCreateThrottle(UserRateThrottle):
    """Limit lesson creation (Admin/Owners/Instructores)"""
    scope = 'lesson_create'

class LessonUpdateThrottle(UserRateThrottle):
    """Limit lesson updates"""
    scope = 'lesson_update'

class MarkAttendanceThrottle(UserRateThrottle):
    """Limit Attendance marking"""
    scope = 'mark_attendance'

class CompleteLessonThrottle(UserRateThrottle):
    """Limit lesson completion marking"""
    scope = 'complete_lesson'

class LessonStatisticsThrottle(UserRateThrottle):
    """Limit lesson statisc queries"""
    scope = 'lesson_stats'

class LessonFeedbackThrottle(UserRateThrottle):
    """Limit feedback viewing"""
    scope = 'lesson_feedback'


# ============================================
# ATTENDANCE MANAGEMENT THROTTLES
# ============================================

class AttendanceListThrottle(UserRateThrottle):
    """Limit attendance listing"""
    scope = 'attendance_list'

class AttendanceCreateThrottle(UserRateThrottle):
    """Limit attendance creation (Instructors/Admins)"""
    scope = 'attendance_create'

class AttendanceUpdateThrottle(UserRateThrottle):
    """Limit attendance updates"""
    scope = 'attendance_update'

class AttendanceBulkCreateThrottle(UserRateThrottle):
    """Limit bulk attendance creation (more restrictive)"""
    scope = 'attendance_bulk_create'

class AttendanceStatisticsThrottle(UserRateThrottle):
    """Limit attendance statistics queries"""
    scope = 'attendance_stats'
# ============================================
# GENERAL PURPOSE THROTTLES
# ============================================

class BurstRateThrottle(UserRateThrottle):
    """Higher rate limit for burst traffic"""
    scope = 'burst'

# ============================================
# FEEDBACK MANAGEMENT THROTTLES
# ============================================

class FeedbackListThrottle(UserRateThrottle):
    """Limit feedback listing"""
    scope = 'feedback_list'


class FeedbackCreateThrottle(UserRateThrottle):
    """Limit feedback creation (students only)"""
    scope = 'feedback_create'


class FeedbackUpdateThrottle(UserRateThrottle):
    """Limit feedback updates (students editing their own)"""
    scope = 'feedback_update'


class FeedbackLessonViewThrottle(UserRateThrottle):
    """Limit lesson feedback viewing"""
    scope = 'feedback_lesson_view'


class FeedbackMyViewThrottle(UserRateThrottle):
    """Limit student's own feedback viewing"""
    scope = 'feedback_my_view'


class FeedbackInstructorViewThrottle(UserRateThrottle):
    """Limit instructor feedback viewing"""
    scope = 'feedback_instructor_view'



# ============================================
# VEHICLE MANAGEMENT THROTTLES
# ============================================

class VehicleListThrottle(UserRateThrottle):
    """Limit vehicle listing"""
    scope = 'vehicle_list'


class VehicleCreateThrottle(UserRateThrottle):
    """Limit vehicle creation (admins/owners)"""
    scope = 'vehicle_create'


class VehicleUpdateThrottle(UserRateThrottle):
    """Limit vehicle updates"""
    scope = 'vehicle_update'


class VehiclePictureUploadThrottle(UserRateThrottle):
    """Limit picture uploads (file upload operation)"""
    scope = 'vehicle_picture_upload'


class VehiclePictureManageThrottle(UserRateThrottle):
    """Limit picture management (delete/set primary)"""
    scope = 'vehicle_picture_manage'


class VehicleMaintenanceThrottle(UserRateThrottle):
    """Limit maintenance operations"""
    scope = 'vehicle_maintenance'


class VehicleStatisticsThrottle(UserRateThrottle):
    """Limit statistics queries"""
    scope = 'vehicle_statistics'


class VehicleHistoryThrottle(UserRateThrottle):
    """Limit vehicle history queries"""
    scope = 'vehicle_history'

# ============================================
# SCHEDULE MANAGEMENT THROTTLES
# ============================================

class ScheduleListThrottle(UserRateThrottle):
    """Limit schedule listing"""
    scope = 'schedule_list'


class ScheduleCreateThrottle(UserRateThrottle):
    """Limit schedule creation"""
    scope = 'schedule_create'


class ScheduleUpdateThrottle(UserRateThrottle):
    """Limit schedule updates"""
    scope = 'schedule_update'


class ScheduleConflictCheckThrottle(UserRateThrottle):
    """Limit conflict checking (expensive query)"""
    scope = 'schedule_conflict_check'


class ScheduleMyScheduleThrottle(UserRateThrottle):
    """Limit my_schedule queries"""
    scope = 'schedule_my_schedule'


class ScheduleAvailabilityThrottle(UserRateThrottle):
    """Limit availability queries (instructor/vehicle)"""
    scope = 'schedule_availability'


class ScheduleCancelThrottle(UserRateThrottle):
    """Limit schedule cancellations"""
    scope = 'schedule_cancel'


class ScheduleRescheduleThrottle(UserRateThrottle):
    """Limit rescheduling operations"""
    scope = 'schedule_reschedule'

# ============================================
#               ACHIEVEMENT
# ============================================
    
class AchievementListThrottle(UserRateThrottle):
    """Limit achievement listing"""
    scope = 'achievement_list'


class AchievementAwardThrottle(UserRateThrottle):
    """Limit manual achievement awarding"""
    scope = 'achievement_award'


class AchievementBulkAwardThrottle(UserRateThrottle):
    """Limit bulk awarding (prevents abuse)"""
    scope = 'achievement_bulk_award'


class AchievementCheckMilestonesThrottle(UserRateThrottle):
    """Limit milestone checking (expensive operation)"""
    scope = 'achievement_check_milestones'


class AchievementLeaderboardThrottle(UserRateThrottle):
    """Limit leaderboard queries"""
    scope = 'achievement_leaderboard'


class AchievementStatisticsThrottle(UserRateThrottle):
    """Limit statistics queries"""
    scope = 'achievement_statistics'
# ============================================
# COMMUNICATION TEMPLATE THROTTLES
# ============================================

class CommunicationTemplateListThrottle(UserRateThrottle):
    """Rate limit for communication template listing"""
    scope = 'communication_template_list'


class CommunicationTemplateCreateThrottle(UserRateThrottle):
    """Rate limit for communication template creation"""
    scope = 'communication_template_create'


class CommunicationTemplateUpdateThrottle(UserRateThrottle):
    """Rate limit for communication template updates"""
    scope = 'communication_template_update'


class CommunicationTemplateDuplicateThrottle(UserRateThrottle):
    """Rate limit for template duplication"""
    scope = 'communication_template_duplicate'


class CommunicationTemplatePreviewThrottle(UserRateThrottle):
    """Rate limit for template preview"""
    scope = 'communication_template_preview'


class CommunicationTemplateUsageStatsThrottle(UserRateThrottle):
    """Rate limit for template usage statistics"""
    scope = 'communication_template_usage_stats'

# ============================================
# AUTOMATED MESSAGE THROTTLES
# ============================================

class AutomatedMessageListThrottle(UserRateThrottle):
    """Rate limit for automated message listing"""
    scope = 'automated_message_list'


class AutomatedMessageCreateThrottle(UserRateThrottle):
    """Rate limit for automated message creation"""
    scope = 'automated_message_create'


class AutomatedMessageUpdateThrottle(UserRateThrottle):
    """Rate limit for automated message updates"""
    scope = 'automated_message_update'


class AutomatedMessageBulkCreateThrottle(UserRateThrottle):
    """Rate limit for bulk message creation"""
    scope = 'automated_message_bulk_create'


class AutomatedMessageBulkCancelThrottle(UserRateThrottle):
    """Rate limit for bulk message cancellation"""
    scope = 'automated_message_bulk_cancel'


class AutomatedMessageSendNowThrottle(UserRateThrottle):
    """Rate limit for sending messages immediately"""
    scope = 'automated_message_send_now'


class AutomatedMessageStatisticsThrottle(UserRateThrottle):
    """Rate limit for message statistics"""
    scope = 'automated_message_statistics'


class AutomatedMessageScheduleThrottle(UserRateThrottle):
    """Rate limit for message schedule queries"""
    scope = 'automated_message_schedule'

# ============================================
# School Analytic THROTTLES 
# ============================================
class SchoolAnalyticsListThrottle(UserRateThrottle):
    """Rate limit for school analytic listing"""
    scope = 'school_analytic_list'

class SchoolAnalyticsCreateThrottle(UserRateThrottle):
    """Rate limit for school creation (Admin/Owner)"""
    scope = 'school_analytic_create'

class SchoolAnalyticsUpdateThrottle(UserRateThrottle):
    """Rate limit for school update (Admin/owner)"""
    scope = 'school_analytic_update'

class SchoolAnalyticsDashboardThrottle(UserRateThrottle):
    """Rate limiting for dashboard """
    scope = 'school_analytic_dashboard'

class SchoolAnalyticsGenerateDailyThrottle(UserRateThrottle):
    """Rate limiting for school generate daily"""
    scope = 'school_analytic_daily'

class SchoolAnalyticsBulkGenerateThrottle(UserRateThrottle):
    """Rate limiting for bulk generate"""
    scope = 'school_analytic_bulk_generate'
    
class SchoolAnalyticsComparisonThrottle(UserRateThrottle):
    """Rate limiting for school comparison"""
    scope = 'school_analytic_comparison'

class SchoolAnalyticsTrendsThrottle(UserRateThrottle):
    """Rate limiting for school trends"""
    scope = 'school_analytic_trends'

class SchoolAnalyticsAlertsThrottle(UserRateThrottle):
    """Rate limiting for school alerts"""
    scope = 'school_analytic_alerts'

class SchoolAnalyticsPredictionsThrottle(UserRateThrottle):
    """Rate limiting for school predictions"""
    scope = 'school_analytic_predictions'

class SchoolAnalyticsExportThrottle(UserRateThrottle):
    """Rate limiting for data export"""
    scope = 'school_analytic_export'

class SchoolAnalyticsSummaryThrottle(UserRateThrottle):
    """Rate limiting for school summary"""
    scope = 'school_analytic_summary'

class SchoolAnalyticsSystemHealthThrottle(UserRateThrottle):
    """Rate limiting for school System health"""
    scope = 'school_analytic_system_health'
# ============================================
# REPORT THROTTLES
# ============================================

class ReportWeeklyThrottle(UserRateThrottle):
    """Rate limit for weekly report generation"""
    rate = '20/hour'

class ReportMonthlyThrottle(UserRateThrottle):
    """Rate limit for monthly report generation"""
    rate = '15/hour'

class ReportSendWeeklyThrottle(UserRateThrottle):
    """Rate limit for sending weekly reports (email intensive)"""
    rate = '5/hour'

class ReportInstructorPerformanceThrottle(UserRateThrottle):
    """Rate limit for instructor performance reports"""
    rate = '25/hour'

class ReportStudentProgressThrottle(UserRateThrottle):
    """Rate limit for student progress reports"""
    rate = '25/hour'

class ReportFinancialSummaryThrottle(UserRateThrottle):
    """Rate limit for financial summary reports"""
    rate = '20/hour'

class ReportExportThrottle(UserRateThrottle):
    """Rate limit for report exports"""
    rate = '10/hour'

class ReportCustomThrottle(UserRateThrottle):
    """Rate limit for custom reports"""
    rate = '15/hour'
    
# ============================================
# DASHBOARD THROTTLES
# ============================================

class DashboardOverviewThrottle(UserRateThrottle):
    """Limit dashboard overview requests"""
    scope = 'dashboard_overview'

class DashboardDetailedThrottle(UserRateThrottle):
    """Limit detailed dashboard requests (more data-intensive)"""
    scope = 'dashboard_detailed'

class DashboardQuickStatsThrottle(UserRateThrottle):
    """Limit quick stats requests"""
    scope = 'dashboard_quick_stats'

class DashboardNotificationsThrottle(UserRateThrottle):
    """Limit notifications requests"""
    scope = 'dashboard_notifications'
    

# ============================================
# SUBSCRIPTION PLAN THROTTLES
# ============================================

class SubscriptionPlanListThrottle(UserRateThrottle):
    scope = 'subscription_plan_list'

class SubscriptionPlanCreateThrottle(UserRateThrottle):
    scope = 'subscription_plan_create'

class SubscriptionPlanUpdateThrottle(UserRateThrottle):
    scope = 'subscription_plan_update'

class SubscriptionPlanStatisticsThrottle(UserRateThrottle):
    scope = 'subscription_plan_statistics'


# ============================================
# SCHOOL SUBSCRIPTION THROTTLES
# ============================================

class SchoolSubscriptionListThrottle(UserRateThrottle):
    scope = 'school_subscription_list'

class SchoolSubscriptionCreateThrottle(UserRateThrottle):
    scope = 'school_subscription_create'

class SchoolSubscriptionUpdateThrottle(UserRateThrottle):
    scope = 'school_subscription_update'

class SchoolSubscriptionActionThrottle(UserRateThrottle):
    """For cancel, renew, upgrade actions"""
    scope = 'school_subscription_action'

class SchoolSubscriptionUsageThrottle(UserRateThrottle):
    """For check_limits and usage_stats"""
    scope = 'school_subscription_usage'

# ============================================
# STUDENT DOCUMENT THROTTLES
# ============================================

class StudentDocumentListThrottle(UserRateThrottle):
    """Rate limit for document listing"""
    rate = '100/hour'

class StudentDocumentCreateThrottle(UserRateThrottle):
    """Rate limit for document creation (file upload intensive)"""
    rate = '20/hour'

class StudentDocumentUpdateThrottle(UserRateThrottle):
    """Rate limit for document updates"""
    rate = '30/hour'

class StudentDocumentBulkUploadThrottle(UserRateThrottle):
    """Rate limit for bulk uploads (very intensive)"""
    rate = '5/hour'

class StudentDocumentDownloadThrottle(UserRateThrottle):
    """Rate limit for document downloads"""
    rate = '50/hour'

class StudentDocumentMyDocumentsThrottle(UserRateThrottle):
    """Rate limit for my documents endpoint"""
    rate = '60/hour'

class StudentDocumentStudentDocsThrottle(UserRateThrottle):
    """Rate limit for viewing student documents"""
    rate = '40/hour'

class StudentDocumentStatisticsThrottle(UserRateThrottle):
    """Rate limit for statistics endpoint"""
    rate = '30/hour'
# ============================================
# ADVANCED THROTTLES (Optional)
# ============================================

class HeaderRateThrottle(SimpleRateThrottle):
    """
    Throttle that adds rate limit headers to responses.
    Useful for API clients to know their limits.
    """
    
    def allow_request(self, request, view):
        # Call parent to check if request should be allowed
        allowed = super().allow_request(request, view)
        
        # Calculate remaining requests
        if self.history:
            self.num_requests = len(self.history)
            self.remaining = self.num_requests if hasattr(self, 'num_requests') else 0
            self.wait = self.throttle_success()
        else:
            self.remaining = getattr(self, 'rate', 0)
            self.wait = None
        
        return allowed
    
    def throttle_success(self):
        """Called when request is allowed - calculate wait time"""
        if self.history:
            remaining_duration = self.duration - (self.now - self.history[-1])
            return remaining_duration
        return None


class LoggingRateThrottle(SimpleRateThrottle):
    """
    Throttle that logs when rate limits are exceeded.
    Useful for monitoring and security.
    """
    
    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        
        if not allowed:
            user_info = f"user {request.user.id}" if request.user.is_authenticated else "anonymous user"
            logger.warning(
                f"Rate limit exceeded for {user_info} "
                f"on {view.__class__.__name__}.{getattr(view, 'action', 'unknown')} "
                f"(scope: {self.scope})"
            )
        
        return allowed


# ============================================
# CUSTOM THROTTLE MIXINS (Optional)
# ============================================

class IPBasedThrottle(SimpleRateThrottle):
    """
    Throttle based on IP address regardless of authentication.
    Useful for preventing DDoS attacks.
    """
    scope = 'ip_based'
    
    def get_cache_key(self, request, view):
        # Get IP address
        ip = self.get_ident(request)
        return f'throttle_{self.scope}_{ip}'


class PerEndpointThrottle(UserRateThrottle):
    """
    Throttle that creates separate limits per endpoint.
    Automatically uses view name as part of scope.
    """
    
    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        # Include view action in cache key for per-endpoint limits
        action = getattr(view, 'action', 'default')
        return self.cache_format % {
            'scope': f'{self.scope}_{action}',
            'ident': ident
        }