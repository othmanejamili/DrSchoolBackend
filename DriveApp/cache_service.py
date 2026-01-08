from django.core.cache import cache

class CacheService:
    """Service for managing cache invalidation"""
    
    @staticmethod
    def invalidate_user_cache(user_id):
        """Invalidate all cache entries for a user"""
        patterns = [
            f'user_queryset_{user_id}_*',
            f'user_detail_{user_id}',
            f'school_users_*',
        ]
        for pattern in patterns:
            cache.delete_pattern(pattern)
    
    @staticmethod
    def invalidate_school_cache(school_id):
        """Invalidate all cache entries for a school"""
        cache.delete_pattern(f'school_{school_id}_*')
        cache.delete('user_stats')
    
    @staticmethod
    def invalidate_stats_cache():
        """Invalidate statistics cache"""
        cache.delete('user_stats')
        cache.delete('school_stats')
