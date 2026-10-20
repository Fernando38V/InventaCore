from django.urls import path
from . import views

app_name = 'auditoria'

urlpatterns = [
    path('', views.listado_auditoria, name='listado'),
]