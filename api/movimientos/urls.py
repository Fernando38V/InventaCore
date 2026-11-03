from rest_framework.routers import DefaultRouter

from movimientos.views import MovimientoViewSet

router = DefaultRouter()
router.register('movimientos', MovimientoViewSet, basename='movimiento')
urlpatterns = router.urls
