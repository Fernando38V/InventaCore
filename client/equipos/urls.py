from django.urls import path
from . import views, views_carga, views_escaner, views_foto

app_name = 'equipos'

urlpatterns = [
    path('', views.listado_equipos, name='listado'),
    path('registrar/', views.registrar_equipo, name='registrar'),
    path('marbetes/', views.marbetes_lote, name='marbetes'),
    path('detalle/<int:num>/', views.detalle_equipo, name='detalle'),
    path('detalle/<int:num>/corregir/', views.corregir_equipo, name='corregir'),
    path('detalle/<int:num>/estado/', views.cambiar_estado_equipo, name='estado'),
    path('detalle/<int:num>/qr/', views.qr_equipo, name='qr'),
    path('detalle/<int:num>/marbete/', views.marbete_equipo, name='marbete'),
    path('detalle/<int:num>/foto/', views_foto.foto_equipo, name='foto'),
    path('detalle/<int:num>/foto/subir/', views_foto.foto_subir, name='foto_subir'),
    path('detalle/<int:num>/foto/quitar/', views_foto.foto_quitar, name='foto_quitar'),
    path('escanear/', views_escaner.escanear, name='escanear'),
    path('escanear/resolver/', views_escaner.resolver, name='resolver_qr'),
    path('carga-masiva/', views_carga.carga_masiva, name='carga_masiva'),
    path('carga-masiva/plantilla/', views_carga.plantilla_carga, name='plantilla_carga'),
    path('carga-masiva/confirmar/', views_carga.confirmar_carga, name='confirmar_carga'),
]
