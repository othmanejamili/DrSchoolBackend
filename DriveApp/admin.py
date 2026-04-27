# admin.py
from django.contrib import admin
from .models import Lesson, Feedback

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'school', 'lesson_type', 'date', 'status']
    list_filter = ['lesson_type', 'status', 'school']
    search_fields = ['title', 'instructor__username', 'school__name']
    date_hierarchy = 'date'

# admin.py


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['student', 'lesson', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['student__user__username', 'lesson__title', 'comment']
    readonly_fields = ['created_at']
    
    def save_model(self, request, obj, form, change):
        # Add any custom logic before saving
        super().save_model(request, obj, form, change)