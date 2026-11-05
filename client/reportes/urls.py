from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('', views.listado_reportes, name='listado'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('excel/inventario/', views.excel_inventario, name='excel_inventario'),
    path('excel/resguardante/<int:num>/', views.excel_resguardante, name='excel_resguardante'),
]
