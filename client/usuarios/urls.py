from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.login_view, name='logout'),     # placeholder temporal
    path('perfil/', views.login_view, name='perfil'),      # placeholder temporal
    path('', views.login_view, name='listado'),             # placeholder temporal
]