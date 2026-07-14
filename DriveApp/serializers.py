from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import( User, DrivingSchool, StudentProfile, Lesson,
                     Attendance, Feedback, VehiclePicture,Vehicle, Schedule, 
                     Achievement, SchoolAnalytics, CommunicationTemplate, 
                     AutomatedMessage, StudentPerformancePrediction,
                       StudentDocument, SubscriptionPlan, SchoolSubscription)
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q ,Count
from django.db import models
from django.core.cache import cache
from .services import (AnalyticsService, StudentProgressService, StudentProfileService,
                        LessonService, AttendanceService, ScheduleService, VehicleService,
                        StudentDocumentService, SubscriptionPlanService, SchoolSubscriptionService,
                        CommunicationService)

import os
import re
from django.utils.text import slugify

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from cloudinary.forms import CloudinaryFileField

User = get_user_model()

from rest_framework_simplejwt.tokens import RefreshToken
 
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={'input_type': 'password'},
    )
    confirm_password = serializers.CharField(write_only=True, required=True)
 
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 'confirm_password',
            'first_name', 'last_name', 'phone_number',
        ]
        extra_kwargs = {
            'email': {
                'required': True,
                'error_messages': {'unique': 'This email is already registered.'},
            },
            'username': {
                'min_length': 3,
                'error_messages': {'unique': 'This username is already taken.'},
            },
            'first_name': {'required': True},
            'last_name':  {'required': True},
        }
 
    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': "Passwords don't match."})
 
        # Run Django's built-in password validators
        try:
            validate_password(attrs['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
 
        return attrs
 
    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
 
        user = User(
            **validated_data,
            role='A',                        # School owner = Admin
            is_active=False,                 # Locked until platform admin approves
            verification_status='pending',   # Needs review
        )
        user.set_password(password)
        user.save()
        return user
 
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        # Always return without revealing if email exists (security)
        return value.lower().strip()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        # Run Django's built-in password validators
        validate_password(data['new_password'])
        return data

class ChangePasswordSerializer(serializers.Serializer):
    """For logged-in users who want to change their password"""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        validate_password(data['new_password'])
        return data
    
# Serializer For Model User
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True,
                                    required=False,
                                    min_length=8,
                                    validators =[validate_password] ,
                                    style={'input_type':'password'}
                                    )
    confirm_password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields =  ['id', 'username', 'email', 'password','confirm_password',
            'first_name', 'last_name', 'phone_number', 'role',
            'created_at', 'updated_at']
        read_only_fields = ['id','created_at','updated_at']
        extra_kwargs = {
            'email': {
                'required':True,
                    'error_messages':
                        {'unique':'This email is already registered'}
                      },
            'username': {
                'min_length':3,
                    'error_messages':
                        {'unique':'This username is already taken'}
                        }
            }


    
    def validate(self, attrs):
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')

        # For CREATE operations, password is required
        if self.instance is None:  # Creating new user
            if not password:
                raise serializers.ValidationError({'password': 'Password is required for user creation'})
            if not confirm_password:
                raise serializers.ValidationError({'confirm_password': 'Please confirm your password'})
        
        # For UPDATE operations, only validate if password is being changed
        elif password or confirm_password:
            if not password:
                raise serializers.ValidationError({'password':'This field is required when changing password.'})
            if not confirm_password:
                raise serializers.ValidationError({'confirm_password':'Please confirm your password.'})
        
        if password and confirm_password:
            if password != confirm_password:
                raise serializers.ValidationError({'confirm_password':"Passwords don't match"})

            try:
                # FIX: Remove confirm_password from attrs before creating User instance
                temp_attrs = attrs.copy()
                temp_attrs.pop('confirm_password', None)
                validate_password(password, user=self.instance or User(**temp_attrs))
            except DjangoValidationError as e:
                raise serializers.ValidationError({'password':list(e.messages)})
        
        return attrs


    def validate_role(self, value):
        """Prevent privilege escalation"""
        
        # Only validate admin role assignment
        if value != 'A':
            return value
        
        request = self.context.get('request')
        # Check if user is authenticated
        if not request or not hasattr(request,'user') or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")
            
        # Check if the requester is an admin
        if request.user.role != 'A':
            raise serializers.ValidationError("Only administrators can assign admin role")
            
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create user with hashed password"""
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
    @transaction.atomic
    def update(self, instance, validated_data):
        """Handle password update correctly"""
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password', None)

        # Update all fields except password
        instance = super().update(instance, validated_data)

        # Handle password separately if provided
        if password:
            instance.set_password(password)
            instance.save()
        return instance
              
# Serializer For Model DrivingSchool
class DrivingSchoolSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = DrivingSchool
        fields =  ['id','owner','name','address','email',
                'phone_number','created_at','owner_username','student_count']
        read_only_fields = ['id','created_at','owner','owner_username','student_count']
        extra_kwargs = {
            'email':{
            'required':True,
            'error_messages':{
                'unique':'This email already exists' 
                }
            },
            'name':{
                'min_length':3,
                'error_messages':{
                    'unique':'This  name is already taken'
                }
            }
        }

    def get_student_count(self, obj):
        """Get count of active students"""
        return obj.student_profiles.filter(status='A').count()
    
    def validate_name(self, value):
        """Validate school name uniqueness per owner"""

        request = self.context.get('request')

        if request and request.user.is_authenticated:
            # Check if owner already has a school with this name
            queryset = DrivingSchool.objects.filter(owner=request.user, name=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError("You already have a school with this name")
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        """Create driving school with owner from request"""
        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required to create a school")

        validated_data['owner']=request.user
        school = DrivingSchool.objects.create(**validated_data)
        return school
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update driving school - prevent owner change"""
        validated_data.pop('owner',None)
        instance = super().update(instance, validated_data)

        return instance
    
#This Serializer For Model Student Profile

class StudentProfileSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)
    school_name = serializers.CharField(source='school.name', read_only=True)
    picture_profile_url = serializers.SerializerMethodField(read_only=True)
    completion_percentage = serializers.SerializerMethodField(read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)  
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    user_phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    # ✅ Use CharField for reads; upload is handled in the service
    # CloudinaryField stores a string (public_id), not a file object after save
    picture_profile = serializers.ImageField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            'id', 'user', 'school', 'picture_profile', 'license_type',
            'progress_theory', 'progress_driving', 'total_hours_theory',
            'total_hours_driving', 'status', 'theory_start_date', 'driving_start_date',
            'completion_date', 'joined_at', 'user_username', 'school_name', 'user_role',
            'picture_profile_url', 'completion_percentage', 'user_email','user_first_name',
            'user_last_name','user_phone_number'
        ]
        read_only_fields = [
            'id', 'joined_at', 'user_username', 'school_name',
            'picture_profile_url', 'user_email', 'completion_percentage'
        ]

    def get_picture_profile_url(self, obj):
        return StudentProfileService.get_profile_picture_url(obj)

    def get_completion_percentage(self, obj):
        return StudentProfileService.calculate_completion_percentage(obj)

    def validate_user(self, value):
        if value.role not in ('S', 'I'):
            raise serializers.ValidationError("User must be a student or instructor")
        if self.instance and value != self.instance.user:
            raise serializers.ValidationError("Cannot change the user of an existing profile")
        return value

    def validate_school(self, value):
        # ✅ Only validate school change on updates, not creation
        # On creation there's no instance to compare against
        if self.instance:
            request = self.context.get('request')
            StudentProfileService.validate_school_change(
                value, self.instance, request.user if request else None
            )
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        request_user = request.user if request else None

        if self.instance is None:
            StudentProfileService.validate_student_creation(
                attrs.get('user'), attrs.get('school'), request_user
            )
        
        StudentProfileService.validate_student_data(attrs, self.instance)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        return StudentProfileService.create_student_profile(validated_data, request.user)

    @transaction.atomic
    def update(self, instance, validated_data):
        return StudentProfileService.update_student_profile(instance, validated_data)

#This Serializer For Model Lesson
class LessonSerializer(serializers.ModelSerializer):
    """Serializer for Lesson model"""
    
    instructor_name = serializers.CharField(
        source='instructor.username', 
        read_only=True
    )
    school_name = serializers.CharField(
        source='school.name', 
        read_only=True
    )
    completion_percentage = serializers.SerializerMethodField()
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )

    class Meta:
        model = Lesson
        fields = [
            'id', 'instructor', 'school', 'title', 'lesson_type', 
            'description', 'duration', 'date', 'status',
            'instructor_name', 'school_name', 'status_display',
            'completion_percentage'
        ]
        read_only_fields = [
            'id', 'instructor_name', 'school_name', 
            'status_display', 'completion_percentage'
        ]

    def get_completion_percentage(self, obj):
        return LessonService.calculate_completion_percentage(obj)    
    
    def validate(self, attrs):
        """Validate lesson data using LessonService"""
        request = self.context.get('request')
        
        # Get the actual objects (they're already resolved by DRF)
        instructor = attrs.get('instructor')
        school = attrs.get('school')
        lesson_date = attrs.get('date')
        duration = attrs.get('duration')

        # Get request user safely
        request_user = None
        if request and hasattr(request, 'user'):
            request_user = request.user

        # Only validate if we have the required fields
        if instructor and school and lesson_date and duration:
            # Use LessonService for validation
            if self.instance is None:  # Creation
                LessonService.validate_lesson_creation(
                    instructor, school, lesson_date, duration, 
                    request_user
                )
            else:  # Update
                LessonService.validate_lesson_update(
                    self.instance, attrs, 
                    request_user
                )
        
        # Validate lesson data
        LessonService.validate_lesson_data(attrs, self.instance)

        return attrs
        
    def validate_duration(self, value):
        """Validate duration using service configuration"""
        if value < LessonService.MIN_DURATION or value > LessonService.MAX_DURATION:
            raise serializers.ValidationError(
                f"Duration must be between {LessonService.MIN_DURATION} and {LessonService.MAX_DURATION} minutes"
            )
        return value

    def validate_instructor(self, value):
        """Ensure user is an instructor"""
        if value.role != 'I':
            raise serializers.ValidationError("Selected user must be an instructor")
        return value
    
    def validate_lesson_type(self, value):
        """Validate lesson type"""
        if value not in ['T', 'D']:
            raise serializers.ValidationError("Lesson type must be 'T' (Theory) or 'D' (Driving)")
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create lesson using LessonService"""
        request = self.context.get('request')
        request_user = request.user if request and hasattr(request, 'user') else None

        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError('Authentication required to create a lesson')
        
        return LessonService.create_lesson(validated_data, request_user)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update lesson using LessonService"""
        request = self.context.get('request')
        request_user = request.user if request and hasattr(request, 'user') else None

        # Check authentication
        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError('Authentication required to update a lesson')
        
        # Check permissions
        if not LessonService.can_modify_lesson(request_user, instance):
            raise serializers.ValidationError('You do not have permission to modify this lesson')
        
        # Update the lesson
        return LessonService.update_lesson(instance, validated_data)
    
#This Serializer For Model Attendance
class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.username", read_only=True)
    lesson_name = serializers.CharField(source="lesson.title", read_only=True)
    instructor_name = serializers.CharField(source="lesson.instructor.username", read_only=True)

    class Meta:
        model = Attendance
        fields = ['id','student','lesson','presence','hours_completed',
                  'notes','created_at','student_name','lesson_name','instructor_name']
        read_only_fields = ['id','created_at','student_name',
                            'lesson_name','instructor_name']
        
    def validate(self, attrs):
        """Validate attendance data using AttendanceService"""
        request = self.context.get('request')
        student = attrs.get('student') or (self.instance.student if self.instance else None)
        lesson = attrs.get('lesson') or (self.instance.lesson if self.instance else None)
        presence = attrs.get('presence')
        hours_completed = attrs.get('hours_completed')

        # Get request user safely
        request_user = request.user if request and hasattr(request, 'user') else None

        # Use AttendanceService for validation
        if self.instance is None:  # Creation
            AttendanceService.validate_attendance_creation(
                student, lesson, presence, hours_completed, request_user
            )
        else:  # Update
            AttendanceService.validate_attendance_update(
                self.instance, attrs, request_user
            )

        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        """Create attendance using AttendanceService"""
        request = self.context.get('request')
        request_user = request.user if request and hasattr(request, 'user') else None
        
        return AttendanceService.create_attendance(validated_data, request_user)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update attendance using AttendanceService"""
        request = self.context.get('request')
        request_user = request.user if request and hasattr(request, 'user') else None
        
        # Check permissions
        if not AttendanceService.can_modify_attendance(request_user, instance):
            raise serializers.ValidationError('You do not have permission to modify this attendance')
        
        return AttendanceService.update_attendance(instance, validated_data)
#This serializer for Model Feedback
class FeedbackSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    lesson_name = serializers.CharField(source='lesson.title', read_only=True)
    instructor_name = serializers.CharField(source='lesson.instructor.username',read_only=True)
    school_name = serializers.CharField(source='lesson.school.name', read_only=True)

    class Meta:
        model = Feedback
        fields = ['id','student','lesson','rating','comment','created_at',
                  'student_name','lesson_name','instructor_name','school_name']
        read_only_fields = ['id','created_at','student_name','lesson_name',
                            'instructor_name','school_name']
        
    def validate(self, attrs):
        """Validate feedback business rules"""
        student = attrs.get('student')
        lesson = attrs.get('lesson')

        # For CREATE operations, validate attendance and uniqueness
        if self.instance is None and student and lesson:
            # Check if student attended the lesson
            attendance = Attendance.objects.filter(student=student, lesson=lesson).first()
            if not attendance or not attendance.presence:
                raise serializers.ValidationError({
                    'lesson': 'Student must have attended the lesson to provide feedback'
                })
            
            # Check school enrollment
            if student.school != lesson.school:
                raise serializers.ValidationError({
                    'student': 'Student is not enrolled in this school'
                })
            
            # Check for existing feedback
            if Feedback.objects.filter(student=student, lesson=lesson).exists():
                raise serializers.ValidationError({
                    'lesson': 'Feedback already exists for this lesson'
                })

        return attrs
    
    def validate_rating(self, value):
        if value < 1 or value > 5 :
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
    
    def validate_student(self, value):
        """Prevent changing student after creation"""
        if self.instance and value != self.instance.student:
            raise serializers.ValidationError("Cannot change the student of existing feedback")
        return value
    
    def validate_lesson(self, value):
        """Prevent changing lesson after creation"""
        if self.instance and value != self.instance.lesson:
            raise serializers.ValidationError("Cannot change the lesson of existing feedback")
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        student = validated_data.get('student')

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required to submit feedback")
        
        if request.user != student.user:
            raise serializers.ValidationError({
                'student': 'You can only submit feedback for your own lessons'
            })
        return Feedback.objects.create(**validated_data)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop('student', None)
        validated_data.pop('lesson', None)
        return super().update(instance, validated_data)

# This serializer For Model VehicleSerializer
class VehiclePictureSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField(read_only=True)
    thumbnail_url = serializers.SerializerMethodField(read_only=True)
    optimized_url = serializers.SerializerMethodField(read_only=True)
    image_size = serializers.SerializerMethodField(read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)

    class Meta:
        model = VehiclePicture
        fields = [
            'id', 'vehicle', 'image', 'image_url', 'thumbnail_url', 
            'optimized_url', 'image_size', 'caption', 'is_primary', 
            'uploaded_by', 'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = [
            'id', 'uploaded_at', 'image_url', 'thumbnail_url', 
            'optimized_url', 'image_size', 'uploaded_by_name'
        ]
        extra_kwargs = {
            'uploaded_by': {'write_only': True}
        }

    def get_image_url(self, obj):
        """Get full Cloudinary URL"""
        if obj.image:
            return str(obj.image.url)
        return None
    
    def get_thumbnail_url(self, obj):
        """Get thumbnail (300x200)"""
        return obj.get_thumbnail_url() if obj.image else None
    
    def get_optimized_url(self, obj):
        """Get optimized full size (1200px width)"""
        return obj.get_optimized_url() if obj.image else None
    
    def get_image_size(self, obj):
        """Get file size from Cloudinary"""
        if obj.image and hasattr(obj.image, 'metadata'):
            try:
                bytes_size = obj.image.metadata.get('bytes', 0)
                if bytes_size < 1024:
                    return f"{bytes_size} B"
                elif bytes_size < 1024 * 1024:
                    return f"{bytes_size / 1024:.2f} KB"
                else:
                    return f"{bytes_size / (1024 * 1024):.2f} MB"
            except:
                pass
        return None
    
    def validate_image(self, value):
        """Validate before upload"""
        is_valid, error = VehicleService.validate_image_file(value)
        if not is_valid:
            raise serializers.ValidationError(error)
        return value
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if 'vehicle' in representation and isinstance(representation['vehicle'], dict):
            representation['vehicle'] = instance.vehicle.id
        return representation
    
#This Serializer for Model Vehicle
class VehicleSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    is_available = serializers.SerializerMethodField(read_only=True)
    maintenance_status = serializers.SerializerMethodField(read_only=True)
    vehicle_age = serializers.SerializerMethodField(read_only=True)
    
    # Image handling
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text=f"Upload up to {VehicleService.MAX_IMAGES_PER_VEHICLE} images (max {VehicleService.MAX_IMAGE_SIZE_MB}MB each)"
    )
    
    image_list = serializers.SerializerMethodField(read_only=True)
    primary_picture = serializers.SerializerMethodField(read_only=True)
    primary_thumbnail = serializers.SerializerMethodField(read_only=True)
    images_summary = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'school', 'school_name', 'plate_number', 'make', 'model',
            'year', 'color', 'transmission', 'status', 'last_maintenance',
            'next_maintenance', 'created_at', 'is_available', 'maintenance_status',
            'vehicle_age', 'images', 'image_list', 'primary_picture', 
            'primary_thumbnail', 'images_summary'
        ]
        read_only_fields = [
            'id', 'created_at', 'school_name', 'is_available', 
            'maintenance_status', 'vehicle_age', 'image_list', 
            'primary_picture', 'primary_thumbnail', 'images_summary',
        ]
    
    def get_image_list(self, obj):
        include_images = self.context.get('include_images', True)
        if not include_images:
            return []
        pictures = obj.pictures.all()
        return VehiclePictureSerializer(pictures, many=True, context=self.context).data

    def get_primary_picture(self, obj):
        """Full size primary picture"""
        primary = obj.pictures.filter(is_primary=True).first()
        return primary.image.url if primary and primary.image else None
    
    def get_primary_thumbnail(self, obj):
        """Thumbnail of primary picture"""
        primary = obj.pictures.filter(is_primary=True).first()
        return primary.get_thumbnail_url() if primary else None
    
    def get_images_summary(self, obj):
        return VehicleService.get_vehicle_images_summary(obj)
    
    def get_is_available(self, obj):
        return VehicleService.is_available(obj)

    def get_maintenance_status(self, obj):
        return VehicleService.get_maintenance_status(obj)

    def get_vehicle_age(self, obj):
        return VehicleService.get_vehicle_age(obj)

    def validate_images(self, value):
        """Validate uploaded images"""
        if not value:
            return value
        
        vehicle = self.instance
        is_valid, error = VehicleService.validate_multiple_images(value, vehicle)
        
        if not is_valid:
            raise serializers.ValidationError(error)
        
        return value

    def validate(self, attrs):
        """Validate vehicle data"""
        request = self.context.get('request')
        school = attrs.get('school') or (self.instance.school if self.instance else None)
        plate_number = attrs.get('plate_number')
        year = attrs.get('year')
        last_maintenance = attrs.get('last_maintenance')
        next_maintenance = attrs.get('next_maintenance')

        request_user = request.user if request and hasattr(request, 'user') else None

        if self.instance is None:  # Creation
            VehicleService.validate_vehicle_creation(
                school, plate_number, year, last_maintenance, next_maintenance, request_user
            )
        else:  # Update
            VehicleService.validate_vehicle_update(
                self.instance, attrs, request_user
            )

        return attrs
    
    def validate_school(self, value):
        """Prevent changing school after creation"""
        if self.instance and value != self.instance.school:
            raise serializers.ValidationError("Cannot change the school of an existing vehicle")
        return value

    def validate_plate_number(self, value):
        """Validate plate number format"""
        VehicleService._validate_plate_number(value)
        return value.upper()

    def validate_year(self, value):
        """Validate vehicle year"""
        VehicleService._validate_year(value)
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        """Create vehicle with images"""
        images_data = validated_data.pop('images', [])
        request = self.context.get('request')
        request_user = request.user if request and hasattr(request, 'user') else None
        
        # Create vehicle
        vehicle = VehicleService.create_vehicle(validated_data, request_user)
        
        # Upload images if provided
        if images_data:
            for idx, image in enumerate(images_data):
                # Optimize image before saving
                #optimized_image = VehicleService.optimize_image(image)
                
                VehiclePicture.objects.create(
                    vehicle=vehicle,
                    #image=optimized_image,
                    is_primary=(idx == 0),  # First image is primary
                    uploaded_by=request_user,
                    caption=f"Image {idx + 1}"
                )
        
        return vehicle
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update vehicle with optional new images"""
        images_data = validated_data.pop('images', None)
        request = self.context.get('request')
        request_user = request.user if request and hasattr(request, 'user') else None
        
        # Check permissions
        if not VehicleService.can_modify_vehicle(request_user, instance):
            raise serializers.ValidationError('You do not have permission to modify this vehicle')
        
        # Update vehicle
        vehicle = VehicleService.update_vehicle(instance, validated_data)
        
        # Add new images if provided
        if images_data:
            current_count = vehicle.pictures.count()
            has_primary = vehicle.pictures.filter(is_primary=True).exists()
            
            for idx, image in enumerate(images_data):
                # Optimize image
                #optimized_image = VehicleService.optimize_image(image)
                
                VehiclePicture.objects.create(
                    vehicle=vehicle,
                    #image=optimized_image,
                    is_primary=(not has_primary and idx == 0),  # Set first as primary if none exists
                    uploaded_by=request_user,
                    caption=f"Image {current_count + idx + 1}"
                )
        
        return vehicle
    
# this Serailizer For Model Schedule
class ScheduleSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    instructor_name = serializers.CharField(source='instructor.username', read_only=True)
    vehicle_info = serializers.SerializerMethodField(read_only=True)
    duration_minutes = serializers.SerializerMethodField(read_only=True)
    school_name = serializers.CharField(source='lesson.school.name', read_only=True)

    class Meta:
        model = Schedule
        fields = [
            'id', 'lesson', 'lesson_title', 'vehicle', 'vehicle_info',
            'instructor', 'instructor_name', 'start_time', 'end_time',
            'duration_minutes', 'school_name'
        ]
        read_only_fields = [
            'id', 'lesson_title', 'instructor_name', 'vehicle_info', 
            'duration_minutes', 'school_name'
        ]

    def get_vehicle_info(self, obj):
        """Get formatted vehicle information"""
        if obj.vehicle:
            return f"{obj.vehicle.make} {obj.vehicle.model} ({obj.vehicle.plate_number})"
        return "No vehicle assigned"

    def get_duration_minutes(self, obj):
        """Calculate lesson duration in minutes"""
        return ScheduleService.get_schedule_duration(obj)

    def validate(self, attrs):
        """Validate schedule data using ScheduleService"""
        request = self.context.get('request')
        lesson = attrs.get('lesson') or (self.instance.lesson if self.instance else None)
        vehicle = attrs.get('vehicle')
        instructor = attrs.get('instructor') or (self.instance.instructor if self.instance else None)
        start_time = attrs.get('start_time') or (self.instance.start_time if self.instance else None)
        end_time = attrs.get('end_time') or (self.instance.end_time if self.instance else None)

        # Get request user safely
        request_user = request.user if request and hasattr(request, 'user') else None
 
        # Use ScheduleService for validation
        if self.instance is None:  # Creation
            ScheduleService.validate_schedule_creation(
                lesson, vehicle, instructor, start_time, end_time, request_user
            )
        else:  # Update
            ScheduleService.validate_schedule_update(
                self.instance, attrs, request_user
            )

        return attrs

    def validate_lesson(self, value):
        """Prevent changing lesson after creation"""
        if self.instance and value != self.instance.lesson:
            raise serializers.ValidationError("Cannot change the lesson of an existing schedule")
        
        if value.status == 'C':
            raise serializers.ValidationError("Cannot schedule a completed lesson")
        

        # Check if lesson already has a schedule
        if not self.instance and hasattr(value, 'schedule'):
            raise serializers.ValidationError("This lesson already has a schedule")
        
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        """Create schedule using ScheduleService"""
        request = self.context.get('request')
        request_user = request.user if request and hasattr(request, 'user') else None
        
        return ScheduleService.create_schedule(validated_data, request_user)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update schedule using ScheduleService"""
        request = self.context.get('request')
        request_user = request.user if request and hasattr(request, 'user') else None
        
        # Check permissions
        if not ScheduleService.can_modify_schedule(request_user, instance):
            raise serializers.ValidationError('You do not have permission to modify this schedule')
        
        return ScheduleService.update_schedule(instance, validated_data)
    
# This Serializer For MODEL ACHIEVEMENT  ==========
class AchievementSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    student_email = serializers.CharField(source='student.user.email', read_only=True)
    school_name = serializers.CharField(source='student.school.name', read_only=True)
    student_role = serializers.CharField(source='student.user.role', read_only=True)

    class Meta:
        model = Achievement
        fields = [
            'id', 'student', 'student_name', 'student_email', 'school_name',
            'type', 'title', 'description', 'icon', 'earned_at', 'points','student_role',
        ]
        read_only_fields = [
            'id', 'student_name', 'student_email', 'school_name', 'earned_at'
        ]

    def validate(self, attrs):
        """Validate achievement data"""
        student = attrs.get('student')
        achievement_type = attrs.get('type')

        # For creation, prevent duplicate achievements
        if self.instance is None and student and achievement_type:
            existing = Achievement.objects.filter(
                student=student,
                type=achievement_type
            ).exists()
            
            if existing:
                raise serializers.ValidationError({
                    'type': 'Student already has this achievement'
                })

        return attrs

    def validate_student(self, value):
        """Prevent changing student after creation"""
        if self.instance and value != self.instance.student:
            raise serializers.ValidationError("Cannot change the student of an existing achievement")
        return value

    def validate_points(self, value):
        """Validate points are reasonable"""
        if value < 0:
            raise serializers.ValidationError("Points cannot be negative")
        if value > 1000:
            raise serializers.ValidationError("Points cannot exceed 1000")
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create achievement"""
        return Achievement.objects.create(**validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update achievement - prevent student change"""
        validated_data.pop('student', None)
        return super().update(instance, validated_data)
    
# ========== SCHOOL ANALYTICS SERIALIZER ==========
class SchoolAnalyticsSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    growth_rate = serializers.SerializerMethodField(read_only=True)
    completion_percentage = serializers.SerializerMethodField(read_only=True)
    revenue_formatted = serializers.SerializerMethodField(read_only=True)
    performance_summary = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SchoolAnalytics
        fields = [
            'id', 'school', 'school_name', 'date', 'total_students',
            'active_students', 'new_students', 'completion_rate', 'revenue',
            'average_rating', 'lessons_completed', 'instructor_utilization',
            'growth_rate', 'completion_percentage', 'revenue_formatted',
            'performance_summary'
        ]
        read_only_fields = [
            'id', 'school_name', 'growth_rate', 'completion_percentage',
            'revenue_formatted', 'performance_summary'
        ]

    def get_growth_rate(self, obj):
        """Calculate student growth rate compared to previous day"""
        return AnalyticsService.calculate_growth_rate(obj)

    def get_completion_percentage(self, obj):
        """Format completion rate as readable percentage"""
        return AnalyticsService.format_completion_percentage(obj.completion_rate)

    def get_revenue_formatted(self, obj):
        """Format revenue with currency symbol"""
        return AnalyticsService.format_revenue(obj.revenue)

    def get_performance_summary(self, obj):
        """Generate performance summary"""
        return AnalyticsService.generate_performance_summary(obj)

    def validate(self, attrs):
        """Validate analytics data"""
        school = attrs.get('school', self.instance.school if self.instance else None)
        date = attrs.get('date', self.instance.date if self.instance else None)

        # Validate school ownership (keep this in serializer since it's request-specific)
        if self.instance is None:
            request = self.context.get('request')
            if request and request.user.is_authenticated and not request.user.is_active and school:
                if school.owner != request.user:
                    raise serializers.ValidationError({
                        'school': 'You can only create analytics for your own school'
                    })
        AnalyticsService.validate_analytics_data(school, date, attrs)

        return attrs

    def validate_school(self, value):
        """Prevent changing school after creation"""
        if self.instance and value != self.instance.school:
            raise serializers.ValidationError("Cannot change the school of existing analytics")
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create analytics record"""
        school = validated_data['school']
        date = validated_data.get('date', timezone.now().date())

        # Check if user is providing manual data or wants auto-generation
        has_manual_metrics = any(
            key in validated_data 
            for key in ['total_students', 'active_students', 'completion_rate', 'revenue']
        )
        if has_manual_metrics:
            # User is manually creating analytics - use validated_data
            return super().create(validated_data)
        else:
            # Auto-generate from actual system data
            return AnalyticsService.generate_daily_analytics(school, date, force_refresh=True)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update analytics - prevent school and date change"""

        validated_data.pop('school', None)
        validated_data.pop('date', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()

        # Invalidate cache for this record
        cached_key = f"analytics_{instance.school.id}_{instance.date}"
        cache.delete(cached_key)

        return instance

# ========== COMMUNICATION TEMPLATE SERIALIZER ==========
class CommunicationTemplateSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    usage_count = serializers.SerializerMethodField(read_only=True)
    variables = serializers.SerializerMethodField(read_only=True)
    last_used = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CommunicationTemplate
        fields = [
            'id', 'school', 'school_name', 'name', 'template_type',
            'subject', 'body', 'is_active', 'created_at',
            'usage_count', 'variables', 'last_used'
        ]
        read_only_fields = [
            'id', 'created_at', 'school_name', 'usage_count', 
            'variables', 'last_used'
        ]

    def get_usage_count(self, obj):
        """Count how many messages use this template"""
        return obj.messages.count()

    def get_variables(self, obj):
        """Extract template variables from subject and body"""
        import re
        variables = set()
        
        # Find all {variable} patterns
        pattern = r'\{(\w+)\}'
        variables.update(re.findall(pattern, obj.subject))
        variables.update(re.findall(pattern, obj.body))
        
        return sorted(list(variables))

    def get_last_used(self, obj):
        """Get the last time this template was used"""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            return last_message.created_at
        return None

    def validate(self, attrs):
        """Validate template data"""
        school = attrs.get('school', self.instance.school if self.instance else None)
        request = self.context.get('request')
        # Validate school ownership

        if self.instance is None:
            if request and request.user.is_authenticated and school:
                if request.user.role == 'A' and not request.user.is_staff:
                    if school.owner != request.user:
                        raise serializers.ValidationError({
                            'school': 'You can only create templates for your own school'
                        })
                
        # Validate template body is not empty
        body = attrs.get('body', '')
        if not body or not body.strip():
            raise serializers.ValidationError({
                'body': 'Template body cannot be empty'
            })

        # Validate name uniqueness per school
        name = attrs.get('name')
        if name and school:
            queryset = CommunicationTemplate.objects.filter(
                school=school,
                name=name
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise serializers.ValidationError({
                    'name': 'A template with this name already exists for your school'
                })

        return attrs

    def validate_school(self, value):
        """Prevent changing school after creation"""
        if self.instance and value != self.instance.school:
            raise serializers.ValidationError("Cannot change the school of existing template")
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create communication template"""
        return CommunicationTemplate.objects.create(**validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update template - prevent school change"""
        validated_data.pop('school', None)
        return super().update(instance, validated_data)

# ========== AUTOMATED MESSAGE SERIALIZER ==========
class AutomatedMessageSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    student_email = serializers.CharField(source='student.user.email', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    school_name = serializers.CharField(source='template.school.name', read_only=True)
    is_overdue = serializers.SerializerMethodField(read_only=True)
    time_until_send = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AutomatedMessage
        fields = [
            'id', 'student', 'student_name', 'student_email', 'template',
            'template_name', 'school_name', 'scheduled_for', 'sent_at',
            'status', 'delivery_error', 'created_at', 'is_overdue',
            'time_until_send'
        ]
        read_only_fields = [
            'id', 'created_at', 'sent_at', 'student_name', 'student_email',
            'template_name', 'school_name', 'is_overdue', 'time_until_send'
        ]

    def get_is_overdue(self, obj):
        """Delegate to service layer"""
        return CommunicationService.get_is_overdue(obj)

    def get_time_until_send(self, obj):
        """Delegate to service layer"""
        return CommunicationService.get_time_until_send(obj)

    def validate(self, attrs):
        """Validate using service layer"""
        student = attrs.get('student', self.instance.student if self.instance else None)
        template = attrs.get('template', self.instance.template if self.instance else None)
        scheduled_for = attrs.get('scheduled_for', self.instance.scheduled_for if self.instance else None)

        if self.instance is None:  # Creation
            user = self.context.get('request').user if self.context.get('request') else None
            CommunicationService.validate_message_creation(student, template, scheduled_for, user)
        else:  # Update
            CommunicationService.validate_message_update(self.instance, attrs)

        return attrs

    def validate_student(self, value):
        """Validation handled in service layer"""
        return value

    def validate_template(self, value):
        """Validation handled in service layer"""
        return value

    def validate_status(self, value):
        """Validation handled in service layer"""
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create using service layer"""
        user = self.context.get('request').user if self.context.get('request') else None
        return CommunicationService.create_message(validated_data, user)

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update using service layer"""
        return CommunicationService.update_message(instance, validated_data)  

# ========== STUDENT PERFORMANCE PREDICTION SERIALIZER ==========
class StudentPerformancePredictionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    student_email = serializers.CharField(source='student.user.email', read_only=True)
    school_name = serializers.CharField(source='student.school.name', read_only=True)
    days_until_completion = serializers.SerializerMethodField(read_only=True)
    risk_level = serializers.SerializerMethodField(read_only=True)
    confidence_percentage = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = StudentPerformancePrediction
        fields = [
            'id', 'student', 'student_name', 'student_email', 'school_name',
            'predicted_completion_date', 'confidence_level', 'success_probability',
            'risk_factors', 'recommendations', 'last_updated', 'created_at',
            'days_until_completion', 'risk_level', 'confidence_percentage'
        ]
        read_only_fields = [
            'id', 'created_at', 'last_updated', 'student_name', 'student_email',
            'school_name', 'days_until_completion', 'risk_level', 'confidence_percentage'
        ]

    def get_days_until_completion(self, obj):
        """Calculate days until predicted completion"""
        return StudentProgressService.calculate_days_until_completion(obj)

    def get_risk_level(self, obj):
        """Calculate risk level based on success probability"""
        return StudentProgressService.calculate_risk_level(obj.success_probability)

    def get_confidence_percentage(self, obj):
        """Convert confidence level to percentage"""
        return StudentProgressService.format_confidence_percentage(obj.confidence_level)

    def validate(self, attrs):
        """Validate prediction data"""
        StudentProgressService.validate_prediction_data(attrs)
        return attrs

    def validate_student(self, value):
        """Prevent changing student after creation"""
        if self.instance and value != self.instance.student:
            raise serializers.ValidationError("Cannot change the student of existing prediction")
        return value

    def validate_risk_factors(self, value):
        """Validate risk_factors JSON structure"""
        return StudentProgressService.validate_risk_factors_structure(value)

    def validate_recommendations(self, value):
        """Validate recommendations JSON structure"""
        return StudentProgressService.validate_recommendations_structure(value)
        


    @transaction.atomic
    def create(self, validated_data):
        """Create prediction with guaranteed instance return"""
        student = validated_data['student']

        # Check if user is providing manual prediction data
        has_manual_prediction = any(
            key in validated_data
            for key in ['predicted_completion_date', 'success_probability', 'confidence_level']
        )

        if has_manual_prediction:
            # Manual creation - use provided data
            return StudentPerformancePrediction.objects.create(**validated_data)
        else:
            # Auto-generation - try service first, fallback to basic prediction
            auto_prediction = StudentProgressService.calculate_completion_estimate(student, force_refresh=True)
            
            if auto_prediction:
                return auto_prediction
            else:
                # Fallback: Create a basic prediction with default values
                return StudentPerformancePrediction.objects.create(
                    student=student,
                    predicted_completion_date=timezone.now().date() + timedelta(days=90),  # Default 3 months
                    success_probability=50.0,  # Neutral probability
                    confidence_level=0.3,  # Low confidence for new students
                    risk_factors={'status': 'initial_prediction'},
                    recommendations=['Complete more lessons to improve prediction accuracy']
                )
        
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update prediction - prevent student change"""
        validated_data.pop('student', None)
        

        instance = super().update(instance, validated_data)

        cache_key = f"completion_estimate_{instance.student.id}"
        cache.delete(cache_key)

        return instance

# ========== STUDENT DOCUMENT SERIALIZER ==========
class StudentDocumentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    school_name = serializers.CharField(source='student.school.name', read_only=True)
    file_url = serializers.SerializerMethodField(read_only=True)
    file_size = serializers.SerializerMethodField(read_only=True)
    file_extension = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = StudentDocument
        fields = [
            'id', 'student', 'student_name', 'school_name', 'document_type',
            'file', 'file_url', 'file_size', 'file_extension', 'uploaded_at'
        ]
        read_only_fields = [
            'id', 'uploaded_at', 'student_name', 'school_name',
            'file_url', 'file_size', 'file_extension'
        ]

    def get_file_url(self, obj):
        if not obj or isinstance(obj, dict):
            return None

        request = self.context.get('request')
        return StudentDocumentService.get_file_url(obj.file, request)


    def get_file_size(self, obj):
        if not obj or isinstance(obj, dict):
            return None

        return StudentDocumentService.get_file_size(obj.file)


    def get_file_extension(self, obj):
        # 🔒 Guard against dicts or invalid objects
        if not obj or isinstance(obj, dict):
            return None

        if not hasattr(obj, 'file') or not obj.file:
            return None

        import os
        return os.path.splitext(obj.file.name)[1].lower()

        # This is a utility, not validation

    def validate(self, attrs):
        """Validate document data"""
        student = attrs.get('student')
        file = attrs.get('file')

        if self.instance and not student:
            student = self.instance.student
        # Validate access permissions
        request = self.context.get('request')
        request_user = request.user if request and request.user.is_authenticated else None
        
        # Use service for validation
        if student and file:
            StudentDocumentService.validate_document_creation(student, file, request_user)
            
        return attrs

    def validate_file(self, value):
        """Validate file upload"""
        StudentDocumentService.validate_file_upload(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create document"""
        return StudentDocumentService.create_document(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update document - prevent student change"""
        return StudentDocumentService.update_document(instance, validated_data)

class StudentDocumentUploadSerializer(serializers.Serializer):
    """Serializer for uploading multiple documents"""
    student_id = serializers.IntegerField(required=False)
    document_type = serializers.CharField(max_length=50)
    files = serializers.ListField(
        child=serializers.FileField(
            max_length=50 * 1024 * 1024,  # 50MB per file
            allow_empty_file=False
        ),
        allow_empty=False,
        max_length=5,  # Max 5 files at once
        min_length=1   # At least 1 file
    )
    
    def validate_file(self, value):
        """Validate file upload"""
        StudentDocumentService.validate_file_upload(value)
        
        # Optional: Check file extension
        StudentDocumentService.validate_file_extension(value)
        
        StudentDocumentService.validate_file_size(value)

        
        name, ext = os.path.splitext(value.name)
        sanitized_name = slugify(name)
        value.name = f"{sanitized_name}{ext}"
        
        return value
    
    def validate_document_type(self, value):
        """Validate document type"""
        valid_types = ['ID Card', 'Driver\'s License', 'Medical Certificate', 'Passport', 'Other']
        if value not in valid_types:
            raise serializers.ValidationError(
                f'Invalid document type. Must be one of: {", ".join(valid_types)}'
            )
        return value
    
    def validate(self, attrs):
        """Validate the entire upload"""
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        
        student_id = attrs.get('student_id')
        
        if user and user.role == 'S':
            # Students can only upload for themselves
            student_profile = user.student_profiles.filter(status='A').first()
            if not student_profile:
                raise serializers.ValidationError({
                    'student_id': 'No active student profile found'
                })
            
            if student_id and student_id != student_profile.id:
                raise serializers.ValidationError({
                    'student_id': 'Students can only upload documents for themselves'
                })
            
            # Set student_id to the student's own ID
            attrs['student_id'] = student_profile.id
        
        elif student_id:
            # For non-students, validate they have access to this student
            try:
                student_profile = StudentProfile.objects.get(id=student_id)
            except StudentProfile.DoesNotExist:
                raise serializers.ValidationError({
                    'student_id': 'Student not found'
                })
            
            # Check permissions (could be moved to service)
            if user.role == 'I':
                instructor_profile = user.student_profiles.filter(status='A').first()
                if not instructor_profile or instructor_profile.school != student_profile.school:
                    raise serializers.ValidationError({
                        'student_id': 'You can only upload documents for students in your school'
                    })
            
            if user.role == 'A' and not user.is_staff:
                if student_profile.school.owner != user:
                    raise serializers.ValidationError({
                        'student_id': 'You can only upload documents for students in your schools'
                    })
        
        return attrs

# ========== SUBSCRIPTION PLAN SERIALIZER ==========
class SubscriptionPlanSerializer(serializers.ModelSerializer):
    price_formatted = serializers.SerializerMethodField(read_only=True)
    duration_display = serializers.SerializerMethodField(read_only=True)
    subscription_count = serializers.SerializerMethodField(read_only=True)
    is_popular = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'price', 'price_formatted', 'duration_days',
            'duration_display', 'max_students', 'max_instructors', 'features',
            'is_active', 'created_at', 'subscription_count', 'is_popular'
        ]
        read_only_fields = [
            'id', 'created_at', 'price_formatted', 'duration_display',
            'subscription_count', 'is_popular'
        ]

    def get_price_formatted(self, obj):
        """Format price with currency"""
        return SubscriptionPlanService.get_price_formatted(obj.price)

    def get_duration_display(self, obj):
        """Convert duration to human-readable format"""
        return SubscriptionPlanService.get_duration_display(obj.duration_days)

    def get_subscription_count(self, obj):
        """Count active subscriptions on this plan"""
        return SubscriptionPlanService.get_subscription_count(obj)

    def get_is_popular(self, obj):
        """Mark popular plans (most subscriptions)"""
        return SubscriptionPlanService.get_is_popular(obj)

    def validate(self, attrs):
        """Validate plan data using service"""
        price = attrs.get('price')
        max_students = attrs.get('max_students')
        max_instructors = attrs.get('max_instructors')
        duration_days = attrs.get('duration_days')
        features = attrs.get('features', {})

        # Use service for validation
        if self.instance is None:  # Creation
            SubscriptionPlanService.validate_plan_creation(
                price, max_students, max_instructors, duration_days, features
            )
        else:  # Update
            SubscriptionPlanService.validate_plan_update(self.instance, attrs)

        return attrs

    def validate_features(self, value):
        """Validate features JSON structure using service"""
        SubscriptionPlanService.validate_features(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create subscription plan using service"""
        return SubscriptionPlanService.create_plan(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update plan using service"""
        return SubscriptionPlanService.update_plan(instance, validated_data)

# ========== SCHOOL SUBSCRIPTION SERIALIZER ==========
class SchoolSubscriptionSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_details = SubscriptionPlanSerializer(source='plan', read_only=True)
    days_remaining = serializers.SerializerMethodField(read_only=True)
    is_expired = serializers.SerializerMethodField(read_only=True)
    can_add_student = serializers.SerializerMethodField(read_only=True)
    can_add_instructor = serializers.SerializerMethodField(read_only=True)
    usage_stats = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SchoolSubscription
        fields = [
            'id', 'school', 'school_name', 'plan', 'plan_name', 'plan_details',
            'status', 'stripe_subscription_id', 'current_period_start',
            'current_period_end', 'created_at', 'days_remaining', 'is_expired',
            'can_add_student', 'can_add_instructor', 'usage_stats'
        ]
        read_only_fields = [
            'id', 'created_at', 'school_name', 'plan_name', 'plan_details',
            'days_remaining', 'is_expired', 'can_add_student', 
            'can_add_instructor', 'usage_stats'
        ]

    def get_days_remaining(self, obj):
        """Calculate days remaining in current period"""
        return SchoolSubscriptionService.get_days_remaining(obj)

    def get_is_expired(self, obj):
        """Check if subscription is expired"""
        return SchoolSubscriptionService.is_expired(obj)

    def get_can_add_student(self, obj):
        """Check if school can add more students"""
        return SchoolSubscriptionService.can_add_student(obj)

    def get_can_add_instructor(self, obj):
        """Check if school can add more instructors"""
        return SchoolSubscriptionService.can_add_instructor(obj)

    def get_usage_stats(self, obj):
        """Get current usage statistics"""
        return SchoolSubscriptionService.get_usage_stats(obj)

    def validate(self, attrs):
        """Validate subscription data using service"""
        if self.instance is None:  # Creation
            school = attrs.get('school')
            plan = attrs.get('plan')
            current_period_start = attrs.get('current_period_start')
            current_period_end = attrs.get('current_period_end')
            
            SchoolSubscriptionService.validate_subscription_creation(
                school, plan, current_period_start, current_period_end
            )
        else:  # Update
            SchoolSubscriptionService.validate_subscription_update(self.instance, attrs)

        return attrs

    def validate_school(self, value):
        """Prevent changing school after creation"""
        if self.instance and value != self.instance.school:
            raise serializers.ValidationError("Cannot change the school of existing subscription")
        return value

    def validate_status(self, value):
        """Validate status transitions using service"""
        if self.instance:
            SchoolSubscriptionService._validate_status_transition(self.instance.status, value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create subscription using service"""
        return SchoolSubscriptionService.create_subscription(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update subscription using service"""
        return SchoolSubscriptionService.update_subscription(instance, validated_data)