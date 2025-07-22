from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views


schema_view = get_schema_view(
    openapi.Info(
        title="Student Management API",
        default_version='v1',
        description="API documentation for Student Management System",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),  # Keep API endpoints under /api/
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('', include('core.urls')),  # Keep dashboard/template views under /
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


