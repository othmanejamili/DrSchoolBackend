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