from rest_framework.routers import DefaultRouter

from personal.views import DepartamentoViewSet, PersonalViewSet

router = DefaultRouter()
router.register('departamentos', DepartamentoViewSet, basename='departamento')
router.register('personal', PersonalViewSet, basename='personal')
urlpatterns = router.urls
