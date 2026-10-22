from django.urls import path
from . import views

app_name = 'movimientos'

urlpatterns = [
    path('', views.listado_movimientos, name='listado'),
    path('nuevo/', views.nuevo_movimiento, name='nuevo'),
]