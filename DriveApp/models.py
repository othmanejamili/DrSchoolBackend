from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
import cloudinary
from django.db import models
from cloudinary.models import CloudinaryField

#This Model For Table User
class User(AbstractUser):
    ROLE_CHOICES = [
        ('A','Admin'),
        ('S','Student'),
        ('I','Instructor')
    ]
    VERIFICATION_STATUS = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )
    role = models.CharField(max_length=1, choices=ROLE_CHOICES, blank=True, null=True)
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='pending'
    )
    phone_number = models.CharField(max_length=16, blank=True, null=True, validators=[phone_validator])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        related_name='custom_user_set',
        related_query_name='custom_user'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        related_name='custom_user_set',
        related_query_name='custom_user'
    )

    def __str__(self):
        return self.username
    
#This Model For Table Driving School  
class DrivingSchool(models.Model):
    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='driving_schools')
    name = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    address = models.CharField(max_length=255, blank=True, null=True,db_index=True)
    email = models.EmailField(unique=True ,db_index=True)
    phone_number = models.CharField(max_length=16, blank=True, null=True, validators=[phone_validator])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Driving School"
        verbose_name_plural = "Driving Schools"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'name'],
                name='unique_school_per_owner'
            )
        ]

    def __str__(self):
        return self.name or f"DrivingSchool {self.id}"
    
#This Model For Table Student Profile
class StudentProfile(models.Model):
    LICENSE_TYPES = [
        ('C','Car'),
        ('M','Moto')
    ]
    STATUS_CHOICES = [
        ('A', 'Active'),
        ('C', 'Completed'),
        ('P', 'Paused'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_profiles')
    school = models.ForeignKey(DrivingSchool, on_delete=models.CASCADE, related_name='student_profiles')
    picture_profile = models.ImageField(upload_to='student_profiles/', blank=True, null=True)
    license_type = models.CharField(max_length=1, choices=LICENSE_TYPES, blank=True, null=True, db_index=True)
    progress_theory = models.DecimalField(max_digits=5, default=0, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    progress_driving = models.DecimalField(max_digits=5,default=0 , decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    total_hours_theory = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1000)])
    total_hours_driving = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1000)])
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='A', db_index=True)
    theory_start_date = models.DateField(blank=True, null=True)
    driving_start_date = models.DateField(blank=True, null=True)
    completion_date = models.DateField(blank=True, null=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['school', 'status']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.school.name}"
    

#This Model For Table Lesson
class Lesson(models.Model):
    LESSON_TYPES = [
        ('T','Theory'),
        ('D','Driving')
    ]
    STATUS_CHOICES = [
        ('S', 'Scheduled'),
        ('C', 'Completed'),
        ('P', 'Paused'),
        ('X', 'Cancelled'),
    ]
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='student_lessons')
    school = models.ForeignKey(DrivingSchool, on_delete=models.CASCADE, related_name='school_lessons')
    title = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    lesson_type = models.CharField(max_length=1, choices=LESSON_TYPES, blank=True, null=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    duration = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(480)])
    date = models.DateTimeField()
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='S', db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['school', 'lesson_type']),
        ]

    def __str__(self):
        return f"{self.instructor.username} - {self.school.name}"

#This Model For Table Attendance
class Attendance(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, 
                           related_name='student_attendance', db_index=True)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, 
                          related_name='lesson_attendance', db_index=True)
    presence = models.BooleanField(default=False)
    hours_completed = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(480)]  # Add lower bound
    ) 
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['student', 'created_at']),
            models.Index(fields=['lesson', 'presence']),
        ]

    def __str__(self):
        return f"{self.student.user.username} - {self.lesson.title}"
    
#This Model For Table Feedback
class Feedback(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='student_feedback')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='lesson_feedback')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Feedback"
        verbose_name_plural = "Feedback"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'lesson'],
                name='unique_Feedback_studentper_lesson'
            )
        ]

    def __str__(self):
        return f"{self.student.user.username} - {self.lesson.title}"

#This Model For Table Vehicle
class Vehicle(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('maintenance', 'Maintenance'),
        ('reserved', 'Reserved'),
        ('out_of_service', 'Out of Service')
    ]
    
    TRANSMISSION_CHOICES = [
        ('manual', 'Manual'),
        ('automatic', 'Automatic')
    ]
    
    school = models.ForeignKey(DrivingSchool, on_delete=models.CASCADE, related_name='vehicles')
    plate_number = models.CharField(max_length=20, unique=True)
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=100)
    year = models.IntegerField(validators=[MinValueValidator(1990), MaxValueValidator(2030)])
    color = models.CharField(max_length=30, blank=True, null=True)
    transmission = models.CharField(max_length=20, choices=TRANSMISSION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    last_maintenance = models.DateField(blank=True, null=True)
    next_maintenance = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.make} {self.model} ({self.plate_number})"


class VehiclePicture(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='pictures')
    image = CloudinaryField('vehicle_image')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Optional: Store Cloudinary public_id for advanced operations
    cloudinary_public_id = models.CharField(max_length=255, blank=True, editable=False)

    class Meta:
        ordering = ['-is_primary', '-uploaded_at']
        verbose_name = "Vehicle Picture"
        verbose_name_plural = "Vehicle Pictures"
        indexes = [
            models.Index(fields=['vehicle', 'is_primary']),
            models.Index(fields=['uploaded_at'])
        ]
    
    def save(self, *args, **kwargs):
        """Store Cloudinary public_id after upload"""
        super().save(*args, **kwargs)
        if self.image and hasattr(self.image, 'public_id'):
            if self.cloudinary_public_id != self.image.public_id:
                self.cloudinary_public_id = self.image.public_id
                super().save(update_fields=['cloudinary_public_id'])
    
    def __str__(self):
        return f"Picture for {self.vehicle.plate_number}"
    
    def get_thumbnail_url(self, width=300, height=200):
        """Get resized thumbnail URL"""
        if self.image:
            return cloudinary.CloudinaryImage(self.cloudinary_public_id).build_url(
                width=width,
                height=height,
                crop='fill',
                quality='auto:good',
                fetch_format='auto'
            )
        return None
    
    def get_optimized_url(self, width=1200):
        """Get optimized image URL"""
        if self.image:
            return cloudinary.CloudinaryImage(self.cloudinary_public_id).build_url(
                width=width,
                crop='limit',
                quality='auto:best',
                fetch_format='auto'
            )
        return None

#This Model For Table Schedule    
class Schedule(models.Model):
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='schedule')  # One-to-one with lesson
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='schedules')
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedules')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    class Meta:
        constraints = [
            # Prevent double-booking instructors
            models.UniqueConstraint(
                fields=['instructor', 'start_time'],
                name='unique_instructor_time_slot'
            ),
            # Prevent double-booking vehicles
            models.UniqueConstraint(
                fields=['vehicle', 'start_time'],
                name='unique_vehicle_time_slot'
            )
        ]

    def __str__(self):
        return f"{self.lesson.title} - {self.start_time}"

#This Model For Table Achievement
class Achievement(models.Model):
    ACHIEVEMENT_TYPES = [
        ('first_lesson', 'First Lesson Completed'),
        ('theory_complete', 'Theory Course Finished'),
        ('driving_master', 'Driving Skills Mastered'),
        ('exam_passed', 'Final Exam Passed'),
    ]
    
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='achievements', db_index=True)
    type = models.CharField(max_length=50, choices=ACHIEVEMENT_TYPES)
    title = models.CharField(max_length=100)  # Human readable
    description = models.TextField()
    icon = models.CharField(max_length=50, default='🏆')  # Emoji or icon class
    earned_at = models.DateTimeField(auto_now_add=True)
    points = models.IntegerField(default=10)

    class Meta:
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.student.user.username} - {self.title}"

#This Model For Table School Analytics
class SchoolAnalytics(models.Model):
    school = models.ForeignKey(DrivingSchool, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField()
    total_students = models.IntegerField(default=0)
    active_students = models.IntegerField(default=0)
    new_students = models.IntegerField(default=0)
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    lessons_completed = models.IntegerField(default=0)
    instructor_utilization = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
       constraints = [
           models.UniqueConstraint(fields=['school', 'date'], name='unique_school_date')
       ]
       ordering = ['-date']

    def __str__(self):
        return f"{self.school.name} Analytics - {self.date}"

#This Model For Table Communication Template
class CommunicationTemplate(models.Model):
    TEMPLATE_TYPES = [
        ('lesson_reminder', 'Lesson Reminder'),
        ('birthday', 'Birthday Wish'),
        ('progress_update', 'Progress Update'),
        ('payment_reminder', 'Payment Reminder'),
        ('achievement', 'Achievement Unlocked'),
    ]
    
    school = models.ForeignKey(DrivingSchool, on_delete=models.CASCADE, related_name='templates')
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.school.name} - {self.name}"

#This Model For Table Automated Message
class AutomatedMessage(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('read', 'Read')
    ]
    
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='messages', db_index=True)
    template = models.ForeignKey(CommunicationTemplate, on_delete=models.CASCADE, related_name='messages', db_index=True)
    scheduled_for = models.DateTimeField()  # When it should be sent
    sent_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    delivery_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_for']

    def __str__(self):
        return f"{self.student.user.username} - {self.template.name}"

#This Model For Table Student Performance Prediction
class StudentPerformancePrediction(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='predictions')
    predicted_completion_date = models.DateField(null=True, blank=True)
    confidence_level = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)  # 0.00 to 1.00
    success_probability = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    risk_factors = models.JSONField(default=dict, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_updated']

    def __str__(self):
        return f"{self.student.user.username} Performance Prediction"
    
#This Model For Table Student Document
class StudentDocument(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=50)
    file = models.FileField(upload_to='student_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.student.user.username

#This Model For Table Subscription Plan 
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=30)
    max_students = models.IntegerField(default=50)
    max_instructors = models.IntegerField(default=5)
    features = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - ${self.price}/month"
    
class SchoolSubscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'), ('canceled', 'Canceled'),
        ('past_due', 'Past Due'), ('trialing', 'Trialing')
    ]
    
    school = models.OneToOneField(DrivingSchool, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trialing')
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.school.name} - {self.plan.name}"