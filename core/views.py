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
        StudentUserProfileUpdateSerializer, StaffUserProfileCreateSerializer, StaffUserProfileUpdateSerializer 
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
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]


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
        user = self.request.user
        if user.user_type == 2:  # Staff sees their subjects
            return Attendance.objects.filter(subject__staff=user).order_by('-date')
        elif user.user_type == 3:  # Student sees their course subjects attendance
            try:
                student_profile = user.student_profile
                return Attendance.objects.filter(subject__course=student_profile.course).order_by('-date')
            except:
                return Attendance.objects.none()
        elif user.user_type == 1:  # Admin sees all
            return Attendance.objects.all().order_by('-date')
        return Attendance.objects.none()
    

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
            staff_profile = StaffProfile.objects.get(user=request.user)
            assigned_subjects = Subject.objects.filter(staff=request.user)
            
            # Get students in staff's courses
            course_ids = assigned_subjects.values_list('course_id', flat=True).distinct()
            students_count = StudentProfile.objects.filter(course_id__in=course_ids).count()
            
            # Get attendance summary
            all_reports = AttendanceReport.objects.filter(
                attendance__subject__staff=request.user
            )
            total_records = all_reports.count()
            present_records = all_reports.filter(status=True).count()
            attendance_percentage = round((present_records / total_records * 100), 2) if total_records > 0 else 0
            
            # Get recent activities
            recent_attendance = Attendance.objects.filter(
                subject__staff=request.user
            ).order_by('-date')[:5]
            
            data = {
                'assigned_subjects_count': assigned_subjects.count(),
                'students_count': students_count,
                'total_attendance_records': total_records,
                'attendance_percentage': attendance_percentage,
                'recent_activities': [
                    {
                        'subject': att.subject.name,
                        'date': att.date,
                        'students_count': att.reports.count()
                    } for att in recent_attendance
                ],
                'subjects': [
                    {
                        'id': subj.id,
                        'name': subj.name,
                        'course': subj.course.name,
                        'students_count': StudentProfile.objects.filter(course=subj.course).count()
                    } for subj in assigned_subjects
                ]
            }
            
            return Response(data)
        except StaffProfile.DoesNotExist:
            return Response({'error': 'Staff profile not found'}, status=404)



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

@login_required(login_url='login')
def student_results_view(request):
    """Student results viewing system"""
    user = request.user
    
    # Only students can access their results
    if user.user_type != 3:
        return redirect('dashboard')
    
    try:
        student_profile = StudentProfile.objects.get(user=user)
        
        # Get student's subjects and results
        subjects = Subject.objects.filter(course=student_profile.course)
        results = StudentResult.objects.filter(student=student_profile).select_related('subject')
        
        # Calculate summary statistics
        if results.exists():
            # Overall statistics
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

