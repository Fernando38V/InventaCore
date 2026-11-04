from django.urls import path

from reportes import views

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view()),
    path('reportes/inventario/', views.InventarioView.as_view()),
    path('reportes/resguardante/<int:num>/', views.ArticulosDeResguardanteView.as_view()),
    path('reportes/historial/<int:num>/', views.HistorialDeArticuloView.as_view()),
]
