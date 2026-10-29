import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from personal.models import Departamento, Personal
from usuarios.models import Rol, Usuario


class Command(BaseCommand):
    help = (
        'Crea la cuenta del primer Administrador y el empleado al que se liga. '
        '`createsuperuser` no sirve aquí porque toda cuenta debe estar ligada '
        'a un empleado (RF-02). Solo funciona mientras no exista un Administrador.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', help='Nombre de usuario para iniciar sesión')
        parser.add_argument('--password', help='Contraseña (si se omite, se pide por teclado)')
        parser.add_argument('--numero-empleado', help='Número de empleado del plantel')
        parser.add_argument('--nombre', help='Nombre(s) de pila')
        parser.add_argument('--primer-apellido')
        parser.add_argument('--segundo-apellido', default='')
        parser.add_argument('--puesto', default='Jefe de Informática')
        parser.add_argument('--departamento', default='DEP-INF',
                            help='Código del departamento (por defecto DEP-INF)')

    def handle(self, *args, **options):
        if Usuario.objects.filter(rol_id='ADMIN').exists():
            raise CommandError(
                'Ya existe un Administrador. Los demás usuarios se crean desde el sistema.')

        username = self._pedir(options['username'], 'Nombre de usuario')
        numero = self._pedir(options['numero_empleado'], 'Número de empleado')
        nombre = self._pedir(options['nombre'], 'Nombre(s)')
        apellido = self._pedir(options['primer_apellido'], 'Primer apellido')
        password = options['password'] or self._pedir_password()

        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError('Contraseña no válida: ' + ' '.join(error.messages))

        try:
            with transaction.atomic():
                departamento = Departamento.objects.get(pk=options['departamento'])
                personal = Personal.objects.create(
                    numero_empleado=numero,
                    nombre_pila=nombre,
                    primer_apellido=apellido,
                    segundo_apellido=options['segundo_apellido'] or None,
                    puesto=options['puesto'],
                    departamento=departamento,
                )
                Usuario.objects.create_user(
                    username=username,
                    password=password,
                    personal=personal,
                    rol=Rol.objects.get(pk='ADMIN'),
                )
        except Departamento.DoesNotExist:
            raise CommandError('No existe el departamento %r.' % options['departamento'])
        except Rol.DoesNotExist:
            raise CommandError('Falta el rol ADMIN. Ejecute primero: python manage.py migrate')
        except Exception as error:
            # Por ejemplo, nombre de usuario o número de empleado repetidos.
            # La transacción ya se deshizo: no queda nada a medias.
            raise CommandError('No se pudo crear el Administrador: %s' % error)

        self.stdout.write(self.style.SUCCESS(
            'Administrador %r creado y ligado a %s (empleado %s).'
            % (username, personal.nombre_completo, numero)))

    def _pedir(self, valor, etiqueta):
        valor = (valor or '').strip()
        if not valor:
            valor = input('%s: ' % etiqueta).strip()
        if not valor:
            raise CommandError('%s es obligatorio.' % etiqueta)
        return valor

    def _pedir_password(self):
        password = getpass.getpass('Contraseña: ')
        if password != getpass.getpass('Repita la contraseña: '):
            raise CommandError('Las contraseñas no coinciden.')
        return password
