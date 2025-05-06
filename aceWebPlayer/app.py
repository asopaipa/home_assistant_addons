from flask import Flask, render_template, request, redirect, url_for, send_from_directory, Response, abort, send_file, jsonify, render_template_string, stream_with_context
from getLinks import generar_m3u_from_url, decode_default_url
from typing import Dict, Optional, Tuple, List
import re
import os
import json
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz
import requests
import io
import threading
import time
import shutil
import argparse
from pathlib import Path
from werkzeug.utils import safe_join
from operator import itemgetter
import asyncio
import subprocess
import uuid
from urllib.parse import quote
import async_playwright, Playwright, TimeoutError as PlaywrightTimeoutError
import random
import logging


app = Flask(__name__)

EPG_XML_PATH = os.getenv("EPG_XML_PATH", 'https://epgshare01.online/epgshare01/epg_ripper_ES1.xml.gz')

# Define las credenciales
USERNAME = "" #si está vacía, no se requerirá autenticación
PASSWORD = ""  

FOLDER_RESOURCES=""
# Ruta del archivo donde se guardarán los datos persistidos
DATA_FILE = ""


def export_iptv(channels, filepath):
    
    filtered_rows = []
    if channels:
        with open(filepath, "w") as f:
            for channel in channels:
                found_streams = asyncio.run(scan_streams(channel.id))
                if found_streams and found_streams[0] and found_streams[0]["url"] and found_streams[0]["headers"]:
                    f.write(f'#EXTINF:-1 tvg-id="" tvg-logo="" group-title="{channel.group}", {channel.name} \n')
                    f.write(format_url_with_headers(found_streams[0]["url"], found_streams[0]["headers"]))
                

    else:
        print("No hay datos para exportar")     



# Configuración básica de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# User agent común para simular un navegador real
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"

# Regex para encontrar URLs M3U8 completas en texto
M3U8_REGEX = re.compile(r'(https?://[^\s"\'`<>#?]+\.m3u8(?:[^\s"\'`<>#]*)?)', re.IGNORECASE)

# Tipos de contenido que podrían contener M3U8 o ser M3U8
TEXT_CONTENT_TYPES = [
    "text/html",
    "application/javascript",
    "application/x-javascript",
    "text/javascript",
    "application/json",
    "application/vnd.apple.mpegurl", # M3U8
    "application/x-mpegurl",        # M3U8
    "audio/mpegurl",                # M3U8
]

async def scan_streams(target_url: str, 
                            page_load_timeout: int = 60_000, # 60 segundos para carga de página
                            m3u8_wait_timeout: int = 30 # 30 segundos adicionales para buscar m3u8 después de carga
                           ) -> tuple[str | None, dict | None]:
    """
    Navega a una URL usando Playwright y busca una URL M3U8 en las peticiones o respuestas.

    Args:
        target_url: La URL principal a visitar.
        page_load_timeout: Tiempo máximo en ms para que la página cargue.
        m3u8_wait_timeout: Tiempo máximo en segundos para esperar un M3U8 después de que la página intente cargar.

    Returns:
        Una tupla (m3u8_url, request_headers) si se encuentra, o (None, None) si no.
    """
    logger.info(f"Iniciando búsqueda de M3U8 para: {target_url}")

    m3u8_found_event = asyncio.Event()
    # Usamos una lista para poder modificarla desde las funciones anidadas
    # result_data[0] = m3u8_url, result_data[1] = headers
    result_data = [None, None] 

    async def _process_m3u8_found(m3u8_url: str, headers: dict):
        if not result_data[0]: # Solo procesar la primera encontrada
            logger.info(f"¡M3U8 ENCONTRADO!: {m3u8_url}")
            logger.debug(f"Cabeceras de la petición asociada: {headers}")
            result_data[0] = m3u8_url
            result_data[1] = headers
            m3u8_found_event.set() # Señalizar que se encontró

    async def handle_request(request):
        if m3u8_found_event.is_set():
            return # Ya se encontró, no procesar más

        req_url_lower = request.url.lower()
        if ".m3u8" in req_url_lower:
            logger.debug(f"Posible M3U8 en URL de petición: {request.url}")
            await _process_m3u8_found(request.url, request.headers)

    async def handle_response(response):
        if m3u8_found_event.is_set():
            return # Ya se encontró, no procesar más

        res_url_lower = response.url.lower()
        content_type = response.header_value("content-type") or ""
        
        logger.debug(f"Respuesta recibida de: {response.url} (Status: {response.status}, Tipo: {content_type})")

        # 1. Comprobar URL de la respuesta
        if ".m3u8" in res_url_lower:
            logger.debug(f"Posible M3U8 en URL de respuesta: {response.url}")
            await _process_m3u8_found(response.url, response.request.headers)
            return

        # 2. Comprobar si el tipo de contenido es directamente M3U8
        if any(m3u8_ct in content_type.lower() for m3u8_ct in ["mpegurl", "vnd.apple.mpegurl"]):
            logger.debug(f"M3U8 detectado por content-type: {response.url}")
            await _process_m3u8_found(response.url, response.request.headers)
            return

        # 3. Comprobar contenido del cuerpo si es un tipo de texto relevante
        is_text_content = any(ct in content_type.lower() for ct in TEXT_CONTENT_TYPES)
        if is_text_content:
            try:
                body = await response.text()
                # logger.debug(f"Cuerpo de {response.url} (parcial): {body[:500]}") # Cuidado con logs grandes
                
                # Buscar con regex
                matches = M3U8_REGEX.findall(body)
                if matches:
                    for m3u8_url_in_body in matches:
                        logger.debug(f"M3U8 encontrado en cuerpo de {response.url}: {m3u8_url_in_body}")
                        await _process_m3u8_found(m3u8_url_in_body, response.request.headers)
                        if m3u8_found_event.is_set(): return # Salir si ya se encontró
                
                # Búsqueda simple si regex falla o por si acaso (menos precisa)
                elif ".m3u8" in body.lower():
                    logger.warning(f"Se encontró '.m3u8' en el cuerpo de {response.url}, pero no una URL completa con regex. Esto podría ser un falso positivo o una URL relativa.")
                    # Podrías intentar construir URLs relativas aquí si fuera necesario
                    # Por ahora, no lo hacemos para evitar complejidad y falsos positivos.

            except Exception as e:
                logger.warning(f"No se pudo leer el cuerpo de la respuesta de {response.url}: {e}")

    async with async_playwright() as p:
        browser = None
        context = None
        page = None
        try:
            logger.info("Lanzando navegador Chromium...")
            browser = await p.chromium.launch(headless=True) # Poner False para depurar visualmente
            
            logger.info("Creando nuevo contexto de navegador...")
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 720}, # Simular un tamaño de pantalla común
                java_script_enabled=True,
                # Podrías añadir aquí configuraciones de proxy si es necesario
            )
            # context.set_default_navigation_timeout(page_load_timeout) # Timeout para navegación
            context.set_default_timeout(page_load_timeout) # Timeout general para acciones

            logger.info("Creando nueva página...")
            page = await context.new_page()

            # Registrar manejadores de eventos
            page.on("request", handle_request)
            page.on("response", handle_response)

            logger.info(f"Navegando a {target_url}...")
            try:
                # 'networkidle' espera a que no haya actividad de red por 500ms.
                # 'domcontentloaded' es más rápido, pero podría no ejecutar todo el JS.
                # 'load' espera al evento load.
                # 'commit' espera a que la respuesta inicial sea recibida.
                await page.goto(target_url, wait_until="networkidle", timeout=page_load_timeout)
                logger.info(f"Navegación a {target_url} completada (o timeout).")
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout durante page.goto({target_url}). Se continuará buscando M3U8 si algo ya se cargó.")
            except Exception as e:
                logger.error(f"Error durante page.goto({target_url}): {e}", exc_info=True)
                # Si page.goto falla catastróficamente, es poco probable que encontremos M3U8
                # pero los handlers ya podrían haber capturado algo si la navegación empezó.

            if not m3u8_found_event.is_set():
                # Simular un poco de interacción humana y dar tiempo a JS adicional
                logger.info("Realizando scroll y esperando un poco más por actividad de red/JS...")
                try:
                    await page.evaluate("window.scrollBy(0, window.innerHeight / 2)")
                    await asyncio.sleep(1) # Pequeña pausa
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await asyncio.sleep(2) # Pausa un poco más larga
                except Exception as e:
                    logger.warning(f"Error durante scroll/sleep post-carga: {e}")
            
            if not m3u8_found_event.is_set():
                logger.info(f"Esperando hasta {m3u8_wait_timeout}s para que se detecte un M3U8...")
                try:
                    await asyncio.wait_for(m3u8_found_event.wait(), timeout=m3u8_wait_timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout esperando el evento M3U8 para {target_url} después de la carga y esperas.")
            
        except Exception as e:
            logger.error(f"Error general en la operación de Playwright para {target_url}: {e}", exc_info=True)
        finally:
            logger.info("Cerrando recursos de Playwright...")
            if page:
                try:
                    await page.close()
                    logger.debug("Página cerrada.")
                except Exception as e:
                    logger.error(f"Error al cerrar la página: {e}")
            if context:
                try:
                    await context.close()
                    logger.debug("Contexto cerrado.")
                except Exception as e:
                    logger.error(f"Error al cerrar el contexto: {e}")
            if browser:
                try:
                    await browser.close()
                    logger.debug("Navegador cerrado.")
                except Exception as e:
                    logger.error(f"Error al cerrar el navegador: {e}")

    if result_data[0]:
        logger.info(f"Búsqueda finalizada. M3U8 encontrado para {target_url}: {result_data[0]}")
        return result_data[0], result_data[1]
    else:
        logger.warning(f"Búsqueda finalizada. No se encontró M3U8 para {target_url}")
        return None, None





def format_url_with_headers(url, headers):
    """
    Formatea una URL y un diccionario de headers en el formato:
    url|Header1=Value1&Header2=Value2&...
    Los valores de los headers son URL-encoded.

    Args:
        url (str): La URL base.
        headers (dict): Un diccionario con los headers.

    Returns:
        str: La cadena formateada.
    """
    # Crear lista de strings "key=encoded_value"
    header_parts = []
    for key, value in headers.items():
        # Codificamos el valor del header. safe='' asegura que caracteres como / también se codifiquen.
        encoded_value = quote(str(value), safe='')
        header_parts.append(f"{key}={encoded_value}")

    # Unir las partes con '&'
    header_string = "&".join(header_parts)

    # Devolver el formato final
    if header_string: # Solo añadir el '|' si hay headers
        return f"{url}|{header_string}\n"
    else:
        return f"{url}\n" # Si no hay headers, devolver solo la URL

def save_to_file(textarea1, textarea2, textarea3, checkbox, con_acexy, acestream_server, acestream_protocol, file_input):

    """
    Guarda los datos de los tres textareas, el estado del checkbox, el servidor Acestream y el protocolo en un archivo JSON.
    
    :param textarea1: Contenido del primer textarea (cadena).
    :param textarea2: Contenido del segundo textarea (cadena).
    :param textarea3: Contenido del tercer textarea (cadena).
    :param checkbox: Estado del checkbox de strm (True o False).
    :param con_acexy: Estado del checkbox de con_acexy (True o False).
    :param file_input: Ruta del archivo donde se guardarán los datos.
    :param acestream_server: Servidor Acestream (cadena).
    :param acestream_protocol: Protocolo Acestream (http o https).
    :param file_input: Ruta del archivo donde se guardarán los datos.
    """
    data = {
        "textarea1": textarea1 if textarea1 is not None else "",
        "textarea2": textarea2 if textarea2 is not None else "",
        "textarea3": textarea3 if textarea3 is not None else "",
        "checkbox": checkbox,
        "con_acexy": con_acexy,
        "acestream_server": acestream_server if acestream_server else "",
        "acestream_protocol": acestream_protocol if acestream_protocol else "http"
    }
    
    with open(file_input, "w") as file:
        json.dump(data, file)





def load_from_file(file_input):
    """
    Carga los datos de los tres textareas, el estado del checkbox, el servidor Acestream y el protocolo desde un archivo JSON.
    
    :param file_input: Ruta del archivo desde donde se cargarán los datos.
    :return: Una tupla con el contenido de textarea1, textarea2, textarea3, el estado del checkbox, con_acexy, el servidor Acestream y el protocolo.
    """

    if os.path.exists(file_input):
        with open(file_input, "r") as file:
            try:
                data = json.load(file)
                textarea1 = data.get("textarea1", "")
                textarea2 = data.get("textarea2", "")
                textarea3 = data.get("textarea3", "")
                checkbox = data.get("checkbox", False)
                con_acexy = data.get("con_acexy", False)
                acestream_server = data.get("acestream_server", "")
                acestream_protocol = data.get("acestream_protocol", "http")
                return textarea1, textarea2, textarea3, checkbox, con_acexy, acestream_server, acestream_protocol
            except json.JSONDecodeError:
                # En caso de error al leer el JSON, devolver valores por defecto
                return "", "", "", False, False, "", "http"
    # Si el archivo no existe, devolver valores por defecto
    return "", "", "", False, False, "", "http"






# Directorio para almacenar temporalmente los segmentos HLS
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_streams')
os.makedirs(TEMP_DIR, exist_ok=True)

# Diccionario para mantener el seguimiento de los procesos activos
active_streams = {}

def clean_old_streams():
    """Limpia streams antiguos periódicamente"""
    while True:
        now = time.time()
        for stream_id in list(active_streams.keys()):
            info = active_streams.get(stream_id)
            if info and now - info['last_access'] > 60:  # 60 segundos sin acceso
                try:
                    print(f"Limpiando stream inactivo: {stream_id}")
                    if info['process'] and info['process'].poll() is None:
                        info['process'].terminate()
                        info['process'].wait(timeout=5)
                        info['process'].kill()
                    
                    # Eliminar directorio de segmentos
                    stream_dir = os.path.join(TEMP_DIR, stream_id)
                    if os.path.exists(stream_dir):
                        shutil.rmtree(stream_dir)
                    
                    del active_streams[stream_id]
                except Exception as e:
                    print(f"Error al limpiar stream {stream_id}: {str(e)}")
        
        time.sleep(10)  # Revisar cada 10 segundos

# Iniciar thread de limpieza
cleanup_thread = threading.Thread(target=clean_old_streams, daemon=True)
cleanup_thread.start()

def start_ffmpeg_process(stream_url, stream_id, stream_headers):
    """Inicia un proceso FFmpeg para generar los segmentos HLS"""
    stream_dir = os.path.join(TEMP_DIR, stream_id)
    os.makedirs(stream_dir, exist_ok=True)
    
    # Ruta para los archivos de playlist y segmentos
    playlist_path = os.path.join(stream_dir, 'playlist.m3u8')
    segment_path = os.path.join(stream_dir, 'segment_%03d.ts')
    
    # Comando FFmpeg optimizado para streaming
    cmd = [
        'ffmpeg',
        '-i', stream_url,               # URL de entrada
        '-headers', stream_headers,
        '-c', 'copy',                   # Copiar sin transcodificar
        '-f', 'hls',                    # Formato de salida HLS
        '-hls_time', '2',               # Duración de cada segmento
        '-hls_list_size', '10',         # Número de segmentos en la playlist
        '-hls_flags', 'delete_segments',# Eliminar segmentos antiguos
        '-hls_segment_filename', segment_path,  # Patrón de nombre de segmentos
        playlist_path                   # Archivo de playlist
    ]
    
    # Iniciar proceso en modo no bloqueante
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**8
    )
    
    # Guardar información del proceso
    active_streams[stream_id] = {
        'process': process,
        'stream_url': stream_url,
        'last_access': time.time(),
        'stream_dir': stream_dir
    }
    
    # Monitorear errores en un hilo separado
    def monitor_errors():
        for line in iter(process.stderr.readline, b''):
            line = line.decode('utf-8', errors='ignore').strip()
            if line and not line.startswith('frame='):  # Filtrar mensajes de progreso
                print(f"FFmpeg [{stream_id}]: {line}")
    
    error_thread = threading.Thread(target=monitor_errors, daemon=True)
    error_thread.start()


 
    
    return stream_id

@app.route('/stream/start/<path:stream_url>')
def create_stream(stream_url):
    
    """Inicia un nuevo stream y devuelve su ID"""
    try:


        result = asyncio.run(scan_streams(stream_url))
        if not result or not result[0]:
            print("Canal no disponible")
            return "Canal no disponible", 500
        # Se utiliza el primer stream de la lista
        stream_data = result[0]
        stream_url_final = stream_data["url"]
        stream_headers = stream_data["headers"]

        print(f"URL antes de ffmpeg: {stream_url_final}")
    
        # Construir el string de headers para FFmpeg.
        # FFmpeg espera los headers en formato "Clave: Valor\r\n"
        headers_str = "".join(f"{key}: {value}\r\n" for key, value in stream_headers.items())

        print(f"Headers antes de ffmpeg: {headers_str}")
            
        # Generar ID único para este stream
        stream_id = str(uuid.uuid4())
        
        # Iniciar proceso FFmpeg
        start_ffmpeg_process(stream_url_final, stream_id, headers_str)
        
        # Devolver ID del stream y URL de la playlist
        playlist_url = f"/stream/playlist/{stream_id}/playlist.m3u8"
        return {
            'stream_id': stream_id,
            'playlist_url': playlist_url,
        }
    except Exception as e:
        print(f"Error al crear stream: {str(e)}")
        return str(e), 500



    
@app.route('/stream/playlist/<stream_id>/<path:filename>')
async def serve_playlist(stream_id, filename):

  
    """Sirve la playlist o segmentos HLS"""
    if stream_id not in active_streams:
        return "Stream no encontrado", 404

    
    # Actualizar timestamp de último acceso
    active_streams[stream_id]['last_access'] = time.time()
    
    # Directorio del stream
    stream_dir = active_streams[stream_id]['stream_dir']

    file_path = os.path.join(stream_dir, filename)


    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < 5 and not os.path.exists(file_path):
        # Añade logs para verificar que está esperando        
        await asyncio.sleep(0.1)  # Pequeña pausa entre verificaciones


    
    # Devolver archivo solicitado
    return send_from_directory(stream_dir, filename)









def requires_auth(f):
    def decorated(*args, **kwargs):
        # Si el usuario está vacío, no aplica la autenticación
        if not USERNAME:
            return f(*args, **kwargs)

        auth = request.authorization
        if not auth or auth.username != USERNAME or auth.password != PASSWORD:
            return Response(
                "Necesitas autenticarte para acceder.\n",
                401,
                {"WWW-Authenticate": 'Basic realm="Login Required"'},
            )
        return f(*args, **kwargs)
    # Hacer el decorador compatible con Flask
    decorated.__name__ = f.__name__
    return decorated


class Channel:
    def __init__(self, name, id, logo, group, tvg_id):
        self.name = name
        self.id = id
        self.logo = logo
        self.group = group
        self.tvg_id = tvg_id
        self.current_program = None
        self.current_program_time = None
        self.next_program = None
        self.next_program_time = None

def parse_time(time_str):
    try:
        # Remove spaces and handle timezone offset
        time_str = time_str.replace(' ', '')
        date_part = time_str[:14]  # YYYYMMDDHHMMSS
        tz_part = time_str[14:]    # +HHMM or -HHMM
        
        # Parse the base datetime
        dt = datetime.strptime(date_part, '%Y%m%d%H%M%S')
        
        # Handle timezone offset
        if tz_part:
            sign = 1 if tz_part[0] == '+' else -1
            hours = int(tz_part[1:3])
            minutes = int(tz_part[3:5]) if len(tz_part) >= 5 else 0
            offset = sign * (hours * 60 + minutes) * 60  # Convert to seconds
            
            # Create timezone aware datetime
            return dt.replace(tzinfo=pytz.FixedOffset(offset // 60))
        
        return dt.replace(tzinfo=pytz.UTC)
    except Exception as e:
        print(f"Error parsing time {time_str}: {e}")
        return None

def parse_epg(epg_url):
    epg_data = {}
    try:
        print(f"Downloading EPG data from {epg_url}...")
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br'
        })

        response = session.get(epg_url, stream=True, timeout=30)
        response.raise_for_status()
        
        print("Download completed. Parsing XML...")
        
        with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
            tree = ET.parse(f)
            root = tree.getroot()

        # Debug information
        channels = root.findall('.//channel')
        programmes = root.findall('.//programme')
        print(f"Found {len(channels)} channels and {len(programmes)} programmes")

        for programme in root.findall('.//programme'):
            channel_id = programme.get('channel')
            if not channel_id:
                continue

            start_time = parse_time(programme.get('start'))
            stop_time = parse_time(programme.get('stop'))
            
            if not start_time or not stop_time:
                continue
                
            title_elem = programme.find('title')
            title = title_elem.text if title_elem is not None else 'No Title'

            if channel_id not in epg_data:
                epg_data[channel_id] = []

            epg_data[channel_id].append({
                'start': start_time,
                'stop': stop_time,
                'title': title
            })

        # Sort programs by start time
        for channel_id in epg_data:
            epg_data[channel_id].sort(key=lambda x: x['start'])

        print(f"EPG parsing completed. Found {len(epg_data)} channels")
        # Debug: Print some channel IDs
        print("Sample channel IDs:", list(epg_data.keys())[:5])
        return epg_data

    except Exception as e:
        print(f"Error in parse_epg: {e}")
        return {}

def get_current_and_next_program(programs, now):
    """Get current and next program based on current time"""
    current_program = None
    next_program = None
    
    # Convert now to UTC if it's not already timezone aware
    if now.tzinfo is None:
        now = pytz.UTC.localize(now)
    
    # Sort programs by start time
    sorted_programs = sorted(programs, key=lambda x: x['start'])
    
    # Find current program
    for i, program in enumerate(sorted_programs):
        program_start = program['start']
        program_end = program['stop']
        
        # Convert to UTC for comparison
        if program_start.tzinfo != pytz.UTC:
            program_start = program_start.astimezone(pytz.UTC)
        if program_end.tzinfo != pytz.UTC:
            program_end = program_end.astimezone(pytz.UTC)
            
        if program_start <= now < program_end:
            current_program = program
            if i + 1 < len(sorted_programs):
                next_program = sorted_programs[i + 1]
            break
    
    return current_program, next_program

def parse_m3u(content):
    channels = []
    current_channel = None
    
    for line in content.splitlines():
        if line.startswith('#EXTINF:'):
            tvg_id_match = re.search('tvg-id="(.*?)"', line)
            logo_match = re.search('tvg-logo="(.*?)"', line)
            group_match = re.search('group-title="(.*?)"', line)
            name = line.split(',')[-1].strip()
            
            current_channel = Channel(
                name=name,
                id=None,
                logo=logo_match.group(1) if logo_match else "",
                group=group_match.group(1) if group_match else "Sin categoría",
                tvg_id=tvg_id_match.group(1) if tvg_id_match else None
            )
        elif current_channel:
            current_channel.id = line.replace('acestream://', '').strip()
            channels.append(current_channel)
            current_channel = None
            
    return channels

# Global EPG cache
epg_data_cache = {}
epg_last_updated = None

def update_epg_data():
    global epg_data_cache, epg_last_updated
    while True:
        try:
            print("Updating EPG data...")
            epg_data_cache = parse_epg(EPG_XML_PATH)
            epg_last_updated = datetime.now(pytz.UTC)
            print("EPG update completed")
        except Exception as e:
            print(f"Error updating EPG: {e}")
        time.sleep(6 * 60 * 60)  # Update every 6 hours

@app.route('/download/<filename>')
@requires_auth
def download_file(filename):
    # Directorio donde están los archivos
    
    try:
        # Descargar el archivo
    
        # Lista de nombres permitidos
        archivos_permitidos = ["acestream_directos.m3u", "web_directos.m3u", "acestream_pelis.m3u", "web_pelis.m3u", "iptv_headers.m3u"]
    
        # Validar si el archivo es permitido
        if filename not in archivos_permitidos:
            abort(403, description="Archivo no autorizado para la descarga.")

        if filename == "iptv_headers.m3u":  
            if os.path.exists(f"{FOLDER_RESOURCES}/web_iptv.m3u") and os.stat(f"{FOLDER_RESOURCES}/web_iptv.m3u").st_size > 5:
                with open(f"{FOLDER_RESOURCES}/web_iptv.m3u", 'r', encoding='utf-8') as file:
                    content = file.read()
                    channels2 = parse_m3u(content)
                    export_iptv(channels2, f"{FOLDER_RESOURCES}/iptv_headers.m3u")
        
        return send_from_directory(FOLDER_RESOURCES, filename, as_attachment=True)
    except FileNotFoundError:
        return f"El archivo {filename} no existe.", 404


@app.route('/', methods=['GET', 'POST'])
@requires_auth
def index():
    channels = []
    groups = set()
    acestream_server = ""
    acestream_protocol = "http"
    
    if request.method == 'POST':
        if request.form.get('default_list') == 'true':
            direccion_bytes, direccion_pelis_bytes, direccion_webs_bytes = decode_default_url()
            direccion = direccion_bytes.decode("utf-8")
            direccion_pelis = direccion_pelis_bytes.decode("utf-8")
            direccion_webs = direccion_webs_bytes.decode("utf-8")
            acestream_server = request.form.get('aceStreamServer', '')
            acestream_protocol = request.form.get('aceStreamProtocol', 'http')
            save_to_file(direccion, direccion_pelis, direccion_webs, False, False, acestream_server, acestream_protocol, DATA_FILE)    
            # Procesar cada línea como una URL
            urls = [direccion]
            urls_pelis = [direccion_pelis]
            urls_webs = [direccion_webs]
            # Usar el servidor Acestream proporcionado o el host por defecto
            host_to_use = acestream_server if acestream_server else request.host
            generar_m3u_from_url(host_to_use, urls, "directos",FOLDER_RESOURCES, False, acestream_protocol)
            generar_m3u_from_url(host_to_use, urls_pelis, "pelis", FOLDER_RESOURCES, False, acestream_protocol)
            generar_m3u_from_url(request.host, urls_webs, "webs",FOLDER_RESOURCES, False, acestream_protocol)
                        
            textarea_content = direccion
            textarea_content_pelis = direccion_pelis
            textarea_content_webs = direccion_webs
            export_strm = False
            con_acexy = False
        elif request.form.get('submit_url') == 'true':
            # Obtener los datos enviados desde el formulario
            textarea_content = request.form.get('urlInput', '').strip()      
            textarea_content_pelis = request.form.get('urlInputPelis', '').strip()   
            textarea_content_webs = request.form.get('urlInputWebs', '').strip()  
            export_strm = False
            export_strm = 'export_strm' in request.form
            con_acexy = False
            con_acexy = 'con_acexy' in request.form
            acestream_server = request.form.get('aceStreamServer', '')
            acestream_protocol = request.form.get('aceStreamProtocol', 'http')
            # Guardar los datos en el archivo
            save_to_file(textarea_content, textarea_content_pelis, textarea_content_webs, export_strm, con_acexy, acestream_server, acestream_protocol, DATA_FILE)       

            # Procesar cada línea como una URL
            urls = [url.strip() for url in textarea_content.splitlines() if url.strip()]
            urls_pelis = [url.strip() for url in textarea_content_pelis.splitlines() if url.strip()]
            urls_webs = [url.strip() for url in textarea_content_webs.splitlines() if url.strip()]

            host_to_use = acestream_server if acestream_server else request.host
            generar_m3u_from_url(host_to_use, urls, "directos", FOLDER_RESOURCES, con_acexy, acestream_protocol)
            generar_m3u_from_url(host_to_use, urls_pelis, "pelis",FOLDER_RESOURCES, con_acexy, acestream_protocol)
            generar_m3u_from_url(host_to_use, urls_webs, "webs", FOLDER_RESOURCES, con_acexy, acestream_protocol)

    else:
        # Cargar los datos persistidos desde el archivo
        textarea_content, textarea_content_pelis, textarea_content_webs, export_strm, con_acexy, acestream_server, acestream_protocol =  load_from_file(DATA_FILE)

    if export_strm:
        
        # Procesar directos y películas
        procesar_directos(f"{FOLDER_RESOURCES}/acestream_directos.m3u", f"{FOLDER_RESOURCES}/output_strm/acestream")
        procesar_peliculas(f"{FOLDER_RESOURCES}/acestream_pelis.m3u", f"{FOLDER_RESOURCES}/output_strm/acestream")

        procesar_directos(f"{FOLDER_RESOURCES}/web_directos.m3u", f"{FOLDER_RESOURCES}/output_strm/web")
        procesar_peliculas(f"{FOLDER_RESOURCES}/web_pelis.m3u", f"{FOLDER_RESOURCES}/output_strm/web")
    else:
        if os.path.exists(f"{FOLDER_RESOURCES}/output_strm/acestream"):
            shutil.rmtree(f"{FOLDER_RESOURCES}/output_strm/acestream")

        if os.path.exists(f"{FOLDER_RESOURCES}/output_strm/web"):
            shutil.rmtree(f"{FOLDER_RESOURCES}/output_strm/web")
    if os.path.exists(f"{FOLDER_RESOURCES}/acestream_directos.m3u") and os.stat(f"{FOLDER_RESOURCES}/acestream_directos.m3u").st_size > 5:
        with open(f"{FOLDER_RESOURCES}/acestream_directos.m3u", 'r', encoding='utf-8') as file:
            content = file.read()
            channels = parse_m3u(content)
    
    if channels:  # Verifica si 'channels' no está vacío
        now = datetime.now(pytz.UTC)
        local_tz = pytz.timezone('Europe/Madrid')  # Change this to your timezone
        
        for channel in channels:
            if channel.tvg_id and channel.tvg_id in epg_data_cache:
                print(f"Processing EPG for channel {channel.name} (ID: {channel.tvg_id})")
                current, next = get_current_and_next_program(epg_data_cache[channel.tvg_id], now)
                
                if current:
                    channel.current_program = current['title']
                    channel.current_program_time = current['start'].astimezone(local_tz)
                    print(f"Current program: {channel.current_program} at {channel.current_program_time}")
                if next:
                    channel.next_program = next['title']
                    channel.next_program_time = next['start'].astimezone(local_tz)
                    print(f"Next program: {channel.next_program} at {channel.next_program_time}")

        groups = {channel.group for channel in channels}
        groups = sorted(list(groups))


    if os.path.exists(f"{FOLDER_RESOURCES}/acestream_pelis.m3u") and os.stat(f"{FOLDER_RESOURCES}/acestream_pelis.m3u").st_size > 5:
        with open(f"{FOLDER_RESOURCES}/acestream_pelis.m3u", 'r', encoding='utf-8') as file:
            content = file.read()
            channels2 = parse_m3u(content)
            channels.extend(channels2)

    if os.path.exists(f"{FOLDER_RESOURCES}/web_iptv.m3u") and os.stat(f"{FOLDER_RESOURCES}/web_iptv.m3u").st_size > 5:
        with open(f"{FOLDER_RESOURCES}/web_iptv.m3u", 'r', encoding='utf-8') as file:
            content = file.read()
            channels2 = parse_m3u(content)
            channels.extend(channels2)
    
    if channels:  # Verifica si 'channels' no está vacío
        groups = {channel.group for channel in channels}
        groups = sorted(list(groups))
    
    return render_template('index.html', channels=channels, groups=groups, textarea_content=textarea_content, export_strm=export_strm, con_acexy=con_acexy, textarea_content_pelis=textarea_content_pelis, textarea_content_webs=textarea_content_webs, acestream_server=acestream_server, acestream_protocol=acestream_protocol)

def procesar_directos(m3u_directos, directorio_salida):
    """
    Procesa el archivo M3U de directos y crea archivos .strm en una única carpeta.
    """
    carpeta_directos = os.path.join(directorio_salida, "Directos")
    os.makedirs(carpeta_directos, exist_ok=True)

    with open(m3u_directos, "r", encoding="utf-8") as f:
        contenido = f.readlines()

    for i, linea in enumerate(contenido):
        linea = linea.strip()
        if linea.startswith("#EXTINF"):
            # Extraer el nombre del canal
            match = re.search(r',(.+)$', linea)
            nombre_canal = match.group(1).strip() if match else f"Directo_{i}"
            nombre_canal=nombre_canal.replace(" ", "_")
        elif linea.startswith("acestream://") or linea.startswith("http"):
            # Crear el archivo STRM con el enlace
            archivo_strm = os.path.join(carpeta_directos, f"{nombre_canal}.strm")
            with open(archivo_strm, "w", encoding="utf-8") as f:
                f.write(linea)



def procesar_peliculas(m3u_peliculas, directorio_salida):
    """
    Procesa el archivo M3U de películas y crea una estructura de carpetas con subcarpetas y archivos .strm.
    """
    carpeta_peliculas = os.path.join(directorio_salida, "Peliculas")
    os.makedirs(carpeta_peliculas, exist_ok=True)

    with open(m3u_peliculas, "r", encoding="utf-8") as f:
        contenido = f.readlines()

    pelicula_actual = None
    for i, linea in enumerate(contenido):
        linea = linea.strip()
        if linea.startswith("#EXTINF"):
            # Extraer el nombre de la película y la calidad
            match = re.search(r',(.+)$', linea)
            if match:
                info = match.group(1).strip()
                # Separar título y calidad
                titulo_match = re.match(r'(.+?)\s+\((\d{4})\)\s+(.+)', info)
                if titulo_match:
                    titulo_pre = titulo_match.group(1).strip()
                    titulo = titulo_pre.replace("/", "_").replace("\\", "_").replace("-", "_").replace(" ", "_").replace("+", "_").replace("*", "_").replace(".", "_").replace("(", "_").replace(")", "_").replace(":", "_").replace("&", "_").replace("[", "_").replace("]", "_")
                    calidad = titulo_match.group(3).strip().replace(" ", "_").replace("[", "_").replace("]", "_").replace("*", "_").replace(".", "_").replace("(", "_").replace(")", "_").replace(":", "_").replace("&", "_")
                else:
                    titulo_pre = info
                    titulo = titulo_pre.replace("/", "_").replace("\\", "_").replace("-", "_").replace(" ", "_").replace("+", "_").replace("*", "_").replace(".", "_").replace("(", "_").replace(")", "_").replace(":", "_").replace("&", "_").replace("[", "_").replace("]", "_")
                    calidad = "Desconocida"
                # Crear carpeta para la película
                pelicula_actual = os.path.join(carpeta_peliculas, titulo)
                os.makedirs(pelicula_actual, exist_ok=True)
        elif linea.startswith("acestream://") or linea.startswith("http"):
            # Crear el archivo STRM con el enlace
            if pelicula_actual:
                archivo_strm = os.path.join(pelicula_actual, f"{titulo}-{calidad}.strm")
                with open(archivo_strm, "w", encoding="utf-8") as f:
                    f.write(linea)






def getReadableByteSize(num, suffix='B') -> str:
    # Si el número es menor que 1024 (en bytes), devolver el valor entero sin sufijo "B"
    if abs(num) < 1024.0:
        return "%d" % num  # No muestra decimales ni sufijo "B"
    
    # Para unidades mayores a 1024, aplicamos el formato con sufijos y sin decimales
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%d%s%s" % (num, unit, suffix)  # No decimales para "K", "M", etc.
        num /= 1024.0
    
    return "%d%s%s" % (num, 'Y', suffix)  # Para valores grandes, se omiten decimales

def getTimeStampString(tSec: float) -> str:
    tObj = datetime.fromtimestamp(tSec)
    tStr = tObj.strftime('%d-%m-%Y %H:%M:%S')
    return tStr

def getIconClassForFilename(fName):
    fileExt = Path(fName).suffix
    fileExt = fileExt[1:] if fileExt.startswith(".") else fileExt
    fileTypes = ["aac", "ai", "bmp", "cs", "css", "csv", "doc", "docx", "exe", "gif", "heic", "html", "java", "jpg", "js", "json", "jsx", "key", "m4p", "md", "mdx", "mov", "mp3",
                 "mp4", "otf", "pdf", "php", "png", "pptx", "psd", "py", "raw", "rb", "sass", "scss", "sh", "sql", "svg", "tiff", "tsx", "ttf", "txt", "wav", "woff", "xlsx", "xml", "yml"]
    fileIconClass = f"bi bi-filetype-{fileExt}" if fileExt in fileTypes else "bi bi-file-earmark"
    return fileIconClass

# route handler
@app.route('/output_strm/', defaults={'reqPath': ''})
@app.route('/output_strm/<path:reqPath>')
def getFiles(reqPath):
    FolderPath = f"{FOLDER_RESOURCES}/output_strm/"
    # Join the base and the requested path
    # could have done os.path.join, but safe_join ensures that files are not fetched from parent folders of the base folder
    absPath = safe_join(FolderPath, reqPath)

    # Return 404 if path doesn't exist
    if not os.path.exists(absPath):
        return "No existe: " + absPath

    # Check if path is a file and serve
    if os.path.isfile(absPath):
        return send_file(absPath)

    # Show directory contents
    def fObjFromScan(x):
        fileStat = x.stat()
        # return file information for rendering
        if os.path.isdir(x.path):
            nombre = x.name + "/"
        else:
            nombre = x.name
        return {'name': nombre[:50],
                'espacios_nombre': "".ljust(51 - len(nombre[:50])),
                'fIcon': "bi bi-folder-fill" if os.path.isdir(x.path) else getIconClassForFilename(x.name),
                'relPath': nombre.replace("\\", "/"),
                'mTime': getTimeStampString(fileStat.st_mtime),
                'espacios_fecha': "       " if os.path.isdir(x.path) else "".ljust(7 - len(getReadableByteSize(fileStat.st_size)[:6])),
                'size': "-" if os.path.isdir(x.path) else getReadableByteSize(fileStat.st_size)[:6]}

    try:
        #fileObjs = [fObjFromScan(x) for x in os.scandir(absPath)]
        fileObjs = sorted(
            [fObjFromScan(x) for x in os.scandir(absPath)],
            key=itemgetter('name')
        )
        # get parent directory url
        parentFolderPath = os.path.relpath(
            Path(absPath).parents[0], FolderPath).replace("\\", "/")
        return render_template('files.html.j2', data={'files': fileObjs,
                                                     'parentFolder': parentFolderPath})
    except Exception as e:
        return "Error: " + str(e)
                  
    

    
if __name__ == '__main__':
    # Configuramos el parser de argumentos
    parser = argparse.ArgumentParser(description="Ejemplo de Flask con argumento -d")
    parser.add_argument("-d", "--directory", help="Directorio para la aplicación", required=False)
    args = parser.parse_args()

    # Verificamos si se proporcionó el argumento y si el directorio existe
    FOLDER_RESOURCES="resources"
    DATA_FILE = "resources/urls.json"
    if args.directory:
        if os.path.exists(args.directory):
            FOLDER_RESOURCES=args.directory
            DATA_FILE = f"{args.directory}/urls.json"
    # Start EPG updater thread
    updater_thread = threading.Thread(target=update_epg_data)
    updater_thread.daemon = True
    updater_thread.start()
    
    app.run(host='0.0.0.0', threaded=True, use_reloader=False)
