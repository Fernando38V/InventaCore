from django.urls import path
from . import views, views_carga

app_name = 'equipos'

urlpatterns = [
    path('', views.listado_equipos, name='listado'),
    path('registrar/', views.registrar_equipo, name='registrar'),
    path('detalle/<int:num>/', views.detalle_equipo, name='detalle'),
    path('detalle/<int:num>/corregir/', views.corregir_equipo, name='corregir'),
    path('detalle/<int:num>/estado/', views.cambiar_estado_equipo, name='estado'),
    path('detalle/<int:num>/qr/', views.qr_equipo, name='qr'),
    path('carga-masiva/', views_carga.carga_masiva, name='carga_masiva'),
    path('carga-masiva/plantilla/', views_carga.plantilla_carga, name='plantilla_carga'),
    path('carga-masiva/confirmar/', views_carga.confirmar_carga, name='confirmar_carga'),
]
