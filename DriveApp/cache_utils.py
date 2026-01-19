"""
Cache utility functions and helpers.
"""

from django.core.cache import cache
import hashlib
import json
from datetime import datetime, timedelta

# ============================================
# CACHE PATTERN UTILITIES (FIXED FOR TESTS)
# ============================================

def delete_pattern_with_fallback(pattern):
    """
    Delete pattern with fallback for cache backends without delete_pattern.
    Returns number of keys deleted, or -1 if unknown.
    """
    try:
        # Try Redis-style pattern deletion
        return cache.delete_pattern(pattern)
    except AttributeError:
        # Fallback for backends without delete_pattern (like LocMemCache)
        # In tests, we'll just clear everything
        try:
            if hasattr(cache, 'clear'):
                cache.clear()
                return -1  # Unknown count
        except:
            pass
        return 0


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
        
        # Delete user-specific patterns (with fallback)
        patterns = [
            f'user_{user_id}_*',
            f'student_profile_user_{user_id}',
            f'*_{user_id}_*',
        ]
        for pattern in patterns:
            delete_pattern_with_fallback(pattern)


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
    
    # Delete school patterns (with fallback)
    patterns = [
        f'school_{school_id}_*',
        f'*_school_{school_id}_*',
    ]
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_schools_cache(user_id, role):
    """Invalidate schools cache for a user"""
    # Delete the main schools cache
    cache.delete(get_schools_cache_key(user_id, role))
    
    # Delete user's school-related patterns (with fallback)
    patterns = [
        f'schools_queryset_{user_id}_*',
        f'*schools*{user_id}*',
        f'*_{user_id}_schools*',
    ]
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


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
        if '*' in pattern:
            delete_pattern_with_fallback(pattern)
        else:
            cache.delete(pattern)


def invalidate_student_profiles_by_school(school_id):
    """Invalidate all student profile caches for a specific school"""
    if not school_id:
        return
    
    patterns = [
        f'*school_{school_id}*student*',
        f'student_profiles_*_school_{school_id}',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


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
        delete_pattern_with_fallback(pattern)


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
# LESSON CACHE INVALIDATION (FIXED)
# ============================================
def invalidate_lesson_cache(lesson_id):
    """Invalidate all caches related to a specific lesson"""
    if not lesson_id:
        return 
    
    # Delete specific lesson caches
    cache_keys = [
        get_lesson_detail_cache_key(lesson_id),
        get_lesson_attendance_cache_key(lesson_id),
        get_lesson_feedback_cache_key(lesson_id),
        get_lesson_schedule_cache_key(lesson_id)
    ]

    for key in cache_keys:
        cache.delete(key)

    # Delete patterns with fallback
    patterns = [
        f'lesson_{lesson_id}_*',
        f'*_lesson_{lesson_id}_*'
    ]

    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_lesson_queryset_caches():
    """Invalidate all lesson queryset caches"""
    patterns = [
        'lessons_queryset_*',
        'upcoming_lessons_*',
        'my_lessons_*',
        'lesson_stats_*',
    ]

    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_instructor_lesson_caches(instructor_id):
    """Invalidate caches for all lessons of an instructor"""
    if not instructor_id:
        return
    
    patterns = [
        f'lessons_queryset_{instructor_id}_*',
        f'upcoming_lessons_{instructor_id}_*',
        f'my_lessons_{instructor_id}_*',
        f'lesson_stats_{instructor_id}_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_school_lesson_caches(school_id):
    """Invalidate caches for all lessons in a school"""
    if not school_id:
        return

    patterns = [
        f'*_school_{school_id}_lessons_*',
        f'lessons_*_school_{school_id}_*',
    ]

    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


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
    
    # Delete patterns with fallback
    patterns = [
        f'feedback_{feedback_id}_*',
        f'*_feedback_{feedback_id}_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_feedback_queryset_caches():
    """Invalidate all feedback queryset caches"""
    patterns = [
        'feedback_queryset_*',
        'my_feedback_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


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
        delete_pattern_with_fallback(pattern)


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
        delete_pattern_with_fallback(pattern)


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
        delete_pattern_with_fallback(pattern)


# ============================================
# VEHICLE CACHE KEYS
# ============================================

def get_vehicle_queryset_cache_key(user_id, role):
    """Generate cache key for vehicle queryset"""
    return f'vehicles_queryset_{user_id}_{role}'


def get_vehicle_detail_cache_key(vehicle_id):
    """Generate cache key for single vehicle"""
    return f'vehicle_detail_{vehicle_id}'


def get_vehicle_pictures_cache_key(vehicle_id):
    """Generate cache key for vehicle pictures"""
    return f'vehicle_pictures_{vehicle_id}'


def get_vehicle_available_cache_key(user_id, transmission=None):
    """Generate cache key for available vehicles"""
    trans_part = f'_{transmission}' if transmission else '_all'
    return f'vehicles_available_{user_id}{trans_part}'


def get_vehicle_maintenance_due_cache_key(user_id):
    """Generate cache key for maintenance due vehicles"""
    return f'vehicles_maintenance_due_{user_id}'


def get_vehicle_statistics_cache_key(user_id, role):
    """Generate cache key for vehicle statistics"""
    return f'vehicle_stats_{user_id}_{role}'


def get_vehicle_history_cache_key(vehicle_id):
    """Generate cache key for vehicle history"""
    return f'vehicle_history_{vehicle_id}'


def get_my_school_vehicles_cache_key(user_id, role):
    """Generate cache key for my school vehicles"""
    return f'my_school_vehicles_{user_id}_{role}'


# ============================================
# VEHICLE CACHE INVALIDATION
# ============================================

def invalidate_vehicle_cache(vehicle_id):
    """Invalidate all caches related to a specific vehicle"""
    if not vehicle_id:
        return
    
    cache_keys = [
        get_vehicle_detail_cache_key(vehicle_id),
        get_vehicle_pictures_cache_key(vehicle_id),
        get_vehicle_history_cache_key(vehicle_id),
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    # Delete patterns with fallback
    patterns = [
        f'vehicle_{vehicle_id}_*',
        f'*_vehicle_{vehicle_id}_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_vehicle_queryset_caches():
    """Invalidate all vehicle queryset caches"""
    patterns = [
        'vehicles_queryset_*',
        'vehicles_available_*',
        'my_school_vehicles_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_vehicle_maintenance_caches():
    """Invalidate all maintenance-related caches"""
    patterns = [
        'vehicles_maintenance_due_*',
        'vehicle_stats_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_vehicle_statistics_caches():
    """Invalidate all vehicle statistics caches"""
    patterns = [
        'vehicle_stats_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_school_vehicle_caches(school_id):
    """Invalidate caches for all vehicles in a school"""
    if not school_id:
        return
    
    patterns = [
        f'*_school_{school_id}_vehicles_*',
        f'vehicles_*_school_{school_id}_*',
        'my_school_vehicles_*',
        'vehicles_available_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_vehicle_pictures_cache(vehicle_id):
    """Invalidate vehicle pictures cache specifically"""
    if not vehicle_id:
        return
    
    cache.delete(get_vehicle_pictures_cache_key(vehicle_id))
    cache.delete(get_vehicle_detail_cache_key(vehicle_id))


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
    
    # Delete patterns with fallback
    patterns = [
        f'attendance_{attendance_id}_*',
        f'*_attendance_{attendance_id}_*'
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_attendance_queryset_caches():
    """Invalidate all attendance queryset caches"""
    patterns = [
        'attendance_queryset_*',
        'attendance_stats_*',
        'student_attendance_*',
        'lesson_attendance_summary_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


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
        delete_pattern_with_fallback(pattern)


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
        delete_pattern_with_fallback(pattern)


# ============================================
# SCHEDULE CACHE KEYS
# ============================================

def get_schedule_queryset_cache_key(user_id, role):
    """Generate cache key for schedule queryset"""
    return f'schedules_queryset_{user_id}_{role}'


def get_schedule_detail_cache_key(schedule_id):
    """Generate cache key for single schedule"""
    return f'schedule_detail_{schedule_id}'


def get_my_schedule_cache_key(user_id, range_filter='upcoming', status_filter=None):
    """Generate cache key for my_schedule with filters"""
    status_part = f'_{status_filter}' if status_filter else '_all'
    return f'my_schedule_{user_id}_{range_filter}{status_part}'


def get_upcoming_schedules_cache_key(user_id, role, date):
    """Generate cache key for upcoming schedules"""
    return f'upcoming_schedules_{user_id}_{role}_{date}'


def get_instructor_availability_cache_key(instructor_id, date, duration):
    """Generate cache key for instructor availability"""
    return f'instructor_avail_{instructor_id}_{date}_{duration}'


def get_vehicle_availability_cache_key(vehicle_id, date, duration):
    """Generate cache key for vehicle availability"""
    return f'vehicle_avail_{vehicle_id}_{date}_{duration}'


def get_schedule_conflicts_cache_key(instructor_id, vehicle_id, start_time, end_time):
    """Generate cache key for conflict check (be careful with this - very specific)"""
    # Hash the parameters to create a shorter key
    key_data = f'{instructor_id}_{vehicle_id}_{start_time}_{end_time}'
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
    return f'schedule_conflicts_{key_hash}'


def get_my_schedule_mobile_cache_key(user_id, date=None):
    """Generate cache key for mobile schedule"""
    date_part = f'_{date}' if date else '_all'
    return f'my_schedule_mobile_{user_id}{date_part}'


# ============================================
# SCHEDULE CACHE INVALIDATION
# ============================================

def invalidate_schedule_cache(schedule_id):
    """Invalidate all caches related to a specific schedule"""
    if not schedule_id:
        return
    
    cache_keys = [
        get_schedule_detail_cache_key(schedule_id),
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    # Delete patterns with fallback
    patterns = [
        f'schedule_{schedule_id}_*',
        f'*_schedule_{schedule_id}_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_schedule_queryset_caches():
    """Invalidate all schedule queryset caches"""
    patterns = [
        'schedules_queryset_*',
        'my_schedule_*',
        'upcoming_schedules_*',
        'my_schedule_mobile_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_instructor_schedule_caches(instructor_id):
    """Invalidate caches for all schedules of an instructor"""
    if not instructor_id:
        return
    
    patterns = [
        f'instructor_avail_{instructor_id}_*',
        f'my_schedule_{instructor_id}_*',
        f'upcoming_schedules_{instructor_id}_*',
        f'schedules_queryset_{instructor_id}_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_vehicle_schedule_caches(vehicle_id):
    """Invalidate caches for all schedules using a vehicle"""
    if not vehicle_id:
        return
    
    patterns = [
        f'vehicle_avail_{vehicle_id}_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_availability_caches():
    """Invalidate all availability caches (instructor and vehicle)"""
    patterns = [
        'instructor_avail_*',
        'vehicle_avail_*',
        'schedule_conflicts_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_school_schedule_caches(school_id):
    """Invalidate caches for all schedules in a school"""
    if not school_id:
        return
    
    patterns = [
        f'*_school_{school_id}_schedules_*',
        f'schedules_*_school_{school_id}_*',
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)

# ============================================
#               ACHIEVEMENT
# ============================================

def get_achievement_queryset_cache_key(user_id, role):
    """Generate cache key for achievement queryset"""
    return f'achievements_queryset_{user_id}_{role}'


def get_my_achievements_cache_key(user_id):
    """Generate cache key for my_achievements"""
    return f'my_achievements_{user_id}'


def get_leaderboard_cache_key(scope, time_period, limit, school_id=None):
    """Generate cache key for leaderboard"""
    school_part = f'_school_{school_id}' if school_id else ''
    return f'leaderboard_{scope}_{time_period}_{limit}{school_part}'


def get_achievement_statistics_cache_key(user_id, role):
    """Generate cache key for statistics"""
    return f'achievement_stats_{user_id}_{role}'


def get_student_progress_cache_key(student_id):
    """Generate cache key for student progress"""
    return f'student_progress_{student_id}'


def get_badges_cache_key(student_id):
    """Generate cache key for badges"""
    return f'badges_{student_id}'


def invalidate_achievement_cache(achievement_id):
    """Invalidate specific achievement cache"""
    if not achievement_id:
        return
    cache.delete(f'achievement_detail_{achievement_id}')


def invalidate_achievement_queryset_caches():
    """Invalidate all achievement queryset caches"""
    patterns = [
        'achievements_queryset_*',
        'my_achievements_*',
        'student_progress_*',
        'badges_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            pass


def invalidate_leaderboard_caches():
    """Invalidate all leaderboard caches"""
    try:
        cache.delete_pattern('leaderboard_*')
    except AttributeError:
        pass


def invalidate_achievement_statistics_caches():
    """Invalidate all statistics caches"""
    try:
        cache.delete_pattern('achievement_stats_*')
    except AttributeError:
        pass


def invalidate_student_achievement_caches(student_id):
    """Invalidate caches for a specific student's achievements"""
    if not student_id:
        return
    
    cache_keys = [
        get_my_achievements_cache_key(student_id),
        get_student_progress_cache_key(student_id),
        get_badges_cache_key(student_id),
    ]
    
    for key in cache_keys:
        cache.delete(key)

# ============================================
# COMMUNICATION TEMPLATE CACHE KEYS
# ============================================

def get_communication_template_queryset_cache_key(user_id, role):
    """Generate cache key for communication template queryset"""
    return f'communication_templates_queryset_{user_id}_{role}'

def get_communication_template_detail_cache_key(template_id):
    """Generate cache key for single template"""
    return f'communication_template_detail_{template_id}'

def get_template_by_type_cache_key(user_id, school_id=None):
    """Generate cache key for templates grouped by type"""
    school_suffix = f'_school_{school_id}' if school_id else ''
    return f'templates_by_type_{user_id}{school_suffix}'

def get_template_usage_stats_cache_key(user_id):
    """Generate cache key for template usage statistics"""
    return f'template_usage_stats_{user_id}'

def get_template_available_variables_cache_key():
    """Generate cache key for available template variables"""
    return 'template_available_variables'

def get_my_school_templates_cache_key(user_id, template_type=None, active_only=False):
    """Generate cache key for user's school templates"""
    type_suffix = f'_type_{template_type}' if template_type else ''
    active_suffix = '_active' if active_only else ''
    return f'my_school_templates_{user_id}{type_suffix}{active_suffix}'

# ============================================
# COMMUNICATION TEMPLATE CACHE INVALIDATION
# ============================================

def invalidate_communication_template_cache(template_id, user_id=None, school_id=None):
    """Invalidate all caches related to a communication template"""
    if not template_id:
        return
    
    # Delete specific template cache
    cache.delete(get_communication_template_detail_cache_key(template_id))
    
    # Delete related patterns
    patterns_to_delete = [
        f'communication_template_{template_id}_*',
        f'*template*{template_id}*',
        'template_by_type_*',
        'template_usage_stats_*',
        'my_school_templates_*'
    ]
    
    for pattern in patterns_to_delete:
        delete_pattern_with_fallback(pattern)
    
    # Invalidate school-specific caches if school_id provided
    if school_id:
        invalidate_school_template_caches(school_id)


def invalidate_communication_template_queryset_caches():
    """Invalidate all template queryset caches"""
    patterns = [
        'communication_templates_queryset_*',
        'template_by_type_*',
        'my_school_templates_*'
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_school_template_caches(school_id):
    """Invalidate template caches for a specific school"""
    if not school_id:
        return
    
    patterns = [
        f'*school_{school_id}*template*',
        f'my_school_templates_*',
        f'template_by_type_*_school_{school_id}'
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)

# ============================================
# AUTOMATED MESSAGE CACHE KEYS
# ============================================

def get_automated_message_queryset_cache_key(user_id, role):
    """Generate cache key for automated message queryset"""
    return f'automated_messages_queryset_{user_id}_{role}'

def get_automated_message_detail_cache_key(message_id):
    """Generate cache key for single message"""
    return f'automated_message_detail_{message_id}'

def get_my_messages_cache_key(student_id, status_filter=None):
    """Generate cache key for student's messages"""
    status_suffix = f'_status_{status_filter}' if status_filter else ''
    return f'my_messages_{student_id}{status_suffix}'

def get_pending_messages_cache_key(user_id):
    """Generate cache key for pending messages"""
    return f'pending_messages_{user_id}'

def get_sent_messages_cache_key(user_id, days=7):
    """Generate cache key for sent messages"""
    return f'sent_messages_{user_id}_days_{days}'

def get_failed_messages_cache_key(user_id):
    """Generate cache key for failed messages"""
    return f'failed_messages_{user_id}'

def get_message_statistics_cache_key(user_id, school_id=None, days=30):
    """Generate cache key for message statistics"""
    school_suffix = f'_school_{school_id}' if school_id else ''
    return f'message_statistics_{user_id}{school_suffix}_days_{days}'

def get_upcoming_schedule_cache_key(user_id, days=7, student_id=None, template_type=None):
    """Generate cache key for upcoming message schedule"""
    student_suffix = f'_student_{student_id}' if student_id else ''
    type_suffix = f'_type_{template_type}' if template_type else ''
    return f'upcoming_schedule_{user_id}_days_{days}{student_suffix}{type_suffix}'

def get_message_summary_cache_key(user_id, role):
    """Generate cache key for message summary"""
    return f'message_summary_{user_id}_{role}'

# ============================================
# AUTOMATED MESSAGE CACHE INVALIDATION
# ============================================

def invalidate_automated_message_cache(message_id, student_id=None, template_id=None):
    """Invalidate all caches related to an automated message"""
    if not message_id:
        return
    
    # Delete specific message cache
    cache.delete(get_automated_message_detail_cache_key(message_id))
    
    # Delete related patterns
    patterns_to_delete = [
        f'automated_message_{message_id}_*',
        f'*message*{message_id}*',
        'pending_messages_*',
        'sent_messages_*',
        'failed_messages_*',
        'message_statistics_*',
        'upcoming_schedule_*',
        'message_summary_*'
    ]
    
    for pattern in patterns_to_delete:
        delete_pattern_with_fallback(pattern)
    
    # Invalidate student-specific caches if student_id provided
    if student_id:
        invalidate_student_message_caches(student_id)
    
    # Invalidate template-specific caches if template_id provided
    if template_id:
        cache.delete(get_template_usage_stats_cache_key('*'))


def invalidate_automated_message_queryset_caches():
    """Invalidate all message queryset caches"""
    patterns = [
        'automated_messages_queryset_*',
        'my_messages_*',
        'pending_messages_*',
        'sent_messages_*',
        'failed_messages_*',
        'upcoming_schedule_*'
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_student_message_caches(student_id):
    """Invalidate message caches for a specific student"""
    if not student_id:
        return
    
    patterns = [
        f'my_messages_{student_id}*',
        f'*student_{student_id}*message*',
        'message_summary_*'
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_template_message_caches(template_id):
    """Invalidate message caches related to a template"""
    if not template_id:
        return
    
    patterns = [
        f'*template_{template_id}*message*',
        'template_usage_stats_*',
        'message_statistics_*'
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)
# ============================================
# SCHOOL ANALYTICS CACHE KEYS
# ============================================

def get_school_analytics_queryset_cache_key(user_id, role):
    """Generate cache key for school analytics queryset"""
    return f'school_analytics_queryset_{user_id}_{role}'

def get_school_analytics_detail_cache_key(analytics_id):
    """Generate cache key for single analytics record"""
    return f'school_analytics_detail_{analytics_id}'

def get_analytics_dashboard_cache_key(user_id, school_id, date_range):
    """Generate cache key for analytics dashboard"""
    return f'analytics_dashboard_{user_id}_school_{school_id}_range_{date_range}'

def get_analytics_trends_cache_key(school_id, metric, days):
    """Generate cache key for trends analysis"""
    return f'analytics_trends_school_{school_id}_metric_{metric}_days_{days}'

def get_analytics_comparison_cache_key(school_ids_str, start_date, end_date):
    """Generate cache key for school comparison"""
    # Hash the school_ids to keep key reasonable length
    import hashlib
    schools_hash = hashlib.md5(school_ids_str.encode()).hexdigest()[:8]
    return f'analytics_comparison_{schools_hash}_{start_date}_{end_date}'

def get_analytics_alerts_cache_key(school_id, days):
    """Generate cache key for alerts"""
    return f'analytics_alerts_school_{school_id}_days_{days}'

def get_analytics_predictions_cache_key(school_id, horizon):
    """Generate cache key for predictions"""
    return f'analytics_predictions_school_{school_id}_horizon_{horizon}'

def get_analytics_summary_cache_key(user_id, role):
    """Generate cache key for analytics summary"""
    return f'analytics_summary_{user_id}_{role}'

def get_analytics_system_health_cache_key():
    """Generate cache key for system health check"""
    return 'analytics_system_health'

def get_school_daily_analytics_cache_key(school_id, date):
    """Generate cache key for daily analytics"""
    return f'school_analytics_daily_{school_id}_{date}'


# ============================================
# SCHOOL ANALYTICS CACHE INVALIDATION
# ============================================

def invalidate_school_analytics_cache(analytics_id, school_id=None):
    """Invalidate all caches related to a school analytics record"""
    if not analytics_id:
        return
    
    # Delete specific analytics cache
    cache.delete(get_school_analytics_detail_cache_key(analytics_id))
    
    # Delete related patterns
    patterns_to_delete = [
        f'school_analytics_{analytics_id}_*',
        f'*analytics*{analytics_id}*',
        'analytics_dashboard_*',
        'analytics_trends_*',
        'analytics_comparison_*',
        'analytics_alerts_*',
        'analytics_predictions_*',
        'analytics_summary_*',
        'analytics_system_health'
    ]
    
    for pattern in patterns_to_delete:
        delete_pattern_with_fallback(pattern)
    
    # Invalidate school-specific analytics caches
    if school_id:
        invalidate_school_specific_analytics_caches(school_id)


def invalidate_school_analytics_queryset_caches():
    """Invalidate all analytics queryset caches"""
    patterns = [
        'school_analytics_queryset_*',
        'analytics_dashboard_*',
        'analytics_summary_*'
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_school_specific_analytics_caches(school_id):
    """Invalidate analytics caches for a specific school"""
    if not school_id:
        return
    
    patterns = [
        f'*school_{school_id}*analytics*',
        f'analytics_dashboard_*_school_{school_id}_*',
        f'analytics_trends_school_{school_id}_*',
        f'analytics_alerts_school_{school_id}_*',
        f'analytics_predictions_school_{school_id}_*',
        f'school_analytics_daily_{school_id}_*'
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)


def invalidate_all_analytics_caches():
    """Clear all analytics-related caches (use sparingly)"""
    patterns = [
        'school_analytics_*',
        'analytics_*',
        '*_analytics_*'
    ]
    
    for pattern in patterns:
        delete_pattern_with_fallback(pattern)
        
# ============================================
# CACHE PATTERN UTILITIES
# ============================================

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
    from .models import StudentProfile
    
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