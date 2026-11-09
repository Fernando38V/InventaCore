/* Agrega el "ojito" para ver u ocultar lo que se escribe en los campos de
   contraseña que lleven el atributo data-ver-contrasena. */
(function () {
  var OJO = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  var OJO_TACHADO = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.9 17.9A10.4 10.4 0 0 1 12 19c-6.5 0-10-7-10-7a17 17 0 0 1 4.1-4.9M9.9 5.2A9.7 9.7 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-2.2 3.2M1 1l22 22M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';

  document.querySelectorAll('input[data-ver-contrasena]').forEach(function (input) {
    var envoltura = document.createElement('div');
    envoltura.className = 'campo-password';
    input.parentNode.insertBefore(envoltura, input);
    envoltura.appendChild(input);

    var boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'campo-password__ver';
    boton.setAttribute('aria-label', 'Mostrar contraseña');
    boton.setAttribute('aria-pressed', 'false');
    boton.innerHTML = OJO;
    envoltura.appendChild(boton);

    boton.addEventListener('click', function () {
      var mostrar = input.type === 'password';
      input.type = mostrar ? 'text' : 'password';
      boton.setAttribute('aria-pressed', String(mostrar));
      boton.setAttribute('aria-label', mostrar ? 'Ocultar contraseña' : 'Mostrar contraseña');
      boton.innerHTML = mostrar ? OJO_TACHADO : OJO;
      input.focus();
    });
  });
})();
