from django.db import models


class CatalogoBase(models.Model):
    """Campos comunes de los catálogos de código corto.

    Los catálogos nunca se borran: se desactivan con `activo` (RNF-06).
    """

    codigo = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        abstract = True
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Categoria(CatalogoBase):
    """Cuenta contable a la que pertenece un artículo ("Nombre de la cuenta").

    Alcance de todo el plantel. Catálogo extensible: el sistema permite
    agregar más cuentas; no hay un número fijo.
    """

    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=150, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta(CatalogoBase.Meta):
        db_table = 'categoria'
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'


class TipoArticulo(CatalogoBase):
    """Clasifica el artículo dentro de su categoría (cámara y proyector dentro
    de EQUIPOS Y APARATOS AUDIOVISUALES, silla dentro de MUEBLES...). Al dar
    de alta se elige primero la categoría y luego uno de sus tipos. Catálogo
    extensible y vacío al arrancar. El mismo nombre puede existir en dos
    categorías distintas, pero no repetirse dentro de una."""

    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=150, null=True, blank=True)
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, db_column='categoria',
        related_name='tipos')
    activo = models.BooleanField(default=True)

    class Meta(CatalogoBase.Meta):
        db_table = 'tipo_articulo'
        constraints = [
            models.UniqueConstraint(
                fields=['categoria', 'nombre'], name='uq_tipo_articulo_categoria_nombre'),
        ]
        verbose_name = 'tipo de artículo'
        verbose_name_plural = 'tipos de artículo'


class Origen(CatalogoBase):
    """Activo, Comodato o Enser. Catálogo fijo: define qué identificador lleva
    el artículo (RF-06). Los códigos ACT, COM y ENS no deben cambiar."""

    descripcion = models.CharField(max_length=150, null=True, blank=True)

    class Meta(CatalogoBase.Meta):
        db_table = 'origen'
        verbose_name = 'origen'
        verbose_name_plural = 'orígenes'


class EstadoOperativo(CatalogoBase):
    """Si el artículo sirve o no (RF-07, RF-10). Independiente del estado de
    registro. NOLOC va siempre junto con la ubicación UBI-NOLOC."""

    activo = models.BooleanField(default=True)

    class Meta(CatalogoBase.Meta):
        db_table = 'estado_operativo'
        verbose_name = 'estado operativo'
        verbose_name_plural = 'estados operativos'


class EstadoRegistro(CatalogoBase):
    """Si falta información administrativa: Pendiente, Registrado o Donado
    (RF-07). Lo calcula el sistema, no se elige a mano."""

    activo = models.BooleanField(default=True)

    class Meta(CatalogoBase.Meta):
        db_table = 'estado_registro'
        verbose_name = 'estado de registro'
        verbose_name_plural = 'estados de registro'


class TipoMovimiento(CatalogoBase):
    """ALTA, REUB, REPA, RETE y BAJA (DEC-006, RF-16). La regla de si un movimiento genera
    resguardo (RF-18) se calcula al crearlo y no se guarda aquí."""

    activo = models.BooleanField(default=True)

    class Meta(CatalogoBase.Meta):
        db_table = 'tipo_movimiento'
        verbose_name = 'tipo de movimiento'
        verbose_name_plural = 'tipos de movimiento'


class Ubicacion(models.Model):
    """Área o laboratorio donde puede estar un artículo (RF-11, RF-12, RF-13).

    UBI-NOLOC es la ubicación de los equipos no localizados y va siempre
    junto con el estado operativo NOLOC.
    """

    codigo = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=150, null=True, blank=True)
    responsable = models.ForeignKey(
        'personal.Personal',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='responsable',
        related_name='ubicaciones_a_cargo',
    )
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'ubicacion'
        ordering = ['nombre']
        verbose_name = 'ubicación'
        verbose_name_plural = 'ubicaciones'

    def __str__(self):
        return self.nombre


class ContadorFolio(models.Model):
    """Último número usado de cada serie de folios (folio interno por mes,
    MOV, RES). Se bloquea la fila al avanzarla, así dos altas simultáneas
    nunca reciben el mismo folio. Tabla `contador_folio`."""

    clave = models.CharField(max_length=30, primary_key=True)
    ultimo = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'contador_folio'
        verbose_name = 'contador de folios'
        verbose_name_plural = 'contadores de folios'

    def __str__(self):
        return '%s: %d' % (self.clave, self.ultimo)
