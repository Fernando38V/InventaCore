from django.urls import path, register_converter

from . import views
from .config import CATALOGOS


class CatalogoConverter:
    """Solo acepta los cuatro catálogos de CATALOGOS (personal tiene sus URLs)."""
    regex = '|'.join(CATALOGOS)

    def to_python(self, valor):
        return valor

    def to_url(self, valor):
        return valor


register_converter(CatalogoConverter, 'catalogo')

app_name = 'catalogos'

urlpatterns = [
    path('', views.inicio, name='listado'),
    path('<catalogo:catalogo>/', views.lista, name='lista'),
    path('<catalogo:catalogo>/nuevo/', views.nuevo, name='nuevo'),
    path('<catalogo:catalogo>/<str:codigo>/editar/', views.editar, name='editar'),
    path('<catalogo:catalogo>/<str:codigo>/estado/', views.cambiar_estado, name='estado'),
]
