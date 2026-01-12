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
# GENERAL PURPOSE THROTTLES
# ============================================

class BurstRateThrottle(UserRateThrottle):
    """Higher rate limit for burst traffic"""
    scope = 'burst'


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