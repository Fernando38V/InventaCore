from rest_framework.routers import DefaultRouter

from auditoria.views import BitacoraViewSet

router = DefaultRouter()
router.register('bitacora', BitacoraViewSet, basename='bitacora')
urlpatterns = router.urls
