from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from api.compat import restriccion_check
from api.inmutable import InmutableModel


class Movimiento(InmutableModel):
    """Cambio en la vida de un artículo (RF-16). Nunca se edita ni se borra
    (RNF-06): una corrección es un movimiento nuevo.

    ALTA lo crea el sistema al registrar el artículo. REUB cambia la
    ubicación, el resguardante o ambos. REPA y RETE envían y regresan de
    reparación (DEC-006). Ya no existe el tipo BAJA: "Obsoleto" es un estado
    del artículo, no un movimiento (DEC-012). Lo que no cambia se repite igual
    para que cada fila muestre el estado completo.
    """

    folio = models.CharField(max_length=20, primary_key=True)  # MOV-0001
    # Cuándo ocurrió (puede ser una fecha pasada) y cuándo se capturó.
    fecha_movimiento = models.DateTimeField(default=timezone.now)
    fecha_registro = models.DateTimeField(default=timezone.now, editable=False)
    motivo = models.CharField(max_length=255)
    articulo = models.ForeignKey(
        'articulos.Articulo', on_delete=models.PROTECT,
        db_column='articulo', related_name='movimientos')
    tipo_movimiento = models.ForeignKey(
        'catalogos.TipoMovimiento', on_delete=models.PROTECT,
        db_column='tipo_movimiento', related_name='movimientos')
    ubicacion_origen = models.ForeignKey(
        'catalogos.Ubicacion', on_delete=models.PROTECT, null=True, blank=True,
        db_column='ubicacion_origen', related_name='salidas')
    ubicacion_destino = models.ForeignKey(
        'catalogos.Ubicacion', on_delete=models.PROTECT,
        db_column='ubicacion_destino', related_name='entradas')
    resguardante_anterior = models.ForeignKey(
        'personal.Personal', on_delete=models.PROTECT, null=True, blank=True,
        db_column='resguardante_anterior', related_name='movimientos_como_anterior')
    resguardante_nuevo = models.ForeignKey(
        'personal.Personal', on_delete=models.PROTECT,
        db_column='resguardante_nuevo', related_name='movimientos_como_nuevo')
    # DEC-016: lo fija el sistema al crear el movimiento. REUB: verdadero si
    # cambió el resguardante. REPA y RETE: falso. ALTA: lo decide la API
    # (las altas históricas de bienes no localizados no generan resguardo).
    requiere_resguardo = models.BooleanField()
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        db_column='usuario', related_name='movimientos')

    class Meta:
        db_table = 'movimiento'
        ordering = ['-fecha_movimiento', '-folio']
        verbose_name = 'movimiento'
        verbose_name_plural = 'movimientos'
        indexes = [
            models.Index(fields=['articulo', 'fecha_movimiento'],
                         name='ix_movimiento_articulo_fecha'),
        ]
        constraints = [
            restriccion_check(
                (Q(tipo_movimiento='ALTA') & Q(ubicacion_origen__isnull=True)
                 & Q(resguardante_anterior__isnull=True))
                | (Q(tipo_movimiento='REUB') & Q(ubicacion_origen__isnull=False)
                   & Q(resguardante_anterior__isnull=False)
                   & (~Q(ubicacion_origen=F('ubicacion_destino'))
                      | ~Q(resguardante_anterior=F('resguardante_nuevo'))))
                | (Q(tipo_movimiento__in=['REPA', 'RETE'])
                   & Q(ubicacion_origen__isnull=False)
                   & Q(resguardante_anterior__isnull=False)
                   & Q(resguardante_anterior=F('resguardante_nuevo'))),
                'chk_movimiento_cambia_algo'),
            # DEC-016. REUB: requiere resguardo si y solo si cambió la persona.
            restriccion_check(
                Q(tipo_movimiento='ALTA')
                | (Q(tipo_movimiento='REUB') & Q(requiere_resguardo=True)
                   & ~Q(resguardante_anterior=F('resguardante_nuevo')))
                | (Q(tipo_movimiento='REUB') & Q(requiere_resguardo=False)
                   & Q(resguardante_anterior=F('resguardante_nuevo')))
                | (Q(tipo_movimiento__in=['REPA', 'RETE'])
                   & Q(requiere_resguardo=False)),
                'chk_movimiento_requiere_resguardo'),
        ]

    def __str__(self):
        return self.folio


class Resguardo(InmutableModel):
    """Documento PDF que el resguardante firma (RF-18, DEC-007, DEC-016).

    Se genera bajo demanda para uno o varios movimientos del mismo
    resguardante. El PDF emitido se conserva sin cambios (`hash_pdf` permite
    comprobarlo) y la reimpresión entrega ese mismo archivo, sin folio ni
    movimiento nuevos. Generarlo no equivale a que esté firmado.
    """

    folio = models.CharField(max_length=20, primary_key=True)  # RES-0001
    fecha_emision = models.DateTimeField(default=timezone.now, editable=False)
    resguardante = models.ForeignKey(
        'personal.Personal', on_delete=models.PROTECT,
        db_column='resguardante', related_name='resguardos')
    usuario_emisor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        db_column='usuario_emisor', related_name='resguardos_emitidos')
    # Ruta del archivo dentro de la carpeta de resguardos (RESGUARDOS_DIR).
    ruta_pdf = models.CharField(max_length=255, unique=True)
    hash_pdf = models.CharField(max_length=64)  # SHA-256 en hexadecimal

    class Meta:
        db_table = 'resguardo'
        ordering = ['-fecha_emision', '-folio']
        verbose_name = 'resguardo'
        verbose_name_plural = 'resguardos'

    def __str__(self):
        return self.folio


class ResguardoDetalle(InmutableModel):
    """Una asignación (movimiento) documentada en un resguardo. El movimiento
    es único: una asignación no se documenta dos veces. El artículo se obtiene
    por el movimiento."""

    num = models.AutoField(primary_key=True)
    resguardo = models.ForeignKey(
        Resguardo, on_delete=models.PROTECT,
        db_column='resguardo', related_name='detalles')
    movimiento = models.OneToOneField(
        Movimiento, on_delete=models.PROTECT,
        db_column='movimiento', related_name='detalle_resguardo')

    class Meta:
        db_table = 'resguardo_detalle'
        ordering = ['num']
        verbose_name = 'detalle de resguardo'
        verbose_name_plural = 'detalles de resguardo'
