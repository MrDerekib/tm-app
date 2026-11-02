# Publicar una versión de TM App

La compilación y la publicación se realizan manualmente.

1. Actualiza `APP_VERSION` en `app_version.py`, la versión de Windows en
   `version_info.txt` y las notas de `CHANGELOG.md` y `RELEASE_NOTES.md`.
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
   Comprueba también **Probar TM sin display**: recepción y contadores de las
   teclas, registro hexadecimal y liberación del puerto al cerrar la prueba.
5. Prepara una release en GitHub con etiqueta `v1.1.0` y título `TM App v1.1.0`.
   Usa el contenido de `RELEASE_NOTES.md` y adjunta `dist/TM App.exe` y el archivo
   `machines.json` de la raíz del proyecto. El JSON permite importar los perfiles
   incluidos sin reemplazar la carpeta de datos de una instalación existente.
   Mantén la release como borrador hasta que el exe y los adjuntos estén listos.
   Al publicarla, márcala como la última versión estable.

La app consulta las releases estables publicadas. Un commit, una etiqueta sin
release, un borrador o una prerelease no generan avisos de nueva versión.

El ejecutable se distribuye mediante Releases; `dist`, los registros de pruebas
y el entorno virtual no se añaden al historial Git. Tampoco se incluye la carpeta
`datos` del desarrollo ni la que se genere durante las pruebas del exe. Los
perfiles y preferencias permanecen en `datos` al reemplazar el ejecutable.
