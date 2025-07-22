from rest_framework import generics, permissions, status as http_status
import csv
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
import tempfile
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib import messages
from django.db import models

from .models import (
    User, Course, SessionYear, 
    Subject, StaffProfile, StudentProfile, 
    Attendance, AttendanceReport, 
    StudentResult, LeaveReport, Notification,
    Feedback
)
from .serializers import (
        UserSerializer, 
        StaffCreateSerializer, 
        StudentCreateSerializer, 
        CourseSerializer, 
        SessionYearSerializer, 
        SubjectSerializer,
        StaffProfileSerializer,
        StudentProfileSerializer,
        AttendanceSerializer,
        AttendanceReportSerializer,
        StudentResultSerializer,
        LeaveReportSerializer,
        LeaveStatusUpdateSerializer,
        NotificationSerializer,
        NotificationCreateSerializer,
        FeedbackCreateSerializer, FeedbackReplySerializer,
        FeedbackSerializer, StudentUserProfileCreateSerializer, 
        StudentUserProfileUpdateSerializer, StaffUserProfileCreateSerializer, StaffUserProfileUpdateSerializer ,
   
)
from .permissions import IsAdminUserType, IsStaffUserType, IsStaffOrAdmin

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Avg, Count, Q, F, Max, Min
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

class StaffCreateView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = StaffCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUserType]

class StudentCreateView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = StudentCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUserType]


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Admin Dashboard
        if user.user_type == 1:
            data = {
                "role": "Admin",
                "stats": {
                    "total_staff": User.objects.filter(user_type=2).count(),
                    "total_students": User.objects.filter(user_type=3).count(),
                    "total_courses": Course.objects.count(),
                    "total_subjects": Subject.objects.count(),
                },
                "recent_notifications": list(
                    Notification.objects.filter(recipient=user)
                    .order_by('-created_at')[:5]
                    .values('message', 'created_at')
                ),
                "attendance_summary": {
                    "total_attendance": AttendanceReport.objects.count(),
                    "present": AttendanceReport.objects.filter(status=True).count(),
                },
                "result_summary": {
                    "average_test_score": round(
                        StudentResult.objects.aggregate(avg=Avg('test_score'))['avg'] or 0, 2
                    ),
                    "average_exam_score": round(
                        StudentResult.objects.aggregate(avg=Avg('exam_score'))['avg'] or 0, 2
                    ),
                },
            }
            return Response(data)

        # Staff Dashboard
        elif user.user_type == 2:
            assigned_subjects = Subject.objects.filter(staff=user)
            course_ids = assigned_subjects.values_list('course_id', flat=True)
            student_count = StudentProfile.objects.filter(course_id__in=course_ids).count()

            data = {
                "role": "Staff",
                "assigned_subjects": [
                    {"id": sub.id, "name": sub.name, "course": sub.course.name}
                    for sub in assigned_subjects
                ],
                "total_students_in_courses": student_count,
                "recent_feedback": list(
                    Feedback.objects.filter(user=user).order_by('-created_at')[:5].values('message', 'created_at')
                ),
            }
            return Response(data)

        # Student Dashboard
        elif user.user_type == 3:
            try:
                student_profile = StudentProfile.objects.get(user=user)
                subjects = Subject.objects.filter(course=student_profile.course)
                data = {
                    "role": "Student",
                    "course": student_profile.course.name if student_profile.course else None,
                    "session": (
                        f"{student_profile.session_year.start_year}-{student_profile.session_year.end_year}"
                        if student_profile.session_year else None
                    ),
                    "subjects": [sub.name for sub in subjects],
                    "attendance_percentage": self._calculate_student_attendance(student_profile),
                    "recent_results": list(
                        StudentResult.objects.filter(student=student_profile)
                        .order_by('-id')[:5]
                        .values('subject__name', 'test_score', 'exam_score')
                    ),
                }
                return Response(data)
            except StudentProfile.DoesNotExist:
                return Response({"error": "Student profile not found"}, status=404)

        return Response({"error": "Invalid user type"}, status=400)

    def _calculate_student_attendance(self, student_profile):
        reports = AttendanceReport.objects.filter(student=student_profile)
        total = reports.count()
        present = reports.filter(status=True).count()
        return round((present / total * 100), 2) if total > 0 else 0


# Course CRUD
@method_decorator(csrf_exempt, name='dispatch')
class CourseListCreateView(generics.ListCreateAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]


@method_decorator(csrf_exempt, name='dispatch')
class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]


# SessionYear CRUD
class SessionYearListCreateView(generics.ListCreateAPIView):
    queryset = SessionYear.objects.all()
    serializer_class = SessionYearSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]


class SessionYearDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SessionYear.objects.all()
    serializer_class = SessionYearSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]


# Subject CRUD
@method_decorator(csrf_exempt, name='dispatch')
class SubjectListCreateView(generics.ListCreateAPIView):
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter subjects based on user type"""
        user = self.request.user
        
        if user.user_type == 1:  # Admin - can see all
            return Subject.objects.all()
        elif user.user_type == 2:  # Staff - only their subjects
            return Subject.objects.filter(staff=user)
        else:  # Students - subjects in their course
            try:
                student_profile = user.student_profile
                return Subject.objects.filter(course=student_profile.course)
            except:
                return Subject.objects.none()

    def perform_create(self, serializer):
        # Only admin can create subjects
        if self.request.user.user_type != 1:
            raise PermissionDenied("Only administrators can create subjects.")
        serializer.save()


@login_required


def upload_results_view(request):
    """Staff results upload page"""
    if request.user.user_type != 2:
        messages.error(request, 'Access denied. Staff only.')
        return redirect('dashboard')
    return render(request, 'staffs/upload_results.html')

class ResultsUploadAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUserType]
    
    def get(self, request):
        """Get subjects and students for results upload"""
        try:
            # Get staff's subjects
            subjects = Subject.objects.filter(staff=request.user)
            
            # Get subject parameter if provided
            subject_id = request.GET.get('subject_id')
            students = []
            
            if subject_id:
                try:
                    subject = subjects.get(id=subject_id)
                    # Get students enrolled in this subject's course
                    students = StudentProfile.objects.filter(
                        course=subject.course
                    ).select_related('user')
                    
                    students_data = [{
                        'id': student.id,
                        'name': student.user.get_full_name(),
                        'username': student.user.username,
                        'course': student.course.name,
                        # Check if result already exists
                        'existing_result': None
                    } for student in students]
                    
                    # Check for existing results
                    for student_data in students_data:
                        try:
                            existing = StudentResult.objects.get(
                                student_id=student_data['id'],
                                subject_id=subject_id
                            )
                            student_data['existing_result'] = {
                                'test_score': existing.test_score,
                                'exam_score': existing.exam_score,
                                'id': existing.id
                            }
                        except StudentResult.DoesNotExist:
                            pass
                    
                    return Response({
                        'students': students_data,
                        'subject': {
                            'id': subject.id,
                            'name': subject.name,
                            'course': subject.course.name
                        }
                    })
                except Subject.DoesNotExist:
                    return Response({'error': 'Subject not found'}, status=404)
            
            return Response({
                'subjects': [{
                    'id': subject.id,
                    'name': subject.name,
                    'course_name': subject.course.name
                } for subject in subjects]
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    
    def post(self, request):
        """Upload/Update student results"""
        try:
            subject_id = request.data.get('subject_id')
            results_data = request.data.get('results', [])
            
            if not subject_id or not results_data:
                return Response({
                    'error': 'Subject ID and results data are required'
                }, status=400)
            
            # Verify subject belongs to this staff
            try:
                subject = Subject.objects.get(id=subject_id, staff=request.user)
            except Subject.DoesNotExist:
                return Response({
                    'error': 'Subject not found or access denied'
                }, status=404)
            
            created_count = 0
            updated_count = 0
            errors = []
            
            for result_data in results_data:
                try:
                    student_id = result_data.get('student_id')
                    test_score = float(result_data.get('test_score', 0))
                    exam_score = float(result_data.get('exam_score', 0))
                    
                    # Validate scores
                    if test_score < 0 or test_score > 100:
                        errors.append(f'Invalid test score for student {student_id}')
                        continue
                    if exam_score < 0 or exam_score > 100:
                        errors.append(f'Invalid exam score for student {student_id}')
                        continue
                    
                    # Get student
                    try:
                        student = StudentProfile.objects.get(id=student_id)
                    except StudentProfile.DoesNotExist:
                        errors.append(f'Student {student_id} not found')
                        continue
                    
                    # Create or update result
                    result, created = StudentResult.objects.update_or_create(
                        student=student,
                        subject=subject,
                        defaults={
                            'test_score': test_score,
                            'exam_score': exam_score
                        }
                    )
                    
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1
                        
                except (ValueError, TypeError) as e:
                    errors.append(f'Invalid data for student {student_id}: {str(e)}')
                except Exception as e:
                    errors.append(f'Error processing student {student_id}: {str(e)}')
            
            return Response({
                'success': True,
                'message': f'Results processed: {created_count} created, {updated_count} updated',
                'created': created_count,
                'updated': updated_count,
                'errors': errors
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)







@method_decorator(csrf_exempt, name='dispatch')
class SubjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]


@method_decorator(csrf_exempt, name='dispatch')
class StaffProfileListCreateView(generics.ListCreateAPIView):
    queryset = StaffProfile.objects.all()
    serializer_class = StaffProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StaffUserProfileCreateSerializer
        return StaffProfileSerializer


class StaffProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = StaffProfile.objects.all()
    serializer_class = StaffProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return StaffUserProfileUpdateSerializer
        return StaffProfileSerializer


class StudentProfileListCreateView(generics.ListCreateAPIView):
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StudentUserProfileCreateSerializer
        return StudentProfileSerializer




class StudentProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = StudentProfile.objects.all()
    serializer_class = StudentProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return StudentUserProfileUpdateSerializer
        return StudentProfileSerializer



class AttendanceCreateView(generics.CreateAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def perform_create(self, serializer):
        # Only staff assigned to the subject can create attendance
        subject = serializer.validated_data['subject']
        if self.request.user.user_type == 2 and subject.staff != self.request.user:
            raise PermissionDenied("You are not allowed to take attendance for this subject")
        serializer.save()


class AttendanceListView(generics.ListAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter attendance based on user type"""
        user = self.request.user
        
        if user.user_type == 1:  # Admin - can see all
            return Attendance.objects.all().order_by('-date')
        elif user.user_type == 2:  # Staff - only their subjects
            return Attendance.objects.filter(
                subject__staff=user
            ).order_by('-date')
        else:  # Students - only their course subjects
            try:
                student_profile = user.student_profile
                return Attendance.objects.filter(
                    subject__course=student_profile.course
                ).order_by('-date')
            except:
                return Attendance.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Add filtering by date range if provided
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        subject_id = request.GET.get('subject')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
            
        serializer = self.get_serializer(queryset, many=True)
        
        # Add subject names to the response
        data = []
        for item in serializer.data:
            try:
                subject = Subject.objects.get(id=item['subject'])
                item['subject_name'] = subject.name
                item['course_name'] = subject.course.name
            except Subject.DoesNotExist:
                item['subject_name'] = 'Unknown Subject'
                item['course_name'] = 'Unknown Course'
            data.append(item)
            
        return Response(data)

    

class AttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def perform_update(self, serializer):
        attendance = self.get_object()
        # Only staff who owns the subject or admin can update
        if self.request.user.user_type == 2 and attendance.subject.staff != self.request.user:
            raise PermissionDenied("You are not allowed to update this attendance")
        serializer.save()

    def perform_destroy(self, instance):
        # Only staff who owns the subject or admin can delete
        if self.request.user.user_type == 2 and instance.subject.staff != self.request.user:
            raise PermissionDenied("You are not allowed to delete this attendance")
        instance.delete()


class AttendanceAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserType]

    def get(self, request):
        user = request.user

        if user.user_type == 1:  # Admin
            total_attendance = AttendanceReport.objects.count()
            present_count = AttendanceReport.objects.filter(status=True).count()
            absent_count = total_attendance - present_count
            return Response({
                "role": "Admin",
                "total_attendance_records": total_attendance,
                "present": present_count,
                "absent": absent_count,
                "attendance_percentage": (present_count / total_attendance * 100) if total_attendance else 0
            })

        elif user.user_type == 2:  # Staff
            subjects = Subject.objects.filter(staff=user)
            reports = AttendanceReport.objects.filter(attendance__subject__in=subjects)
            total = reports.count()
            present = reports.filter(status=True).count()
            return Response({
                "role": "Staff",
                "subjects_managed": subjects.count(),
                "total_reports": total,
                "present": present,
                "attendance_percentage": (present / total * 100) if total else 0
            })

        elif user.user_type == 3:  # Student
            student_profile = StudentProfile.objects.get(user=user)
            reports = AttendanceReport.objects.filter(student=student_profile)
            total = reports.count()
            present = reports.filter(status=True).count()
            return Response({
                "role": "Student",
                "total_classes": total,
                "present": present,
                "attendance_percentage": (present / total * 100) if total else 0
            })

        return Response({"error": "Invalid user type"}, status=http_status.HTTP_400_BAD_REQUEST)

    

class StudentResultListCreateView(generics.ListCreateAPIView):
    serializer_class = StudentResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 1:  # Admin
            return StudentResult.objects.all()
        elif user.user_type == 2:  # Staff
            return StudentResult.objects.filter(subject__staff=user)
        elif user.user_type == 3:  # Student
            return StudentResult.objects.filter(student__user=user)
        return StudentResult.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.user_type == 2:
            subject = serializer.validated_data['subject']
            if subject.staff != user:
                raise PermissionDenied("You cannot add results for subjects you don't teach")
        serializer.save()


class StudentResultDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = StudentResult.objects.all()
    serializer_class = StudentResultSerializer
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if user.user_type == 2 and instance.subject.staff != user:
            raise PermissionDenied("You cannot update results for this subject")
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if user.user_type == 2 and instance.subject.staff != user:
            raise PermissionDenied("You cannot delete results for this subject")
        instance.delete()


class ResultAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserType]

    def get(self, request):
        user = request.user

        if user.user_type == 1:  # Admin
            total_results = StudentResult.objects.count()
            avg_test = StudentResult.objects.aggregate(Avg('test_score'))['test_score__avg'] or 0
            avg_exam = StudentResult.objects.aggregate(Avg('exam_score'))['exam_score__avg'] or 0

            # Subject-wise average
            subjects = Subject.objects.all()
            subject_stats = []
            for subj in subjects:
                subj_results = StudentResult.objects.filter(subject=subj)
                subj_avg_test = subj_results.aggregate(Avg('test_score'))['test_score__avg'] or 0
                subj_avg_exam = subj_results.aggregate(Avg('exam_score'))['exam_score__avg'] or 0
                subject_stats.append({
                    "subject": subj.name,
                    "avg_test": subj_avg_test,
                    "avg_exam": subj_avg_exam
                })

            return Response({
                "role": "Admin",
                "total_results": total_results,
                "avg_test_score": avg_test,
                "avg_exam_score": avg_exam,
                "subject_stats": subject_stats
            })

        elif user.user_type == 2:  # Staff
            subjects = Subject.objects.filter(staff=user)
            subject_stats = []
            for subj in subjects:
                subj_results = StudentResult.objects.filter(subject=subj)
                subj_avg_test = subj_results.aggregate(Avg('test_score'))['test_score__avg'] or 0
                subj_avg_exam = subj_results.aggregate(Avg('exam_score'))['exam_score__avg'] or 0
                subject_stats.append({
                    "subject": subj.name,
                    "avg_test": subj_avg_test,
                    "avg_exam": subj_avg_exam
                })

            return Response({
                "role": "Staff",
                "subjects_managed": len(subject_stats),
                "subject_stats": subject_stats
            })

        elif user.user_type == 3:  # Student
            student_profile = StudentProfile.objects.get(user=user)
            student_results = StudentResult.objects.filter(student=student_profile)
            avg_test = student_results.aggregate(Avg('test_score'))['test_score__avg'] or 0
            avg_exam = student_results.aggregate(Avg('exam_score'))['exam_score__avg'] or 0

            subject_stats = []
            for res in student_results:
                subject_stats.append({
                    "subject": res.subject.name,
                    "test_score": res.test_score,
                    "exam_score": res.exam_score
                })

            return Response({
                "role": "Student",
                "avg_test_score": avg_test,
                "avg_exam_score": avg_exam,
                "subject_wise_scores": subject_stats
            })

        return Response({"error": "Invalid user type"}, status=400)
    

# Create & List Leaves
class LeaveListCreateView(generics.ListCreateAPIView):
    serializer_class = LeaveReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 1:  # Admin sees all
            return LeaveReport.objects.all()
        return LeaveReport.objects.filter(user=user)  # Staff/Student see their requests

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class LeaveApproveRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserType]

    @swagger_auto_schema(
        operation_description="Update leave request status (Admin only)",
        request_body=LeaveStatusUpdateSerializer,
        responses={
            200: openapi.Response(
                description="Leave status updated successfully",
                examples={
                    "application/json": {
                        "message": "Leave status updated to Approved",
                        "id": 1,
                        "user": "John Doe",
                        "leave_date": "2024-01-15",
                        "status": "Approved"
                    }
                }
            ),
            403: "Only Admin can approve/reject leave",
            404: "Leave request not found"
        }
    )
    def patch(self, request, pk):
        if request.user.user_type != 1:  # Only Admin
            return Response({"error": "Only Admin can approve/reject leave"}, status=403)
        
        try:
            leave = LeaveReport.objects.get(pk=pk)
        except LeaveReport.DoesNotExist:
            return Response({"error": "Leave request not found"}, status=404)

        # Validate input using serializer
        serializer = LeaveStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        leave.status = serializer.validated_data['status']
        leave.save()

        return Response({
            "message": f"Leave status updated to {leave.status}",
            "id": leave.id,
            "user": leave.user.get_full_name(),
            "leave_date": leave.leave_date,
            "status": leave.status
        }, status=http_status.HTTP_200_OK)
    


# Admin sends notifications
class NotificationCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserType]

    @swagger_auto_schema(
        operation_description="Send notification to users (Admin only)",
        request_body=NotificationCreateSerializer,
        responses={
            200: openapi.Response(
                description="Notification sent successfully",
                examples={
                    "application/json": {
                        "message": "Notification sent to 25 users"
                    }
                }
            ),
            400: "Invalid request data",
            403: "Only Admin can send notifications"
        }
    )
    def post(self, request):
        if request.user.user_type != 1:
            return Response({"error": "Only Admin can send notifications"}, status=403)

        serializer = NotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        message = serializer.validated_data['message']
        recipient_type = serializer.validated_data['recipient_type']

        # Select recipients
        if recipient_type == "staff":
            recipients = User.objects.filter(user_type=2)
        elif recipient_type == "student":
            recipients = User.objects.filter(user_type=3)
        else:
            recipients = User.objects.exclude(user_type=1)  # All except Admin

        for user in recipients:
            Notification.objects.create(recipient=user, message=message)

        return Response({"message": f"Notification sent to {recipients.count()} users"})
class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')
    

class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Mark a single notification as read",
        responses={
            200: openapi.Response(description="Notification marked as read"),
            404: "Notification not found"
        }
    )
    def patch(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return Response({"error": "Notification not found"}, status=404)

        notification.is_read = True
        notification.save()
        return Response({"message": "Notification marked as read"}, status=200)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Mark all notifications for the logged-in user as read",
        responses={200: openapi.Response(description="All notifications marked as read")}
    )
    def patch(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({"message": f"{count} notifications marked as read"}, status=200)



# Create Feedback
class FeedbackCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Submit feedback (Staff/Student only)",
        request_body=FeedbackCreateSerializer,
        responses={201: "Feedback submitted successfully"}
    )
    def post(self, request):
        if request.user.user_type == 1:
            return Response({"error": "Admins cannot submit feedback"}, status=403)

        serializer = FeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        Feedback.objects.create(user=request.user, message=serializer.validated_data['message'])
        return Response({"message": "Feedback submitted successfully"}, status=201)


# List Feedback
class FeedbackListView(generics.ListAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 1:  # Admin sees all
            return Feedback.objects.select_related('user').order_by('-created_at')
        return Feedback.objects.filter(user=user).order_by('-created_at')


# Admin Reply to Feedback
class FeedbackReplyView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Reply to a feedback (Admin only)",
        request_body=FeedbackReplySerializer,
        responses={200: "Reply added successfully"}
    )
    def patch(self, request, pk):
        if request.user.user_type != 1:
            return Response({"error": "Only Admin can reply"}, status=403)

        feedback = get_object_or_404(Feedback, pk=pk)

        serializer = FeedbackReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feedback.reply = serializer.validated_data['reply']
        feedback.save()
        return Response({"message": "Reply added successfully"})
    



@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUserType])
def analytics_overview(request):
    if request.user.user_type != 1:
        return Response({"error": "Only Admin can view analytics"}, status=403)

    total_students = User.objects.filter(user_type=3).count()
    total_staff = User.objects.filter(user_type=2).count()
    total_courses = Course.objects.count()

    # Attendance Percentage
    total_attendance = AttendanceReport.objects.count()
    present_attendance = AttendanceReport.objects.filter(status=True).count()
    attendance_percentage = (present_attendance / total_attendance * 100) if total_attendance > 0 else 0

    # Average Result Performance
    avg_score = StudentResult.objects.aggregate(avg=Avg((F('test_score') + F('exam_score')) / 2))['avg']
    avg_score = round(avg_score, 2) if avg_score else 0

    return Response({
        "total_students": total_students,
        "total_staff": total_staff,
        "total_courses": total_courses,
        "attendance_percentage": attendance_percentage,
        "average_result_score": avg_score
    })



@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUserType])
def attendance_analytics(request):
    if request.user.user_type != 1:
        return Response({"error": "Only Admin can view analytics"}, status=403)

    data = AttendanceReport.objects.values('attendance__subject__name').annotate(
        total=Count('id'),
        present=Count('id', filter=Q(status=True)),
        absent=Count('id', filter=Q(status=False))
    )

    for record in data:
        total = record['total']
        record['attendance_rate'] = round((record['present'] / total) * 100, 2) if total > 0 else 0

    return Response(data)



@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUserType])
def result_analytics(request):
    if request.user.user_type != 1:
        return Response({"error": "Only Admin can view analytics"}, status=403)

    data = StudentResult.objects.values('subject__name').annotate(
        avg_score=Avg((F('test_score') + F('exam_score')) / 2)
    )

    for record in data:
        record['avg_score'] = round(record['avg_score'], 2) if record['avg_score'] else 0

    return Response(data)



# Export Attendance to CSV
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUserType])
def export_attendance_csv(request):
    if request.user.user_type != 1:
        return Response({"error": "Only Admin can export reports"}, status=403)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Student', 'Subject', 'Date', 'Status'])

    reports = AttendanceReport.objects.select_related('student', 'attendance__subject')
    for report in reports:
        writer.writerow([
            report.student.get_full_name(),
            report.attendance.subject.name,
            report.attendance.date,
            'Present' if report.status else 'Absent'
        ])

    return response



@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUserType])
def export_results_csv(request):
    if request.user.user_type != 1:
        return Response({"error": "Only Admin can export reports"}, status=403)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="results_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Student', 'Subject', 'Test Score', 'Exam Score', 'Average'])

    results = StudentResult.objects.select_related('student', 'subject')
    for result in results:
        avg = (result.test_score + result.exam_score) / 2
        writer.writerow([
            result.student.get_full_name(),
            result.subject.name,
            result.test_score,
            result.exam_score,
            avg
        ])

    return response



@login_required
def export_student_results_pdf(request):
    """Export student results as PDF"""
    try:
        if request.user.user_type == 3:  # Student
            student_profile = request.user.student_profile
            results = StudentResult.objects.filter(student=student_profile).select_related('subject')
        else:
            # For admin/staff, get student_id from query params
            student_id = request.GET.get('student_id')
            if not student_id:
                return HttpResponse('Student ID required', status=400)
            
            try:
                student_profile = StudentProfile.objects.get(id=student_id)
                results = StudentResult.objects.filter(student=student_profile).select_related('subject')
            except StudentProfile.DoesNotExist:
                return HttpResponse('Student not found', status=404)
        
        # Calculate statistics
        total_subjects = results.count()
        passed_count = 0
        failed_count = 0
        total_score = 0
        
        for result in results:
            combined_score = result.test_score + result.exam_score
            total_score += combined_score
            if combined_score >= 100:  # Pass mark is 50% of 200
                passed_count += 1
            else:
                failed_count += 1
        
        overall_average = (total_score / (total_subjects * 2)) if total_subjects > 0 else 0
        
        context = {
            'student_profile': student_profile,
            'results': results,
            'passed_count': passed_count,
            'failed_count': failed_count,
            'overall_average': overall_average,
            'current_date': datetime.datetime.now().strftime('%B %d, %Y'),
            'current_year': datetime.datetime.now().year,
        }
        
        # Render HTML template
        html_string = render_to_string('reports/results_pdf.html', context)
        
        # Generate PDF
        html = HTML(string=html_string)
        pdf = html.write_pdf()
        
        # Create response
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"results_{student_profile.user.username}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        return HttpResponse(f'Error generating PDF: {str(e)}', status=500)



@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUserType])
def export_attendance_pdf(request):
    if request.user.user_type != 1:
        return Response({"error": "Only Admin can export reports"}, status=403)

    reports = AttendanceReport.objects.select_related('student', 'attendance__subject')
    html_string = render_to_string('reports/attendance_pdf.html', {'reports': reports})

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.pdf"'

    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        HTML(string=html_string).write_pdf(target=tmp.name)
        tmp.seek(0)
        response.write(tmp.read())

    return response






# Template views


@login_required(login_url='login')
def dashboard(request):
    user = request.user
    today = timezone.now().date()
    
    context = {
        'today': today,
        'user': user
    }
    
    if user.user_type == 1:  # Admin
        context.update({
            'total_students': User.objects.filter(user_type=3).count(),
            'total_staff': User.objects.filter(user_type=2).count(),
            'total_courses': Course.objects.count(),
            'total_subjects': Subject.objects.count(),
        })
    
    elif user.user_type == 2:  # Staff
        try:
            staff_profile = StaffProfile.objects.get(user=user)
            assigned_subjects = Subject.objects.filter(staff=user)
            course_ids = assigned_subjects.values_list('course_id', flat=True)
            
            # Debug: Let's see what we're getting
            print(f"Staff: {user.username}")
            print(f"Assigned subjects: {assigned_subjects}")
            print(f"Course IDs: {list(course_ids)}")
            
            # Get students in courses where this staff teaches
            students_in_courses = StudentProfile.objects.filter(course_id__in=course_ids)
            print(f"Students in courses: {students_in_courses}")
            
            context.update({
                'assigned_subjects_count': assigned_subjects.count(),
                'total_students_in_courses': students_in_courses.count(),
                # Add debug info
                'debug_assigned_subjects': list(assigned_subjects.values('id', 'name', 'course__name')),
                'debug_course_ids': list(course_ids),
                'debug_students': list(students_in_courses.values('id', 'user__username', 'course__name')),
            })
        except StaffProfile.DoesNotExist:
            context.update({
                'assigned_subjects_count': 0,
                'total_students_in_courses': 0,
            })
    elif user.user_type == 3:  # Student
        try:
            student_profile = StudentProfile.objects.get(user=user)
            subjects = Subject.objects.filter(course=student_profile.course)
            
            # Calculate attendance percentage
            reports = AttendanceReport.objects.filter(student=student_profile)
            total_reports = reports.count()
            present_reports = reports.filter(status=True).count()
            attendance_percentage = round((present_reports / total_reports * 100), 2) if total_reports > 0 else 0
            
            # Calculate average score
            results = StudentResult.objects.filter(student=student_profile)
            if results.exists():
                avg_score = results.aggregate(
                    avg=Avg((F('test_score') + F('exam_score')) / 2)
                )['avg']
                average_score = round(avg_score, 2) if avg_score else 0
            else:
                average_score = 0
            
            context.update({
                'student_course': student_profile.course.name if student_profile.course else None,
                'student_session': f"{student_profile.session_year.start_year} - {student_profile.session_year.end_year}" if student_profile.session_year else None,
                'total_subjects': subjects.count(),
                'attendance_percentage': attendance_percentage,
                'average_score': average_score,
            })
        except StudentProfile.DoesNotExist:
            context.update({
                'student_course': None,
                'student_session': None,
                'total_subjects': 0,
                'attendance_percentage': 0,
                'average_score': 0,
            })
    
    return render(request, 'dashboard.html', context)





@login_required(login_url='login')
def students_list(request):
    students = StudentProfile.objects.select_related('user', 'course', 'session_year').all()
    return render(request, 'students/students_list.html', {'students': students})


@login_required(login_url='login')
def staff_list(request):
    staff_members = StaffProfile.objects.select_related('user').all()
    return render(request, 'staffs/staff_list.html', {'staff_members': staff_members})



# Add these new views to your existing views.py file

@login_required(login_url='login')
def staff_subjects(request):
    """Staff view to see their assigned subjects"""
    if request.user.user_type != 2:
        return redirect('dashboard')
    
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
        assigned_subjects = Subject.objects.filter(staff=request.user).select_related('course')
        
        # Get students for each subject
        subjects_with_students = []
        for subject in assigned_subjects:
            students = StudentProfile.objects.filter(course=subject.course).select_related('user')
            subjects_with_students.append({
                'subject': subject,
                'students_count': students.count(),
                'students': students
            })
        
        context = {
            'staff_profile': staff_profile,
            'subjects_with_students': subjects_with_students,
            'total_subjects': assigned_subjects.count(),
            'total_students': sum([item['students_count'] for item in subjects_with_students])
        }
        
        return render(request, 'staffs/staff_subjects.html', context)
    except StaffProfile.DoesNotExist:
        return redirect('dashboard')


@login_required(login_url='login')
def staff_students(request):
    """Staff view to see students in their courses"""
    if request.user.user_type != 2:
        return redirect('dashboard')
    
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
        assigned_subjects = Subject.objects.filter(staff=request.user)
        course_ids = assigned_subjects.values_list('course_id', flat=True).distinct()
        
        # Get all students in courses where this staff teaches
        students = StudentProfile.objects.filter(
            course_id__in=course_ids
        ).select_related('user', 'course', 'session_year')
        
        # Group students by course
        students_by_course = {}
        for student in students:
            course_name = student.course.name if student.course else 'No Course'
            if course_name not in students_by_course:
                students_by_course[course_name] = []
            students_by_course[course_name].append(student)
        
        # Get attendance summary for each student
        students_with_attendance = []
        for student in students:
            # Get attendance reports for this student in subjects taught by this staff
            reports = AttendanceReport.objects.filter(
                student=student,
                attendance__subject__staff=request.user
            )
            total_reports = reports.count()
            present_reports = reports.filter(status=True).count()
            attendance_percentage = round((present_reports / total_reports * 100), 2) if total_reports > 0 else 0
            
            students_with_attendance.append({
                'student': student,
                'total_classes': total_reports,
                'present_classes': present_reports,
                'attendance_percentage': attendance_percentage
            })
        
        context = {
            'staff_profile': staff_profile,
            'students_by_course': students_by_course,
            'students_with_attendance': students_with_attendance,
            'total_students': students.count(),
            'assigned_subjects': assigned_subjects
        }
        
        return render(request, 'staffs/staff_students.html', context)
    except StaffProfile.DoesNotExist:
        return redirect('dashboard')


@login_required(login_url='login')
def staff_attendance_summary(request):
    """Staff attendance summary and analytics"""
    if request.user.user_type != 2:
        return redirect('dashboard')
    
    try:
        staff_profile = StaffProfile.objects.get(user=request.user)
        assigned_subjects = Subject.objects.filter(staff=request.user)
        
        # Get all attendance records for this staff's subjects
        attendance_records = Attendance.objects.filter(
            subject__staff=request.user
        ).select_related('subject').order_by('-date')
        
        # Calculate summary statistics
        total_classes = attendance_records.count()
        
        # Get all attendance reports for this staff's subjects
        all_reports = AttendanceReport.objects.filter(
            attendance__subject__staff=request.user
        )
        total_student_records = all_reports.count()
        present_records = all_reports.filter(status=True).count()
        overall_attendance_percentage = round((present_records / total_student_records * 100), 2) if total_student_records > 0 else 0
        
        # Subject-wise attendance summary
        subject_summaries = []
        for subject in assigned_subjects:
            subject_reports = AttendanceReport.objects.filter(
                attendance__subject=subject
            )
            subject_total = subject_reports.count()
            subject_present = subject_reports.filter(status=True).count()
            subject_percentage = round((subject_present / subject_total * 100), 2) if subject_total > 0 else 0
            
            subject_summaries.append({
                'subject': subject,
                'total_records': subject_total,
                'present_records': subject_present,
                'attendance_percentage': subject_percentage,
                'classes_taken': Attendance.objects.filter(subject=subject).count()
            })
        
        # Recent attendance activities
        recent_activities = attendance_records[:10]
        
        context = {
            'staff_profile': staff_profile,
            'total_classes': total_classes,
            'total_student_records': total_student_records,
            'present_records': present_records,
            'overall_attendance_percentage': overall_attendance_percentage,
            'subject_summaries': subject_summaries,
            'recent_activities': recent_activities,
            'assigned_subjects_count': assigned_subjects.count()
        }
        
        return render(request, 'staffs/staff_attendance_summary.html', context)
    except StaffProfile.DoesNotExist:
        return redirect('dashboard')


# API endpoint for staff dashboard data
class StaffDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUserType]
    
    def get(self, request):
        try:
            # Get staff profile
            staff_profile = request.user.staff_profile
            
            # Get subjects taught by this staff
            subjects = Subject.objects.filter(staff=request.user)
            
            # Get students from all subjects taught by this staff
            student_profiles = StudentProfile.objects.filter(
                course__subjects__staff=request.user
            ).distinct()
            
            # Get recent attendance records for this staff's subjects
            recent_attendance = Attendance.objects.filter(
                subject__staff=request.user
            ).order_by('-created_at')[:5]
            
            # Calculate attendance statistics
            total_classes_taken = Attendance.objects.filter(
                subject__staff=request.user
            ).count()
            
            # Get attendance reports for statistics
            attendance_reports = AttendanceReport.objects.filter(
                attendance__subject__staff=request.user
            )
            
            total_attendance_records = attendance_reports.count()
            present_count = attendance_reports.filter(status=True).count()
            absent_count = total_attendance_records - present_count
            
            attendance_percentage = 0
            if total_attendance_records > 0:
                attendance_percentage = round((present_count / total_attendance_records) * 100, 1)
            
            # Get recent results uploaded by this staff
            recent_results = StudentResult.objects.filter(
                subject__staff=request.user
            ).order_by('-created_at')[:5]
            
            return Response({
                'staff_profile': {
                    'id': staff_profile.id,
                    'name': staff_profile.user.get_full_name(),
                    'username': staff_profile.user.username,
                    'email': staff_profile.user.email,
                    'phone': staff_profile.phone_number,
                    'address': staff_profile.address,
                    'gender': staff_profile.gender,
                },
                'statistics': {
                    'subjects_count': subjects.count(),
                    'students_count': student_profiles.count(),
                    'classes_taken': total_classes_taken,
                    'attendance_percentage': attendance_percentage,
                    'total_present': present_count,
                    'total_absent': absent_count,
                },
                'subjects': SubjectSerializer(subjects, many=True).data,
                'recent_attendance': [
                    {
                        'id': att.id,
                        'subject_name': att.subject.name,
                        'date': att.date,
                        'total_students': att.reports.count(),
                        'present_count': att.reports.filter(status=True).count(),
                        'absent_count': att.reports.filter(status=False).count(),
                    } for att in recent_attendance
                ],
                'recent_results': [
                    {
                        'id': result.id,
                        'student_name': result.student.user.get_full_name(),
                        'subject_name': result.subject.name,
                        'test_score': result.test_score,
                        'exam_score': result.exam_score,
                        'created_at': result.created_at.strftime('%Y-%m-%d'),
                    } for result in recent_results
                ]
            })
            
        except StaffProfile.DoesNotExist:
            return Response({
                'error': 'Staff profile not found. Please contact administrator.'
            }, status=404)
        except Exception as e:
            return Response({
                'error': f'An error occurred: {str(e)}'
            }, status=500)




@login_required(login_url='login')
def courses_list(request):
    courses = Course.objects.all()
    return render(request, 'course_subject/courses_list.html', {'courses': courses})

@login_required(login_url='login')
def subjects_list(request):
    subjects = Subject.objects.select_related('course', 'staff').all()
    return render(request, 'course_subject/subjects_list.html', {'subjects': subjects})



@login_required(login_url='login')
def attendance_list_view(request):
    return render(request, 'attendance/attendance_list.html')

@login_required(login_url='login')
def take_attendance_view(request):
    return render(request, 'attendance/take_attendance.html')

@login_required(login_url='login')
def attendance_reports_view(request):
    return render(request, 'attendance/attendance_reports.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'form': {'errors': True}})
    return render(request, 'login.html', {'form': {}})

def logout_view(request):
    logout(request)
    return redirect('login')






@login_required(login_url='login')
def student_progress_view(request):
    """Student progress tracking view"""
    user = request.user
    
    # Only students can access their progress
    if user.user_type != 3:
        return redirect('dashboard')
    
    try:
        student_profile = StudentProfile.objects.get(user=user)
        
        # Get student's subjects
        subjects = Subject.objects.filter(course=student_profile.course)
        
        # Calculate overall statistics
        results = StudentResult.objects.filter(student=student_profile)
        attendance_reports = AttendanceReport.objects.filter(student=student_profile)
        
        # Calculate GPA and averages
        if results.exists():
            avg_test_score = results.aggregate(avg=Avg('test_score'))['avg'] or 0
            avg_exam_score = results.aggregate(avg=Avg('exam_score'))['avg'] or 0
            overall_average = (avg_test_score + avg_exam_score) / 2
            gpa = calculate_gpa(overall_average)
        else:
            avg_test_score = avg_exam_score = overall_average = gpa = 0
        
        # Calculate attendance percentage
        total_attendance = attendance_reports.count()
        present_count = attendance_reports.filter(status=True).count()
        attendance_percentage = (present_count / total_attendance * 100) if total_attendance > 0 else 0
        
        # Get recent activities (last 10 results and attendance)
        recent_results = results.order_by('-created_at')[:5]
        recent_attendance = attendance_reports.order_by('-attendance__date')[:5]
        
        # Subject-wise performance
        subject_performance = []
        for subject in subjects:
            subject_results = results.filter(subject=subject)
            subject_attendance = attendance_reports.filter(attendance__subject=subject)
            
            if subject_results.exists():
                subj_avg = (subject_results.aggregate(
                    avg_test=Avg('test_score'),
                    avg_exam=Avg('exam_score')
                ))
                subj_average = ((subj_avg['avg_test'] or 0) + (subj_avg['avg_exam'] or 0)) / 2
            else:
                subj_average = 0
            
            subj_attendance_pct = 0
            if subject_attendance.exists():
                subj_present = subject_attendance.filter(status=True).count()
                subj_total = subject_attendance.count()
                subj_attendance_pct = (subj_present / subj_total * 100) if subj_total > 0 else 0
            
            subject_performance.append({
                'subject': subject,
                'average_score': round(subj_average, 1),
                'attendance_percentage': round(subj_attendance_pct, 1),
                'grade': calculate_letter_grade(subj_average),
                'status': get_performance_status(subj_average, subj_attendance_pct)
            })
        
        context = {
            'student_profile': student_profile,
            'subjects': subjects,
            'overall_gpa': round(gpa, 2),
            'overall_average': round(overall_average, 1),
            'attendance_percentage': round(attendance_percentage, 1),
            'total_subjects': subjects.count(),
            'completed_assessments': results.count(),
            'recent_results': recent_results,
            'recent_attendance': recent_attendance,
            'subject_performance': subject_performance,
            'improvement_areas': get_improvement_areas(subject_performance),
            'strengths': get_student_strengths(subject_performance),
        }
        
        return render(request, 'students/student_progress.html', context)
        
    except StudentProfile.DoesNotExist:
        return render(request, 'students/student_progress.html', {
            'error': 'Student profile not found'
        })



@login_required
def student_subjects_view(request):
    """Student subjects view"""
    if request.user.user_type != 3:
        messages.error(request, 'Access denied. Students only.')
        return redirect('dashboard')
    
    try:
        student_profile = request.user.student_profile
        subjects = Subject.objects.filter(
            course=student_profile.course
        ).select_related('staff', 'course').order_by('name')
        
        context = {
            'student_profile': student_profile,
            'subjects': subjects,
            'course': student_profile.course,
        }
        
        return render(request, 'students/student_subjects.html', context)
        
    except StudentProfile.DoesNotExist:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')

class StudentSubjectsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get student's subjects and course info"""
        if request.user.user_type != 3:
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            student_profile = request.user.student_profile
            subjects = Subject.objects.filter(
                course=student_profile.course
            ).select_related('staff', 'course')
            
            subjects_data = []
            for subject in subjects:
                # Get attendance statistics for this subject
                total_classes = Attendance.objects.filter(subject=subject).count()
                student_attendance = AttendanceReport.objects.filter(
                    attendance__subject=subject,
                    student=student_profile
                ).count()
                present_count = AttendanceReport.objects.filter(
                    attendance__subject=subject,
                    student=student_profile,
                    status=True
                ).count()
                
                attendance_percentage = 0
                if student_attendance > 0:
                    attendance_percentage = round((present_count / student_attendance) * 100, 1)
                
                # Get result for this subject
                result = None
                try:
                    student_result = StudentResult.objects.get(
                        student=student_profile,
                        subject=subject
                    )
                    result = {
                        'test_score': student_result.test_score,
                        'exam_score': student_result.exam_score,
                        'total_score': student_result.test_score + student_result.exam_score,
                        'percentage': (student_result.test_score + student_result.exam_score) / 2,
                    }
                except StudentResult.DoesNotExist:
                    pass
                
                subjects_data.append({
                    'id': subject.id,
                    'name': subject.name,
                    'staff_name': subject.staff.get_full_name(),
                    'staff_email': subject.staff.email,
                    'total_classes': total_classes,
                    'attendance_percentage': attendance_percentage,
                    'classes_attended': present_count,
                    'classes_missed': student_attendance - present_count,
                    'result': result,
                    'created_at': subject.created_at.strftime('%Y-%m-%d'),
                })
            
            return Response({
                'student_profile': {
                    'name': student_profile.user.get_full_name(),
                    'course': student_profile.course.name,
                    'session_year': f"{student_profile.session_year.start_year} - {student_profile.session_year.end_year}",
                },
                'course': {
                    'id': student_profile.course.id,
                    'name': student_profile.course.name,
                    'total_subjects': subjects.count(),
                },
                'subjects': subjects_data
            })
            
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)





@login_required(login_url='login')
def student_results_view(request):
    """Student results viewing system"""
    user = request.user
    
    # Only students can access their results
    if user.user_type != 3:
        return redirect('dashboard')
    
    try:
        student_profile = request.user.student_profile
        results = StudentResult.objects.filter(
            student=student_profile
        ).select_related('subject').order_by('subject__name')
        
        # Get student's subjects and results
        subjects = Subject.objects.filter(course=student_profile.course)
        results = StudentResult.objects.filter(student=student_profile).select_related('subject')
        
        # Calculate summary statistics
        if results.exists():
            # Overall statisticsF
            avg_test = results.aggregate(avg=Avg('test_score'))['avg'] or 0
            avg_exam = results.aggregate(avg=Avg('exam_score'))['avg'] or 0
            overall_avg = (avg_test + avg_exam) / 2
            
            # Highest scores
            highest_test = results.aggregate(max=Max('test_score'))['max'] or 0
            highest_exam = results.aggregate(max=Max('exam_score'))['max'] or 0
            highest_overall = max(highest_test, highest_exam)
            
            # GPA calculation
            gpa = calculate_gpa(overall_avg)
            
            # Grade distribution
            grade_distribution = calculate_grade_distribution(results)
            
        else:
            overall_avg = highest_overall = gpa = 0
            grade_distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        
        # Subject-wise performance summary
        subject_summary = []
        for subject in subjects:
            subject_results = results.filter(subject=subject)
            if subject_results.exists():
                subj_avg_test = subject_results.aggregate(avg=Avg('test_score'))['avg'] or 0
                subj_avg_exam = subject_results.aggregate(avg=Avg('exam_score'))['avg'] or 0
                subj_overall = (subj_avg_test + subj_avg_exam) / 2
                
                subject_summary.append({
                    'subject': subject,
                    'average_score': round(subj_overall, 1),
                    'test_average': round(subj_avg_test, 1),
                    'exam_average': round(subj_avg_exam, 1),
                    'grade': calculate_letter_grade(subj_overall),
                    'total_assessments': subject_results.count(),
                    'trend': calculate_trend(subject_results)
                })
        
        context = {
            'student_profile': student_profile,
            'subjects': subjects,
            'results': results.order_by('-created_at'),
            'overall_average': round(overall_avg, 1),
            'current_gpa': round(gpa, 2),
            'highest_score': round(highest_overall, 1),
            'highest_grade': calculate_letter_grade(highest_overall),
            'total_assessments': results.count(),
            'grade_distribution': grade_distribution,
            'subject_summary': subject_summary,
            'performance_trend': calculate_performance_trend(results),
        }
        
        return render(request, 'students/student_results.html', context)
        
    except StudentProfile.DoesNotExist:
        return render(request, 'students/student_results.html', {
            'error': 'Student profile not found'
        })



@login_required
def student_lecturers_view(request):
    """Student lecturers view"""
    if request.user.user_type != 3:
        messages.error(request, 'Access denied. Students only.')
        return redirect('dashboard')
    
    try:
        student_profile = request.user.student_profile
        
        # Get all subjects for the student's course with their staff
        subjects = Subject.objects.filter(
            course=student_profile.course
        ).select_related('staff', 'staff__staff_profile', 'course').order_by('name')
        
        # Group subjects by lecturer
        lecturers_dict = {}
        for subject in subjects:
            staff_id = subject.staff.id
            if staff_id not in lecturers_dict:
                lecturers_dict[staff_id] = {
                    'staff': subject.staff,
                    'profile': getattr(subject.staff, 'staff_profile', None),
                    'subjects': []
                }
            lecturers_dict[staff_id]['subjects'].append(subject)
        
        lecturers = list(lecturers_dict.values())
        
        context = {
            'student_profile': student_profile,
            'lecturers': lecturers,
            'total_lecturers': len(lecturers),
            'total_subjects': subjects.count(),
        }
        
        return render(request, 'students/student_lecturers.html', context)
        
    except StudentProfile.DoesNotExist:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')

class StudentLecturersAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get student's lecturers and their contact information"""
        if request.user.user_type != 3:
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            student_profile = request.user.student_profile
            
            # Get all subjects for the student's course
            subjects = Subject.objects.filter(
                course=student_profile.course
            ).select_related('staff', 'staff__staff_profile', 'course')
            
            # Group by lecturer and collect detailed information
            lecturers_dict = {}
            for subject in subjects:
                staff_id = subject.staff.id
                if staff_id not in lecturers_dict:
                    staff_profile = getattr(subject.staff, 'staff_profile', None)
                    
                    # Get teaching statistics for this lecturer
                    total_subjects_taught = Subject.objects.filter(staff=subject.staff).count()
                    
                    # Get attendance statistics for subjects taught by this lecturer to this student
                    lecturer_subjects = Subject.objects.filter(
                        staff=subject.staff,
                        course=student_profile.course
                    )
                    
                    total_classes = 0
                    attended_classes = 0
                    
                    for lec_subject in lecturer_subjects:
                        subject_attendance = AttendanceReport.objects.filter(
                            attendance__subject=lec_subject,
                            student=student_profile
                        )
                        total_classes += subject_attendance.count()
                        attended_classes += subject_attendance.filter(status=True).count()
                    
                    attendance_percentage = 0
                    if total_classes > 0:
                        attendance_percentage = round((attended_classes / total_classes) * 100, 1)
                    
                    # Get results for subjects taught by this lecturer
                    results = StudentResult.objects.filter(
                        student=student_profile,
                        subject__staff=subject.staff
                    )
                    
                    average_grade = 0
                    if results.exists():
                        total_score = sum((r.test_score + r.exam_score) for r in results)
                        average_grade = round(total_score / (results.count() * 2), 1)
                    
                    lecturers_dict[staff_id] = {
                        'id': subject.staff.id,
                        'name': subject.staff.get_full_name(),
                        'username': subject.staff.username,
                        'email': subject.staff.email,
                        'first_name': subject.staff.first_name,
                        'last_name': subject.staff.last_name,
                        'profile': {
                            'phone_number': staff_profile.phone_number if staff_profile else None,
                            'address': staff_profile.address if staff_profile else None,
                            'gender': staff_profile.gender if staff_profile else None,
                        } if staff_profile else None,
                        'subjects': [],
                        'statistics': {
                            'total_subjects_taught': total_subjects_taught,
                            'subjects_with_student': 0,  # Will be calculated below
                            'attendance_percentage': attendance_percentage,
                            'average_grade': average_grade,
                            'total_classes': total_classes,
                            'attended_classes': attended_classes,
                        }
                    }
                
                # Add subject to lecturer's list
                lecturers_dict[staff_id]['subjects'].append({
                    'id': subject.id,
                    'name': subject.name,
                    'course_name': subject.course.name,
                    'created_at': subject.created_at.strftime('%Y-%m-%d'),
                })
                
                # Update subjects count with student
                lecturers_dict[staff_id]['statistics']['subjects_with_student'] = len(lecturers_dict[staff_id]['subjects'])
            
            # Convert to list and sort by name
            lecturers_list = list(lecturers_dict.values())
            lecturers_list.sort(key=lambda x: x['name'])
            
            return Response({
                'student_profile': {
                    'name': student_profile.user.get_full_name(),
                    'course': student_profile.course.name,
                    'session_year': f"{student_profile.session_year.start_year} - {student_profile.session_year.end_year}",
                },
                'course': {
                    'id': student_profile.course.id,
                    'name': student_profile.course.name,
                },
                'lecturers': lecturers_list,
                'summary': {
                    'total_lecturers': len(lecturers_list),
                    'total_subjects': sum(len(lec['subjects']) for lec in lecturers_list),
                    'average_attendance': round(sum(lec['statistics']['attendance_percentage'] for lec in lecturers_list) / len(lecturers_list), 1) if lecturers_list else 0,
                }
            })
            
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

class SendMessageToLecturerAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Send a message/feedback to a lecturer"""
        if request.user.user_type != 3:
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            lecturer_id = request.data.get('lecturer_id')
            message = request.data.get('message', '').strip()
            subject_id = request.data.get('subject_id')  # Optional
            
            if not lecturer_id or not message:
                return Response({'error': 'Lecturer ID and message are required'}, status=400)
            
            if len(message) < 10:
                return Response({'error': 'Message must be at least 10 characters long'}, status=400)
            
            # Verify lecturer exists and teaches the student
            try:
                lecturer = User.objects.get(id=lecturer_id, user_type=2)
                student_profile = request.user.student_profile
                
                # Check if lecturer teaches any subject in student's course
                lecturer_subjects = Subject.objects.filter(
                    staff=lecturer,
                    course=student_profile.course
                )
                
                if not lecturer_subjects.exists():
                    return Response({'error': 'This lecturer does not teach in your course'}, status=400)
                
            except User.DoesNotExist:
                return Response({'error': 'Lecturer not found'}, status=404)
            
            # Create feedback/message
            subject_name = ""
            if subject_id:
                try:
                    subject_obj = Subject.objects.get(id=subject_id, staff=lecturer)
                    subject_name = f" - {subject_obj.name}"
                except Subject.DoesNotExist:
                    pass
            
            feedback_message = f"Message from {request.user.get_full_name()} ({student_profile.course.name}){subject_name}:\n\n{message}"
            
            feedback = Feedback.objects.create(
                user=request.user,
                message=feedback_message
            )
            
            # Create notification for the lecturer
            notification = Notification.objects.create(
                recipient=lecturer,
                message=f"New message from student {request.user.get_full_name()}: {message[:50]}{'...' if len(message) > 50 else ''}"
            )
            
            return Response({
                'success': True,
                'message': 'Message sent successfully to the lecturer'
            })
            
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)







@login_required
def student_attendance_view(request):
    """Student attendance view"""
    if request.user.user_type != 3:
        messages.error(request, 'Access denied. Students only.')
        return redirect('dashboard')
    
    try:
        student_profile = request.user.student_profile
        
        # Get all attendance reports for this student
        attendance_reports = AttendanceReport.objects.filter(
            student=student_profile
        ).select_related('attendance__subject', 'attendance').order_by('-attendance__date')
        
        # Calculate overall statistics
        total_classes = attendance_reports.count()
        present_count = attendance_reports.filter(status=True).count()
        absent_count = total_classes - present_count
        overall_percentage = (present_count / total_classes * 100) if total_classes > 0 else 0
        
        context = {
            'student_profile': student_profile,
            'attendance_reports': attendance_reports[:10],  # Recent 10 for template
            'total_classes': total_classes,
            'present_count': present_count,
            'absent_count': absent_count,
            'overall_percentage': round(overall_percentage, 1),
        }
        
        return render(request, 'students/student_attendance.html', context)
        
    except StudentProfile.DoesNotExist:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')

class StudentAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get student's attendance data"""
        if request.user.user_type != 3:
            return Response({'error': 'Access denied'}, status=403)
        
        try:
            student_profile = request.user.student_profile
            
            # Get query parameters for filtering
            subject_id = request.GET.get('subject_id')
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Base queryset
            attendance_reports = AttendanceReport.objects.filter(
                student=student_profile
            ).select_related('attendance__subject', 'attendance')
            
            # Apply filters
            if subject_id:
                attendance_reports = attendance_reports.filter(
                    attendance__subject_id=subject_id
                )
            
            if start_date:
                attendance_reports = attendance_reports.filter(
                    attendance__date__gte=start_date
                )
            
            if end_date:
                attendance_reports = attendance_reports.filter(
                    attendance__date__lte=end_date
                )
            
            # Order by date (most recent first)
            attendance_reports = attendance_reports.order_by('-attendance__date')
            
            # Calculate statistics
            total_classes = attendance_reports.count()
            present_count = attendance_reports.filter(status=True).count()
            absent_count = total_classes - present_count
            overall_percentage = (present_count / total_classes * 100) if total_classes > 0 else 0
            
            # Subject-wise statistics
            subject_stats = {}
            for report in attendance_reports:
                subject_name = report.attendance.subject.name
                if subject_name not in subject_stats:
                    subject_stats[subject_name] = {
                        'subject_id': report.attendance.subject.id,
                        'total': 0,
                        'present': 0,
                        'absent': 0,
                        'percentage': 0
                    }
                
                subject_stats[subject_name]['total'] += 1
                if report.status:
                    subject_stats[subject_name]['present'] += 1
                else:
                    subject_stats[subject_name]['absent'] += 1
            
            # Calculate percentages for each subject
            for subject_name, stats in subject_stats.items():
                if stats['total'] > 0:
                    stats['percentage'] = round((stats['present'] / stats['total']) * 100, 1)
            
            # Monthly attendance trend
            monthly_stats = {}
            for report in attendance_reports:
                month_key = report.attendance.date.strftime('%Y-%m')
                if month_key not in monthly_stats:
                    monthly_stats[month_key] = {'total': 0, 'present': 0}
                
                monthly_stats[month_key]['total'] += 1
                if report.status:
                    monthly_stats[month_key]['present'] += 1
            
            # Convert to list for frontend
            monthly_trend = []
            for month, stats in sorted(monthly_stats.items()):
                percentage = (stats['present'] / stats['total'] * 100) if stats['total'] > 0 else 0
                monthly_trend.append({
                    'month': month,
                    'total': stats['total'],
                    'present': stats['present'],
                    'percentage': round(percentage, 1)
                })
            
            # Prepare attendance records
            attendance_records = []
            for report in attendance_reports:
                attendance_records.append({
                    'id': report.id,
                    'subject_name': report.attendance.subject.name,
                    'date': report.attendance.date.strftime('%Y-%m-%d'),
                    'status': report.status,
                    'status_display': 'Present' if report.status else 'Absent',
                    'day_of_week': report.attendance.date.strftime('%A'),
                })
            
            return Response({
                'student_profile': {
                    'name': student_profile.user.get_full_name(),
                    'course': student_profile.course.name,
                    'session_year': f"{student_profile.session_year.start_year} - {student_profile.session_year.end_year}",
                },
                'statistics': {
                    'total_classes': total_classes,
                    'present_count': present_count,
                    'absent_count': absent_count,
                    'overall_percentage': round(overall_percentage, 1),
                },
                'subject_wise_stats': subject_stats,
                'monthly_trend': monthly_trend,
                'attendance_records': attendance_records,
                'subjects': list(Subject.objects.filter(
                    course=student_profile.course
                ).values('id', 'name'))
            })
            
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)



# Helper functions
def calculate_gpa(average_score):
    """Convert average score to GPA (4.0 scale)"""
    if average_score >= 97: return 4.0
    elif average_score >= 93: return 3.7
    elif average_score >= 90: return 3.3
    elif average_score >= 87: return 3.0
    elif average_score >= 83: return 2.7
    elif average_score >= 80: return 2.3
    elif average_score >= 77: return 2.0
    elif average_score >= 73: return 1.7
    elif average_score >= 70: return 1.3
    elif average_score >= 67: return 1.0
    elif average_score >= 65: return 0.7
    else: return 0.0

def calculate_letter_grade(score):
    """Convert numeric score to letter grade"""
    if score >= 97: return 'A+'
    elif score >= 93: return 'A'
    elif score >= 90: return 'A-'
    elif score >= 87: return 'B+'
    elif score >= 83: return 'B'
    elif score >= 80: return 'B-'
    elif score >= 77: return 'C+'
    elif score >= 73: return 'C'
    elif score >= 70: return 'C-'
    elif score >= 67: return 'D+'
    elif score >= 65: return 'D'
    else: return 'F'

def calculate_grade_distribution(results):
    """Calculate distribution of grades"""
    distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    
    for result in results:
        avg_score = (result.test_score + result.exam_score) / 2
        grade = calculate_letter_grade(avg_score)
        
        if grade.startswith('A'):
            distribution['A'] += 1
        elif grade.startswith('B'):
            distribution['B'] += 1
        elif grade.startswith('C'):
            distribution['C'] += 1
        elif grade.startswith('D'):
            distribution['D'] += 1
        else:
            distribution['F'] += 1
    
    # Convert to percentages
    total = sum(distribution.values())
    if total > 0:
        for grade in distribution:
            distribution[grade] = round((distribution[grade] / total) * 100, 1)
    
    return distribution

def get_performance_status(average_score, attendance_percentage):
    """Determine performance status based on score and attendance"""
    if average_score >= 85 and attendance_percentage >= 90:
        return 'excellent'
    elif average_score >= 75 and attendance_percentage >= 80:
        return 'good'
    elif average_score >= 65 and attendance_percentage >= 70:
        return 'average'
    else:
        return 'needs_improvement'

def get_improvement_areas(subject_performance):
    """Identify areas that need improvement"""
    areas = []
    for perf in subject_performance:
        if perf['average_score'] < 70 or perf['attendance_percentage'] < 75:
            areas.append({
                'subject': perf['subject'].name,
                'issue': 'Low performance' if perf['average_score'] < 70 else 'Poor attendance',
                'score': perf['average_score'],
                'attendance': perf['attendance_percentage']
            })
    return areas

def get_student_strengths(subject_performance):
    """Identify student's academic strengths"""
    strengths = []
    for perf in subject_performance:
        if perf['average_score'] >= 85 and perf['attendance_percentage'] >= 90:
            strengths.append({
                'subject': perf['subject'].name,
                'score': perf['average_score'],
                'grade': perf['grade']
            })
    return strengths

def calculate_trend(subject_results):
    """Calculate performance trend for a subject"""
    if subject_results.count() < 2:
        return 'stable'
    
    recent_results = subject_results.order_by('-created_at')[:3]
    older_results = subject_results.order_by('-created_at')[3:6]
    
    if recent_results.exists() and older_results.exists():
        recent_avg = sum([(r.test_score + r.exam_score) / 2 for r in recent_results]) / recent_results.count()
        older_avg = sum([(r.test_score + r.exam_score) / 2 for r in older_results]) / older_results.count()
        
        if recent_avg > older_avg + 5:
            return 'improving'
        elif recent_avg < older_avg - 5:
            return 'declining'
    
    return 'stable'

def calculate_performance_trend(results):
    """Calculate overall performance trend over time"""
    if results.count() < 4:
        return []
    
    # Group results by month
    monthly_data = {}
    for result in results:
        month_key = result.created_at.strftime('%Y-%m')
        if month_key not in monthly_data:
            monthly_data[month_key] = []
        monthly_data[month_key].append((result.test_score + result.exam_score) / 2)
    
    # Calculate monthly averages
    trend_data = []
    for month, scores in sorted(monthly_data.items()):
        avg_score = sum(scores) / len(scores)
        trend_data.append({
            'month': month,
            'average': round(avg_score, 1)
        })
    
    return trend_data[-8:]  # Last 8 months






class StaffProfileStatsAPIView(APIView):
    permission_classes = [IsStaffUserType]
    
    def get(self, request):
        staff_profile = request.user.staff_profile
        subjects = Subject.objects.filter(staff=request.user)
        
        # Calculate stats
        total_subjects = subjects.count()
        total_students = StudentProfile.objects.filter(course__in=subjects.values('course')).distinct().count()
        total_classes = Attendance.objects.filter(subject__in=subjects).count()
        
        # Calculate average attendance
        attendance_reports = AttendanceReport.objects.filter(attendance__subject__in=subjects)
        avg_attendance = attendance_reports.aggregate(
            avg=Avg('status')
        )['avg'] or 0
        avg_attendance = round(avg_attendance * 100, 1)
        
        total_courses = subjects.values('course').distinct().count()
        
        # Get subjects with stats
        subjects_data = []
        for subject in subjects:
            student_count = StudentProfile.objects.filter(course=subject.course).count()
            classes_taken = Attendance.objects.filter(subject=subject).count()
            subject_attendance = AttendanceReport.objects.filter(
                attendance__subject=subject
            ).aggregate(avg=Avg('status'))['avg'] or 0
            
            subjects_data.append({
                'name': subject.name,
                'course_name': subject.course.name,
                'student_count': student_count,
                'classes_taken': classes_taken,
                'avg_attendance': round(subject_attendance * 100, 1)
            })
        
        return Response({
            'total_subjects': total_subjects,
            'total_students': total_students,
            'total_classes': total_classes,
            'avg_attendance': avg_attendance,
            'total_courses': total_courses,
            'subjects': subjects_data
        })

class StaffProfileActivitiesAPIView(APIView):
    permission_classes = [IsStaffUserType]
    
    def get(self, request):
        # Get recent activities for staff
        activities = []
        
        # Recent attendance taken
        recent_attendance = Attendance.objects.filter(
            subject__staff=request.user
        ).order_by('-created_at')[:5]
        
        for attendance in recent_attendance:
            activities.append({
                'type': 'attendance',
                'title': f'Attendance taken for {attendance.subject.name}',
                'description': f'Recorded attendance for {attendance.date}',
                'time_ago': self.get_time_ago(attendance.created_at)
            })
        
        # Recent results uploaded
        recent_results = StudentResult.objects.filter(
            subject__staff=request.user
        ).order_by('-created_at')[:5]
        
        for result in recent_results:
            activities.append({
                'type': 'result',
                'title': f'Result uploaded for {result.student.user.get_full_name()}',
                'description': f'{result.subject.name} - Total: {result.test_score + result.exam_score}',
                'time_ago': self.get_time_ago(result.created_at)
            })
        
        # Sort by most recent
        activities.sort(key=lambda x: x['time_ago'])
        
        return Response({'activities': activities[:10]})
    
    def get_time_ago(self, datetime_obj):
        now = timezone.now()
        diff = now - datetime_obj
        
        if diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "Just now"

class StaffProfileUpdateAPIView(APIView):
    permission_classes = [IsStaffUserType]
    
    def put(self, request):
        try:
            staff_profile = request.user.staff_profile
            serializer = StaffUserProfileUpdateSerializer(staff_profile, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': 'Profile updated successfully',
                    'full_name': request.user.get_full_name()
                })
            return Response(serializer.errors, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class StudentProfileStatsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.user_type != 3:
            return Response({'error': 'Access denied'}, status=403)
            
        student_profile = request.user.student_profile
        
        # Get subjects for student's course
        subjects = Subject.objects.filter(course=student_profile.course)
        total_subjects = subjects.count()
        
        # Calculate average grade
        results = StudentResult.objects.filter(student=student_profile)
        if results.exists():
            avg_grade = results.aggregate(
                avg=Avg(models.F('test_score') + models.F('exam_score'))
            )['avg'] or 0
            average_grade = round(avg_grade, 1)
        else:
            average_grade = 0
        
        # Calculate attendance rate
        attendance_reports = AttendanceReport.objects.filter(student=student_profile)
        if attendance_reports.exists():
            attendance_rate = attendance_reports.aggregate(
                avg=Avg('status')
            )['avg'] or 0
            attendance_rate = round(attendance_rate * 100, 1)
        else:
            attendance_rate = 0
        
        total_classes = attendance_reports.count()
        total_lecturers = subjects.values('staff').distinct().count()
        
        # Get subject performance
        subject_performance = []
        for subject in subjects:
            try:
                result = StudentResult.objects.get(student=student_profile, subject=subject)
                test_score = result.test_score
                exam_score = result.exam_score
            except StudentResult.DoesNotExist:
                test_score = 0
                exam_score = 0
            
            # Get attendance for this subject
            subject_attendance = AttendanceReport.objects.filter(
                student=student_profile,
                attendance__subject=subject
            ).aggregate(avg=Avg('status'))['avg'] or 0
            
            subject_performance.append({
                'name': subject.name,
                'lecturer': subject.staff.get_full_name(),
                'attendance': round(subject_attendance * 100, 1),
                'test_score': test_score,
                'exam_score': exam_score
            })
        
        # Get attendance trend (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        attendance_trend = []
        
        return Response({
            'total_subjects': total_subjects,
            'average_grade': average_grade,
            'total_classes': total_classes,
            'attendance_rate': attendance_rate,
            'total_lecturers': total_lecturers,
            'subject_performance': subject_performance,
            'attendance_trend': attendance_trend
        })

class StudentProfileActivitiesAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        if request.user.user_type != 3:
            return Response({'error': 'Access denied'}, status=403)
            
        student_profile = request.user.student_profile
        activities = []
        
        # Recent attendance records
        recent_attendance = AttendanceReport.objects.filter(
            student=student_profile
        ).order_by('-attendance__created_at')[:5]
        
        for report in recent_attendance:
            status = "Present" if report.status else "Absent"
            activities.append({
                'type': 'attendance',
                'title': f'Attendance recorded - {status}',
                'description': f'{report.attendance.subject.name} on {report.attendance.date}',
                'time_ago': self.get_time_ago(report.attendance.created_at)
            })
        
        # Recent results
        recent_results = StudentResult.objects.filter(
            student=student_profile
        ).order_by('-created_at')[:5]
        
        for result in recent_results:
            total = result.test_score + result.exam_score
            activities.append({
                'type': 'result',
                'title': f'New result available',
                'description': f'{result.subject.name} - Score: {total}',
                'time_ago': self.get_time_ago(result.created_at)
            })
        
        return Response({'activities': activities[:10]})
    
    def get_time_ago(self, datetime_obj):
        now = timezone.now()
        diff = now - datetime_obj
        
        if diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "Just now"

class StudentProfileUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def put(self, request):
        if request.user.user_type != 3:
            return Response({'error': 'Access denied'}, status=403)
            
        try:
            student_profile = request.user.student_profile
            serializer = StudentUserProfileUpdateSerializer(student_profile, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': 'Profile updated successfully',
                    'full_name': request.user.get_full_name()
                })
            return Response(serializer.errors, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class AdminProfileStatsAPIView(APIView):
    permission_classes = [IsAdminUserType]
    
    def get(self, request):
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        total_staff = User.objects.filter(user_type=2).count()
        total_students = User.objects.filter(user_type=3).count()
        total_courses = Course.objects.count()
        
        return Response({
            'total_users': total_users,
            'active_users': active_users,
            'total_staff': total_staff,
            'total_students': total_students,
            'total_courses': total_courses
        })

class AdminProfileActivitiesAPIView(APIView):
    permission_classes = [IsAdminUserType]
    
    def get(self, request):
        activities = []
        
        # Recent user registrations
        recent_users = User.objects.order_by('-date_joined')[:5]
        for user in recent_users:
            user_type = dict(User.USER_TYPE_CHOICES)[user.user_type]
            activities.append({
                'title': f'New {user_type.lower()} registered',
                'description': f'{user.get_full_name()} joined the system',
                'time': self.get_time_ago(user.date_joined)
            })
        
        return Response({'activities': activities})
    
    def get_time_ago(self, datetime_obj):
        now = timezone.now()
        diff = now - datetime_obj
        
        if diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        else:
            return "Recently"

class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        
        if not request.user.check_password(current_password):
            return Response({'error': 'Current password is incorrect'}, status=400)
        
        if len(new_password) < 8:
            return Response({'error': 'Password must be at least 8 characters long'}, status=400)
        
        request.user.set_password(new_password)
        request.user.save()
        
        return Response({'message': 'Password changed successfully'})
    


@login_required
def profile_view(request):
    """Render appropriate profile template based on user type"""
    if request.user.user_type == 1:  # Admin
        return render(request, 'profiles/admin_profile.html')
    elif request.user.user_type == 2:  # Staff
        return render(request, 'profiles/staff_profile.html')
    elif request.user.user_type == 3:  # Student
        return render(request, 'profiles/student_profile.html')
    else:
        return redirect('login')
