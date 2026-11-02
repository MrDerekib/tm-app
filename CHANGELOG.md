# Cambios de TM App

## 1.1.0 — 2026-11-02

- Detección de nuevas versiones estables en GitHub, con comprobación automática
  al iniciar, consulta manual desde Ayuda y enlace a la descarga.
- Modo de prueba del TM sin display, con las 20 teclas, contadores y registro
  hexadecimal. Solo recibe datos; códigos de teclas verificados en un TM físico.
- Perfiles incluidos para Procesador DMX (30 operaciones) y Procesador MVE
  (27 operaciones), conservando sus secuencias y pausas.
- Reordenación de acciones mediante drag and drop en Operaciones y en el editor,
  con desplazamiento automático de listas largas y orden guardado por equipo.
- Corregida la edición de pausas de macros: «Aplicar a todas» conserva la
  selección y «Cambiar pausa seleccionada» actualiza el paso sin perderla.
- Campos de pausa identificados e indicación cuando falta seleccionar un paso.

## 1.0.0

- Terminal RS-232 con configuración editable y perfil inicial VP1994+.
- Cálculo PID incluido entre las operaciones del perfil inicial VP1994+.
- Consola con actualización de lecturas continuas y aspecto personalizable.
- Envío manual de comandos carácter por carácter y envío de Intro.
- Creación, edición y eliminación de equipos y acciones.
- Grabación de macros con pausas configurables y valores variables.
- Ejecución de operaciones mediante botón, doble clic o Intro.
- Importación y exportación selectiva de perfiles y comandos, con elección del
  equipo de destino y copia de seguridad antes de importar.
- Icono de TM App en el ejecutable, la barra de tareas y la interfaz.
- Datos portables en una carpeta `datos` junto al exe, conservados al actualizar
  el ejecutable y trasladables junto con la app.

La transferencia de firmware por RS-485 queda pendiente.
