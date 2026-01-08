# DriveApp/tests/test_redis.py
import os
import django
import redis
from django.test import TestCase
from django.core.cache import cache
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')
django.setup()


class RedisCacheTestCase(TestCase):
    """Test Redis cache functionality"""
    
    def setUp(self):
        """Setup before each test"""
        # Clear cache before each test
        cache.clear()
    
    def test_redis_connection(self):
        """Test that Redis is connected and working"""
        # Test basic cache operations
        cache.set('test_key', 'test_value', timeout=10)
        value = cache.get('test_key')
        self.assertEqual(value, 'test_value')
        print("✅ Basic cache set/get works")
        
        # Test Redis connection directly
        try:
            r = redis.Redis.from_url(settings.CACHES['default']['LOCATION'])
            self.assertTrue(r.ping())
            print("✅ Redis ping successful")
            
            # Test Redis operations
            r.set('redis_test', 'redis_value')
            self.assertEqual(r.get('redis_test'), b'redis_value')
            print("✅ Redis direct operations work")
            
        except Exception as e:
            self.fail(f"Redis connection failed: {e}")
    
    def test_cache_expiration(self):
        """Test cache expiration"""
        import time
        cache.set('expire_key', 'expire_value', timeout=1)
        time.sleep(2)
        self.assertIsNone(cache.get('expire_key'))
        print("✅ Cache expiration works")
    
    def test_cache_delete(self):
        """Test cache deletion"""
        cache.set('delete_key', 'delete_value')
        cache.delete('delete_key')
        self.assertIsNone(cache.get('delete_key'))
        print("✅ Cache delete works")
    
    def test_cache_keys(self):
        """Test cache key patterns"""
        from DriveApp.cache_utils import get_user_queryset_cache_key
        
        key = get_user_queryset_cache_key(123, 'A')
        expected = 'user_queryset_123_A'
        self.assertEqual(key, expected)
        print(f"✅ Cache key generation works: {key}")
    
    def test_cache_invalidation(self):
        """Test cache invalidation"""
        from DriveApp.cache_utils import (
            get_user_stats_cache_key, 
            get_user_queryset_cache_key,
            invalidate_user_caches
        )
        
        # Set up test data in cache
        cache.set(get_user_stats_cache_key(), {'test': 'data'})
        cache.set(get_user_queryset_cache_key(1, 'A'), [1, 2, 3])
        cache.set(get_user_queryset_cache_key(1, 'I'), [4, 5, 6])
        
        # Verify data is cached
        self.assertIsNotNone(cache.get(get_user_stats_cache_key()))
        self.assertIsNotNone(cache.get(get_user_queryset_cache_key(1, 'A')))
        self.assertIsNotNone(cache.get(get_user_queryset_cache_key(1, 'I')))
        
        # Invalidate
        invalidate_user_caches(1)
        
        # Verify invalidation
        self.assertIsNone(cache.get(get_user_stats_cache_key()))
        self.assertIsNone(cache.get(get_user_queryset_cache_key(1, 'A')))
        self.assertIsNone(cache.get(get_user_queryset_cache_key(1, 'I')))
        print("✅ Cache invalidation works")


if __name__ == '__main__':
    import unittest
    unittest.main()