from django.urls import path
from rest_framework.routers import DefaultRouter

from usuarios import views

router = DefaultRouter()
router.register('usuarios', views.UsuarioViewSet, basename='usuario')

urlpatterns = [
    path('auth/login/', views.LoginView.as_view()),
    path('auth/logout/', views.LogoutView.as_view()),
    path('auth/yo/', views.YoView.as_view()),
    path('auth/cambiar-password/', views.CambiarContrasenaView.as_view()),
] + router.urls
