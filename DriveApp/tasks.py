# tasks.py

"""
Celery tasks for asynchronous and scheduled operations.
Handles analytics generation, automated messaging, and maintenance tasks.
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta, datetime
import logging
from django.core.mail import send_mail
from django.conf import settings
from .models import (DrivingSchool, SchoolAnalytics, AutomatedMessage,
                      StudentProfile, CommunicationTemplate,Lesson)
from .services import (
    AnalyticsService, 
    StudentProgressService, 
    AchievementService,
    CommunicationService,
    FeedbackService,
    VehicleService,
    ReportService
)
logger = logging.getLogger(__name__)


# tasks.py  (add this alongside your existing tasks)


@shared_task(name='send_reset_code_email', bind=True, max_retries=3)
def send_reset_code_email(self, recipient_email: str, code: str, user_name: str = ''):
    try:
        send_mail(
            subject='Your Password Reset Code — Driving School',
            message=f'''
Hello {user_name or 'there'},

Your password reset verification code is:

    {code}

This code expires in 10 minutes. Do not share it with anyone.

If you did not request this, ignore this email.

Best regards,
Driving School Team
            '''.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        logger.info(f"✅ Reset code sent to {recipient_email}")
        return {'success': True}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
    



@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_approval_email(self, user_id, school_id):
    from .models import User, DrivingSchool

    try:
        user   = User.objects.get(id=user_id)
        school = DrivingSchool.objects.select_related('subscriptions__plan').get(id=school_id)

        login_url = f"{settings.FRONTEND_URL1}/login"
        subject   = f"🎉 Your school has been approved — {school.name}"

        plain_message = f"""
Hi {user.first_name},

Great news! Your driving school "{school.name}" has been approved on DriveSchool.

You can now log in and start managing your school:
{login_url}

Your login credentials:
  Email:    {user.email}
  Password: The password you chose during registration

What you can do now:
  - Add instructors to your school
  - Register students
  - Track progress and sessions

If you have any questions, reply to this email.

Welcome aboard,
The DriveSchool Team
        """.strip()

        # ✅ Build rows before the outer f-string
        next_steps_rows = ''.join(
            f"""
            <tr>
              <td style="padding:10px 0;border-bottom:1px solid #f1f5f9;">
                <table cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="font-size:18px;width:36px;">{icon}</td>
                    <td>
                      <div style="font-size:14px;font-weight:600;color:#111827;">{title}</div>
                      <div style="font-size:12px;color:#9ca3af;margin-top:2px;">{desc}</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            """
            for icon, title, desc in [
                ('👨‍🏫', 'Add instructors',   'Invite your team to the platform'),
                ('👨‍🎓', 'Register students', 'Start enrolling students right away'),
                ('📊',   'Track progress',    'Monitor sessions and performance'),
            ]
        )

        html_message = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06);">

          <!-- Header -->
          <tr>
            <td style="background:#1d4ed8;padding:36px 40px;text-align:center;">
              <span style="font-size:24px;font-weight:900;color:#ffffff;letter-spacing:-0.5px;">DriveSchool</span>
            </td>
          </tr>

          <!-- Approved banner -->
          <tr>
            <td style="background:#ecfdf5;border-bottom:1px solid #d1fae5;padding:24px 40px;text-align:center;">
              <div style="font-size:40px;margin-bottom:8px;">🎉</div>
              <h1 style="margin:0;font-size:22px;font-weight:800;color:#065f46;">Your school is approved!</h1>
              <p style="margin:8px 0 0;font-size:14px;color:#6b7280;">{school.name} is now live on DriveSchool</p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:36px 40px;">
              <p style="margin:0 0 20px;font-size:15px;color:#374151;line-height:1.6;">
                Hi <strong>{user.first_name}</strong>,
              </p>
              <p style="margin:0 0 28px;font-size:15px;color:#374151;line-height:1.6;">
                We've reviewed your application and your driving school has been approved.
                You can now log in and start managing your school right away.
              </p>

              <!-- Login details -->
              <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:20px 24px;margin-bottom:28px;">
                <p style="margin:0 0 12px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#9ca3af;">Your login details</p>
                <table width="100%" cellpadding="4" cellspacing="0">
                  <tr>
                    <td style="font-size:13px;color:#6b7280;width:80px;">Email</td>
                    <td style="font-size:13px;font-weight:600;color:#111827;">{user.email}</td>
                  </tr>
                  <tr>
                    <td style="font-size:13px;color:#6b7280;">Password</td>
                    <td style="font-size:13px;color:#6b7280;font-style:italic;">The password you chose at registration</td>
                  </tr>
                </table>
              </div>

              <!-- What's next -->
              <p style="margin:0 0 16px;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#9ca3af;">What you can do now</p>
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
                {next_steps_rows}
              </table>

              <!-- CTA -->
              <div style="text-align:center;">
                <a href="{login_url}"
                   style="display:inline-block;background:#1d4ed8;color:#ffffff;font-size:15px;font-weight:700;
                          text-decoration:none;padding:14px 36px;border-radius:10px;letter-spacing:0.01em;">
                  Log in to my school →
                </a>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8fafc;border-top:1px solid #f1f5f9;padding:24px 40px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#9ca3af;">
                Questions? Reply to this email or contact our support team.<br>
                © 2025 DriveSchool. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
        """.strip()

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Approval email sent to {user.email} for school '{school.name}'")
        return f"Approval email sent to {user.email}"

    except Exception as exc:
        logger.error(f"Failed to send approval email (user={user_id}): {exc}")
        raise self.retry(exc=exc)
 
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_rejection_email(self, user_id, school_id, reason=""):
    """
    Send rejection email to school owner with optional reason.
    Retries up to 3 times with 60s delay if it fails.
    """
    from .models import User, DrivingSchool
 
    try:
        user   = User.objects.get(id=user_id)
        school = DrivingSchool.objects.get(id=school_id)
 
        subject = f"Update on your DriveSchool application — {school.name}"
 
        plain_message = f"""
Hi {user.first_name},
 
Thank you for applying to DriveSchool.
 
After reviewing your application for "{school.name}", we're unable to approve it at this time.
 
{"Reason: " + reason if reason else ""}
 
If you believe this is a mistake or would like to reapply, please contact our support team
by replying to this email.
 
Best regards,
The DriveSchool Team
        """.strip()
 
        reason_block = f"""
        <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:16px 20px;margin-bottom:24px;">
          <p style="margin:0 0 6px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#ef4444;">Reason</p>
          <p style="margin:0;font-size:14px;color:#374151;">{reason}</p>
        </div>
        """ if reason else ""
 
        html_message = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06);">
          <tr>
            <td style="background:#1d4ed8;padding:36px 40px;text-align:center;">
              <span style="font-size:24px;font-weight:900;color:#ffffff;">DriveSchool</span>
            </td>
          </tr>
          <tr>
            <td style="background:#fef9f9;border-bottom:1px solid #fecaca;padding:24px 40px;text-align:center;">
              <div style="font-size:36px;margin-bottom:8px;">📋</div>
              <h1 style="margin:0;font-size:20px;font-weight:800;color:#991b1b;">Application Update</h1>
              <p style="margin:8px 0 0;font-size:14px;color:#6b7280;">{school.name}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:36px 40px;">
              <p style="margin:0 0 20px;font-size:15px;color:#374151;line-height:1.6;">
                Hi <strong>{user.first_name}</strong>,
              </p>
              <p style="margin:0 0 24px;font-size:15px;color:#374151;line-height:1.6;">
                Thank you for your interest in DriveSchool. After reviewing your application
                for <strong>{school.name}</strong>, we're unable to approve it at this time.
              </p>
              {reason_block}
              <p style="margin:0 0 28px;font-size:15px;color:#374151;line-height:1.6;">
                If you believe this is a mistake or would like more information,
                please reply to this email and our team will get back to you.
              </p>
              <div style="text-align:center;">
                <a href="mailto:{settings.DEFAULT_FROM_EMAIL}"
                   style="display:inline-block;background:#374151;color:#ffffff;font-size:14px;font-weight:700;
                          text-decoration:none;padding:12px 28px;border-radius:10px;">
                  Contact Support
                </a>
              </div>
            </td>
          </tr>
          <tr>
            <td style="background:#f8fafc;border-top:1px solid #f1f5f9;padding:20px 40px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#9ca3af;">© 2025 DriveSchool. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
        """.strip()
 
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
 
        logger.info(f"Rejection email sent to {user.email} for school '{school.name}'")
        return f"Rejection email sent to {user.email}"
 
    except Exception as exc:
        logger.error(f"Failed to send rejection email (user={user_id}): {exc}")
        raise self.retry(exc=exc)
 




# ========== ANALYTICS TASKS ==========

@shared_task(name='generate_daily_analytics')
def generate_daily_analytics_for_all_schools():
    """
    Generate daily analytics for all active schools.
    Run daily at midnight.
    """
    logger.info("Starting daily analytics generation for all schools")
    
    schools = DrivingSchool.objects.all()
    success_count = 0
    error_count = 0
    
    for school in schools:
        try:
            AnalyticsService.generate_daily_analytics(school)
            success_count += 1
            logger.info(f"Analytics generated for school: {school.name}")
        except Exception as e:
            error_count += 1
            logger.error(f"Failed to generate analytics for {school.name}: {str(e)}")
    
    logger.info(f"Analytics generation completed. Success: {success_count}, Errors: {error_count}")
    
    return {
        'success': success_count,
        'errors': error_count,
        'total': schools.count()
    }


@shared_task(name='generate_school_analytics')
def generate_school_analytics(school_id, date=None):
    """
    Generate analytics for a specific school.
    Can be called manually or scheduled.
    """
    
    try:
        school = DrivingSchool.objects.get(id=school_id)
        if date:
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        analytics = AnalyticsService.generate_daily_analytics(school, date)
        
        logger.info(f"Analytics generated for {school.name} on {analytics.date}")
        
        return {
            'success': True,
            'school': school.name,
            'date': str(analytics.date),
            'metrics': {
                'total_students': analytics.total_students,
                'active_students': analytics.active_students,
                'completion_rate': analytics.completion_rate,
                'average_rating': analytics.average_rating
            }
        }
    except DrivingSchool.DoesNotExist:
        logger.error(f"School with id {school_id} not found")
        return {'success': False, 'error': 'School not found'}
    except Exception as e:
        logger.error(f"Error generating analytics: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='generate_weekly_report')
def generate_weekly_report_for_schools():
    """
    Generate weekly performance reports for all schools.
    Run every Monday at 8 AM.
    """
    logger.info("Starting weekly report generation")
    
    schools = DrivingSchool.objects.all()
    reports_sent = 0
    
    for school in schools:
        try:
            # Generate 7-day summary
            summary = AnalyticsService.get_school_summary(school, days=7)
            
            # Send report email
            ReportService.send_weekly_report(school, summary)
            reports_sent += 1
            
            logger.info(f"Weekly report sent to {school.name}")
        except Exception as e:
            logger.error(f"Failed to send report to {school.name}: {str(e)}")
    
    return {
        'reports_sent': reports_sent,
        'total_schools': schools.count()
    }


@shared_task(name='cleanup_old_analytics')
def cleanup_old_analytics():
    """
    Remove analytics records older than 2 years.
    Run monthly.
    """

    cutoff_date = timezone.now().date() - timedelta(days=730)
    
    deleted_count, _ = SchoolAnalytics.objects.filter(
        date__lt=cutoff_date
    ).delete()
    
    logger.info(f"Cleaned up {deleted_count} old analytics records")
    
    return {
        'deleted': deleted_count,
        'cutoff_date': str(cutoff_date)
    }


# ========== COMMUNICATION TASKS ==========

@shared_task(name='send_scheduled_messages')
def send_scheduled_messages():
    """Send all pending automated messages that are due."""
    from .models import AutomatedMessage
    
    logger.info("Processing scheduled messages")
    
    pending_messages = AutomatedMessage.objects.filter(
        status='pending',
        scheduled_for__lte=timezone.now()
    )
    
    sent_count = 0
    failed_count = 0
    
    for message in pending_messages:
        try:
            # ✅ FIXED: Use correct method name
            CommunicationService._send_single_message(message)
            message.status = 'sent'
            message.sent_at = timezone.now()
            message.save()
            sent_count += 1
            
            logger.info(f"Message sent to {message.student.user.email}")
        except Exception as e:
            message.status = 'failed'
            message.delivery_error = str(e)
            message.save()
            failed_count += 1
            
            logger.error(f"Failed to send message to {message.student.user.email}: {str(e)}")
    
    return {
        'sent': sent_count,
        'failed': failed_count,
        'total': pending_messages.count()
    }


@shared_task(name='send_lesson_reminders')
def send_lesson_reminders():
    """
    Send reminders for lessons scheduled in the next 24 hours.
    Run every hour.
    """
    
    logger.info("Sending lesson reminders")
    
    tomorrow = timezone.now() + timedelta(hours=24)
    
    upcoming_lessons = Lesson.objects.filter(
        date__gte=timezone.now(),
        date__lte=tomorrow,
        status='S'  # Scheduled
    ).select_related('instructor', 'school')
    
    reminders_sent = 0
    
    for lesson in upcoming_lessons:
        # Get students enrolled in this lesson
        students = lesson.lesson_attendance.values_list('student', flat=True)
        
        for student_id in students:
            try:
                # Check if reminder already sent
                if AutomatedMessage.objects.filter(
                    student_id=student_id,
                    template__template_type='lesson_reminder',
                    created_at__date=timezone.now().date()
                ).exists():
                    continue
                
                # Get or create reminder template
                template, _ = CommunicationTemplate.objects.get_or_create(
                    school=lesson.school,
                    template_type='lesson_reminder',
                    defaults={
                        'name': 'Lesson Reminder',
                        'subject': 'Reminder: Upcoming Lesson',
                        'body': 'Hi {student_name}, reminder that you have a {lesson_type} lesson tomorrow at {lesson_time}.',
                        'is_active': True
                    }
                )
                
                # Create and send message
                message = AutomatedMessage.objects.create(
                    student_id=student_id,
                    template=template,
                    scheduled_for=timezone.now()
                )
                
                CommunicationService._send_message(message)
                message.status = 'sent'
                message.sent_at = timezone.now()
                message.save()
                
                reminders_sent += 1
                
            except Exception as e:
                logger.error(f"Failed to send lesson reminder: {str(e)}")
    
    return {
        'lessons': upcoming_lessons.count(),
        'reminders_sent': reminders_sent
    }


@shared_task(name='send_progress_updates')
def send_weekly_progress_updates():
    """
    Send weekly progress updates to all active students.
    Run every Sunday at 6 PM.
    """
    
    logger.info("Sending weekly progress updates")
    
    active_students = StudentProfile.objects.filter(
        status='A'
    ).select_related('user', 'school')
    
    updates_sent = 0
    
    for student in active_students:
        try:
            # Get or create progress update template
            template, _ = CommunicationTemplate.objects.get_or_create(
                school=student.school,
                template_type='progress_update',
                defaults={
                    'name': 'Weekly Progress Update',
                    'subject': 'Your Weekly Progress Report',
                    'body': '''Hi {student_name},
                    
                    Here's your progress this week:
                    -✅ Theory Progress: {progress_theory}%
                    -✅ Driving Progress: {progress_driving}%
                    -✅ Total Theory Hours: {total_hours_theory}
                    -✅ Total Driving Hours: {total_hours_driving}

                    Keep up the great work you'll be better✅!''',
                    'is_active': True
                }
            )
            
            # Create and send message
            message = AutomatedMessage.objects.create(
                student=student,
                template=template,
                scheduled_for=timezone.now()
            )
            
            CommunicationService._send_single_message(message)
            message.status = 'sent'
            message.sent_at = timezone.now()
            message.save()
            
            updates_sent += 1
            
        except Exception as e:
            logger.error(f"Failed to send progress update to {student.user.email}: {str(e)}")
    
    return {
        'total_students': active_students.count(),
        'updates_sent': updates_sent
    }


# ========== STUDENT PERFORMANCE TASKS ==========

@shared_task(name='update_performance_predictions')
def update_performance_predictions():
    """
    Update performance predictions for all active students.
    Run daily at 2 AM.
    """
    
    logger.info("Updating performance predictions")
    
    active_students = StudentProfile.objects.filter(status='A')
    updated_count = 0
    
    for student in active_students:
        try:
            StudentProgressService.calculate_completion_estimate(student)
            updated_count += 1
        except Exception as e:
            logger.error(f"Failed to update prediction for student {student.user.username}: {str(e)}")
    
    return {
        'total_students': active_students.count(),
        'updated': updated_count
    }


@shared_task(name='check_student_achievements')
def check_student_achievements():
    """
    Check and award achievements for all active students.
    Run daily at 3 AM.
    """
    
    logger.info("Checking student achievements")
    
    active_students = StudentProfile.objects.filter(status='A')
    achievements_awarded = 0
    
    for student in active_students:
        try:
            before_count = student.achievements.count()
            AchievementService.check_and_award(student)
            after_count = student.achievements.count()
            
            new_achievements = after_count - before_count
            if new_achievements > 0:
                achievements_awarded += new_achievements
                logger.info(f"Awarded {new_achievements} achievement(s) to {student.user.username}")
                
        except Exception as e:
            logger.error(f"Failed to check achievements for {student.user.username}: {str(e)}")
    
    return {
        'students_checked': active_students.count(),
        'achievements_awarded': achievements_awarded
    }


@shared_task(name='identify_at_risk_students')
def identify_at_risk_students():
    """
    Identify students at risk of not completing and notify instructors.
    Run daily at 9 AM.
    """
    from .models import StudentProfile, StudentPerformancePrediction
    from .services import CommunicationService
    
    logger.info("Identifying at-risk students")
    
    at_risk_predictions = StudentPerformancePrediction.objects.filter(
        success_probability__lt=60,
        student__status='A'
    ).select_related('student__user', 'student__school')
    
    notifications_sent = 0
    
    for prediction in at_risk_predictions:
        try:
            # Notify school owner
            CommunicationService.notify_at_risk_student(
                prediction.student,
                prediction.risk_factors,
                prediction.recommendations
            )
            notifications_sent += 1
            
        except Exception as e:
            logger.error(f"Failed to send at-risk notification: {str(e)}")
    
    return {
        'at_risk_students': at_risk_predictions.count(),
        'notifications_sent': notifications_sent
    }


# ========== MAINTENANCE TASKS ==========

@shared_task(name='check_vehicle_maintenance')
def check_vehicle_maintenance():
    """
    Check for vehicles needing maintenance and send alerts.
    Run daily at 7 AM.
    """
    from .models import Vehicle
    from .services import CommunicationService
    
    logger.info("Checking vehicle maintenance schedules")
    
    today = timezone.now().date()
    upcoming_maintenance = today + timedelta(days=7)
    
    # Vehicles due for maintenance in next 7 days
    due_soon = Vehicle.objects.filter(
        next_maintenance__lte=upcoming_maintenance,
        next_maintenance__gte=today,
        status='available'
    ).select_related('school__owner')
    
    # Overdue maintenance
    overdue = Vehicle.objects.filter(
        next_maintenance__lt=today,
        status='available'
    ).select_related('school__owner')
    
    alerts_sent = 0
    
    # Send alerts for overdue vehicles
    for vehicle in overdue:
        try:
            CommunicationService.send_maintenance_alert(
                vehicle,
                urgency='high',
                message=f"URGENT: {vehicle.make} {vehicle.model} ({vehicle.plate_number}) is overdue for maintenance"
            )
            
            # Update vehicle status
            vehicle.status = 'maintenance'
            vehicle.save()
            
            alerts_sent += 1
            
        except Exception as e:
            logger.error(f"Failed to send overdue alert for vehicle {vehicle.plate_number}: {str(e)}")
    
    # Send reminders for upcoming maintenance
    for vehicle in due_soon:
        try:
            CommunicationService.send_maintenance_alert(
                vehicle,
                urgency='medium',
                message=f"Reminder: {vehicle.make} {vehicle.model} ({vehicle.plate_number}) needs maintenance soon"
            )
            alerts_sent += 1
            
        except Exception as e:
            logger.error(f"Failed to send reminder for vehicle {vehicle.plate_number}: {str(e)}")
    
    return {
        'overdue': overdue.count(),
        'due_soon': due_soon.count(),
        'alerts_sent': alerts_sent
    }


@shared_task(name='cleanup_expired_sessions')
def cleanup_expired_sessions():
    """
    Clean up expired user sessions.
    Run daily at 4 AM.
    """
    from django.contrib.sessions.models import Session
    
    logger.info("Cleaning up expired sessions")
    
    expired_count = Session.objects.filter(
        expire_date__lt=timezone.now()
    ).delete()[0]
    
    logger.info(f"Deleted {expired_count} expired sessions")
    
    return {'deleted': expired_count}


@shared_task(name='backup_daily_data')
def backup_daily_data():
    """
    Trigger daily database backup.
    Run daily at 1 AM.
    """
    from django.core.management import call_command
    import os
    
    logger.info("Starting daily backup")
    
    try:
        backup_dir = os.path.join('backups', timezone.now().strftime('%Y-%m-%d'))
        os.makedirs(backup_dir, exist_ok=True)
        
        # This assumes you have a backup management command
        call_command('dbbackup', output_path=backup_dir)
        
        logger.info(f"Backup completed successfully in {backup_dir}")
        
        return {
            'success': True,
            'backup_path': backup_dir,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


# ========== SUBSCRIPTION TASKS ==========

@shared_task(name='check_subscription_expiry')
def check_subscription_expiry():
    """
    Check for expiring subscriptions and send warnings.
    Run daily at 10 AM.
    """
    from .models import SchoolSubscription
    from .services import CommunicationService
    
    logger.info("Checking subscription expiry dates")
    
    today = timezone.now()
    warning_date = today + timedelta(days=7)
    
    # Subscriptions expiring in 7 days
    expiring_soon = SchoolSubscription.objects.filter(
        current_period_end__lte=warning_date,
        current_period_end__gte=today,
        status='active'
    ).select_related('school__owner', 'plan')
    
    warnings_sent = 0
    
    for subscription in expiring_soon:
        try:
            days_remaining = (subscription.current_period_end - today).days
            
            CommunicationService.send_subscription_warning(
                subscription.school.owner,
                subscription,
                days_remaining
            )
            
            warnings_sent += 1
            
        except Exception as e:
            logger.error(f"Failed to send expiry warning for {subscription.school.name}: {str(e)}")
    
    return {
        'expiring_soon': expiring_soon.count(),
        'warnings_sent': warnings_sent
    }


@shared_task(name='deactivate_expired_subscriptions')
def deactivate_expired_subscriptions():
    """
    Deactivate subscriptions that have expired.
    Run daily at 11 AM.
    """
    from .models import SchoolSubscription
    
    logger.info("Deactivating expired subscriptions")
    
    expired = SchoolSubscription.objects.filter(
        current_period_end__lt=timezone.now(),
        status__in=['active', 'trialing']
    )
    
    deactivated_count = 0
    
    for subscription in expired:
        try:
            subscription.status = 'canceled'
            subscription.save()
            deactivated_count += 1
            
            logger.info(f"Deactivated subscription for {subscription.school.name}")
            
        except Exception as e:
            logger.error(f"Failed to deactivate subscription: {str(e)}")
    
    return {
        'expired': expired.count(),
        'deactivated': deactivated_count
    }


# ========== MONITORING TASKS ==========

@shared_task(name='system_health_check')
def system_health_check():
    """
    Perform system health checks and report issues.
    Run every 30 minutes.
    """
    from django.db import connection
    from django.core.cache import cache
    
    logger.info("Performing system health check")
    
    health_status = {
        'timestamp': timezone.now().isoformat(),
        'database': False,
        'cache': False,
        'celery': True,  # If this runs, Celery is working
        'errors': []
    }
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['database'] = True
    except Exception as e:
        health_status['errors'].append(f"Database error: {str(e)}")
    
    # Check cache
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            health_status['cache'] = True
        else:
            health_status['errors'].append("Cache read/write failed")
    except Exception as e:
        health_status['errors'].append(f"Cache error: {str(e)}")
    
    if health_status['errors']:
        logger.error(f"Health check found issues: {health_status['errors']}")
    else:
        logger.info("All systems operational")
    
    return health_status


@shared_task(name='generate_usage_statistics')
def generate_usage_statistics():
    """
    Generate platform-wide usage statistics.
    Run daily at 11 PM.
    """
    from .models import (DrivingSchool, StudentProfile, Lesson, 
                         Attendance, User)
    
    logger.info("Generating usage statistics")
    
    stats = {
        'date': timezone.now().date().isoformat(),
        'schools': {
            'total': DrivingSchool.objects.count(),
            'active': DrivingSchool.objects.filter(
                student_profiles__status='A'
            ).distinct().count()
        },
        'users': {
            'total': User.objects.count(),
            'students': User.objects.filter(role='S').count(),
            'instructors': User.objects.filter(role='I').count(),
            'admins': User.objects.filter(role='A').count()
        },
        'students': {
            'total': StudentProfile.objects.count(),
            'active': StudentProfile.objects.filter(status='A').count(),
            'completed': StudentProfile.objects.filter(status='C').count()
        },
        'lessons': {
            'total': Lesson.objects.count(),
            'scheduled': Lesson.objects.filter(status='S').count(),
            'completed': Lesson.objects.filter(status='C').count()
        },
        'attendance': {
            'total': Attendance.objects.count(),
            'present': Attendance.objects.filter(presence=True).count(),
            'absent': Attendance.objects.filter(presence=False).count()
        }
    }
    
    logger.info(f"Usage statistics: {stats}")
    
    return stats


# ========== ERROR HANDLING TASK ==========
@shared_task(name='retry_failed_messages')
def retry_failed_messages(message_id):
    """Retry sending a failed message."""
    from .models import AutomatedMessage
    
    try:
        message = AutomatedMessage.objects.get(id=message_id, status='failed')
        
        # ✅ FIXED: Use correct method name
        CommunicationService._send_single_message(message)
        message.status = 'sent'
        message.sent_at = timezone.now()
        message.delivery_error = None
        message.save()
        
        logger.info(f"Successfully retried message {message_id}")
        
        return {'success': True, 'message_id': message_id}
        
    except AutomatedMessage.DoesNotExist:
        logger.error(f"Message {message_id} not found")
        return {'success': False, 'error': 'Message not found'}
        
    except Exception as e:
        logger.error(f"Retry failed for message {message_id}: {str(e)}")
        return {'success': False, 'error': f'{str(e)}'}

# tasks.py - Add this test task at the bottom

