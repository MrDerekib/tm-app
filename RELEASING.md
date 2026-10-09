# Publicar una versión de TM App

La compilación y la publicación se realizan manualmente.

1. Actualiza la versión en `version_info.txt` y las notas de `CHANGELOG.md`.
2. Ejecuta las pruebas desde la carpeta del proyecto:

   ```powershell
   & .\.venv\Scripts\python.exe -m unittest -v
   & .\.venv\Scripts\python.exe .\smoke_ui.py
   ```

3. Compila el ejecutable:

   ```powershell
   & .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean '.\TM App.spec'
   ```

4. Comprueba `dist/TM App.exe` en Windows: arranque, iconos, perfiles, importación
   y comunicación con el equipo. Comprueba también que funciona sin Python instalado.
   El primer arranque crea `dist/datos` con el perfil inicial. Para comprobar un
   arranque nuevo, copia solo el exe a una carpeta vacía; para comprobar la
   portabilidad de los perfiles, copia el exe junto con `datos` a otra carpeta.
5. En GitHub, crea una release con la etiqueta `v1.0.0` para la primera versión.
   Usa `TM App v1.0.0` como título, añade las notas correspondientes y adjunta
   `dist/TM App.exe`.

El ejecutable se distribuye mediante Releases; `dist`, los registros de pruebas
y el entorno virtual no se añaden al historial Git. Tampoco se incluye la carpeta
`datos` del desarrollo ni la que se genere durante las pruebas del exe. Los
perfiles y preferencias permanecen en `datos` al reemplazar el ejecutable.
