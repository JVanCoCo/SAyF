import sqlite3
import sys
import time
import warnings
import tempfile
import pyperclip
import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from doctr.models import ocr_predictor
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

# ---------------------------------------------------------------- Variables ----------------------------------------------------------------

NOMBRE_BASE_DATOS = 'SAyF/documentos.db'
SCOPES = ['https://www.googleapis.com/auth/drive']
ARCHIVO_CUENTA_SERVICIO = 'SAyF/useful-maxim-415719-1f78bc2c18df.json'
ID_CARPETA_PADRE = '1kSomEHwcl6RXHxeCXMsF3KCDLBShtYKS'


@st.cache_resource
# ---------------------------------------------------------------- main --------------------------------
def main():
    # Configura la salida estándar para soportar codificación UTF-8
    sys.stdout.reconfigure(encoding='utf-8')

    # Ignora las advertencias
    warnings.filterwarnings("ignore")

    # Configuración inicial de la página de Streamlit
    st.set_page_config(
        page_title="Digitalizador de texto del `SAyF`",
        initial_sidebar_state="expanded"
    )
    # Título de la aplicación en la interfaz de usuario
    st.title("Digitalizador de texto del `SAyF`")


# ---------------------------------------------------------------- Drive ----------------------------------------------------------------
def autenticar():
    """
    Función para la autenticación de la API de Google Drive
    """
    creds = service_account.Credentials.from_service_account_file(
        ARCHIVO_CUENTA_SERVICIO)
    return creds


def guardar_en_google_drive(ruta_foto, nombre_archivo, tipo_mime):
    """
    Función para subir una foto a Google Drive
    Args:
    - ruta_foto: Ruta a la foto para subir
    - nombre_archivo: Nombre del archivo a guardar en Google Drive
    - tipo_mime: Tipo MIME del archivo
    """
    creds = autenticar()
    service = build('drive', 'v3', credentials=creds)

    metadatos_archivo = {
        'name': nombre_archivo,
        'parents': [ID_CARPETA_PADRE]
    }

    media = MediaFileUpload(ruta_foto, mimetype=tipo_mime)
    archivo = service.files().create(body=metadatos_archivo,
                                     media_body=media).execute()

    # Obtiene el enlace público del archivo
    id_archivo = archivo.get('id')

    # Genera el enlace público del archivo
    enlace = f"https://drive.google.com/uc?id={id_archivo}"

    return enlace

# ---------------------------------------------------------------- OCR ----------------------------------------------------------------


def ocr(obj):
    """
    Función para realizar el reconocimiento óptico de caracteres (OCR) en un documento.

    Args:
        item: Documento a procesar.

    Returns:
        result: Resultado del OCR.
        json_output: Resultado del OCR en formato JSON.
    """
    modelo = ocr_predictor("db_resnet50", "crnn_vgg16_bn", pretrained=True)
    resultado = modelo(obj)
    json_salida = resultado.export()
    return resultado, json_salida


def procesar_resultado(json_salida):
    """
    Procesa el resultado del OCR para extraer palabras por línea y palabras completas.

    Args:
        result: Resultado del OCR.
        json_output: Resultado del OCR en formato JSON.

    Returns:
        palabras_completas: Lista de todas las palabras encontradas.
        palabras_por_linea: Lista de listas de palabras por línea.
    """
    palabras_por_linea = [
        [palabra["value"] for palabra in linea["words"]]
        for bloque in json_salida["pages"][0]["blocks"]
        for linea in bloque["lines"]
    ]

    return palabras_por_linea

# ---------------------------------------------------------------- Streamlit ----------------------------------------------------------------


def mostrar_resultado(palabras_por_linea, tiempo_inicio):
    """
    Muestra el resultado del OCR y proporciona opciones para descargar el resultado en varios formatos.

    Args:
        palabras_por_linea: Lista de listas de palabras por línea.
        tiempo_inicio: Tiempo de inicio del procesamiento.
    """
    tiempo_transcurrido = time.time() - tiempo_inicio

    if st.button('Copiar Texto'):
        texto_para_copiar = '\n'.join([' '.join(palabras_linea)
                                       for palabras_linea in palabras_por_linea])
        pyperclip.copy(texto_para_copiar)

    st.write(f"## Texto:")
    st.sidebar.write("### Descargar Resultados")

    archivo_pdf = generar_pdf(palabras_por_linea)
    with open(archivo_pdf, 'rb') as f:
        datos_pdf = f.read()
    st.sidebar.download_button(
        label='Descargar PDF', data=datos_pdf, file_name='resultado_ocr.pdf', mime='application/pdf')

    archivo_excel = generar_excel(palabras_por_linea)
    with open(archivo_excel, 'rb') as f:
        datos_excel = f.read()
    st.sidebar.download_button(label='Descargar Excel', data=datos_excel, file_name='resultado_ocr.xlsx',
                               mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    archivo_word = generar_word(palabras_por_linea)
    with open(archivo_word, 'rb') as f:
        datos_word = f.read()
    st.sidebar.download_button(label='Descargar Word', data=datos_word, file_name='resultado_ocr.docx',
                               mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    if st.sidebar.button('Copiar texto'):
        texto_para_copiar = '\n'.join([' '.join(palabras_linea)
                                       for palabras_linea in palabras_por_linea])
        pyperclip.copy(texto_para_copiar)

    for palabras_linea in palabras_por_linea:
        st.write(" ".join(palabras_linea))

    st.write(f"### Tiempo transcurrido: `{tiempo_transcurrido:.2f} segundos`")


def generar_pdf(palabras_por_linea):
    """
    Genera un archivo PDF con el texto procesado.

    Args:
        palabras_por_linea: Lista de listas de palabras por línea.

    Returns:
        nombre_archivo_pdf: Nombre del archivo PDF generado.
    """
    ruta_fuente = 'SAyF/Roboto/Roboto-Black.ttf'
    try:
        pdfmetrics.registerFont(TTFont('Roboto', ruta_fuente))
        nombre_fuente = 'Roboto'
    except Exception as e:
        st.error(f"Error al cargar la fuente {ruta_fuente}: {e}")
        nombre_fuente = 'Helvetica'  # Fallback to default font
        st.warning(
            f"No se pudo cargar la fuente {ruta_fuente}, usando {nombre_fuente}")

    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as archivo_tmp:
        nombre_archivo_pdf = archivo_tmp.name

    doc = SimpleDocTemplate(nombre_archivo_pdf, pagesize=letter)
    elementos = []

    datos = [[' '.join(linea)] for linea in palabras_por_linea]
    tabla = Table(datos)
    tabla.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                               ('FONTNAME', (0, 0), (-1, -1), nombre_fuente)]))
    elementos.append(tabla)

    doc.build(elementos)
    return nombre_archivo_pdf


def generar_excel(palabras_por_linea):
    """
    Genera un archivo Excel con el texto procesado.

    Args:
        palabras_por_linea: Lista de listas de palabras por línea.

    Returns:
        nombre_archivo_excel: Nombre del archivo Excel generado.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as archivo_tmp:
        nombre_archivo_excel = archivo_tmp.name

    datos = {'Líneas': [' '.join(linea) for linea in palabras_por_linea]}
    df = pd.DataFrame(datos)
    df.to_excel(nombre_archivo_excel, index=False)

    return nombre_archivo_excel


def generar_word(palabras_por_linea):
    """
    Genera un archivo Word con el texto procesado.

    Args:
        palabras_por_linea: Lista de listas de palabras por línea.

    Returns:
        nombre_archivo_word: Nombre del archivo Word generado.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as archivo_tmp:
        nombre_archivo_word = archivo_tmp.name

    doc = Document()
    for linea in palabras_por_linea:
        doc.add_paragraph(' '.join(linea))

    doc.save(nombre_archivo_word)
    return nombre_archivo_word

# ---------------------------------------------------------------- Base de datos ----------------------------------------------------------------


def guardar(imagen_subida, texto, enlace):
    """ 
    Guarda la imagen y el texto procesado en la base de datos.

    Args:
        imagen_subida: Imagen subida por el usuario.
        texto: Texto procesado.
        enlace: Enlace de la imagen subida.
    """
    nombre = imagen_subida.name
    id_foto = guardar_foto(nombre, enlace)
    guardar_texto(id_foto, texto)


def guardar_foto(nombre, enlace):
    """ 
    Guarda la imagen en la base de datos.

    Args: 
        nombre: Nombre de la imagen.
        enlace: Enlace de la imagen.
    """
    with obtener_conexion_bd() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO FOTOS (NOMBRE, DIRECCION) VALUES (?, ?)", (nombre, enlace))
        conn.commit()
        id_foto = cursor.lastrowid

        return id_foto


def guardar_texto(id_foto, texto):
    """
    Guarda el texto procesado en la base de datos.

    Args: 
        id_foto: ID de la imagen.
        texto: Texto procesado.
    """
    with obtener_conexion_bd() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO TEXTO (ID_FOTO, TEXTO) VALUES (?, ?)", (id_foto, texto))
        conn.commit()


def crear_tablas():
    """
    Crea las tablas de la base de datos.
    """
    conn = obtener_conexion_bd()
    try:
        cursor = conn.cursor()
        # Crear tablas
        cursor.execute('''
                    CREATE TABLE IF NOT EXISTS FOTOS (
                            ID INTEGER PRIMARY KEY,
                            NOMBRE TEXT NOT NULL,
                            FECHA TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            DIRECCION TEXT
                        )
                    ''')

        cursor.execute('''
                    CREATE TABLE IF NOT EXISTS TEXTO (
                            ID INTEGER PRIMARY KEY,
                            ID_FOTO INTEGER, 
                            TEXTO TEXT,
                            FECHA_TEXTO TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
        print("Tablas creadas exitosamente")

        # Confirmar la transacción
        conn.commit()
    except Exception as e:
        print(f"Error al crear las tablas: {e}")
    finally:
        conn.close()


def obtener_conexion_bd():
    """
    Función para obtener una nueva conexión a la base de datos.
    """
    try:
        conn = sqlite3.connect(NOMBRE_BASE_DATOS)
        conn.row_factory = sqlite3.Row
        print(f"Conexión a la base de datos {NOMBRE_BASE_DATOS} establecida.")
        return conn
    except sqlite3.Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None


if __name__ == "__main__":
    main()
