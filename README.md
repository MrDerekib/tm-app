# TM App — Terminal de Mantenimiento

App Windows independiente para comandos RS-232. Perfil inicial VP1994+:
COM1, 2400 baudios, 8N1, sin control de flujo.
El icono compacto representa el TM físico en vertical. El mismo diseño se usa
en el ejecutable, la barra de tareas, la barra de título y la cabecera.
Los datos se guardan en `%LOCALAPPDATA%/TM App`. Al abrir por primera vez esta
versión se copian los perfiles y preferencias de versiones anteriores, sin
sobrescribir los que ya existan en la carpeta nueva ni eliminar los originales.
En Windows, el mismo icono se usa en la barra de tareas al ejecutar `app.py`.

## Ejecutable para Windows

Cuando se publique una versión, descarga `TM App.exe` desde **Releases** del
repositorio y ejecútalo. No necesita instalador ni Python. Los perfiles y las
preferencias se conservan en la carpeta de datos del usuario.

## Uso

1. Ejecuta `.venv/Scripts/python.exe app.py` desde la carpeta del proyecto.
2. Selecciona el equipo y el puerto COM. El resumen muestra los parámetros
   activos; pulsa **Configurar conexión** para editar baudios, bits de datos,
   paridad, bits de parada, control de flujo e Intro en una ventana aparte.
   La VP1994+ tiene por defecto 2400, 8N1, sin control de flujo e Intro CR.
   **Aplicar** usa los nuevos valores al conectar. **Guardar para este equipo**
   también los conserva para futuras sesiones. **Cancelar** descarta los cambios.
3. Cierra HyperTerminal para liberar el puerto y pulsa **Conectar**. Selecciona
   una operación y ejecútala con **Ejecutar operación**, doble clic en la lista
   o Intro con la lista enfocada. Usa el cable RS-232 con vuestro pinout.
   Desconecta antes de cambiar parámetros. No hay modo simulado en la aplicación.
   Al conectar se envía un Intro con el terminador configurado para salir de una
   lectura continua que haya quedado activa (como el estado de fotocélulas) y
   empezar desde el prompt del equipo.
4. La consola muestra solo el texto continuo del equipo (CP850), sin marcas de tiempo
   entre fragmentos. CR vuelve al principio de la línea para sobrescribirla;
   LF avanza a la siguiente. CRLF y LFCR producen un solo salto de línea.
   La lectura de switch queda activa y actualiza los ocho bits en la misma línea.
   El estado de fotocélulas ocupa dos líneas que se actualizan en bucle.
   Con el campo de envío vacío, pulsa **Enviar** o la tecla Intro para salir de
   esa lectura; también puedes escribir un comando manual y enviarlo desde ahí.
   Cada envío manual vacía el campo y devuelve el foco a la entrada, para encadenar
   comandos con el teclado. Intro dentro del campo envía el texto carácter por
   carácter, con 200 ms entre pulsaciones; el botón **Enviar** hace lo mismo.
   Con el campo vacío, cualquiera de los dos envía solo Intro.
   **Añadir Enter** empieza
   desmarcado y controla si se añade el terminador al enviar texto, tanto con
   el teclado como con el botón **Enviar**.
   Si una operación aún está enviándose, un comando manual cancela sus pasos
   pendientes y se envía después; varios comandos manuales se ponen en cola.
   Intro con el campo vacío se transmite inmediatamente e interrumpe el envío
   en curso. Los comandos ya enviados no se deshacen.
   Los envíos y avisos aparecen en un registro separado. «Comandos enviados» solo
   indica que terminó el envío; las respuestas pueden seguir llegando después.
   El registro exportado incluye RX escapado para conservar los caracteres recibidos.
5. Guarda el registro desde la barra superior.

**Aspecto de la consola** permite elegir tipografía instalada, tamaño de 6 a 48
puntos, color de texto y color de fondo con vista previa. Pulsa **Guardar** para
aplicarlo y conservarlo entre sesiones. **Cancelar** conserva el aspecto anterior.
Las preferencias se guardan en `%LOCALAPPDATA%/TM App/appearance.json`.

Se incluyen las 16 operaciones existentes de comandos; la transferencia de firmware
queda pendiente. Las operaciones de borrado, escritura y reset piden confirmación
por defecto. **Confirmar operaciones sensibles**, debajo de **Ejecutar operación**,
permite omitir esos avisos; la elección se guarda para el usuario.
**Machaque Título** pide la cantidad al ejecutarse, proponiendo 50. Puedes cambiarla
en cada ejecución; el valor debe contener solo dígitos.
En las acciones VP1994+ que envían la clave `ABCD`, cada letra se manda por separado
con 200 ms de pausa para que el equipo pueda procesarlas. Los perfiles locales antiguos
con esa clave se actualizan al abrir la app; las demás acciones se conservan.
Cancelar detiene los siguientes pasos; no revierte comandos enviados ni garantiza
que se detenga una acción mecánica ya iniciada en el equipo.

## Añadir máquinas y operaciones

Desconecta y pulsa **Equipos y acciones**:

1. Selecciona un equipo existente o pulsa **Crear nuevo equipo**. Asigna nombre
   y parámetros RS-232 mediante los campos del formulario.
2. Pulsa **Grabar nuevo comando**, después **Grabar**, y escribe las teclas en
   el recuadro oscuro. Se captura cada pulsación en orden, incluyendo Intro,
   Tab, Esc, Retroceso, Supr y Ctrl+A…Ctrl+Z. Mayúsculas y símbolos ASCII se
   conservan tal como los produce tu teclado. La grabación no envía nada al equipo.
3. Pulsa **Detener grabación**. Asigna un nombre a la acción y, opcionalmente,
   una descripción y un mensaje de confirmación antes de ejecutarla.
4. El **Delay por tecla** configura la pausa posterior a las teclas nuevas;
   **Aplicar a todas** cambia todas las pausas. También puedes seleccionar una
   tecla y cambiar solo su pausa, eliminarla o vaciar la grabación.
   Los tiempos reales que tardes en escribir no se graban: se usa el delay elegido.
   Para pedir un dato al ejecutar cualquier macro, usa **Insertar valor variable**:
   indica el nombre de la pregunta, un valor inicial y si será número o texto.
   El paso se coloca después del paso seleccionado (o al final si no seleccionas
   ninguno). Puedes editarlo o cambiar su pausa como cualquier otro paso.
5. Pulsa **Guardar acción** y después **Guardar equipos y acciones**.

**Editar acción y pausas** permite modificar acciones existentes o continuar
su grabación. Los comandos ya incluidos conservan sus pausas originales.
**Eliminar equipo** elimina el equipo seleccionado y todas sus acciones tras
confirmarlo. La eliminación se aplica al pulsar **Guardar equipos y acciones**;
cerrar el editor sin guardar la descarta. Debe quedar al menos un equipo.
No se añade Intro automáticamente al comienzo ni al final de una grabación.
Solo se capturan las teclas dentro del recuadro; no hay captura global del teclado.
No se admiten pegado, flechas, teclas de función ni secuencias ANSI.

Los perfiles se guardan en `%LOCALAPPDATA%/TM App/machines.json` y se
conservan los que ya tengas. AutoHotkey no es una dependencia del proyecto:
las operaciones iniciales son datos y no existe un flujo de importación de scripts.

## Compartir perfiles entre usuarios

Pulsa **Exportar perfiles** y marca los equipos completos o solo las acciones
que quieres compartir. Después guarda el archivo JSON. En otro TM App, pulsa
**Importar perfiles** mientras esté desconectado, elige ese archivo y marca
qué equipos o acciones quieres añadir:

La columna **Destino local** indica dónde se importará cada equipo del archivo.
Selecciona su fila (o una de sus acciones) y usa el desplegable inferior para
elegir un equipo local, aunque tenga otro nombre, o **Crear equipo nuevo**.
Se propone un destino cuando el nombre coincide exactamente o existe una única
coincidencia ignorando mayúsculas y espacios. Puedes cambiarlo antes de continuar.
El nombre del equipo local se conserva al importar en él.

- **Equipo completo:** se importa la conexión y todas las acciones del archivo.
  Si eliges un destino local, sustituye su configuración y acciones.
- **Acciones concretas:** si eliges un destino local, conserva su conexión y las
  demás acciones; añade las seleccionadas. Si una acción tiene el mismo nombre,
  sustituye esa acción. Si eliges crear un equipo nuevo, lo crea con el nombre
  del archivo y las acciones marcadas.

Puedes combinar acciones de varios equipos del archivo en un mismo destino.
Para sustituir un equipo completo, selecciona un único equipo de origen para ese destino.

La app pide confirmación antes de cualquier sustitución. Antes de importar guarda
una copia de los perfiles locales en
`%LOCALAPPDATA%/TM App/machines.backup.json`.

Si cambias la conexión en la pantalla principal, pulsa **Guardar para este equipo**
antes de exportar para incluir los ajustes nuevos. El archivo compartido incluye
las secuencias de comandos tal como están guardadas.

## Desarrollo

Desde la carpeta del proyecto, con Python para Windows instalado:

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

```powershell
& .\.venv\Scripts\python.exe .\app.py
& .\.venv\Scripts\python.exe -m unittest -v
& .\.venv\Scripts\python.exe .\smoke_ui.py
```

Se ejecuta el código fuente; no se generan builds salvo petición explícita.
El firmware por RS-485, su migración a Windows 11 y la interpretación de
respuestas para evaluar pruebas siguen pendientes.

## Compilación manual de v1.0.0

Desde la carpeta del proyecto, con PyInstaller instalado en `.venv`:

```powershell
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean '.\TM App.spec'
```

Genera `dist/TM App.exe`, un ejecutable independiente sin instalador ni consola.
Incluye el perfil inicial, los iconos de la interfaz y el recurso de icono del
ejecutable, además de la versión 1.0.0 en las propiedades de Windows.
Los perfiles y las preferencias del usuario permanecen en `%LOCALAPPDATA%/TM App`.
Consulta [RELEASING.md](RELEASING.md) para publicar el ejecutable en GitHub y
[CHANGELOG.md](CHANGELOG.md) para las notas de versión.
