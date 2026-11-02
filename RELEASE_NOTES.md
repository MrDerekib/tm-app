# TM App v1.1.0

## Novedades

- **Avisos de nuevas versiones:** la app comprueba GitHub al iniciar y avisa si
  hay una versión más reciente. También puedes buscarla desde **Ayuda**.
- **Prueba del TM sin display:** teclado visual con las 20 teclas del terminal,
  contadores de pulsaciones y registro de los códigos recibidos. Verificado con
  un TM físico y conexión solo de recepción.
- **Acciones ordenadas a tu gusto:** arrastra y suelta para reordenarlas en la
  lista de operaciones o en el editor de equipos. Una etiqueta muestra la acción
  y su destino; Escape cancela el arrastre. El orden se guarda por equipo.
- **Más perfiles incluidos:** Procesador DMX con 30 operaciones y Procesador MVE
  con 27, junto al perfil de VP existente.

## Correcciones

- Corregida la edición de pausas de las macros: aplicar una pausa a todos los
  pasos conserva la selección y permite seguir editando un paso concreto.
- Campos de pausa identificados e indicación cuando falta seleccionar un paso.
- Aspecto de Ayuda y de la configuración de la prueba del TM unificado con el
  resto de la interfaz.

## Actualizar

Cierra TM App y sustituye el ejecutable por el nuevo **`TM App.exe`**.
**Conserva tu carpeta `datos`** para mantener perfiles, comandos y colores.

Para añadir los perfiles nuevos a una instalación existente, descarga también
**`machines.json`**, adjunto a esta versión, y utiliza **Importar perfiles**.
Puedes seleccionar los equipos o comandos que quieras incorporar.

La app sigue siendo portable: no necesita instalación ni Python.
