from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class Rol(models.Model):
    """Perfil de acceso: ADMIN (todo, incluida la bitácora y administrar
    usuarios) o CONSULTA (consulta, historial, resguardos y reportes; no
    modifica nada ni ve la bitácora). DEC-001, RF-01, RF-02."""

    clave = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=150, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'rol'
        ordering = ['nombre']
        verbose_name = 'rol'
        verbose_name_plural = 'roles'

    def __str__(self):
        return self.nombre


class UsuarioManager(BaseUserManager):
    def create_user(self, username, password, personal, rol, **extra):
        """Crea una cuenta ligada a un empleado (RF-02).

        `personal` es una instancia de Personal y `rol` una de Rol.
        La contraseña se guarda con hash, nunca en texto plano (RNF-01).
        """
        if not username:
            raise ValueError('El nombre de usuario es obligatorio.')
        if not password:
            raise ValueError('La contraseña es obligatoria.')
        usuario = self.model(username=username, personal=personal, rol=rol, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario


class Usuario(AbstractBaseUser):
    """Cuenta de acceso al sistema, ligada a un solo empleado (RF-01, RF-02).

    - Inicio de sesión solo con usuario y contraseña, sin correo.
    - No tiene `last_login` (decisión del equipo: no se guarda último acceso).
    - La baja es lógica con `activo = False`; la cuenta nunca se borra y
      conserva su historial en la bitácora (RF-03).
    - No usa PermissionsMixin: los permisos salen del rol (ADMIN o CONSULTA).
    """

    num = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True)
    # La columna se llama `contrasena` en el diseño SQL.
    password = models.CharField(max_length=255, db_column='contrasena')
    activo = models.BooleanField(default=True)
    personal = models.OneToOneField(
        'personal.Personal',
        on_delete=models.PROTECT,
        db_column='personal',
        related_name='usuario',
    )
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column='rol',
        related_name='usuarios',
    )

    last_login = None  # quita el campo heredado de AbstractBaseUser

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    class Meta:
        db_table = 'usuario'
        ordering = ['username']
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    @property
    def is_active(self):
        """Django consulta este atributo al autenticar: una cuenta dada de
        baja no puede iniciar sesión."""
        return self.activo

    @property
    def es_administrador(self):
        return self.rol_id == 'ADMIN'

    @property
    def es_consulta(self):
        return self.rol_id == 'CONSULTA'

    def __str__(self):
        return self.username
