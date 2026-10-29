from rest_framework.routers import DefaultRouter

from catalogos import views

router = DefaultRouter()
router.register('categorias', views.CategoriaViewSet, basename='categoria')
router.register('tipos-articulo', views.TipoArticuloViewSet, basename='tipo-articulo')
router.register('ubicaciones', views.UbicacionViewSet, basename='ubicacion')
router.register('origenes', views.OrigenViewSet, basename='origen')
router.register('estados-operativos', views.EstadoOperativoViewSet, basename='estado-operativo')
router.register('estados-registro', views.EstadoRegistroViewSet, basename='estado-registro')
router.register('tipos-movimiento', views.TipoMovimientoViewSet, basename='tipo-movimiento')
urlpatterns = router.urls
