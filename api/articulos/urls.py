from rest_framework.routers import DefaultRouter

from articulos.views import ArticuloViewSet

router = DefaultRouter()
router.register('articulos', ArticuloViewSet, basename='articulo')
urlpatterns = router.urls
