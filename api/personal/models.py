from django.db import models


class Departamento(models.Model):
    """Área a la que pertenece el personal del plantel (RF-14).

    Se pueden agregar más desde el sistema. Nunca se borran: se desactivan
    con `activo` (RNF-06). Tabla `departamento` del diseño SQL.
    """

    codigo = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=150)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'departamento'
        ordering = ['nombre']
        verbose_name = 'departamento'
        verbose_name_plural = 'departamentos'

    def __str__(self):
        return self.nombre


class Personal(models.Model):
    """Empleado del plantel que puede ser resguardante de equipo (RF-14, RF-15).

    `num` es el consecutivo interno que usan las llaves foráneas.
    `numero_empleado` es el número oficial del plantel, solo para búsquedas
    y filtros. Un empleado dado de baja (`activo = False`) conserva los
    equipos a su nombre hasta que un movimiento los reasigne.
    """

    num = models.AutoField(primary_key=True)
    numero_empleado = models.CharField(max_length=20, unique=True)
    nombre_pila = models.CharField(max_length=50)
    primer_apellido = models.CharField(max_length=50)
    segundo_apellido = models.CharField(max_length=50, null=True, blank=True)
    puesto = models.CharField(max_length=50)
    activo = models.BooleanField(default=True)
    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.PROTECT,
        db_column='departamento',
        related_name='personal',
    )

    class Meta:
        db_table = 'personal'
        ordering = ['primer_apellido', 'segundo_apellido', 'nombre_pila']
        verbose_name = 'empleado'
        verbose_name_plural = 'personal'

    @property
    def nombre_completo(self):
        partes = [self.nombre_pila, self.primer_apellido, self.segundo_apellido]
        return ' '.join(p for p in partes if p)

    def __str__(self):
        return self.nombre_completo
