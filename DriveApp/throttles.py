"""
Custom throttle classes for rate limiting.
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.response import Response

import logging
logger = logging.getLogger(__name__)

class LoginRateThrottle(AnonRateThrottle):
    """Rate limit for login attempts"""
    scope = 'login'


class RegisterStudentThrottle(UserRateThrottle):  # Changed from RegisterRateThrottle
    """Rate limit for student registration"""
    scope = 'register'


class StatsThrottle(UserRateThrottle):  # Changed from StatsRateThrottle
    """Rate limit for statistics endpoints"""
    scope = 'stats'


class SchoolUsersThrottle(UserRateThrottle):  # NEW: Added this class
    """Limit school user listing"""
    scope = 'school_users'


class BurstRateThrottle(UserRateThrottle):
    """Higher rate limit for burst traffic"""
    scope = 'burst'
    rate = '60/minute'


class HeaderRateThrottle(SimpleRateThrottle):
    """Throttle that adds rate limit headers to responses"""
    
    def allow_request(self, request, view):
        # Call parent to check if request should be allowed
        allowed = super().allow_request(request, view)
        
        # Calculate remaining requests
        if self.history:
            self.num_requests = len(self.history)
            self.remaining = self.rate - self.num_requests
            self.wait = self.throttle_success()
        else:
            self.remaining = self.rate
            self.wait = None
        
        return allowed
    
    def throttle_success(self):
        """Called when request is allowed"""
        if self.history:
            remaining_duration = self.duration - (self.now - self.history[-1])
            return remaining_duration
        return None
    
class LoggingRateThrottle(SimpleRateThrottle):
    def allow_request(self, request, view):
        allowed = super().allow_request(request, view)
        
        if not allowed:
            logger.warning(
                f"Rate limit exceeded for user {request.user.id} "
                f"on {view.__class__.__name__}.{view.action} "
                f"(scope: {self.scope})"
            )
        
        return allowed