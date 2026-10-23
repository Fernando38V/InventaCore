from django.urls import path
from . import views

app_name = 'equipos'

urlpatterns = [
    path('', views.listado_equipos, name='listado'),
    path('registrar/', views.registrar_equipo, name='registrar'),
    path('detalle/<int:num>/', views.detalle_equipo, name='detalle'),
    path('detalle/<int:num>/qr/', views.qr_equipo, name='qr'),
]