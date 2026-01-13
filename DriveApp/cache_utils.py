"""
Cache utility functions and helpers.
"""

from django.core.cache import cache
import hashlib
import json


# ============================================
# USER CACHE KEYS
# ============================================

def get_user_queryset_cache_key(user_id, role):
    """Generate cache key for user queryset"""
    return f'user_queryset_{user_id}_{role}'


def get_user_stats_cache_key():
    """Generate cache key for user stats"""
    return 'user_stats_v1'


# ============================================
# SCHOOL CACHE KEYS
# ============================================

def get_school_stats_cache_key(school_id=None):
    """Generate cache key for school stats"""
    if school_id:
        return f'school_{school_id}_stats'
    return 'school_stats_v1'


def get_school_users_cache_key(user_id, role_filter):
    """Generate cache key for school users list"""
    return f'school_users_{user_id}_{role_filter or "all"}'


def get_school_student_count_cache_key(school_id):
    """Generate cache key for school student count"""
    return f'school_{school_id}_student_count'


def get_schools_cache_key(user_id, role):
    """Generate cache key for schools queryset"""
    return f'schools_queryset_{user_id}_{role}'


# ============================================
# STUDENT PROFILE CACHE KEYS (NEW)
# ============================================

def get_student_profile_cache_key(user_id, role):
    """Generate cache key for student profile queryset"""
    return f'student_profiles_queryset_{user_id}_{role}'


def get_student_profile_detail_cache_key(profile_id):
    """Generate cache key for single student profile"""
    return f'student_profile_detail_{profile_id}'


def get_student_progress_cache_key(profile_id):
    """Generate cache key for student progress data"""
    return f'student_progress_{profile_id}'


def get_student_prediction_cache_key(profile_id):
    """Generate cache key for student performance prediction"""
    return f'student_prediction_{profile_id}'


# ============================================
# GENERIC CACHE KEY GENERATOR
# ============================================

def generate_cache_key_from_request(request, prefix):
    """Generate a unique cache key from request parameters"""
    query_params = dict(request.query_params)
    user_id = request.user.id if request.user.is_authenticated else 'anonymous'
    
    # Sort query params for consistent keys
    sorted_params = json.dumps(query_params, sort_keys=True)
    key_data = f"{prefix}_{user_id}_{sorted_params}"
    
    return hashlib.md5(key_data.encode()).hexdigest()


# ============================================
# USER CACHE INVALIDATION
# ============================================

def invalidate_user_caches(user_id=None):
    """Invalidate all user-related caches"""
    # Delete user stats
    cache.delete(get_user_stats_cache_key())
    
    if user_id:
        # Delete specific user caches
        for role in ['A', 'I', 'S']:
            cache.delete(get_user_queryset_cache_key(user_id, role))
            cache.delete(get_student_profile_cache_key(user_id, role))
        
        # Delete user-specific patterns
        patterns = [
            f'user_{user_id}_*',
            f'student_profile_user_{user_id}',
            f'*_{user_id}_*',
        ]
        for pattern in patterns:
            try:
                cache.delete_pattern(pattern)
            except AttributeError:
                # Some cache backends don't support delete_pattern
                pass


# ============================================
# SCHOOL CACHE INVALIDATION
# ============================================

def invalidate_school_caches(school_id):
    """Invalidate school-related caches"""
    if not school_id:
        return
    
    # Delete specific school caches
    cache.delete(get_school_stats_cache_key(school_id))
    cache.delete(get_school_student_count_cache_key(school_id))
    
    # Delete school patterns
    patterns = [
        f'school_{school_id}_*',
        f'*_school_{school_id}_*',
    ]
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


def invalidate_schools_cache(user_id, role):
    """Invalidate schools cache for a user"""
    # Delete the main schools cache
    cache.delete(get_schools_cache_key(user_id, role))
    
    # Delete user's school-related patterns
    patterns = [
        f'schools_queryset_{user_id}_*',
        f'*schools*{user_id}*',
        f'*_{user_id}_schools*',
    ]
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


# ============================================
# STUDENT PROFILE CACHE INVALIDATION (NEW)
# ============================================

def invalidate_student_profile_cache(user_id):
    """Invalidate all caches related to a student profile"""
    if not user_id:
        return
    
    # Delete specific student profile caches
    for role in ['A', 'I', 'S']:
        cache.delete(get_student_profile_cache_key(user_id, role))
    
    # Delete student-specific caches
    patterns_to_delete = [
        f'student_profile_user_{user_id}',
        f'student_profile_detail_*',
        f'student_progress_{user_id}',
        f'student_prediction_{user_id}',
        f'*student*{user_id}*',
    ]
    
    for pattern in patterns_to_delete:
        try:
            if '*' in pattern:
                cache.delete_pattern(pattern)
            else:
                cache.delete(pattern)
        except AttributeError:
            # Fallback for cache backends without delete_pattern
            cache.delete(pattern.replace('*', ''))


def invalidate_student_profiles_by_school(school_id):
    """Invalidate all student profile caches for a specific school"""
    if not school_id:
        return
    
    patterns = [
        f'*school_{school_id}*student*',
        f'student_profiles_*_school_{school_id}',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


# ============================================
# BULK CACHE OPERATIONS
# ============================================

def invalidate_all_student_caches():
    """Invalidate ALL student-related caches (use sparingly!)"""
    patterns = [
        'student_*',
        '*_student_*',
        'student_profile_*',
        'student_progress_*',
        'student_prediction_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


def invalidate_all_caches():
    """Clear entire cache (nuclear option - use only in emergencies)"""
    cache.clear()

# ============================================
# LESSON CACHE KEYS
# ============================================
    
def get_lesson_queryset_cache_key(user_id, role):
    """Generate cache key for lesson queryset"""
    return f'lessons_queryset_{user_id}_{role}'

def get_lesson_detail_cache_key(lesson_id):
    """Generate cache key for single lesson"""
    return f'lesson_detail_{lesson_id}'

def get_lesson_attendance_cache_key(lesson_id):
    """Generate cache key for lesson attendance"""
    return f'lesson_attendance_{lesson_id}'

def get_lesson_feedback_cache_key(lesson_id):
    """Generate cache key for lesson feedback"""
    return f'lesson_feedback_{lesson_id}'

def get_lesson_schedule_cache_key(lesson_id):
    """Generate cache key for lesson schedule"""
    return f'lesson_schedule_{lesson_id}'

def get_upcoming_lessons_cache_key(user_id, role):
    """Generate cache key for upcoming lessons"""
    return f'upcoming_lessons_{user_id}_{role}'


def get_my_lessons_cache_key(user_id, role, status_filter=None):
    """Generate cache key for my lessons"""
    status_part = f'_{status_filter}' if status_filter else '_all'
    return f'my_lessons_{user_id}_{role}{status_part}'


def get_lesson_statistics_cache_key(user_id, role):
    """Generate cache key for lesson statistics"""
    return f'lesson_stats_{user_id}_{role}'

# ============================================
# LESSON CACHE INVALIDATION
# ============================================
def invalidate_lesson_cache(lesson_id):
    """Invalidate all caches related to a specific lesson"""
    if not lesson_id:
        return 
    
    # Delete specific lesson caches
    cache_key = [
        get_lesson_detail_cache_key(lesson_id),
        get_lesson_attendance_cache_key(lesson_id),
        get_lesson_feedback_cache_key(lesson_id),
        get_lesson_schedule_cache_key(lesson_id)
    ]

    for key in cache_key:
        cache.delete(key)

    #Delete patterns
    patterns = [
        f'lesson_{lesson_id}_*',
        f'*_lesson_{lesson_id}_*'
    ]

    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AssertionError:
            pass
    
def invalidate_lesson_queryset_caches():
    """Invalidate all lesson queryset caches"""
    patterns = [
        'lessons_queryset_*',
        'upcoming_lessons_*',
        'my_lessons_*',
        'lesson_stats_*',
    ]

    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass

def invalidate_instructor_lesson_caches(instructor_id):
    """Invalidate caches for all lessons of an instructor"""
    patterns = [
        f'lessons_queryset_{instructor_id}_*',
        f'upcoming_lessons_{instructor_id}_*',
        f'my_lessons_{instructor_id}_*',
        f'lesson_stats_{instructor_id}_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass
        
def invalidate_school_lesson_caches(school_id):
    """Invalidate caches for all lessons in a school"""

    patterns = [
        f'*_school_{school_id}_lessons_*',
        f'lessons_*_school_{school_id}_*',
    ]

    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass
        

# ============================================
# FEEDBACK CACHE KEYS
# ============================================

def get_feedback_queryset_cache_key(user_id, role):
    """Generate cache key for feedback queryset"""
    return f'feedback_queryset_{user_id}_{role}'


def get_feedback_detail_cache_key(feedback_id):
    """Generate cache key for single feedback"""
    return f'feedback_detail_{feedback_id}'


def get_lesson_feedback_cache_key(lesson_id):
    """Generate cache key for lesson's feedback list"""
    return f'lesson_feedback_{lesson_id}'


def get_student_feedback_cache_key(student_id):
    """Generate cache key for student's feedback list"""
    return f'student_feedback_{student_id}'


def get_instructor_feedback_cache_key(instructor_id):
    """Generate cache key for instructor's feedback"""
    return f'instructor_feedback_{instructor_id}'


def get_my_feedback_cache_key(user_id):
    """Generate cache key for current student's feedback"""
    return f'my_feedback_{user_id}'


def get_lesson_feedback_stats_cache_key(lesson_id):
    """Generate cache key for lesson feedback statistics"""
    return f'lesson_feedback_stats_{lesson_id}'


def get_instructor_feedback_stats_cache_key(instructor_id):
    """Generate cache key for instructor feedback statistics"""
    return f'instructor_feedback_stats_{instructor_id}'


# ============================================
# FEEDBACK CACHE INVALIDATION
# ============================================

def invalidate_feedback_cache(feedback_id):
    """Invalidate all caches related to a specific feedback"""
    if not feedback_id:
        return
    
    cache_keys = [
        get_feedback_detail_cache_key(feedback_id),
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    # Delete patterns
    patterns = [
        f'feedback_{feedback_id}_*',
        f'*_feedback_{feedback_id}_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


def invalidate_feedback_queryset_caches():
    """Invalidate all feedback queryset caches"""
    patterns = [
        'feedback_queryset_*',
        'my_feedback_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


def invalidate_lesson_feedback_caches(lesson_id):
    """Invalidate caches for all feedback of a lesson"""
    if not lesson_id:
        return
    
    cache_keys = [
        get_lesson_feedback_cache_key(lesson_id),
        get_lesson_feedback_stats_cache_key(lesson_id),
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    patterns = [
        f'lesson_feedback_{lesson_id}_*',
        f'lesson_{lesson_id}_feedback_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


def invalidate_student_feedback_caches(student_id):
    """Invalidate caches for all feedback from a student"""
    if not student_id:
        return
    
    cache_keys = [
        get_student_feedback_cache_key(student_id),
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    patterns = [
        f'student_feedback_{student_id}_*',
        f'my_feedback_{student_id}',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


def invalidate_instructor_feedback_caches(instructor_id):
    """Invalidate caches for all feedback for an instructor"""
    if not instructor_id:
        return
    
    cache_keys = [
        get_instructor_feedback_cache_key(instructor_id),
        get_instructor_feedback_stats_cache_key(instructor_id),
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    patterns = [
        f'instructor_feedback_{instructor_id}_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass

        
# ============================================
# ATTENDANCE CACHE KEYS
# ============================================

def get_attendance_queryset_cache_key(user_id, role):
    """Generate cache key for attendance queryset"""
    return f'attendance_queryset_{user_id}_{role}'


def get_attendance_detail_cache_key(attendance_id):
    """Generate cache key for single attendance record"""
    return f'attendance_detail_{attendance_id}'


def get_student_attendance_cache_key(user_id):
    """Generate cache key for student's attendance records"""
    return f'student_attendance_{user_id}'


def get_lesson_attendance_summary_cache_key(lesson_id):
    """Generate cache key for lesson attendance summary"""
    return f'lesson_attendance_summary_{lesson_id}'


def get_attendance_statistics_cache_key(user_id, role):
    """Generate cache key for attendance statistics"""
    return f'attendance_stats_{user_id}_{role}'


# ============================================
# ATTENDANCE CACHE INVALIDATION
# ============================================

def invalidate_attendance_cache(attendance_id):
    """Invalidate all caches related to a specific attendance record"""
    if not attendance_id:
        return
    
    # Delete specific attendance caches
    cache_keys = [
        get_attendance_detail_cache_key(attendance_id)
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    # Delete patterns
    patterns = [
        f'attendance_{attendance_id}_*',
        f'*_attendance_{attendance_id}_*'
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


def invalidate_attendance_queryset_caches():
    """Invalidate all attendance queryset caches"""
    patterns = [
        'attendance_queryset_*',
        'attendance_stats_*',
        'student_attendance_*',
        'lesson_attendance_summary_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


def invalidate_student_attendance_caches(student_id):
    """Invalidate caches for all attendance records of a student"""
    if not student_id:
        return
    
    patterns = [
        f'student_attendance_*_{student_id}_*',
        f'*_student_{student_id}_attendance_*',
        f'attendance_*_student_{student_id}_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


def invalidate_lesson_attendance_caches(lesson_id):
    """Invalidate caches for all attendance records of a lesson"""
    if not lesson_id:
        return
    
    # Delete specific lesson attendance caches
    cache.delete(get_lesson_attendance_summary_cache_key(lesson_id))
    
    patterns = [
        f'lesson_attendance_summary_{lesson_id}',
        f'*_lesson_{lesson_id}_attendance_*',
        f'attendance_*_lesson_{lesson_id}_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass

# ============================================
# CACHE PATTERN UTILITIES
# ============================================

def delete_pattern_with_fallback(pattern):
    """
    Delete pattern with fallback for cache backends without delete_pattern.
    Returns number of keys deleted, or -1 if unknown.
    """
    try:
        return cache.delete_pattern(pattern)
    except AttributeError:
        # Fallback: just clear everything (not ideal but works)
        cache.clear()
        return -1  # Unknown count


def cache_exists(key):
    """Check if a cache key exists"""
    return cache.get(key) is not None


def get_cache_ttl(key):
    """
    Get time-to-live for a cache key (if supported by backend).
    Returns None if not supported or key doesn't exist.
    """
    try:
        return cache.ttl(key)
    except AttributeError:
        return None


# ============================================
# CACHE STATISTICS (for monitoring)
# ============================================

def get_cache_stats():
    """
    Get cache statistics (if supported by backend).
    Useful for monitoring cache performance.
    """
    try:
        return cache.get_stats()
    except AttributeError:
        return {
            'message': 'Cache backend does not support statistics',
            'backend': str(type(cache))
        }


# ============================================
# CACHE WARMING (Optional)
# ============================================

def warm_user_cache(user):
    """
    Pre-populate cache for a user.
    Useful after login or significant data changes.
    """
    from .models import User, StudentProfile
    
    # Warm user queryset cache
    cache_key = get_user_queryset_cache_key(user.id, user.role)
    
    if user.role == 'S':
        # Warm student profile cache
        try:
            profile = StudentProfile.objects.select_related('user', 'school').get(user=user)
            profile_cache_key = f'student_profile_user_{user.id}'
            from .serializers import StudentProfileSerializer
            serializer = StudentProfileSerializer(profile)
            cache.set(profile_cache_key, serializer.data, 60 * 3)
        except StudentProfile.DoesNotExist:
            pass


# ============================================
# CACHE DECORATORS (Helper functions)
# ============================================

def cache_result(timeout=300, key_prefix=''):
    """
    Decorator to cache function results.
    
    Usage:
        @cache_result(timeout=600, key_prefix='expensive_calc')
        def expensive_calculation(param1, param2):
            # ... expensive operation
            return result
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and args
            key_data = f"{key_prefix}_{func.__name__}_{str(args)}_{str(kwargs)}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        
        return wrapper
    return decorator