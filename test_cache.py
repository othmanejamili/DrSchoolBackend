import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')
django.setup()

from django.core.cache import cache
from django.test import TestCase
from DriveApp.cache_utils import (
    get_user_queryset_cache_key, 
    get_user_stats_cache_key,
    invalidate_user_caches
)

class CacheTest:
    """Test cache functionality"""
    
    def test_basic_cache(self):
        """Test basic cache operations"""
        # Set value
        cache.set('test_key', 'test_value', 60)
        
        # Get value
        value = cache.get('test_key')
        assert value == 'test_value', f"Expected 'test_value', got {value}"
        print("✅ Basic cache set/get works")
        
        # Test expiration
        import time
        cache.set('expire_key', 'expire_value', 1)
        time.sleep(2)
        expired_value = cache.get('expire_key')
        assert expired_value is None, "Cache expiration failed"
        print("✅ Cache expiration works")
        
        # Test delete
        cache.set('delete_key', 'delete_value')
        cache.delete('delete_key')
        assert cache.get('delete_key') is None, "Cache delete failed"
        print("✅ Cache delete works")
        
        # Test cache key generation
        key = get_user_queryset_cache_key(123, 'A')
        assert key == 'user_queryset_123_A', f"Unexpected key: {key}"
        print("✅ Cache key generation works")
    
    def test_invalidation(self):
        """Test cache invalidation"""
        # Set up test data
        cache.set(get_user_stats_cache_key(), {'test': 'data'})
        cache.set(get_user_queryset_cache_key(1, 'A'), [1, 2, 3])
        cache.set(get_user_queryset_cache_key(1, 'I'), [4, 5, 6])
        
        # Invalidate
        invalidate_user_caches(1)
        
        # Verify invalidation
        assert cache.get(get_user_stats_cache_key()) is None, "Stats cache not invalidated"
        assert cache.get(get_user_queryset_cache_key(1, 'A')) is None, "User cache A not invalidated"
        assert cache.get(get_user_queryset_cache_key(1, 'I')) is None, "User cache I not invalidated"
        print("✅ Cache invalidation works")

if __name__ == "__main__":
    test = CacheTest()
    test.test_basic_cache()
    test.test_invalidation()
    print("\n🎉 All cache tests passed!")