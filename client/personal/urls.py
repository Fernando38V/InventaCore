from django.urls import path

from catalogos import views

app_name = 'personal'

# Las mismas vistas genéricas de catalogos, configuradas con PERSONAL.
urlpatterns = [
    path('', views.lista, {'catalogo': 'personal'}, name='listado'),
    path('nuevo/', views.nuevo, {'catalogo': 'personal'}, name='nuevo'),
    path('<int:codigo>/editar/', views.editar, {'catalogo': 'personal'}, name='editar'),
    path('<int:codigo>/estado/', views.cambiar_estado, {'catalogo': 'personal'}, name='estado'),
]
