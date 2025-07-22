from django.db import models


from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

GENDER_CHOICES = (
    ('Male', 'Male'),
    ('Female', 'Female'),
)

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        (1, 'ADMIN'),
        (2, 'STAFF'),
        (3, 'STUDENT'),
    )
    user_type = models.PositiveSmallIntegerField(choices=USER_TYPE_CHOICES, default=3)

    def __str__(self):
        return self.get_display_name()

    def get_display_name(self):
        return self.get_full_name() or self.username
    

class Course(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SessionYear(models.Model):
    start_year = models.CharField(max_length=10)
    end_year = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.start_year} - {self.end_year}"


class Subject(models.Model):
    name = models.CharField(max_length=100)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='subjects')
    staff = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'user_type': 2}, related_name='subjects')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.course.name})"
    


class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    address = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    profile_pic = models.ImageField(upload_to='staff_pics/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} (Staff)"
    

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, related_name='students')
    session_year = models.ForeignKey(SessionYear, on_delete=models.SET_NULL, null=True, related_name='students')
    address = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    profile_pic = models.ImageField(upload_to='student_pics/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} (Student)"
    


class Attendance(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject.name} - {self.date}"


class AttendanceReport(models.Model):
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='reports')
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='attendance_reports')
    status = models.BooleanField(default=False)  # True = Present, False = Absent

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.attendance.subject.name} ({'Present' if self.status else 'Absent'})"



class StudentResult(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='results')
    test_score = models.FloatField()
    exam_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'subject')  # Prevent duplicate results for same subject

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.subject.name}"
    


class LeaveReport(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    leave_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.status}"



class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification for {self.recipient.get_full_name()}"



class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    message = models.TextField()
    reply = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback from {self.user.get_full_name()}"

