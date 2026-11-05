"""
URL configuration for client project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path, re_path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('cuentas/', include('usuarios.urls')),
    path('articulos/', include('equipos.urls')),
    # Antes el módulo vivía en /equipos/: los enlaces y QR viejos se redirigen.
    re_path(r'^equipos/(?P<resto>.*)$',
            RedirectView.as_view(url='/articulos/%(resto)s', permanent=True, query_string=True)),
    path('movimientos/', include('movimientos.urls')),
    path('personal/', include('personal.urls')),
    path('reportes/', include('reportes.urls')),
    path('catalogos/', include('catalogos.urls')),
    path('auditoria/', include('auditoria.urls')),
    path('', RedirectView.as_view(pattern_name='usuarios:login', permanent=False)),
]