from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views
from .views import (
    UserListView, 
    StaffCreateView, 
    StudentCreateView, 
    DashboardView,
    CourseListCreateView, CourseDetailView,
    SessionYearListCreateView, SessionYearDetailView,
    SubjectListCreateView, SubjectDetailView, 
    StaffProfileListCreateView, StaffProfileDetailView,
    StudentProfileListCreateView, StudentProfileDetailView, 
    AttendanceCreateView, AttendanceListView, AttendanceDetailView,
    AttendanceAnalyticsView, StudentResultListCreateView, StudentResultDetailView,
    ResultAnalyticsView, LeaveApproveRejectView, LeaveListCreateView, NotificationCreateView,
    NotificationListView, NotificationMarkAllReadView, NotificationMarkReadView,
    FeedbackCreateView, FeedbackListView, FeedbackReplyView,
    analytics_overview, attendance_analytics, result_analytics,
    export_attendance_csv, export_results_csv, export_attendance_pdf,
    login_view, logout_view,take_attendance_view, attendance_list_view, 
    attendance_reports_view, student_progress_view, student_results_view,
)

urlpatterns = [
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('register/staff/', StaffCreateView.as_view(), name='register-staff'),
    path('register/student/', StudentCreateView.as_view(), name='register-student'),
    path('api-dashboard/', DashboardView.as_view(), name='api-dashboard'),


    # Academic Management
    path('api-courses/', CourseListCreateView.as_view(), name='api-course-list-create'),
    path('api-courses/<int:pk>/', CourseDetailView.as_view(), name='api-course-detail'),

    path('api-sessions/', SessionYearListCreateView.as_view(), name='session-list-create'),
    path('api-sessions/<int:pk>/', SessionYearDetailView.as_view(), name='session-detail'),

    path('api-subjects/', SubjectListCreateView.as_view(), name='subject-list-create'),
    path('api-subjects/<int:pk>/', SubjectDetailView.as_view(), name='subject-detail'),

    path('api-staff-profiles/', StaffProfileListCreateView.as_view(), name='staff-profile-list-create'),
    path('api-staff-profiles/<int:pk>/', StaffProfileDetailView.as_view(), name='staff-profile-detail'),

    path('api-student-profiles/', StudentProfileListCreateView.as_view(), name='student-profile-list-create'),
    path('api-student-profiles/<int:pk>/', StudentProfileDetailView.as_view(), name='student-profile-detail'),
    # Student Progress and Results
    path('student/progress/', student_progress_view, name='student_progress'),
    path('student/results/', student_results_view, name='student_results'),




    # Attendance Management
    path('api-attendance/', AttendanceListView.as_view(), name='attendance-list'),
    path('api-attendance/create/', AttendanceCreateView.as_view(), name='attendance-create'),
    path('api-attendance/<int:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
    path('api-attendance/analytics/', AttendanceAnalyticsView.as_view(), name='attendance-analytics'),

    # Result Management
    path('api-results/', StudentResultListCreateView.as_view(), name='result-list-create'),
    path('api-results/<int:pk>/', StudentResultDetailView.as_view(), name='result-detail'),
    path('api-results/analytics/', ResultAnalyticsView.as_view(), name='result-analytics'),

    # Leave Management
    path('api-leave/', LeaveListCreateView.as_view(), name='leave-list-create'),
    path('api-leave/<int:pk>/status/', LeaveApproveRejectView.as_view(), name='leave-approve-reject'),

    # Notifications
    path('api-notifications/', NotificationListView.as_view(), name='notification-list'),
    path('api-notifications/send/', NotificationCreateView.as_view(), name='notification-create'),
    path('api-notifications/<int:pk>/mark-read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('api-notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),

    # Feedback
    path('api-feedback/', FeedbackListView.as_view(), name='feedback-list'),
    path('api-feedback/create/', FeedbackCreateView.as_view(), name='feedback-create'),
    path('api-feedback/<int:pk>/reply/', FeedbackReplyView.as_view(), name='feedback-reply'),

    # Analytics
    path('api-analytics/overview/', analytics_overview, name='analytics-overview'),
    path('api-analytics/attendance/', attendance_analytics, name='attendance-analytics'),
    path('api-analytics/results/', result_analytics, name='result-analytics'),


    # Reports Export
    path('api-reports/attendance/csv/', export_attendance_csv, name='attendance-export-csv'),
    path('api-reports/results/csv/', export_results_csv, name='results-export-csv'),
    path('api-reports/attendance/pdf/', export_attendance_pdf, name='attendance-export-pdf'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('students/', views.students_list, name='students_list'),

    path('staff/', views.staff_list, name='staff_list'), 
    path('staff/subjects/', views.staff_subjects, name='staff_subjects'),
    path('staff/students/', views.staff_students, name='staff_students'),
    path('staff/attendance-summary/', views.staff_attendance_summary, name='staff_attendance_summary'),
    # Staff API endpoint
    path('api/staff/dashboard/', views.StaffDashboardAPIView.as_view(), name='staff_dashboard_api'),

    path('courses/', views.courses_list, name='courses_list'),
    path('subjects/', views.subjects_list, name='subjects_list'),

    path('attendance/', attendance_list_view, name='attendance_list'),
    path('attendance/take/', take_attendance_view, name='take_attendance'),
    path('attendance/reports/', attendance_reports_view, name='attendance_reports'), 
    
     

    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'), 

    path('', views.login_view, name='home'),
]
