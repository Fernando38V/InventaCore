from django.urls import path

from . import views, views_cuentas

app_name = 'usuarios'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views_cuentas.perfil, name='perfil'),
    # Usuarios y Roles: solo Administrador (usuarios/middleware.py).
    path('', views_cuentas.lista, name='listado'),
    path('usuarios/nuevo/', views_cuentas.nuevo, name='nuevo'),
    path('usuarios/<int:num>/editar/', views_cuentas.editar, name='editar'),
    path('usuarios/<int:num>/estado/', views_cuentas.cambiar_estado, name='estado'),
    path('usuarios/<int:num>/password/', views_cuentas.restablecer, name='restablecer'),
]
