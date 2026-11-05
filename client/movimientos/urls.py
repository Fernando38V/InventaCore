from django.urls import path, re_path
from . import views, views_resguardos

app_name = 'movimientos'

urlpatterns = [
    path('', views.listado_movimientos, name='listado'),
    path('nuevo/', views.nuevo_movimiento, name='nuevo'),
    path('resguardos/', views_resguardos.resguardos, name='resguardos'),
    path('resguardos/emitir/', views_resguardos.emitir_resguardo, name='emitir_resguardo'),
    re_path(r'^resguardos/(?P<folio>RES-\d+)/pdf/$', views_resguardos.pdf_resguardo,
            name='pdf_resguardo'),
]