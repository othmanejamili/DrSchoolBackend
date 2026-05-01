# admin.py
from django.contrib import admin
from .models import Lesson, Feedback, SubscriptionPlan

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



##############################################################
    
    # admin.py
#
# Register your models here with custom approve/reject actions.
# The actions trigger Celery tasks to send emails asynchronously.
#
# Add this to your app's admin.py (replace or extend existing registrations).

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone
from .models import User, DrivingSchool, SubscriptionPlan, SchoolSubscription
from .tasks import send_approval_email, send_rejection_email


# ── Inline: show school + subscription inside User admin ────────────────────
class DrivingSchoolInline(admin.StackedInline):
    model = DrivingSchool
    fk_name = 'owner'
    extra = 0
    readonly_fields = ['created_at']
    fields = ['name', 'address', 'email', 'phone_number', 'created_at']
    show_change_link = True


# ── User Admin ───────────────────────────────────────────────────────────────
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [DrivingSchoolInline]

    list_display = [
        'username', 'email', 'full_name', 'role',
        'verification_badge', 'is_active', 'created_at',
    ]
    list_filter  = ['role', 'verification_status', 'is_active', 'created_at']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    readonly_fields = ['created_at', 'updated_at', 'last_login', 'date_joined']

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Platform Info', {
            'fields': ('role', 'verification_status', 'phone_number', 'created_at', 'updated_at'),
        }),
    )

    actions = ['approve_school_owners', 'reject_school_owners']

    @admin.display(description='Name')
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or '—'

    @admin.display(description='Status')
    def verification_badge(self, obj):
        colors = {
            'pending':  ('#f59e0b', '⏳ Pending'),
            'approved': ('#10b981', '✅ Approved'),
            'rejected': ('#ef4444', '❌ Rejected'),
        }
        color, label = colors.get(obj.verification_status, ('#9ca3af', '—'))
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>', color, label
        )

    @admin.action(description='✅ Approve selected school owners')
    def approve_school_owners(self, request, queryset):
        approved = 0
        skipped  = 0

        for user in queryset.filter(role='A', verification_status='pending'):
            # Activate account
            user.is_active = True
            user.verification_status = 'approved'
            user.save(update_fields=['is_active', 'verification_status'])

            # Get their school
            school = user.driving_schools.first()
            if not school:
                skipped += 1
                continue

            # Activate subscription
            if hasattr(school, 'subscriptions'):
                sub = school.subscriptions
                sub.status = 'active'
                sub.current_period_start = timezone.now()
                sub.save(update_fields=['status', 'current_period_start'])

            # Fire async email via Celery
            send_approval_email.delay(user.id, school.id)
            approved += 1

        if approved:
            self.message_user(request, f"✅ {approved} school(s) approved. Confirmation emails are being sent.")
        if skipped:
            self.message_user(request, f"⚠️  {skipped} user(s) skipped — no school found.", level='warning')

    @admin.action(description='❌ Reject selected school owners')
    def reject_school_owners(self, request, queryset):
        rejected = 0

        for user in queryset.filter(role='A', verification_status='pending'):
            user.is_active = False
            user.verification_status = 'rejected'
            user.save(update_fields=['is_active', 'verification_status'])

            school = user.driving_schools.first()
            if school and hasattr(school, 'subscriptions'):
                school.subscriptions.status = 'canceled'
                school.subscriptions.save(update_fields=['status'])

            # Fire async email via Celery (no reason — admin can add later)
            if school:
                send_rejection_email.delay(user.id, school.id, reason="")
            rejected += 1

        self.message_user(request, f"❌ {rejected} school(s) rejected. Notification emails are being sent.")


# ── SchoolSubscription Inline ─────────────────────────────────────────────────
class SchoolSubscriptionInline(admin.StackedInline):
    model = SchoolSubscription
    extra = 0
    readonly_fields = ['created_at', 'stripe_subscription_id']
    fields = ['plan', 'status', 'current_period_start', 'current_period_end', 'created_at']


# ── DrivingSchool Admin ───────────────────────────────────────────────────────
@admin.register(DrivingSchool)
class DrivingSchoolAdmin(admin.ModelAdmin):
    inlines = [SchoolSubscriptionInline]

    list_display = [
        'name', 'owner_link', 'owner_status', 'email',
        'phone_number', 'subscription_status', 'created_at',
    ]
    list_filter  = ['created_at', 'subscriptions__status', 'owner__verification_status']
    search_fields = ['name', 'email', 'owner__username', 'owner__email']
    readonly_fields = ['created_at', 'owner']
    ordering = ['-created_at']

    @admin.display(description='Owner')
    def owner_link(self, obj):
        return format_html(
            '<a href="/admin/DriveApp/user/{}/change/">{}</a>',
            obj.owner.id,
            obj.owner.username,
        )

    @admin.display(description='Owner Status')
    def owner_status(self, obj):
        colors = {
            'pending':  ('#f59e0b', '⏳ Pending'),
            'approved': ('#10b981', '✅ Approved'),
            'rejected': ('#ef4444', '❌ Rejected'),
        }
        color, label = colors.get(obj.owner.verification_status, ('#9ca3af', '—'))
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, label)

    @admin.display(description='Subscription')
    def subscription_status(self, obj):
        if not hasattr(obj, 'subscriptions'):
            return format_html('<span style="color:#9ca3af;">—</span>')
        colors = {
            'active':   '#10b981',
            'trialing': '#f59e0b',
            'canceled': '#ef4444',
            'past_due': '#f97316',
        }
        s = obj.subscriptions.status
        color = colors.get(s, '#9ca3af')
        return format_html(
            '<span style="color:{};font-weight:600;">{} · {}</span>',
            color, s.capitalize(), obj.subscriptions.plan.name,
        )


# ── SubscriptionPlan Admin ───────────────────────────────────────────────────
@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'duration_days', 'max_students', 'max_instructors', 'is_active']
    list_editable = ['is_active']
    ordering = ['price']


# ── SchoolSubscription Admin ─────────────────────────────────────────────────
@admin.register(SchoolSubscription)
class SchoolSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['school', 'plan', 'status', 'current_period_start', 'current_period_end']
    list_filter  = ['status', 'plan']
    search_fields = ['school__name', 'school__owner__email']
    readonly_fields = ['created_at']