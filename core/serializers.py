from rest_framework import serializers
from .models import (
    User,Course, SessionYear, 
    Subject, StaffProfile, StudentProfile, 
    Attendance, AttendanceReport, StudentResult, LeaveReport,
    Notification, Feedback
)
from django.contrib.auth.hashers import make_password

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'


class StaffCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
    
    def create(self, validated_data):
        validated_data['user_type'] = 2  # Staff
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class StudentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
    
    def create(self, validated_data):
        validated_data['user_type'] = 3  # Student
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = '__all__'


class SessionYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionYear
        fields = '__all__'


class SubjectSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    staff_name = serializers.CharField(source='staff.get_full_name', read_only=True)
    
    class Meta:
        model = Subject
        fields = ['id', 'name', 'course', 'staff', 'course_name', 'staff_name', 'created_at']
        read_only_fields = ['id', 'created_at', 'course_name', 'staff_name']

    def validate(self, data):
        # Check if subject with same name exists for the same course
        if self.instance:
            # For updates, exclude current instance
            existing = Subject.objects.filter(
                name=data.get('name', self.instance.name),
                course=data.get('course', self.instance.course)
            ).exclude(id=self.instance.id)
        else:
            # For creation
            existing = Subject.objects.filter(
                name=data['name'],
                course=data['course']
            )
        
        if existing.exists():
            raise serializers.ValidationError("A subject with this name already exists for this course.")
        
        return data




class StaffProfileSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = StaffProfile
        fields = [
            'id', 'user_full_name', 'full_name', 'gender', 
            'phone_number', 'address', 'user'
        ]
        read_only_fields = ['id', 'created_at', 'user_full_name', 'full_name']

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

class StaffUserProfileCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    address = serializers.CharField(max_length=255)
    gender = serializers.ChoiceField(choices=[('Male', 'Male'), ('Female', 'Female')])
    phone_number = serializers.CharField(max_length=15)

    def create(self, validated_data):
        user_data = {
            'username': validated_data['username'],
            'password': make_password(validated_data['password']),
            'first_name': validated_data['first_name'],
            'last_name': validated_data['last_name'],
            'email': validated_data['email'],
            'user_type': 2,  # Staff
        }
        user = User.objects.create(**user_data)
        profile_data = {
            'user': user,
            'address': validated_data['address'],
            'gender': validated_data['gender'],
            'phone_number': validated_data['phone_number'],
        }
        staff_profile = StaffProfile.objects.create(**profile_data)
        return staff_profile

    def to_representation(self, instance):
        return {
            'id': instance.id,
            'username': instance.user.username,
            'full_name': instance.user.get_full_name(),
            'gender': instance.gender,
            'phone_number': instance.phone_number,
            'address': instance.address,
        }

class StaffUserProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    address = serializers.CharField(max_length=255, required=False)
    gender = serializers.ChoiceField(choices=[('Male', 'Male'), ('Female', 'Female')], required=False)
    phone_number = serializers.CharField(max_length=15, required=False)

    def update(self, instance, validated_data):
        # Update User fields
        user_fields = ['first_name', 'last_name']
        user_data = {k: v for k, v in validated_data.items() if k in user_fields}
        if user_data:
            for key, value in user_data.items():
                setattr(instance.user, key, value)
            instance.user.save()

        # Update StaffProfile fields
        profile_fields = ['address', 'gender', 'phone_number']
        profile_data = {k: v for k, v in validated_data.items() if k in profile_fields}
        if profile_data:
            for key, value in profile_data.items():
                setattr(instance, key, value)
            instance.save()

        return instance

    def to_representation(self, instance):
        return {
            'id': instance.id,
            'username': instance.user.username,
            'first_name': instance.user.first_name,
            'last_name': instance.user.last_name,
            'full_name': instance.user.get_full_name(),
            'gender': instance.gender,
            'phone_number': instance.phone_number,
            'address': instance.address,
        }


class StudentMessageSerializer(serializers.Serializer):
    lecturer_id = serializers.IntegerField()
    message = serializers.CharField(min_length=10, max_length=1000)
    subject_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_lecturer_id(self, value):
        try:
            lecturer = User.objects.get(id=value, user_type=2)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Lecturer not found")
    
    def validate_message(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Message must be at least 10 characters long")
        return value.strip()




class StudentProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    course_name = serializers.SerializerMethodField()
    session_year_display = serializers.SerializerMethodField()
    class Meta:
        model = StudentProfile
        fields = [
            'id', 'full_name', 'course_name', 'session_year_display',
            'gender', 'phone_number', 'address', 'course', 'session_year'
        ]
        read_only_fields = ['id', 'full_name', 'course_name', 'session_year_display', 'address']

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    def get_session_year_display(self, obj):
        if obj.session_year:
            return f"{obj.session_year.start_year} - {obj.session_year.end_year}"
        return ""
    
    def get_course_name(self, obj):
        return obj.course.name if obj.course else ""


class StudentUserProfileCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    session_year = serializers.PrimaryKeyRelatedField(queryset=SessionYear.objects.all())
    address = serializers.CharField(max_length=255)
    gender = serializers.ChoiceField(choices=[('Male', 'Male'), ('Female', 'Female')])
    phone_number = serializers.CharField(max_length=15)


    
    def get_full_name(self, obj):
        # Returns "First Last"
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    def get_session_year_display(self, obj):
        if obj.session_year:
            return f"{obj.session_year.start_year} - {obj.session_year.end_year}"
        return ""
    def create(self, validated_data):
        user_data = {
            'username': validated_data['username'],
            'password': make_password(validated_data['password']),
            'first_name': validated_data['first_name'],
            'last_name': validated_data['last_name'],
            'email': validated_data['email'],
            'user_type': 3,  # Student
            
        }
        user = User.objects.create(**user_data)
        profile_data = {
            'user': user,
            'course': validated_data['course'],
            'session_year': validated_data['session_year'],
            'address': validated_data['address'],
            'gender': validated_data['gender'],
            'phone_number': validated_data['phone_number'],
        }
        student_profile = StudentProfile.objects.create(**profile_data)
        return student_profile

    def to_representation(self, instance):
        return {
            'id': instance.id,
            'username': instance.user.username,
            'full_name': instance.user.get_full_name(),
            'course': instance.course.name,
            'session_year': f"{instance.session_year.start_year} - {instance.session_year.end_year}",
            'gender': instance.gender,
            'phone_number': instance.phone_number,
            'address': instance.address,
        }
    

class StudentUserProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), required=False)
    session_year = serializers.PrimaryKeyRelatedField(queryset=SessionYear.objects.all(), required=False)
    address = serializers.CharField(max_length=255, required=False)
    gender = serializers.ChoiceField(choices=[('Male', 'Male'), ('Female', 'Female')], required=False)
    phone_number = serializers.CharField(max_length=15, required=False)

    def update(self, instance, validated_data):
        # Update User fields
        user_fields = ['first_name', 'last_name']
        user_data = {k: v for k, v in validated_data.items() if k in user_fields}
        if user_data:
            for key, value in user_data.items():
                setattr(instance.user, key, value)
            instance.user.save()

        # Update StudentProfile fields
        profile_fields = ['course', 'session_year', 'address', 'gender', 'phone_number']
        profile_data = {k: v for k, v in validated_data.items() if k in profile_fields}
        if profile_data:
            for key, value in profile_data.items():
                setattr(instance, key, value)
            instance.save()

        return instance

    def to_representation(self, instance):
        return {
            'id': instance.id,
            'username': instance.user.username,
            'first_name': instance.user.first_name,
            'last_name': instance.user.last_name,
            'full_name': instance.user.get_full_name(),
            'course': instance.course.id if instance.course else None,
            'course_name': instance.course.name if instance.course else '',
            'session_year': instance.session_year.id if instance.session_year else None,
            'session_year_display': f"{instance.session_year.start_year} - {instance.session_year.end_year}" if instance.session_year else '',
            'gender': instance.gender,
            'phone_number': instance.phone_number,
            'address': instance.address,
        }





class AttendanceReportSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)

    class Meta:
        model = AttendanceReport
        fields = '__all__'


class AttendanceSerializer(serializers.ModelSerializer):
    reports = AttendanceReportSerializer(many=True)

    class Meta:
        model = Attendance
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        reports_data = validated_data.pop('reports')
        attendance = Attendance.objects.create(**validated_data)
        for report in reports_data:
            AttendanceReport.objects.create(attendance=attendance, **report)
        # Re-serialize with reports
        return attendance

    def update(self, instance, validated_data):
        reports_data = validated_data.pop('reports', None)
        instance.subject = validated_data.get('subject', instance.subject)
        instance.date = validated_data.get('date', instance.date)
        instance.save()

        if reports_data is not None:
            instance.reports.all().delete()
            for report_data in reports_data:
                AttendanceReport.objects.create(attendance=instance, **report_data)
        return instance

    def to_representation(self, instance):
        # Ensure nested reports include student names
        representation = super().to_representation(instance)
        representation['reports'] = AttendanceReportSerializer(instance.reports.all(), many=True).data
        return representation
    

class StudentResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = StudentResult
        fields = '__all__'
        read_only_fields = ['id', 'created_at']



class LeaveReportSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = LeaveReport
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at', 'status']



# Add this to your serializers.py

class LeaveStatusUpdateSerializer(serializers.Serializer):
    STATUS_CHOICES = [
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    
    def validate_status(self, value):
        if value not in ['Approved', 'Rejected']:
            raise serializers.ValidationError("Status must be either 'Approved' or 'Rejected'")
        return value
    


class NotificationSerializer(serializers.ModelSerializer):
    
    recipient_name = serializers.CharField(source='recipient.get_full_name', read_only=True)
    message = serializers.CharField()

    class Meta:
        model = Notification
        fields = serializers.ChoiceField(choices=['staff', 'student', 'all'])
        read_only_fields = ['id', 'created_at', 'is_read', 'recipient_name']


class NotificationCreateSerializer(serializers.Serializer):
    RECIPIENT_CHOICES = [
        ('staff', 'Staff'),
        ('student', 'Student'),
        ('all', 'All Users'),
    ]
    
    message = serializers.CharField(max_length=500)
    recipient_type = serializers.ChoiceField(choices=RECIPIENT_CHOICES)
    
    def validate_message(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Message must be at least 5 characters long")
        return value.strip()
    

# For creating feedback
class FeedbackCreateSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=5, max_length=1000)

# For listing feedback
class FeedbackSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = Feedback
        fields = '__all__'
        read_only_fields = ['id', 'user_name', 'reply', 'created_at']


class FeedbackReplySerializer(serializers.Serializer):
    reply = serializers.CharField(min_length=3)
    def validate_reply(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Reply must be at least 3 characters long")
        return value.strip()

