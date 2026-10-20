from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('', views.listado_reportes, name='listado'),
    path('dashboard/', views.dashboard, name='dashboard'),
]