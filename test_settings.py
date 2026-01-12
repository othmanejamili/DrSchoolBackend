#!/usr/bin/env python
"""Test settings configuration"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')

import django
django.setup()

from django.conf import settings

print("🔍 Testing Django Settings")
print("="*60)

# Test key configurations
tests = [
    ("DEBUG", settings.DEBUG, bool),
    ("TESTING", settings.TESTING, bool),
    ("ALLOWED_HOSTS", settings.ALLOWED_HOSTS, list),
    ("DATABASES['default']['ENGINE']", settings.DATABASES['default']['ENGINE'], str),
    ("CACHES['default']['BACKEND']", settings.CACHES['default']['BACKEND'], str),
    ("REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['user']", 
     settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].get('user'), str),
    ("AUTH_USER_MODEL", settings.AUTH_USER_MODEL, str),
    ("DEBUG_TOOLBAR_CONFIG['IS_RUNNING_TESTS']", 
     settings.DEBUG_TOOLBAR_CONFIG.get('IS_RUNNING_TESTS'), bool),
]

all_passed = True
for name, value, expected_type in tests:
    try:
        if isinstance(value, expected_type):
            print(f"✅ {name}: {value}")
        else:
            print(f"❌ {name}: {type(value)} (expected {expected_type})")
            all_passed = False
    except AttributeError:
        print(f"⚠️  {name}: Not found")
        all_passed = False

print("\n" + "="*60)
if all_passed:
    print("✅ All settings tests passed!")
else:
    print("❌ Some settings tests failed")