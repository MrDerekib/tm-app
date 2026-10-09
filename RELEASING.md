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
5. En GitHub, crea una release con la etiqueta `v1.0.0` para la primera versión.
   Usa `TM App v1.0.0` como título, añade las notas correspondientes y adjunta
   `dist/TM App.exe`.

El ejecutable se distribuye mediante Releases; `dist`, los registros de pruebas
y el entorno virtual no se añaden al historial Git. Los perfiles del usuario
permanecen en `%LOCALAPPDATA%/TM App` al reemplazar el ejecutable.
