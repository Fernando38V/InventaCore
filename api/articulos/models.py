from django.db import models
from django.db.models import Q
from django.utils import timezone

from api.compat import restriccion_check


class Articulo(models.Model):
    """Bien del plantel (antes `equipo`). Tabla `articulo` del diseño SQL.

    Lleva marbete (Activo) o folio interno (Comodato y Enser), nunca ambos
    (RF-06). Nunca se borra: se da de baja con el estado operativo AUTB
    (RF-10, RNF-06). La ubicación y el resguardante guardados aquí son los
    ACTUALES; el historial vive en `Movimiento`. Las reglas de negocio
    (estado de registro, NOLOC, folios, bitácora) las aplica la capa de
    servicios; los CHECK de abajo son la última defensa si algo se salta.
    """

    num = models.AutoField(primary_key=True)
    marbete_oficial = models.CharField(
        max_length=25, null=True, blank=True, unique=True)
    folio_interno = models.CharField(
        max_length=25, null=True, blank=True, unique=True)
    marca = models.CharField(max_length=50, null=True, blank=True)
    modelo = models.CharField(max_length=60, null=True, blank=True)
    # Único y opcional en todos los orígenes. Debe guardarse como NULL, nunca
    # como cadena vacía (el CHECK lo impide).
    num_serie = models.CharField(max_length=50, null=True, blank=True, unique=True)
    color = models.CharField(max_length=25)
    descripcion = models.CharField(max_length=150)
    fecha_adquisicion = models.DateField(null=True, blank=True)
    # NULL si el costo aún no se conoce (Pendiente) o si es Donado.
    costo_adquisicion = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    fecha_alta = models.DateTimeField(default=timezone.now, editable=False)

    # DEC-002: solo el tipo; la categoría se obtiene por tipo_articulo.categoria.
    tipo_articulo = models.ForeignKey(
        'catalogos.TipoArticulo', on_delete=models.PROTECT,
        db_column='tipo_articulo', related_name='articulos')
    ubicacion = models.ForeignKey(
        'catalogos.Ubicacion', on_delete=models.PROTECT,
        db_column='ubicacion', related_name='articulos')
    resguardante = models.ForeignKey(
        'personal.Personal', on_delete=models.PROTECT,
        db_column='resguardante', related_name='articulos')
    origen = models.ForeignKey(
        'catalogos.Origen', on_delete=models.PROTECT,
        db_column='origen', related_name='articulos')
    estado_operativo = models.ForeignKey(
        'catalogos.EstadoOperativo', on_delete=models.PROTECT,
        db_column='estado_operativo', related_name='articulos')
    estado_registro = models.ForeignKey(
        'catalogos.EstadoRegistro', on_delete=models.PROTECT,
        db_column='estado_registro', related_name='articulos')

    class Meta:
        db_table = 'articulo'
        ordering = ['num']
        verbose_name = 'artículo'
        verbose_name_plural = 'artículos'
        constraints = [
            # RF-06: Activo -> marbete y sin folio; Comodato/Enser -> folio y sin marbete.
            restriccion_check(
                (Q(origen='ACT') & Q(marbete_oficial__isnull=False)
                 & ~Q(marbete_oficial='') & Q(folio_interno__isnull=True))
                | (Q(origen__in=['COM', 'ENS']) & Q(folio_interno__isnull=False)
                   & ~Q(folio_interno='') & Q(marbete_oficial__isnull=True)),
                'chk_articulo_identificador'),
            restriccion_check(
                Q(num_serie__isnull=True) | ~Q(num_serie=''),
                'chk_articulo_serie'),
            # DEC-011: color y descripción obligatorios, y no vacíos.
            restriccion_check(~Q(color='') & ~Q(descripcion=''),
                              'chk_articulo_color_descripcion'),
            restriccion_check(
                Q(costo_adquisicion__isnull=True) | Q(costo_adquisicion__gte=0),
                'chk_articulo_costo'),
            # DEC-008: Donado tiene prioridad (su costo ni se exige ni se
            # prohíbe, PEND-004). REG: costo y fecha. PEND: le falta alguno.
            restriccion_check(
                Q(estado_registro='DON')
                | (Q(estado_registro='REG') & Q(costo_adquisicion__isnull=False)
                   & Q(fecha_adquisicion__isnull=False))
                | (Q(estado_registro='PEND')
                   & (Q(costo_adquisicion__isnull=True)
                      | Q(fecha_adquisicion__isnull=True))),
                'chk_articulo_estado_registro'),
            # UBI-NOLOC y el estado NOLOC van siempre juntos.
            restriccion_check(
                (Q(ubicacion='UBI-NOLOC') & Q(estado_operativo='NOLOC'))
                | (~Q(ubicacion='UBI-NOLOC') & ~Q(estado_operativo='NOLOC')),
                'chk_articulo_no_localizado'),
        ]

    @property
    def categoria(self):
        """DEC-002: la categoría sale del tipo."""
        return self.tipo_articulo.categoria

    @property
    def identificador(self):
        """Lo que identifica al artículo: marbete (Activo) o folio interno."""
        return self.marbete_oficial or self.folio_interno

    def __str__(self):
        return '%s - %s' % (self.identificador, self.descripcion)
