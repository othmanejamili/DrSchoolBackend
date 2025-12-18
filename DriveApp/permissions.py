from rest_framework import permissions


class IsPlatformAdmin(permissions.BasePermission):
    """
    Permission check for Platform Admins ONLY (role='A' AND is_staff=True).
    """
    message = "Only platform administrators can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role == 'A' and
            request.user.is_staff  # ← This is the key difference!
        )
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

class IsSchoolOwner(permissions.BasePermission):
    """
    Permission check for School Owners ONLY (role='A' AND NOT is_staff).
    """
    message = "Only school owners can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role == 'A' and
            not request.user.is_staff  # ← NOT is_staff!
        )
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
    
class IsPlatformAdminOrSchoolOwner(permissions.BasePermission):
    """
    Permission for either Platform Admins OR School Owners.
    """
    message = "Only platform administrators or school owners can perform this action."

    def has_permission(self, request, view):
        # Platform admin
        is_platform_admin = bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role == 'A' and
            request.user.is_staff
        )
        
        # School owner
        is_school_owner = bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role == 'A' and
            not request.user.is_staff
        )

        
        return is_platform_admin or is_school_owner
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

class IsPlatformAdminOrSchoolOwnerOrInstructor(permissions.BasePermission):
    """
    Permission for either Platform Admins OR School Owners.
    """
    message = "Only platform administrators or school owners can perform this action."

    def has_permission(self, request, view):
        # Platform admin
        is_platform_admin = bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role == 'A' and
            request.user.is_staff
        )
        
        # School owner
        is_school_owner = bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role == 'A' and
            not request.user.is_staff
        )

        #school Instructor
        is_school_instructor = bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'I'
        )
        
        
        return is_platform_admin or is_school_owner or is_school_instructor
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
    
class IsInstructor(permissions.BasePermission):
    """
    Permission check for Instructors and Admins.
    Roles: 'I' (Instructor) or 'A' (Admin)
    """
    message = "Only instructors can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'I'
        )


class IsStudent(permissions.BasePermission):
    """
    Permission check for Students only.
    Role: 'S' (Student)
    """
    message = "Only students can perform this action."

    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'S'  
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to only allow owners or admins to edit/delete.
    - Read: Any authenticated user
    - Write/Delete: Owner or Admin
    """
    message = "You can only modify your own data."

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        user = request.user
        
        # Admins can do anything
        if user.role == 'A' and not user.is_staff:
            return True

        # Check if object has a user field
        if hasattr(obj, 'user'):
            return obj.user == user
        
        # Check through student relationship
        if hasattr(obj, 'student') and hasattr(obj.student, 'user'):
            return obj.student.user == user
        
        # For User objects, check if editing themselves
        if obj.__class__.__name__ == 'User':
            return obj == user

        return False


class IsSameSchool(permissions.BasePermission):
    """
    Check if the requesting user belongs to the same school as the resource.
    - Platform Admins bypass this check
    - Instructors and Students must be in the same school as the resource
    """
    message = "You can only access resources from your school."

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Platform admins bypass this check
        if user.role == 'A':
            return True
        
        user_school = None
        
        # Get user's school from their student profile
        if hasattr(user, 'student_profiles'):
            # Get active student profile
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                user_school = student_profile.school
        
        if not user_school:
            return False
        
        # Get object's school
        obj_school = None
        
        # Check direct school relationship
        if hasattr(obj, 'school'):
            obj_school = obj.school
        
        # Check through student_profile relationship
        elif hasattr(obj, 'student_profile') and obj.student_profile:
            obj_school = obj.student_profile.school
        
        # Check if object IS a school
        elif obj.__class__.__name__ == 'DrivingSchool':
            obj_school = obj
        
        # Check if object is a User with student profiles
        elif obj.__class__.__name__ == 'User' and hasattr(obj, 'student_profiles'):
            profile = obj.student_profiles.filter(status='A').first()
            if profile:
                obj_school = profile.school
        
        return obj_school == user_school


class HasActiveSubscription(permissions.BasePermission):
    """
    Check if the user's school has an active subscription.
    - Platform Admins bypass subscription checks
    - Other roles require their school to have an active, non-expired subscription
    """
    message = "Your school's subscription is inactive or expired."

    def has_permission(self, request, view):
        user = request.user
        
        # Platform admins bypass subscription checks
        if user.role == 'A':
            return True
        
        school = None
        
        # Get user's school from their student profile
        if hasattr(user, 'student_profiles'):
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                school = student_profile.school
        
        if not school:
            return False
        
        # Check subscription
        if hasattr(school, 'subscription'):
            subscription = school.subscription
            # Check both is_active flag and expiration
            return subscription.is_active and not subscription.is_expired()
        
        # If no subscription exists, deny access
        return False


class IsInstructorOrOwner(permissions.BasePermission):
    """
    Permission for resources that instructors can manage or users can access their own.
    - Admins: Full access
    - Instructors: Can manage students in their school
    - Students: Can only access their own resources
    """
    message = "You don't have permission to access this resource."

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Admins have full access
        if user.role == 'A':
            return True
        
        # Check if user is the owner
        if hasattr(obj, 'user') and obj.user == user:
            return True
        
        if obj.__class__.__name__ == 'User' and obj == user:
            return True
        
        # Instructors can access students in their school
        if user.role == 'I':
            user_school = None
            obj_school = None
            
            # Get instructor's school
            if hasattr(user, 'student_profiles'):
                profile = user.student_profiles.filter(status='A').first()
                if profile:
                    user_school = profile.school
            
            # Get object's school
            if hasattr(obj, 'school'):
                obj_school = obj.school
            elif hasattr(obj, 'student_profile'):
                obj_school = obj.student_profile.school
            elif obj.__class__.__name__ == 'User' and hasattr(obj, 'student_profiles'):
                profile = obj.student_profiles.filter(status='A').first()
                if profile:
                    obj_school = profile.school
            
            # Allow if same school and target is a student
            if user_school and obj_school and user_school == obj_school:
                if hasattr(obj, 'user'):
                    return obj.user.role == 'S'
                elif obj.__class__.__name__ == 'User':
                    return obj.role == 'S'
        
        return False


# permissions.py
class CanUpdateStudentProfile(permissions.BasePermission):
    """
    Permission to update student profiles with specific rules:
    - Students can update their own profile
    - Platform admins can update any profile
    - School owners can update profiles in their schools
    - Instructors CANNOT update profiles (only via update_progress action)
    """
    message = "You don't have permission to update this student profile."

    def has_permission(self, request, view):
        # Only allow authenticated users
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Platform admins can update any profile
        if user.role == 'A' and user.is_staff:
            return True
        
        # Students can only update their own profile
        if user.role == 'S':
            return obj.user == user
        
        # School owners can update profiles in their schools
        if user.role == 'A' and not user.is_staff:  # School owner
            return obj.school.owner == user
        
        # Instructors cannot update profiles directly
        # (They can only use the update_progress action)
        if user.role == 'I':
            return False
        
        return False

class CanManageSchool(permissions.BasePermission):
    """
    Permission to manage school-level resources.
    - Platform Admins: Can manage all schools
    - Instructors: Can manage their own school (if they have admin privileges)
    """
    message = "You don't have permission to manage this school."

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Platform admins can manage all schools
        if user.role == 'A':
            return True
        
        # For instructors, check if managing their own school
        if user.role == 'I':
            user_school = None
            
            if hasattr(user, 'student_profiles'):
                profile = user.student_profiles.filter(status='A').first()
                if profile:
                    user_school = profile.school
            
            # Get the school from the object
            if obj.__class__.__name__ == 'DrivingSchool':
                return obj == user_school
            elif hasattr(obj, 'school'):
                return obj.school == user_school
        
        return False