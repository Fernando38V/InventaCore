from django.urls import path
from rest_framework.routers import DefaultRouter

from articulos.views import ArticuloViewSet
from articulos.views_carga import ConfirmarView, PlantillaView, ValidarView

router = DefaultRouter()
router.register('articulos', ArticuloViewSet, basename='articulo')
urlpatterns = [
    path('carga-masiva/plantilla/', PlantillaView.as_view()),
    path('carga-masiva/validar/', ValidarView.as_view()),
    path('carga-masiva/confirmar/', ConfirmarView.as_view()),
] + router.urls
