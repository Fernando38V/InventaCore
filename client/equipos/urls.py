from django.urls import path

from . import views

app_name = 'equipos'

urlpatterns = [
    path('', views.listado_equipos, name='listado'),
    path('detalle/<int:num>/', views.detalle_equipo, name='detalle'),
]