import app
import time
import tempfile
import streamlit as st
from doctr.io import DocumentFile

# Permite al usuario subir un archivo de imagen (JPEG o PNG)
archivo_subido = st.file_uploader(" ", type=["jpg", "jpeg", "png"])

if archivo_subido is not None:
    try:
        # Registra el tiempo de inicio del proceso
        tiempo_inicio = time.time()


        app.crear_tablas()

        # Crea un archivo temporal para almacenar la imagen subida
        with tempfile.NamedTemporaryFile(delete=False) as archivo_tmp:
            archivo_tmp.write(archivo_subido.read())
            ruta_archivo_tmp = archivo_tmp.name

        nombre_archivo = archivo_subido.name
        tipo_mime = archivo_subido.type
        ruta_foto = ruta_archivo_tmp

        # Reinicia el puntero del archivo subido
        archivo_subido.seek(0)
        imagen = archivo_subido.read()
        documento_imagen = DocumentFile.from_images(imagen)

        # Realiza el OCR sobre la imagen y procesa el resultado
        _, json_salida = app.ocr(documento_imagen)
        palabras_por_linea = app.procesar_resultado(json_salida)

        # Mostrar los resultados
        app.mostrar_resultado(palabras_por_linea, tiempo_inicio)

        # Sube la imagen a Google Drive y obtiene el enlace de descarga
        enlace = app.guardar_en_google_drive(
            ruta_foto, nombre_archivo, tipo_mime)
        st.write("Aquí está el enlace a tu archivo subido:", enlace)

        # Guardar los resultados en la base de datos
        palabras_por_linea_str = '\n'.join(
            [' '.join(linea) for linea in palabras_por_linea])

        app.guardar(archivo_subido, palabras_por_linea_str, enlace)
    except Exception as e:
        st.error(f"Ocurrió un error al procesar la imagen: {e}")
