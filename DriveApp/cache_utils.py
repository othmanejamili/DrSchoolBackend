"""
Cache utility functions and helpers.
"""

from django.core.cache import cache
import hashlib
import json


def get_user_queryset_cache_key(user_id, role):
    """Generate cache key for user queryset"""
    return f'user_queryset_{user_id}_{role}'


def get_user_stats_cache_key():
    """Generate cache key for user stats"""
    return 'user_stats_v1'


def get_school_users_cache_key(user_id, role_filter):
    """Generate cache key for school users list"""
    return f'school_users_{user_id}_{role_filter or "all"}'


def get_school_student_count_cache_key(school_id):
    """Generate cache key for school student count"""
    return f'school_{school_id}_student_count'


def generate_cache_key_from_request(request, prefix):
    """Generate a unique cache key from request parameters"""
    query_params = dict(request.query_params)
    user_id = request.user.id if request.user.is_authenticated else 'anonymous'
    
    # Sort query params for consistent keys
    sorted_params = json.dumps(query_params, sort_keys=True)
    key_data = f"{prefix}_{user_id}_{sorted_params}"
    
    return hashlib.md5(key_data.encode()).hexdigest()


def invalidate_user_caches(user_id=None):
    """Invalidate all user-related caches"""
    cache.delete(get_user_stats_cache_key())
    
    if user_id:
        # Delete specific user caches
        for role in ['A', 'I', 'S']:
            cache.delete(get_user_queryset_cache_key(user_id, role))


def invalidate_school_caches(school_id):
    """Invalidate school-related caches"""
    cache.delete(get_school_student_count_cache_key(school_id))
    cache.delete_pattern(f'school_users_*_{school_id}_*')