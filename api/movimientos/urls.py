from rest_framework.routers import DefaultRouter

from movimientos.views import MovimientoViewSet, ResguardoViewSet

router = DefaultRouter()
router.register('movimientos', MovimientoViewSet, basename='movimiento')
router.register('resguardos', ResguardoViewSet, basename='resguardo')
urlpatterns = router.urls
