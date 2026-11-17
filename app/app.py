"""
Sistema de Gestión de Presupuestos — Constructora Altura (Inversiones Rumay Ltda.)
ICN-292 Sistemas de Información para la Gestión · USM · Entrega 2

Aplicación web (Streamlit) sobre la base MySQL `altura_db` (schema.sql + seed.sql).

Cubre los requerimientos de la Entrega 1 y de la entrevista con la empresa (15-11-2026):
  RF1  catálogo centralizado de partidas (alta, edición de precio, desactivación, historial)
  RF2  creación de presupuestos con las condiciones de la obra
  RF3  detalle de partidas con cálculo automático
  RF4  gastos generales (RN-5), utilidad (RN-8) e IVA (RN-9) sobre el costo directo
  RF5  valor UF del día (consulta automática opcional a mindicador.cl)
  RF6  cotizaciones externas: solicitud, recepción y selección
  RF7  alerta de precios por revisar (3-6 meses) y vencidos (> 6 meses) (RN-4)
  RF8  flujo Borrador → En revisión → Aprobado → Emitido; solo el Gerente aprueba (RN-7)
  RF9  PDF del presupuesto y envío al cliente por correo (n8n → Outlook), con registro del envío
  + correcciones registradas automáticamente durante la revisión (KPI de la E1)
  + obras y plazos de entrega, e indicadores / preguntas de oro del Gerente

Todas las cifras se calculan desde la base de datos: la app no muestra valores fijos.
El SQL usa solo lo visto en el curso (Sesiones 08-09, Ayudantías 5-6). La base hace cumplir las
reglas que caben en el DDL (PK, FK, NOT NULL, UNIQUE, CHECK, ENUM); las que dependen de otra tabla o
del estado anterior (flujo de estados, quién aprueba, historial de precios, bloqueo de presupuestos
cerrados) las hace cumplir esta app en la sección «Reglas de negocio», dentro de transacciones.

Ejecución:
    pip install -r requirements.txt
    (copiar secrets.toml.example a .streamlit/secrets.toml y completar la conexión)
    python -m streamlit run app.py
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import os
import re
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterator

import mysql.connector
import pandas as pd
import requests
import streamlit as st
from fpdf import FPDF
from mysql.connector import pooling

# =============================================================================
# 0. Parámetros de negocio (validados con la empresa, entrevista 15-11-2026)
# =============================================================================
GG_MIN, GG_MAX, GG_SIN_JUSTIFICAR = 5.0, 12.0, 10.0   # RN-5: habituales 5/8/10 %, hasta 12 %
GG_HABITUALES = (5.0, 8.0, 10.0, 12.0)
UTIL_MIN, UTIL_MAX = 12.0, 20.0                       # RN-8: rango habitual (fuera de él se justifica)
UTIL_MIN_ABS, UTIL_MAX_ABS = 8.0, 25.0                # RN-8: límites absolutos
IVA_DEFECTO = 19.0                                     # RN-9
MESES_POR_REVISAR, MESES_VENCIDO = 3, 6               # RN-4 (precios se actualizan cada 3 a 6 meses)
DIAS_POR_REVISAR, DIAS_VENCIDO = 90, 180             # los mismos plazos en días (DATEDIFF)
ESTADOS = ['Borrador', 'En revision', 'Aprobado', 'Rechazado', 'Emitido']
ESTADOS_EDITABLES = ('Borrador', 'En revision')
EMPRESA = 'Constructora Altura - Inversiones Rumay Ltda.'

st.set_page_config(page_title='Presupuestos · Constructora Altura', page_icon='🏗️', layout='wide')


# =============================================================================
# 1. Configuración (sin contraseñas en el código: .streamlit/secrets.toml o variables de entorno)
# =============================================================================
RUTA_SECRETOS = Path(__file__).resolve().parent / '.streamlit' / 'secrets.toml'


def _leer_toml(ruta: Path) -> dict:
    try:
        import tomllib                      # Python 3.11+
        with open(ruta, 'rb') as f:
            return tomllib.load(f)
    except ModuleNotFoundError:
        import toml                         # dependencia de Streamlit (Python < 3.11)
        return toml.load(ruta)


def _secretos() -> tuple[dict, str]:
    """Busca la configuración en este orden:
    1) .streamlit/secrets.toml junto a este archivo (funciona aunque la app se ejecute desde otra carpeta)
    2) st.secrets (carpeta desde donde se ejecutó streamlit o ~/.streamlit/secrets.toml)
    3) variables de entorno (MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, ...)"""
    if RUTA_SECRETOS.is_file():
        try:
            return _leer_toml(RUTA_SECRETOS), str(RUTA_SECRETOS)
        except Exception as e:  # noqa: BLE001
            return {}, f'{RUTA_SECRETOS} (formato inválido: {e})'
    try:
        if 'mysql' in st.secrets:
            return st.secrets.to_dict(), 'st.secrets'
    except Exception:  # noqa: BLE001
        pass
    return {}, f'variables de entorno (no se encontró {RUTA_SECRETOS})'


def _secreto(seccion: str, clave: str, env: str, defecto: Any = None) -> Any:
    datos, _ = _secretos()
    if clave in datos.get(seccion, {}):
        return datos[seccion][clave]
    return os.environ.get(env, defecto)


def config_mysql() -> dict:
    cfg = {
        'host': _secreto('mysql', 'host', 'MYSQL_HOST', 'localhost'),
        'port': int(_secreto('mysql', 'port', 'MYSQL_PORT', 3306)),
        'user': _secreto('mysql', 'user', 'MYSQL_USER', 'root'),
        'password': _secreto('mysql', 'password', 'MYSQL_PASSWORD', ''),
        'database': _secreto('mysql', 'database', 'MYSQL_DATABASE', 'altura_db'),
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_0900_ai_ci',
    }
    socket = _secreto('mysql', 'unix_socket', 'MYSQL_UNIX_SOCKET', None)
    if socket:
        cfg['unix_socket'] = socket
    return cfg


def url_n8n() -> str | None:
    return _secreto('n8n', 'webhook_url', 'N8N_WEBHOOK_URL', None) or None


# =============================================================================
# 2. Acceso a datos
# =============================================================================
@st.cache_resource(show_spinner=False)
def _pool() -> pooling.MySQLConnectionPool:
    return pooling.MySQLConnectionPool(pool_name='altura', pool_size=5, **config_mysql())


@contextmanager
def conexion() -> Iterator[Any]:
    con = _pool().get_connection()
    try:
        yield con
    finally:
        con.close()


def _a_float(df: pd.DataFrame) -> pd.DataFrame:
    """mysql-connector devuelve Decimal; se pasan a float para mostrar y graficar."""
    for c in df.columns:
        if df[c].map(lambda v: isinstance(v, Decimal)).any():
            df[c] = df[c].map(lambda v: float(v) if isinstance(v, Decimal) else v)
    return df


def consultar(sql: str, params: dict | tuple | None = None) -> pd.DataFrame:
    with conexion() as con:
        cur = con.cursor()
        cur.execute(sql, params or ())
        filas = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        cur.close()
        con.commit()   # cierra la transacción de lectura (lecturas siempre frescas)
    return _a_float(pd.DataFrame(filas, columns=cols))


def valor(sql: str, params: dict | tuple | None = None) -> Any:
    df = consultar(sql, params)
    return None if df.empty else df.iat[0, 0]


@contextmanager
def transaccion() -> Iterator[Any]:
    """Todas las escrituras van en una transacción: o se guarda todo o nada (ACID)."""
    with conexion() as con:
        cur = con.cursor()
        try:
            yield cur
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            cur.close()


# Traducción de las restricciones de la base a mensajes para el usuario
MENSAJES_CHECK = {
    'ck_ppto_rn5': 'RN-5: los gastos generales deben estar entre 5 % y 12 %.',
    'ck_ppto_rn5_just': 'RN-5: sobre 10 % de gastos generales hay que justificar las condiciones de la obra.',
    'ck_ppto_rn8': 'RN-8: la utilidad debe estar entre 8 % y 25 %.',
    'ck_ppto_rn8_just': 'RN-8: fuera del rango habitual de 12 % a 20 % hay que justificar la utilidad.',
    'ck_partida_fecha': 'Un precio debe tener fecha de actualización y origen; una partida sin precio, ninguno.',
    'ck_ppto_rn7': 'RN-7: el estado no calza con la aprobación (aprobador y fechas de aprobación y emisión).',
    'ck_ppto_fechas': 'Las fechas de aprobación y emisión deben ser posteriores al inicio.',
    'ck_param_valor': 'El parámetro debe estar entre 0 y 100.',
    'ck_ppto_rn9': 'RN-9: el IVA debe estar entre 0 % y 30 %.',
    'ck_ppto_uf': 'El valor UF debe ser mayor que cero.',
    'ck_ppto_m2': 'La superficie debe ser mayor que cero.',
    'ck_ppto_plazo': 'El plazo debe ser mayor que cero.',
    'ck_detalle_cantidad': 'La cantidad debe ser mayor que cero.',
    'ck_detalle_precio': 'El precio aplicado debe ser mayor que cero.',
    'ck_cliente_rut_fmt': 'RUT con formato inválido (use 76.123.456-0).',
    'ck_contratista_rut_fmt': 'RUT con formato inválido (use 76.123.456-0).',
    'ck_cotiz_recepcion': 'Una cotización recibida debe tener monto mayor que cero y fecha de recepción.',
    'ck_cotiz_fechas': 'La fecha de recepción no puede ser anterior a la de solicitud.',
    'ck_cotiz_sel': 'Solo se puede seleccionar una cotización ya recibida.',
    'ck_partida_precio': 'El precio debe ser mayor que cero.',
    'ck_partida_mo': 'El % de mano de obra debe estar entre 0 y 100.',
    'ck_obra_fechas': 'La fecha de término no puede ser anterior a la de inicio.',
    'ck_envio_email': 'Correo de destino inválido.',
}


class ReglaNegocio(Exception):
    """Regla que la app hace cumplir porque un CHECK no puede expresarla (mira otras tablas)."""


def mensaje_error(e: Exception) -> str:
    if isinstance(e, ReglaNegocio):
        return str(e)
    if isinstance(e, mysql.connector.Error):
        if e.errno == 1265 and 'estado' in (e.msg or ''):
            return 'Estado no válido para el presupuesto.'
        if e.errno == 3819:                                   # CHECK violado
            m = re.search(r"'(\w+)'", e.msg or '')
            return MENSAJES_CHECK.get(m.group(1) if m else '', f'Dato no válido ({e.msg}).')
        if e.errno == 1062:
            if 'DETALLE_PRESUPUESTO.PRIMARY' in (e.msg or ''):
                return 'Esa partida ya está en el presupuesto: modifique su cantidad.'
            return f'Ya existe un registro con ese valor ({e.msg}).'
        if e.errno == 1451:
            return 'No se puede eliminar: el registro está siendo usado por otros datos.'
        if e.errno in (2003, 2005, 1045, 1049):
            cfg, origen = config_mysql(), _secretos()[1]
            return (f"No fue posible conectarse a la base de datos: {e.msg}. "
                    f"Configuración leída desde: {origen} · usuario «{cfg['user']}» · "
                    f"contraseña {'informada' if cfg['password'] else 'VACÍA'} · base «{cfg['database']}».")
        return f'Error de base de datos ({e.errno}): {e.msg}'
    return str(e)


def ejecutar(accion: Callable[[], Any], exito: str | None = None) -> bool:
    """Ejecuta una escritura mostrando un mensaje claro si la base la rechaza."""
    try:
        accion()
    except Exception as e:  # noqa: BLE001
        st.error(mensaje_error(e))
        return False
    if exito:
        st.session_state['_aviso'] = exito
    return True


# =============================================================================
# 3. Utilidades de formato y validación
# =============================================================================
def clp(x: Any) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return '—'
    return '$' + f'{round(float(x)):,.0f}'.replace(',', '.')


def uf(x: Any) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return '—'
    return f'{float(x):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') + ' UF'


def pct(x: Any) -> str:
    return '—' if x is None or pd.isna(x) else f'{float(x):g} %'


def normalizar_rut(texto: str) -> str | None:
    """Devuelve el RUT con formato 76.123.456-0 si el dígito verificador es válido."""
    limpio = re.sub(r'[^0-9kK]', '', texto or '').upper()
    if len(limpio) < 8:
        return None
    cuerpo, dv = limpio[:-1], limpio[-1]
    if not cuerpo.isdigit():
        return None
    suma, mult = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    esperado = {11: '0', 10: 'K'}.get(11 - suma % 11, str(11 - suma % 11))
    if dv != esperado:
        return None
    return f'{int(cuerpo):,}'.replace(',', '.') + '-' + dv


def email_valido(texto: str) -> bool:
    return bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', texto or ''))


def hash_clave(clave: str) -> str:
    # Igual a SHA2(clave, 256) de MySQL, usado en el seed. Prototipo académico: en producción
    # usar bcrypt/Argon2 con sal.
    return hashlib.sha256(clave.encode('utf-8')).hexdigest()


@st.cache_data(ttl=3600, show_spinner=False)
def uf_de_hoy() -> float | None:
    """Valor UF del día desde mindicador.cl (API pública con datos del Banco Central)."""
    try:
        r = requests.get('https://mindicador.cl/api/uf', timeout=6)
        r.raise_for_status()
        return float(r.json()['serie'][0]['valor'])
    except Exception:
        return None


def avisar() -> None:
    if '_aviso' in st.session_state:
        st.success(st.session_state.pop('_aviso'))


def ir_a(pagina: str, **estado: Any) -> None:
    st.session_state['_ir_a'] = pagina
    st.session_state.update(estado)
    st.rerun()


def es_gerente() -> bool:
    return st.session_state.get('usuario', {}).get('rol') == 'Gerente General'


def tabla(df: pd.DataFrame, **kw: Any) -> None:
    st.dataframe(df, hide_index=True, width='stretch', **kw)


# =============================================================================
# 4. Inicio de sesión
# =============================================================================
def pantalla_login() -> None:
    st.title('🏗️ Constructora Altura')
    st.caption('Sistema de gestión de presupuestos · Inversiones Rumay Ltda.')
    with st.form('login'):
        email = st.text_input('Correo', key='login_email')
        clave = st.text_input('Contraseña', type='password', key='login_clave')
        entrar = st.form_submit_button('Ingresar', type='primary')
    if entrar:
        try:
            df = consultar('SELECT id_usuario, nombre, email, rol FROM USUARIO '
                           'WHERE email = %s AND password_hash = %s AND activo = TRUE',
                           (email.strip().lower(), hash_clave(clave)))
        except Exception as e:  # noqa: BLE001
            st.error(mensaje_error(e))
            return
        if df.empty:
            st.error('Correo o contraseña incorrectos.')
        else:
            st.session_state['usuario'] = df.iloc[0].to_dict()
            st.rerun()


# =============================================================================
# 5. Consultas reutilizadas
# =============================================================================
SQL_TOTALES = """
SELECT t.*, p.fecha_inicio, p.fecha_aprobacion, p.fecha_emision, p.direccion_obra, p.justificacion_gg, p.justificacion_utilidad,
       p.plazo_ejecucion_dias, p.id_cliente, p.id_usuario, p.id_usuario_aprobador,
       c.rut AS rut_cliente, c.email_contacto, u.nombre AS elaborado_por, a.nombre AS aprobado_por
FROM v_presupuesto_totales t
JOIN PRESUPUESTO p ON p.id_presupuesto = t.id_presupuesto
JOIN CLIENTE c ON c.id_cliente = p.id_cliente
JOIN USUARIO u ON u.id_usuario = p.id_usuario
LEFT JOIN USUARIO a ON a.id_usuario = p.id_usuario_aprobador
"""

SQL_ESTADO_PRECIO = f"""
CASE WHEN p.precio_unitario_referencial IS NULL THEN 'Sin precio'
     WHEN DATEDIFF(NOW(), p.ultima_actualizacion) > {DIAS_VENCIDO} THEN 'Vencido'
     WHEN DATEDIFF(NOW(), p.ultima_actualizacion) >= {DIAS_POR_REVISAR} THEN 'Por revisar'
     ELSE 'Vigente' END
"""

SEMAFORO = {'Vigente': '🟢 Vigente', 'Por revisar': '🟡 Por revisar', 'Vencido': '🔴 Vencido', 'Sin precio': '⚪ Sin precio'}


def presupuesto(id_ppto: int) -> dict | None:
    df = consultar(SQL_TOTALES + ' WHERE t.id_presupuesto = %s', (id_ppto,))
    return None if df.empty else df.iloc[0].to_dict()


def lineas(id_ppto: int) -> pd.DataFrame:
    return consultar(f"""
        SELECT d.nro_linea, p.id_partida, p.codigo, p.descripcion, p.codigo_unidad AS unidad, d.cantidad,
               d.precio_aplicado, ROUND(d.cantidad * d.precio_aplicado, 0) AS subtotal,
               p.precio_unitario_referencial AS precio_catalogo, p.ultima_actualizacion,
               {SQL_ESTADO_PRECIO} AS estado_precio, r.codigo_raiz, r.nombre_raiz, r.orden_raiz, p.orden
        FROM DETALLE_PRESUPUESTO d
        JOIN PARTIDA p ON p.id_partida = d.id_partida
        JOIN v_capitulo_raiz r ON r.id_capitulo = p.id_capitulo
        WHERE d.id_presupuesto = %s
        ORDER BY r.orden_raiz, p.orden""", (id_ppto,))


def cotizaciones(id_ppto: int) -> pd.DataFrame:
    return consultar("""
        SELECT x.nro_cotizacion, e.id_especialidad, e.nombre AS especialidad, c.nombre AS contratista,
               x.fecha_solicitud, x.fecha_recepcion, x.monto_cotizado, x.seleccionada,
               r.codigo_raiz, r.nombre_raiz, r.orden_raiz
        FROM COTIZACION_EXTERNA x
        JOIN ESPECIALIDAD e ON e.id_especialidad = x.id_especialidad
        JOIN CONTRATISTA c ON c.id_contratista = x.id_contratista
        LEFT JOIN v_capitulo_raiz r ON r.id_capitulo = e.id_capitulo
        WHERE x.id_presupuesto = %s
        ORDER BY e.nombre, x.nro_cotizacion""", (id_ppto,))


def _costo_directo(cur: Any, id_ppto: int) -> Decimal:
    cur.execute('SELECT costo_directo FROM v_presupuesto_totales WHERE id_presupuesto = %s', (id_ppto,))
    return Decimal(cur.fetchone()[0] or 0)


# =============================================================================
# 5b. Reglas de negocio que no caben en un CHECK (antes eran triggers; el curso no los ve)
#     Todas se ejecutan dentro de la misma transacción que el cambio: si una falla,
#     ROLLBACK y no se guarda nada (atomicidad, Sesión 08).
# =============================================================================
ABIERTOS = ('Borrador', 'En revision')
TRANSICIONES = {'Borrador': ('En revision',), 'En revision': ('Borrador', 'Aprobado', 'Rechazado'),
                'Rechazado': ('Borrador',), 'Aprobado': ('Emitido',)}


def estado_de(cur: Any, id_ppto: int) -> str:
    cur.execute('SELECT estado FROM PRESUPUESTO WHERE id_presupuesto = %s', (id_ppto,))
    fila = cur.fetchone()
    if fila is None:
        raise ReglaNegocio(f'No existe el presupuesto {id_ppto}.')
    return fila[0]


def exigir_abierto(cur: Any, id_ppto: int) -> None:
    """Trazabilidad: el detalle y las cotizaciones solo cambian en Borrador o En revisión."""
    if estado_de(cur, id_ppto) not in ABIERTOS:
        raise ReglaNegocio('El presupuesto está cerrado (aprobado, rechazado o emitido): no se puede modificar.')


def exigir_emitido(cur: Any, id_ppto: int, que: str) -> None:
    if estado_de(cur, id_ppto) != 'Emitido':
        raise ReglaNegocio(f'Solo un presupuesto Emitido puede {que}.')


def cambiar_estado(cur: Any, id_ppto: int, nuevo: str, id_usuario: int) -> None:
    """RF8 / RN-7: flujo Borrador → En revisión → Aprobado → Emitido (o Rechazado → Borrador)."""
    actual = estado_de(cur, id_ppto)
    if nuevo not in TRANSICIONES.get(actual, ()):
        raise ReglaNegocio(f'Transición no permitida: {actual} → {nuevo} (flujo Borrador → En revisión → Aprobado → Emitido).')
    if nuevo == 'En revision':
        cur.execute('SELECT COUNT(*) FROM DETALLE_PRESUPUESTO WHERE id_presupuesto = %s', (id_ppto,))
        if cur.fetchone()[0] == 0:
            raise ReglaNegocio('El presupuesto no tiene partidas: no puede pasar a revisión.')
    if nuevo in ('Aprobado', 'Rechazado'):
        cur.execute('SELECT rol FROM USUARIO WHERE id_usuario = %s', (id_usuario,))
        fila = cur.fetchone()
        if fila is None or fila[0] != 'Gerente General':
            raise ReglaNegocio('RN-7: solo el Gerente General puede aprobar o rechazar un presupuesto.')
    if nuevo == 'Aprobado':
        cur.execute('SELECT COUNT(*) FROM COTIZACION_EXTERNA WHERE id_presupuesto = %s AND fecha_recepcion IS NULL', (id_ppto,))
        if cur.fetchone()[0] > 0:
            raise ReglaNegocio('Hay cotizaciones externas pendientes: no se puede aprobar.')
    sql = {'En revision': ('UPDATE PRESUPUESTO SET estado = %s WHERE id_presupuesto = %s', (nuevo, id_ppto)),
           'Aprobado':    ('UPDATE PRESUPUESTO SET estado = %s, id_usuario_aprobador = %s, fecha_aprobacion = NOW() '
                           'WHERE id_presupuesto = %s', (nuevo, id_usuario, id_ppto)),
           'Rechazado':   ('UPDATE PRESUPUESTO SET estado = %s, id_usuario_aprobador = %s WHERE id_presupuesto = %s',
                           (nuevo, id_usuario, id_ppto)),
           'Emitido':     ('UPDATE PRESUPUESTO SET estado = %s, fecha_emision = NOW() WHERE id_presupuesto = %s', (nuevo, id_ppto)),
           'Borrador':    ('UPDATE PRESUPUESTO SET estado = %s, id_usuario_aprobador = NULL, fecha_aprobacion = NULL '
                           'WHERE id_presupuesto = %s', (nuevo, id_ppto))}[nuevo]
    cur.execute(*sql)


def actualizar_precio_partida(cur: Any, id_partida: int, nuevo: float) -> None:
    """RN-3 y pregunta 3.1: el precio reemplazado pasa a HISTORIAL_PRECIO y PARTIDA queda con el
    precio nuevo, la fecha del día y origen «Sistema». Si el precio ya se cambió hoy, se corrige sin
    agregar otra fila al historial."""
    hoy = dt.date.today()
    cur.execute('SELECT precio_unitario_referencial, ultima_actualizacion FROM PARTIDA WHERE id_partida = %s', (id_partida,))
    precio, fecha = cur.fetchone()
    if precio is not None and Decimal(str(nuevo)) == precio:
        return
    if precio is not None and fecha < hoy:
        cur.execute('INSERT INTO HISTORIAL_PRECIO (id_partida, fecha_desde, fecha_hasta, precio) VALUES (%s, %s, %s, %s)',
                    (id_partida, fecha, hoy, precio))
    cur.execute("UPDATE PARTIDA SET precio_unitario_referencial = %s, ultima_actualizacion = %s, origen_precio = 'Sistema' "
                'WHERE id_partida = %s', (nuevo, hoy, id_partida))


def cambio_con_correccion(id_ppto: int, estado: str, motivo: str, cambio: Callable[[Any], None]) -> None:
    """Aplica un cambio al presupuesto. Si está En revisión, registra la corrección (KPI de la E1)
    con el costo directo antes y después, en la misma transacción."""
    with transaccion() as cur:
        exigir_abierto(cur, id_ppto)
        antes = _costo_directo(cur, id_ppto) if estado == 'En revision' else None
        cambio(cur)
        if estado == 'En revision':
            despues = _costo_directo(cur, id_ppto)
            if despues != antes:
                cur.execute('SELECT IF(MAX(nro_correccion) IS NULL, 1, MAX(nro_correccion) + 1) FROM CORRECCION_PRESUPUESTO '
                            'WHERE id_presupuesto = %s', (id_ppto,))
                nro = cur.fetchone()[0]
                cur.execute('INSERT INTO CORRECCION_PRESUPUESTO (id_presupuesto, nro_correccion, fecha, id_usuario, '
                            'costo_directo_antes, costo_directo_despues, motivo) VALUES (%s, %s, NOW(), %s, %s, %s, %s)',
                            (id_ppto, nro, int(st.session_state['usuario']['id_usuario']), antes, despues, motivo.strip()))


# =============================================================================
# 6. PDF del presupuesto (RF9)
# =============================================================================
def _latin1(texto: Any) -> str:
    t = str(texto if texto is not None else '')
    t = t.replace('–', '-').replace('—', '-').replace('·', '-').replace('“', '"').replace('”', '"').replace('’', "'")
    return t.encode('latin-1', 'replace').decode('latin-1')


class _PDF(FPDF):
    def __init__(self, borrador: bool):
        super().__init__(format='A4')
        self.borrador = borrador
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(12, 12, 12)

    def header(self) -> None:
        self.set_font('helvetica', 'B', 13)
        self.set_text_color(13, 59, 102)
        self.cell(0, 7, _latin1(EMPRESA), new_x='LMARGIN', new_y='NEXT')
        self.set_draw_color(13, 59, 102)
        self.line(12, self.get_y() + 1, 198, self.get_y() + 1)
        self.ln(4)
        if self.borrador:
            self.set_font('helvetica', 'B', 10)
            self.set_text_color(198, 40, 40)
            self.cell(0, 6, _latin1('BORRADOR - documento no válido como oferta (presupuesto no emitido)'), new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font('helvetica', '', 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 5, _latin1(f'Página {self.page_no()}/{{nb}} - Valores en pesos chilenos'), align='C')


def generar_pdf(id_ppto: int) -> bytes:
    p = presupuesto(id_ppto)
    det = lineas(id_ppto)
    ext = cotizaciones(id_ppto)
    ext = ext[ext['seleccionada'] == 1] if not ext.empty else ext
    pdf = _PDF(borrador=p['estado'] != 'Emitido')
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font('helvetica', 'B', 15)
    pdf.cell(0, 9, _latin1(f'PRESUPUESTO N.° {id_ppto}'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('helvetica', '', 10)
    fecha = p['fecha_emision'] or p['fecha_inicio']
    datos = [
        ('Cliente', f"{p['cliente']} (RUT {p['rut_cliente']})"),
        ('Proyecto', p['nombre_proyecto']),
        ('Dirección de la obra', p['direccion_obra'] or '-'),
        ('Superficie', f"{p['superficie_m2']:g} m2" if pd.notna(p['superficie_m2']) and p['superficie_m2'] else '-'),
        ('Condiciones', f"{p['ubicacion']} - jornada {p['tipo_jornada'].lower()}"
                        + (' - incluye fines de semana' if p['trabajo_fin_semana'] else '')),
        ('Plazo de ejecución', f"{int(p['plazo_ejecucion_dias'])} días corridos" if pd.notna(p['plazo_ejecucion_dias']) else '-'),
        ('Fecha', pd.to_datetime(fecha).strftime('%d-%m-%Y')),
        ('Valor UF del día', '$ ' + f"{float(p['valor_uf_dia']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')),
    ]
    for k, v in datos:
        pdf.set_font('helvetica', 'B', 10)
        pdf.cell(45, 6, _latin1(k))
        pdf.set_font('helvetica', '', 10)
        pdf.multi_cell(0, 6, _latin1(v), new_x='LMARGIN', new_y='NEXT')
    pdf.ln(3)

    # Partidas agrupadas por capítulo, como en la planilla de la empresa
    pdf.set_font('helvetica', '', 8.5)
    with pdf.table(col_widths=(16, 86, 12, 18, 26, 28), text_align=('LEFT', 'LEFT', 'CENTER', 'RIGHT', 'RIGHT', 'RIGHT'),
                   line_height=4.6, first_row_as_headings=True) as t:
        enc = t.row()
        for h in ('Ítem', 'Descripción', 'Un.', 'Cantidad', 'P. unitario', 'Total'):
            enc.cell(_latin1(h))
        bloques: dict[tuple, list] = {}
        for _, l in det.iterrows():
            bloques.setdefault((l['orden_raiz'], l['codigo_raiz'], l['nombre_raiz']), []).append(
                (l['codigo'], l['descripcion'], l['unidad'], f"{l['cantidad']:g}".replace('.', ','),
                 clp(l['precio_aplicado']), clp(l['subtotal'])))
        for _, x in ext.iterrows():
            k = (x['orden_raiz'] if pd.notna(x['orden_raiz']) else 9999, x['codigo_raiz'] or '-', x['nombre_raiz'] or 'ESPECIALIDADES')
            bloques.setdefault(k, []).append(('', f"{x['especialidad']} (subcontrato, según cotización)", 'GL', '1',
                                              clp(x['monto_cotizado']), clp(x['monto_cotizado'])))
        for (_, cod, nom), filas in sorted(bloques.items(), key=lambda kv: kv[0][0]):
            r = t.row()
            r.cell(_latin1(f'{cod}  {nom}'), colspan=6)
            for f in filas:
                r = t.row()
                for v in f:
                    r.cell(_latin1(v))
    pdf.ln(4)

    totales = [
        ('Costo directo', p['costo_directo']),
        (f"Gastos generales ({p['pct_gastos_generales']:g} %)", p['gastos_generales']),
        (f"Utilidad ({p['pct_utilidad']:g} %)", p['utilidad']),
        ('TOTAL NETO', p['total_neto']),
        (f"IVA ({p['pct_iva']:g} %)", p['iva']),
        ('TOTAL CON IVA', p['total_con_iva']),
    ]
    for k, v in totales:
        negrita = k.startswith('TOTAL')
        pdf.set_font('helvetica', 'B' if negrita else '', 10)
        pdf.cell(130, 6, _latin1(k), align='R')
        pdf.cell(56, 6, _latin1(clp(v)), align='R', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(130, 6, 'TOTAL CON IVA EN UF', align='R')
    pdf.cell(56, 6, _latin1(uf(p['total_con_iva_uf'])), align='R', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)
    pdf.set_font('helvetica', '', 8.5)
    pdf.multi_cell(0, 4.5, _latin1(
        'Gastos generales y utilidad calculados sobre el costo directo. Las partidas de especialidades se valorizan '
        'según la cotización del subcontratista seleccionado. Valores sujetos a variación de la UF.'))
    return bytes(pdf.output())


# =============================================================================
# 7. Envío al cliente por n8n → Outlook (RF9) y registro del envío
# =============================================================================
def _json(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime, pd.Timestamp)):
        return pd.to_datetime(v).isoformat()
    if isinstance(v, float) and pd.isna(v):
        return None
    if hasattr(v, 'item'):
        return v.item()
    return v


def enviar_a_cliente(id_ppto: int, email_destino: str) -> tuple[bool, str]:
    p = presupuesto(id_ppto)
    det = lineas(id_ppto)
    ext = cotizaciones(id_ppto)
    pdf = generar_pdf(id_ppto)
    nombre_pdf = f'Presupuesto_{id_ppto}_Constructora_Altura.pdf'
    paquete = {
        'evento': 'presupuesto_emitido',
        'id_presupuesto': id_ppto,
        'nombre_proyecto': p['nombre_proyecto'],
        'cliente': {'rut': p['rut_cliente'], 'razon_social': p['cliente']},
        'email_destino': email_destino,
        'asunto': f"Presupuesto N.° {id_ppto} - {p['nombre_proyecto']} - Constructora Altura",
        'cuerpo': (f"Estimados {p['cliente']}:\n\nAdjuntamos el presupuesto N.° {id_ppto} para el proyecto "
                   f"\"{p['nombre_proyecto']}\", por un total de {clp(p['total_con_iva'])} IVA incluido "
                   f"({uf(p['total_con_iva_uf'])}).\n\nQuedamos atentos a sus comentarios.\n\nConstructora Altura"),
        'fecha_emision': _json(p['fecha_emision']),
        'valor_uf_dia': _json(p['valor_uf_dia']),
        'totales': {k: _json(p[k]) for k in ('costo_directo', 'gastos_generales', 'utilidad', 'total_neto', 'iva',
                                              'total_con_iva', 'total_neto_uf', 'total_con_iva_uf')},
        'partidas': [{k: _json(v) for k, v in r.items() if k in ('codigo', 'descripcion', 'unidad', 'cantidad',
                                                                  'precio_aplicado', 'subtotal')} for r in det.to_dict('records')],
        'externos': [{'especialidad': r['especialidad'], 'contratista': r['contratista'], 'monto': _json(r['monto_cotizado'])}
                     for r in ext.to_dict('records') if r['seleccionada']],
        'pdf': {'nombre_archivo': nombre_pdf, 'mime': 'application/pdf', 'base64': base64.b64encode(pdf).decode()},
    }
    url = url_n8n()
    if not url:
        ok, detalle = False, 'No hay URL de n8n configurada (n8n.webhook_url en secrets.toml).'
    else:
        try:
            r = requests.post(url, json=paquete, timeout=25)
            ok = 200 <= r.status_code < 300
            detalle = 'PDF adjunto enviado desde el correo corporativo' if ok else f'n8n respondió {r.status_code}: {r.text[:150]}'
        except requests.RequestException as e:
            ok, detalle = False, f'No se pudo contactar a n8n: {e.__class__.__name__}'
    with transaccion() as cur:
        exigir_emitido(cur, id_ppto, 'enviarse al cliente')
        cur.execute('INSERT INTO ENVIO_PRESUPUESTO (id_presupuesto, fecha_envio, email_destino, canal, resultado, detalle) '
                    'VALUES (%s, NOW(), %s, %s, %s, %s)',
                    (id_ppto, email_destino, 'Outlook (n8n)', 'Enviado' if ok else 'Error', detalle[:255]))
    return ok, detalle


# =============================================================================
# 8. Páginas
# =============================================================================
def pagina_inicio() -> None:
    st.title('Panel principal')
    st.caption('Todos los indicadores se calculan en línea desde la base de datos.')
    avisar()
    estados = consultar('SELECT estado, COUNT(*) AS n FROM PRESUPUESTO GROUP BY estado')
    n = {e: int(estados.loc[estados.estado == e, 'n'].sum()) for e in ESTADOS}
    emit = consultar("SELECT COUNT(*) AS n, IF(COUNT(*) = 0, 0, SUM(total_neto)) AS neto, IF(COUNT(*) = 0, 0, SUM(total_con_iva)) AS bruto "
                     "FROM v_presupuesto_totales WHERE estado = 'Emitido'").iloc[0]
    vig = consultar('SELECT estado_precio, COUNT(*) AS n FROM v_partida_vigencia GROUP BY estado_precio')
    con_precio = int(vig.loc[vig.estado_precio != 'Sin precio', 'n'].sum())
    vigentes = int(vig.loc[vig.estado_precio == 'Vigente', 'n'].sum())
    vencidas = int(vig.loc[vig.estado_precio.str.startswith('Vencido'), 'n'].sum())
    horas = valor("SELECT ROUND(AVG(TIMESTAMPDIFF(MINUTE, fecha_inicio, fecha_emision)) / 60, 1) FROM PRESUPUESTO "
                  "WHERE estado = 'Emitido'")   # TIMESTAMPDIFF: diferencia en minutos (DATEDIFF solo mide días)
    pendientes = int(valor('SELECT COUNT(*) FROM COTIZACION_EXTERNA WHERE fecha_recepcion IS NULL') or 0)

    c = st.columns(4)
    c[0].metric('Presupuestos abiertos', n['Borrador'] + n['En revision'] + n['Aprobado'],
                help='Borrador + En revisión + Aprobado')
    c[1].metric('Emitidos', int(emit['n']), help='Presupuestos enviados al cliente')
    c[2].metric('Total emitido (neto)', clp(emit['neto']), help=f"Con IVA: {clp(emit['bruto'])}")
    c[3].metric('Tiempo medio de elaboración', f'{horas:g} h' if horas is not None else '—',
                help='Desde el inicio hasta la emisión (meta E1: 4 h para un presupuesto estándar)')
    c = st.columns(4)
    c[0].metric('Precios vigentes (< 3 meses)', f'{100 * vigentes / con_precio:.0f} %' if con_precio else '—',
                help='Sobre las partidas con precio de referencia')
    c[1].metric('Precios vencidos (> 6 meses)', vencidas)
    c[2].metric('Cotizaciones externas pendientes', pendientes)
    c[3].metric('Esperando aprobación', n['En revision'])

    st.subheader('Presupuestos')
    df = consultar(SQL_TOTALES + ' ORDER BY t.id_presupuesto DESC')
    if not df.empty:
        vista = df[['id_presupuesto', 'nombre_proyecto', 'cliente', 'estado', 'fecha_inicio', 'total_neto', 'total_con_iva', 'total_con_iva_uf']]
        tabla(vista.rename(columns={'id_presupuesto': 'N.°', 'nombre_proyecto': 'Proyecto', 'cliente': 'Cliente', 'estado': 'Estado',
                                    'fecha_inicio': 'Inicio', 'total_neto': 'Total neto', 'total_con_iva': 'Total c/IVA',
                                    'total_con_iva_uf': 'Total c/IVA (UF)'}),
              column_config={'Total neto': st.column_config.NumberColumn(format='$%,.0f'),
                             'Total c/IVA': st.column_config.NumberColumn(format='$%,.0f'),
                             'Total c/IVA (UF)': st.column_config.NumberColumn(format='%,.2f')})

    alertas = consultar(f"""
        SELECT pr.id_presupuesto AS id, pr.nombre_proyecto, pr.estado,
               SUM(IF(DATEDIFF(NOW(), p.ultima_actualizacion) > {DIAS_VENCIDO}, 1, 0)) AS vencidas,
               SUM(IF(DATEDIFF(NOW(), p.ultima_actualizacion) BETWEEN {DIAS_POR_REVISAR} AND {DIAS_VENCIDO}, 1, 0)) AS por_revisar
        FROM DETALLE_PRESUPUESTO d JOIN PRESUPUESTO pr ON pr.id_presupuesto = d.id_presupuesto
        JOIN PARTIDA p ON p.id_partida = d.id_partida
        WHERE pr.estado IN ('Borrador', 'En revision', 'Aprobado')
        GROUP BY pr.id_presupuesto, pr.nombre_proyecto, pr.estado
        HAVING vencidas > 0 OR por_revisar > 0""")
    durante = consultar(f"""
        SELECT pr.id_presupuesto AS id, pr.nombre_proyecto, pr.plazo_ejecucion_dias AS plazo,
               SUM(IF(DATEDIFF(NOW(), p.ultima_actualizacion) + pr.plazo_ejecucion_dias > {DIAS_VENCIDO}, 1, 0)) AS lineas
        FROM DETALLE_PRESUPUESTO d JOIN PRESUPUESTO pr ON pr.id_presupuesto = d.id_presupuesto
        JOIN PARTIDA p ON p.id_partida = d.id_partida
        WHERE pr.estado IN ('Borrador', 'En revision', 'Aprobado') AND pr.plazo_ejecucion_dias IS NOT NULL
        GROUP BY pr.id_presupuesto, pr.nombre_proyecto, pr.plazo_ejecucion_dias HAVING lineas > 0""")
    if not alertas.empty:
        st.subheader('⚠️ Alertas de precios (RN-4)')
        for _, a in alertas.iterrows():
            st.warning(f"Presupuesto {a['id']} «{a['nombre_proyecto']}» ({a['estado']}): {int(a['vencidas'])} línea(s) con "
                       f"precio vencido y {int(a['por_revisar'])} por revisar. Actualícelas antes de emitir.")
    if not durante.empty:
        st.subheader('📅 Precios que vencerán durante la obra')
        for _, a in durante.iterrows():
            st.info(f"Presupuesto {a['id']} «{a['nombre_proyecto']}»: {int(a['lineas'])} línea(s) tendrán más de {MESES_VENCIDO} meses "
                    f"antes de terminar la obra ({int(a['plazo'])} días). Considere reajuste o cotizar de nuevo al comprar.")


def pagina_nuevo() -> None:
    st.title('Nuevo presupuesto')
    avisar()
    clientes = consultar('SELECT id_cliente, razon_social, rut FROM CLIENTE ORDER BY razon_social')
    if clientes.empty:
        st.info('Primero registre un cliente en la página «Clientes».')
        return
    uf_sugerida = uf_de_hoy()
    uf_ultima = valor('SELECT valor_uf_dia FROM PRESUPUESTO ORDER BY fecha_inicio DESC LIMIT 1')

    with st.form('nuevo_ppto'):
        st.subheader('1. Antecedentes')
        c1, c2 = st.columns(2)
        id_cliente = c1.selectbox('Cliente', clientes['id_cliente'].tolist(), key='np_cliente',
                                  format_func=lambda i: '{} ({})'.format(*clientes.loc[clientes.id_cliente == i, ['razon_social', 'rut']].iloc[0]))
        nombre = c2.text_input('Nombre del proyecto', key='np_nombre')
        direccion = c1.text_input('Dirección de la obra (incluya comuna / ciudad)', key='np_dir')
        superficie = c2.number_input('Superficie (m²) — opcional', min_value=0.0, step=10.0, key='np_m2')
        plazo = c1.number_input('Plazo de ejecución ofrecido (días corridos)', min_value=0, step=1, key='np_plazo',
                                help='Referencia de la empresa: una obra completa de oficina toma 5-6 meses (150-180 días) o más.')
        valor_uf = c2.number_input('Valor UF del día ($)', min_value=0.0, step=0.01, format='%.2f', key='np_uf',
                                   value=float(uf_sugerida or uf_ultima or 0.0),
                                   help='Se propone la UF de hoy (mindicador.cl) o, si no hay conexión, la del último presupuesto.')

        st.subheader('2. Condiciones de la obra (factores de gastos generales)')
        c1, c2, c3 = st.columns(3)
        ubicacion = c1.radio('Ubicación', ['Santiago', 'Fuera de Santiago'], key='np_ubic', horizontal=True)
        jornada = c2.radio('Jornada', ['Diurna', 'Nocturna'], key='np_jornada', horizontal=True)
        finde = c3.checkbox('Trabajo en fines de semana', key='np_finde')

        st.subheader('3. Porcentajes (sobre el costo directo)')
        c1, c2, c3 = st.columns(3)
        gg = c1.number_input('Gastos generales (%) — RN-5', min_value=GG_MIN, max_value=GG_MAX, value=8.0, step=1.0, key='np_gg',
                             help='Habituales 5, 8 o 10 %; hasta 12 % según las condiciones de la obra. Incluye imprevistos y gastos de zona.')
        util = c2.number_input('Utilidad (%) — RN-8', min_value=UTIL_MIN_ABS, max_value=UTIL_MAX_ABS, value=15.0, step=1.0, key='np_util',
                               help='Habitual 12–20 % (ej. 12, 13, 15, 18 %). Fuera de ese rango hay que justificar (mín. 8 %, máx. 25 %).')
        iva = c3.number_input('IVA (%) — RN-9', min_value=0.0, max_value=30.0, value=IVA_DEFECTO, step=1.0, key='np_iva')
        justif = st.text_area('Justificación de gastos generales (obligatoria sobre 10 %)', key='np_just',
                              placeholder='Ej.: obra fuera de Santiago, trabajo nocturno con oficinas ocupadas, izaje...')
        justif_util = st.text_area('Justificación de la utilidad (obligatoria fuera de 12–20 %)', key='np_just_util',
                                   placeholder='Ej.: obra de gran tamaño y cliente recurrente (utilidad menor), obra de alto riesgo (mayor)...')
        crear = st.form_submit_button('Crear presupuesto en borrador', type='primary')

    if not crear:
        return
    errores = []
    if not nombre.strip():
        errores.append('Ingrese el nombre del proyecto.')
    if valor_uf <= 0:
        errores.append('Ingrese el valor UF del día.')
    if gg > GG_SIN_JUSTIFICAR and not justif.strip():
        errores.append('RN-5: sobre 10 % de gastos generales debe justificar las condiciones de la obra.')
    if not (UTIL_MIN <= util <= UTIL_MAX) and not justif_util.strip():
        errores.append('RN-8: fuera del rango habitual de 12 % a 20 % debe justificar la utilidad.')
    for e in errores:
        st.error(e)
    if errores:
        return
    nuevo: dict = {}

    def crear_ppto() -> None:
        with transaccion() as cur:
            cur.execute("""INSERT INTO PRESUPUESTO (id_cliente, id_usuario, nombre_proyecto, direccion_obra, superficie_m2,
                               fecha_inicio, valor_uf_dia, ubicacion, tipo_jornada, trabajo_fin_semana, pct_gastos_generales,
                               justificacion_gg, pct_utilidad, justificacion_utilidad, pct_iva, plazo_ejecucion_dias, estado)
                           VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Borrador')""",
                        (int(id_cliente), int(st.session_state['usuario']['id_usuario']), nombre.strip(), direccion.strip() or None,
                         superficie or None, valor_uf, ubicacion, jornada, finde, gg, justif.strip() or None, util,
                         justif_util.strip() or None, iva, int(plazo) or None))
            nuevo['id'] = cur.lastrowid

    if ejecutar(crear_ppto):
        ir_a('Presupuestos', ppto_sel=nuevo['id'], _aviso=f'Presupuesto N.° {nuevo["id"]} creado en borrador. Agregue sus partidas.')


def pagina_presupuestos() -> None:
    st.title('Presupuestos')
    avisar()
    df = consultar(SQL_TOTALES + ' ORDER BY t.id_presupuesto DESC')
    if df.empty:
        st.info('Aún no hay presupuestos. Cree uno en «Nuevo presupuesto».')
        return
    filtro = st.multiselect('Filtrar por estado', ESTADOS, default=[], key='pp_filtro', placeholder='Todos los estados')
    vista = df[df.estado.isin(filtro)] if filtro else df
    ids = vista['id_presupuesto'].astype(int).tolist()
    if not ids:
        st.info('No hay presupuestos con ese estado.')
        return
    sel = st.session_state.get('ppto_sel')
    idx = ids.index(sel) if sel in ids else 0
    id_ppto = st.selectbox('Presupuesto', ids, index=idx, key='pp_select',
                           format_func=lambda i: '{}  ·  {}  ·  {}  ·  {}'.format(
                               i, *vista.loc[vista.id_presupuesto == i, ['nombre_proyecto', 'cliente', 'estado']].iloc[0]))
    st.session_state['ppto_sel'] = id_ppto
    detalle_presupuesto(int(id_ppto))


def detalle_presupuesto(id_ppto: int) -> None:
    p = presupuesto(id_ppto)
    estado = p['estado']
    editable = estado in ESTADOS_EDITABLES
    colores = {'Borrador': 'gray', 'En revision': 'orange', 'Aprobado': 'blue', 'Rechazado': 'red', 'Emitido': 'green'}
    st.markdown(f"### N.° {id_ppto} · {p['nombre_proyecto']}  :{colores[estado]}-badge[{estado}]")
    st.caption(f"{p['cliente']} (RUT {p['rut_cliente']}) · {p['direccion_obra'] or 'sin dirección'} · {p['ubicacion']} · "
               f"jornada {p['tipo_jornada'].lower()}{' · fines de semana' if p['trabajo_fin_semana'] else ''} · "
               f"elaborado por {p['elaborado_por']}" + (f" · aprobado por {p['aprobado_por']}" if p['aprobado_por'] else ''))

    c = st.columns(6)
    c[0].metric('Costo directo', clp(p['costo_directo']))
    c[1].metric(f"GG ({pct(p['pct_gastos_generales'])})", clp(p['gastos_generales']))
    c[2].metric(f"Utilidad ({pct(p['pct_utilidad'])})", clp(p['utilidad']))
    c[3].metric('Total neto', clp(p['total_neto']))
    c[4].metric(f"IVA ({pct(p['pct_iva'])})", clp(p['iva']))
    c[5].metric('Total con IVA', clp(p['total_con_iva']), help=uf(p['total_con_iva_uf']))
    if p['justificacion_gg']:
        st.caption(f"Justificación GG: {p['justificacion_gg']}")
    if p['justificacion_utilidad']:
        st.caption(f"Justificación utilidad: {p['justificacion_utilidad']}")
    comp = consultar('SELECT * FROM v_presupuesto_composicion WHERE id_presupuesto = %s', (id_ppto,))
    if not comp.empty and comp.iloc[0]['total_neto']:
        k = comp.iloc[0]
        tn = float(k['total_neto'])
        st.caption(f"Composición del total neto (pregunta 3.2): remuneraciones {100 * (k['remuneraciones_base'] + k['recargo_jornada']) / tn:.1f} % "
                   f"(recargo de jornada {100 * k['recargo_jornada'] / tn:.1f} %) · materiales {100 * k['materiales'] / tn:.1f} % · "
                   f"subcontratos {100 * k['costo_externos'] / tn:.1f} %  — % de mano de obra estimado por tipo de partida.")
        if p['estado'] in ABIERTOS and k['recargo_jornada'] > 0 and k['gg_neto'] < k['gg_minimo']:   # solo mientras se puede corregir
            sugerido = 100 * (k['gg_minimo'] + k['recargo_jornada']) / k['costo_directo']
            st.warning(f"Los gastos generales ({pct(p['pct_gastos_generales'])}) no alcanzan a cubrir el recargo de mano de obra por "
                       f"jornada nocturna / fines de semana ({clp(k['recargo_jornada'])}). Haría falta ≈ {sugerido:.1f} %; "
                       f"si supera el 12 %, conviene recargar los precios unitarios de mano de obra en vez de los GG.")
    if estado == 'En revision':
        st.info('El presupuesto está **en revisión**: cada cambio que altere el costo queda registrado como corrección (con motivo).')

    t1, t2, t3, t4 = st.tabs(['Partidas', 'Cotizaciones externas', 'Correcciones', 'Flujo, PDF y envío'])
    with t1:
        seccion_partidas(id_ppto, estado, editable)
    with t2:
        seccion_cotizaciones(id_ppto, estado, editable)
    with t3:
        corr = consultar("""SELECT k.nro_correccion AS 'N.°', k.fecha AS Fecha, u.nombre AS Usuario,
                                   k.costo_directo_antes AS 'Costo antes', k.costo_directo_despues AS 'Costo después',
                                   k.motivo AS Motivo
                            FROM CORRECCION_PRESUPUESTO k JOIN USUARIO u ON u.id_usuario = k.id_usuario
                            WHERE k.id_presupuesto = %s ORDER BY k.nro_correccion""", (id_ppto,))
        if corr.empty:
            st.caption('Sin correcciones registradas.')
        else:
            tabla(corr, column_config={'Costo antes': st.column_config.NumberColumn(format='$%,.0f'),
                                       'Costo después': st.column_config.NumberColumn(format='$%,.0f')})
            ini, fin = float(corr.iloc[0]['Costo antes']), float(p['costo_directo'])
            if fin:
                st.metric('Error de costo inicial vs. revisado', f'{100 * abs(ini - fin) / fin:.2f} %', help='Meta E1: ≤ 5 %')
    with t4:
        seccion_flujo(id_ppto, p)


def seccion_partidas(id_ppto: int, estado: str, editable: bool) -> None:
    det = lineas(id_ppto)
    if det.empty:
        st.caption('El presupuesto aún no tiene partidas.')
    else:
        v = det.copy()
        v['Precio'] = v['estado_precio'].map(SEMAFORO)
        v['Dif. vs catálogo'] = v['precio_catalogo'] - v['precio_aplicado']
        tabla(v[['nro_linea', 'codigo_raiz', 'codigo', 'descripcion', 'unidad', 'cantidad', 'precio_aplicado', 'subtotal',
                 'Precio', 'precio_catalogo', 'Dif. vs catálogo']].rename(columns={
                    'nro_linea': 'Línea', 'codigo_raiz': 'Cap.', 'codigo': 'Código', 'descripcion': 'Descripción', 'unidad': 'Un.',
                    'cantidad': 'Cantidad', 'precio_aplicado': 'P. aplicado', 'subtotal': 'Subtotal', 'precio_catalogo': 'P. catálogo'}),
              column_config={k: st.column_config.NumberColumn(format='$%,.0f') for k in ('P. aplicado', 'Subtotal', 'P. catálogo', 'Dif. vs catálogo')})
        venc = int((det.estado_precio == 'Vencido').sum())
        rev = int((det.estado_precio == 'Por revisar').sum())
        antiguos = det[(det.precio_catalogo.notna()) & (det.precio_aplicado != det.precio_catalogo)]
        if editable and (venc or rev):          # en un presupuesto cerrado ya no se puede corregir: no se avisa
            st.warning(f'RN-4: {venc} línea(s) con precio vencido (> {MESES_VENCIDO} meses) y {rev} por revisar '
                       f'({MESES_POR_REVISAR}–{MESES_VENCIDO} meses). Actualice esos precios en el catálogo antes de emitir.')
        if editable and not antiguos.empty:
            st.warning(f'{len(antiguos)} línea(s) usan un precio distinto al vigente del catálogo '
                       f'(diferencia total {clp((antiguos.precio_catalogo - antiguos.precio_aplicado).mul(antiguos.cantidad).sum())}).')
    if not editable:
        st.caption(f'El presupuesto está {estado.lower()}: el detalle ya no se puede modificar (trazabilidad).')
        return

    motivo_req = estado == 'En revision'
    with st.expander('➕ Agregar partida', expanded=det.empty):
        caps = consultar('SELECT id_capitulo, codigo, nombre FROM CAPITULO WHERE id_capitulo_padre IS NULL ORDER BY orden')
        cap = st.selectbox('Capítulo', [None] + caps['id_capitulo'].tolist(), key=f'ap_cap_{id_ppto}',
                           format_func=lambda i: 'Todos' if i is None else '{} {}'.format(*caps.loc[caps.id_capitulo == i, ['codigo', 'nombre']].iloc[0]))
        cat = consultar(f"""SELECT p.id_partida, p.codigo, p.descripcion, p.codigo_unidad, p.precio_unitario_referencial AS precio,
                                   {SQL_ESTADO_PRECIO} AS estado_precio, r.id_raiz
                            FROM PARTIDA p JOIN v_capitulo_raiz r ON r.id_capitulo = p.id_capitulo
                            WHERE p.activo = TRUE AND p.id_partida NOT IN
                                  (SELECT id_partida FROM DETALLE_PRESUPUESTO WHERE id_presupuesto = %s)
                            ORDER BY r.orden_raiz, p.orden""", (id_ppto,))
        if cap is not None:
            cat = cat[cat.id_raiz == cap]
        if cat.empty:
            st.caption('No quedan partidas disponibles en este capítulo.')
        else:
            with st.form(f'agregar_{id_ppto}', clear_on_submit=True):
                id_part = st.selectbox('Partida', cat['id_partida'].tolist(), key=f'ap_part_{id_ppto}',
                                       format_func=lambda i: '{} · {} · {} · {}'.format(
                                           *cat.loc[cat.id_partida == i, ['codigo', 'descripcion', 'codigo_unidad']].iloc[0],
                                           (lambda f: f"{clp(f.precio)} ({SEMAFORO[f.estado_precio]})")(cat.loc[cat.id_partida == i].iloc[0])))
                c1, c2 = st.columns(2)
                cant = c1.number_input('Cantidad', min_value=0.0, step=1.0, key=f'ap_cant_{id_ppto}')
                precio_manual = c2.number_input('Precio unitario ($) — solo si la partida no tiene precio o se cotizó otro',
                                                min_value=0.0, step=100.0, key=f'ap_precio_{id_ppto}')
                motivo = st.text_input('Motivo de la corrección', key=f'ap_mot_{id_ppto}') if motivo_req else ''
                ok = st.form_submit_button('Agregar', type='primary')
            if ok:
                fila = cat.loc[cat.id_partida == id_part].iloc[0]
                precio = precio_manual or (fila.precio if pd.notna(fila.precio) else 0)
                if cant <= 0:
                    st.error('La cantidad debe ser mayor que cero.')
                elif precio <= 0:
                    st.error('La partida no tiene precio de referencia: ingrese el precio unitario cotizado.')
                elif motivo_req and not motivo.strip():
                    st.error('En revisión, indique el motivo de la corrección.')
                else:
                    def add(cur: Any) -> None:
                        cur.execute('SELECT activo FROM PARTIDA WHERE id_partida = %s', (int(id_part),))
                        if not cur.fetchone()[0]:
                            raise ReglaNegocio('La partida está desactivada en el catálogo.')
                        cur.execute('SELECT IF(MAX(nro_linea) IS NULL, 1, MAX(nro_linea) + 1) FROM DETALLE_PRESUPUESTO WHERE id_presupuesto = %s', (id_ppto,))
                        nro = cur.fetchone()[0]
                        cur.execute('INSERT INTO DETALLE_PRESUPUESTO (id_presupuesto, id_partida, nro_linea, cantidad, precio_aplicado) '
                                    'VALUES (%s, %s, %s, %s, %s)', (id_ppto, int(id_part), nro, cant, precio))
                    if ejecutar(lambda: cambio_con_correccion(id_ppto, estado, motivo, add), 'Partida agregada.'):
                        st.rerun()

    if det.empty:
        return
    with st.expander('✏️ Modificar o quitar una partida'):
        with st.form(f'editar_{id_ppto}'):
            nro = st.selectbox('Línea', det['nro_linea'].astype(int).tolist(), key=f'ed_linea_{id_ppto}',
                               format_func=lambda n: '{} · {} · {}'.format(n, *det.loc[det.nro_linea == n, ['codigo', 'descripcion']].iloc[0]))
            c1, c2, c3 = st.columns(3)
            nueva_cant = c1.number_input('Nueva cantidad (0 = no cambiar)', min_value=0.0, step=1.0, key=f'ed_cant_{id_ppto}')
            nuevo_precio = c2.number_input('Nuevo precio ($, 0 = no cambiar)', min_value=0.0, step=100.0, key=f'ed_precio_{id_ppto}')
            usar_catalogo = c3.checkbox('Usar el precio vigente del catálogo', key=f'ed_cat_{id_ppto}')
            quitar = st.checkbox('Quitar la línea del presupuesto', key=f'ed_quitar_{id_ppto}')
            motivo = st.text_input('Motivo de la corrección', key=f'ed_mot_{id_ppto}') if motivo_req else ''
            ok = st.form_submit_button('Aplicar cambio')
        if ok:
            fila = det.loc[det.nro_linea == nro].iloc[0]
            precio = fila.precio_catalogo if usar_catalogo else (nuevo_precio or fila.precio_aplicado)
            cant = nueva_cant or fila.cantidad
            if motivo_req and not motivo.strip():
                st.error('En revisión, indique el motivo de la corrección.')
            elif usar_catalogo and pd.isna(fila.precio_catalogo):
                st.error('La partida no tiene precio en el catálogo.')
            else:
                def cambio(cur: Any) -> None:
                    if quitar:
                        cur.execute('DELETE FROM DETALLE_PRESUPUESTO WHERE id_presupuesto = %s AND nro_linea = %s', (id_ppto, int(nro)))
                    else:
                        cur.execute('UPDATE DETALLE_PRESUPUESTO SET cantidad = %s, precio_aplicado = %s '
                                    'WHERE id_presupuesto = %s AND nro_linea = %s', (cant, precio, id_ppto, int(nro)))
                if ejecutar(lambda: cambio_con_correccion(id_ppto, estado, motivo, cambio), 'Cambio aplicado.'):
                    st.rerun()
        lin_cat = det[(det.precio_catalogo.notna()) & (det.precio_aplicado != det.precio_catalogo)]
        if not lin_cat.empty and st.button(f'Actualizar las {len(lin_cat)} línea(s) al precio vigente del catálogo', key=f'ed_todas_{id_ppto}'):
            if motivo_req:
                mot = 'Actualización de precios al valor vigente del catálogo'
            else:
                mot = ''

            def act(cur: Any) -> None:
                for _, ln in lin_cat.iterrows():
                    cur.execute('UPDATE DETALLE_PRESUPUESTO SET precio_aplicado = %s WHERE id_presupuesto = %s AND id_partida = %s',
                                (float(ln.precio_catalogo), id_ppto, int(ln.id_partida)))
            if ejecutar(lambda: cambio_con_correccion(id_ppto, estado, mot, act), 'Precios actualizados.'):
                st.rerun()


def seccion_cotizaciones(id_ppto: int, estado: str, editable: bool) -> None:
    cot = cotizaciones(id_ppto)
    if cot.empty:
        st.caption('Sin cotizaciones externas.')
    else:
        v = cot.copy()
        v['Estado'] = v.apply(lambda r: '✅ Seleccionada' if r.seleccionada else ('📨 Recibida' if pd.notna(r.fecha_recepcion) else '⏳ Pendiente'), axis=1)
        v['Días de respuesta'] = (pd.to_datetime(v.fecha_recepcion) - pd.to_datetime(v.fecha_solicitud)).dt.days
        tabla(v[['nro_cotizacion', 'especialidad', 'contratista', 'fecha_solicitud', 'fecha_recepcion', 'Días de respuesta', 'monto_cotizado', 'Estado']]
              .rename(columns={'nro_cotizacion': 'N.°', 'especialidad': 'Especialidad', 'contratista': 'Contratista',
                               'fecha_solicitud': 'Solicitada', 'fecha_recepcion': 'Recibida', 'monto_cotizado': 'Monto'}),
              column_config={'Monto': st.column_config.NumberColumn(format='$%,.0f')})
    if not editable:
        return
    motivo_req = estado == 'En revision'
    c1, c2, c3 = st.columns(3)
    with c1, st.form(f'solicitar_{id_ppto}', clear_on_submit=True):
        st.markdown('**Solicitar cotización**')
        contr = consultar('SELECT c.id_contratista, c.nombre, e.id_especialidad, e.nombre AS especialidad FROM CONTRATISTA c '
                          'JOIN ESPECIALIDAD e ON e.id_especialidad = c.id_especialidad WHERE c.activo = TRUE ORDER BY e.nombre, c.nombre')
        id_c = st.selectbox('Contratista', contr['id_contratista'].tolist(), key=f'sc_c_{id_ppto}',
                            format_func=lambda i: '{} · {}'.format(*contr.loc[contr.id_contratista == i, ['especialidad', 'nombre']].iloc[0]))
        f_sol = st.date_input('Fecha de solicitud', value=dt.date.today(), key=f'sc_f_{id_ppto}', format='DD-MM-YYYY')
        if st.form_submit_button('Registrar solicitud') and id_c is not None:
            esp = int(contr.loc[contr.id_contratista == id_c, 'id_especialidad'].iloc[0])

            def sol() -> None:
                with transaccion() as cur:
                    exigir_abierto(cur, id_ppto)
                    cur.execute('SELECT IF(MAX(nro_cotizacion) IS NULL, 1, MAX(nro_cotizacion) + 1) FROM COTIZACION_EXTERNA WHERE id_presupuesto = %s', (id_ppto,))
                    nro = cur.fetchone()[0]
                    cur.execute('INSERT INTO COTIZACION_EXTERNA (id_presupuesto, nro_cotizacion, id_contratista, id_especialidad, fecha_solicitud) '
                                'VALUES (%s, %s, %s, %s, %s)', (id_ppto, nro, int(id_c), esp, f_sol))
            if ejecutar(sol, 'Solicitud registrada.'):
                st.rerun()
    pend = cot[cot.fecha_recepcion.isna()] if not cot.empty else cot
    with c2, st.form(f'recibir_{id_ppto}', clear_on_submit=True):
        st.markdown('**Registrar cotización recibida**')
        nro = st.selectbox('Cotización pendiente', pend['nro_cotizacion'].astype(int).tolist() if not pend.empty else [], key=f'rc_n_{id_ppto}',
                           format_func=lambda n: '{} · {} · {}'.format(n, *pend.loc[pend.nro_cotizacion == n, ['especialidad', 'contratista']].iloc[0]))
        monto = st.number_input('Monto cotizado ($ neto)', min_value=0.0, step=10000.0, key=f'rc_m_{id_ppto}')
        f_rec = st.date_input('Fecha de recepción', value=dt.date.today(), key=f'rc_f_{id_ppto}', format='DD-MM-YYYY')
        if st.form_submit_button('Registrar recepción') and nro is not None:
            if monto <= 0:
                st.error('Ingrese el monto cotizado.')
            else:
                def rec() -> None:
                    with transaccion() as cur:
                        exigir_abierto(cur, id_ppto)
                        cur.execute('UPDATE COTIZACION_EXTERNA SET monto_cotizado = %s, fecha_recepcion = %s '
                                    'WHERE id_presupuesto = %s AND nro_cotizacion = %s', (monto, f_rec, id_ppto, int(nro)))
                if ejecutar(rec, 'Cotización recibida.'):
                    st.rerun()
    recib = cot[cot.fecha_recepcion.notna() & (cot.seleccionada == 0)] if not cot.empty else cot
    with c3, st.form(f'seleccionar_{id_ppto}'):
        st.markdown('**Seleccionar la cotización que entra al costo**')
        nro_s = st.selectbox('Cotización recibida', recib['nro_cotizacion'].astype(int).tolist() if not recib.empty else [], key=f'sl_n_{id_ppto}',
                             format_func=lambda n: '{} · {} · {} · {}'.format(n, *recib.loc[recib.nro_cotizacion == n, ['especialidad', 'contratista']].iloc[0],
                                                                         clp(recib.loc[recib.nro_cotizacion == n, 'monto_cotizado'].iloc[0])))
        motivo = st.text_input('Motivo de la corrección', key=f'sl_m_{id_ppto}') if motivo_req else ''
        if st.form_submit_button('Seleccionar') and nro_s is not None:
            if motivo_req and not motivo.strip():
                st.error('En revisión, indique el motivo de la corrección.')
            else:
                esp = int(recib.loc[recib.nro_cotizacion == nro_s, 'id_especialidad'].iloc[0])

                def sel(cur: Any) -> None:   # solo una seleccionada por especialidad
                    cur.execute('UPDATE COTIZACION_EXTERNA SET seleccionada = FALSE WHERE id_presupuesto = %s AND id_especialidad = %s',
                                (id_ppto, esp))
                    cur.execute('UPDATE COTIZACION_EXTERNA SET seleccionada = TRUE WHERE id_presupuesto = %s AND nro_cotizacion = %s',
                                (id_ppto, int(nro_s)))
                if ejecutar(lambda: cambio_con_correccion(id_ppto, estado, motivo, sel), 'Cotización seleccionada.'):
                    st.rerun()


def seccion_flujo(id_ppto: int, p: dict) -> None:
    estado = p['estado']
    usuario = st.session_state['usuario']
    st.markdown('**Flujo del presupuesto (RF8 / RN-7):** Borrador → En revisión → Aprobado → Emitido')
    fechas = {'Inicio': p['fecha_inicio'], 'Aprobación': p['fecha_aprobacion'], 'Emisión': p['fecha_emision']}
    st.caption(' · '.join(f'{k}: {pd.to_datetime(v).strftime("%d-%m-%Y %H:%M")}' for k, v in fechas.items() if pd.notna(v)))

    def mover(nuevo: str) -> Callable[[], None]:
        def f() -> None:
            with transaccion() as cur:
                cambiar_estado(cur, id_ppto, nuevo, int(usuario['id_usuario']))
        return f

    c = st.columns(4)
    if estado == 'Borrador':
        if c[0].button('📤 Enviar a revisión', key='fl_rev', type='primary'):
            if ejecutar(mover('En revision'), 'Presupuesto enviado a revisión.'):
                st.rerun()
    elif estado == 'En revision':
        if es_gerente():
            if c[0].button('✅ Aprobar', key='fl_apr', type='primary'):
                if ejecutar(mover('Aprobado'), 'Presupuesto aprobado.'):
                    st.rerun()
            if c[1].button('❌ Rechazar', key='fl_rech'):
                if ejecutar(mover('Rechazado'), 'Presupuesto rechazado.'):
                    st.rerun()
        else:
            c[0].info('Solo el Gerente General puede aprobar o rechazar (RN-7).')
        if c[2].button('↩️ Devolver a borrador', key='fl_bor'):
            if ejecutar(mover('Borrador'), 'Presupuesto devuelto a borrador.'):
                st.rerun()
    elif estado == 'Aprobado':
        if c[0].button('📄 Emitir', key='fl_emi', type='primary'):
            if ejecutar(mover('Emitido'), 'Presupuesto emitido: ya puede enviarse al cliente.'):
                st.rerun()
    elif estado == 'Rechazado':
        if c[0].button('↩️ Reabrir como borrador', key='fl_reab'):
            if ejecutar(mover('Borrador'), 'Presupuesto reabierto.'):
                st.rerun()

    st.divider()
    try:
        pdf = generar_pdf(id_ppto)
        st.download_button('⬇️ Descargar PDF' + ('' if estado == 'Emitido' else ' (borrador)'), data=pdf,
                           file_name=f'Presupuesto_{id_ppto}_Constructora_Altura.pdf', mime='application/pdf', key='fl_pdf')
    except Exception as e:  # noqa: BLE001
        st.error(f'No se pudo generar el PDF: {e}')

    if estado == 'Emitido':
        st.markdown('**Enviar al cliente** (n8n → correo corporativo Outlook, con el PDF adjunto)')
        with st.form('envio'):
            destino = st.text_input('Correo del cliente', value=p['email_contacto'] or '', key='fl_dest')
            enviar = st.form_submit_button('📧 Enviar presupuesto', type='primary')
        if enviar:
            if not email_valido(destino):
                st.error('Ingrese un correo válido.')
            else:
                with st.spinner('Enviando a n8n...'):
                    try:
                        ok, detalle = enviar_a_cliente(id_ppto, destino.strip())
                    except Exception as e:  # noqa: BLE001
                        ok, detalle = False, mensaje_error(e)
                (st.success if ok else st.error)(('Enviado: ' if ok else 'No se envió: ') + detalle)
        env = consultar("SELECT fecha_envio AS Fecha, email_destino AS Destino, canal AS Canal, resultado AS Resultado, detalle AS Detalle "
                        "FROM ENVIO_PRESUPUESTO WHERE id_presupuesto = %s ORDER BY fecha_envio DESC", (id_ppto,))
        if not env.empty:
            st.markdown('**Historial de envíos**')
            tabla(env)


def pagina_catalogo() -> None:
    st.title('Catálogo de partidas')
    avisar()
    cat = consultar(f"""SELECT p.id_partida, p.codigo, p.descripcion, p.codigo_unidad AS unidad,
                               p.precio_unitario_referencial AS precio, p.ultima_actualizacion,
                               {SQL_ESTADO_PRECIO} AS estado_precio, p.origen_precio, p.pct_mano_obra, p.fuente, p.activo,
                               r.id_raiz, r.codigo_raiz, r.nombre_raiz
                        FROM PARTIDA p JOIN v_capitulo_raiz r ON r.id_capitulo = p.id_capitulo
                        ORDER BY r.orden_raiz, p.orden""")
    act = cat[cat.activo == 1]
    cnt = act.estado_precio.value_counts()
    c = st.columns(5)
    c[0].metric('Partidas activas', len(act))
    for i, k in enumerate(('Vigente', 'Por revisar', 'Vencido', 'Sin precio'), 1):
        c[i].metric(SEMAFORO[k], int(cnt.get(k, 0)))
    st.caption(f'Semáforo (RN-4): vigente < {MESES_POR_REVISAR} meses · por revisar {MESES_POR_REVISAR}–{MESES_VENCIDO} meses · '
               f'vencido > {MESES_VENCIDO} meses desde la última actualización. La empresa actualiza precios con cada obra nueva.')

    c1, c2, c3 = st.columns([2, 2, 3])
    caps = act[['id_raiz', 'codigo_raiz', 'nombre_raiz']].drop_duplicates()
    f_cap = c1.selectbox('Capítulo', [None] + caps['id_raiz'].tolist(), key='cat_cap',
                         format_func=lambda i: 'Todos' if i is None else '{} {}'.format(*caps.loc[caps.id_raiz == i, ['codigo_raiz', 'nombre_raiz']].iloc[0]))
    f_est = c2.multiselect('Estado del precio', list(SEMAFORO), key='cat_est', placeholder='Todos')
    f_txt = c3.text_input('Buscar por código o descripción', key='cat_txt')
    ver_inact = st.checkbox('Mostrar también partidas desactivadas', key='cat_inact')
    v = cat if ver_inact else act
    if f_cap is not None:
        v = v[v.id_raiz == f_cap]
    if f_est:
        v = v[v.estado_precio.isin(f_est)]
    if f_txt:
        v = v[v.codigo.str.contains(f_txt, case=False, regex=False) | v.descripcion.str.contains(f_txt, case=False, regex=False)]
    vv = v.copy()
    vv['Estado'] = vv.estado_precio.map(SEMAFORO)
    tabla(vv[['codigo', 'descripcion', 'unidad', 'precio', 'ultima_actualizacion', 'Estado', 'origen_precio', 'pct_mano_obra', 'fuente', 'activo']]
          .rename(columns={'codigo': 'Código', 'descripcion': 'Descripción', 'unidad': 'Un.', 'precio': 'Precio ref.',
                           'ultima_actualizacion': 'Actualizado', 'origen_precio': 'Origen precio', 'pct_mano_obra': '% M.O. (diurno)',
                           'fuente': 'Partida de', 'activo': 'Activa'}),
          column_config={'Precio ref.': st.column_config.NumberColumn(format='$%,.0f'),
                         'Activa': st.column_config.CheckboxColumn()}, height=420)

    t1, t2, t3 = st.tabs(['Actualizar precio / datos', 'Nueva partida', 'Historial de precios'])
    with t1, st.form('cat_editar'):
        id_p = st.selectbox('Partida', cat['id_partida'].tolist(), key='ce_part',
                            format_func=lambda i: '{} · {}'.format(*cat.loc[cat.id_partida == i, ['codigo', 'descripcion']].iloc[0]))
        fila = cat.loc[cat.id_partida == id_p].iloc[0] if id_p is not None else None
        c1, c2, c3 = st.columns(3)
        nuevo_precio = c1.number_input('Nuevo precio de referencia ($, 0 = no cambiar)', min_value=0.0, step=100.0, key='ce_precio')
        mo = c2.number_input('% mano de obra (−1 = no cambiar)', min_value=-1.0, max_value=100.0, value=-1.0, step=5.0, key='ce_mo')
        activa = c3.selectbox('Estado', ['No cambiar', 'Activa', 'Desactivada'], key='ce_act')
        st.caption('Al cambiar el precio, la fecha se actualiza sola (RN-3) y el precio anterior queda en el historial.')
        if st.form_submit_button('Guardar', type='primary') and fila is not None:
            sets, params = [], []
            if mo >= 0:
                sets.append('pct_mano_obra = %s')
                params.append(mo)
            if activa != 'No cambiar':
                sets.append('activo = %s')
                params.append(activa == 'Activa')
            if not sets and nuevo_precio <= 0:
                st.info('No hay cambios que guardar.')
            else:
                def upd() -> None:
                    with transaccion() as cur:
                        if nuevo_precio > 0:
                            actualizar_precio_partida(cur, int(id_p), nuevo_precio)
                        if sets:
                            cur.execute(f"UPDATE PARTIDA SET {', '.join(sets)} WHERE id_partida = %s", (*params, int(id_p)))
                if ejecutar(upd, f'Partida {fila.codigo} actualizada.'):
                    st.rerun()
    with t2, st.form('cat_nueva', clear_on_submit=True):
        caps_all = consultar('SELECT id_capitulo, codigo, nombre FROM CAPITULO ORDER BY orden')
        unidades = consultar('SELECT codigo_unidad, descripcion FROM UNIDAD_MEDIDA ORDER BY codigo_unidad')
        c1, c2 = st.columns(2)
        id_cap = c1.selectbox('Capítulo / subcapítulo', caps_all['id_capitulo'].tolist(), key='cn_cap',
                              format_func=lambda i: '{} {}'.format(*caps_all.loc[caps_all.id_capitulo == i, ['codigo', 'nombre']].iloc[0]))
        codigo = c2.text_input('Código (ej. 4.3.7)', key='cn_cod')
        desc = st.text_input('Descripción', key='cn_desc')
        c1, c2, c3 = st.columns(3)
        unidad = c1.selectbox('Unidad', unidades['codigo_unidad'].tolist(), key='cn_un')
        precio = c2.number_input('Precio de referencia ($, 0 = sin precio)', min_value=0.0, step=100.0, key='cn_precio')
        mo = c3.number_input('% mano de obra', min_value=0.0, max_value=100.0, value=40.0, step=5.0, key='cn_mo')
        if st.form_submit_button('Crear partida', type='primary'):
            if not codigo.strip() or not desc.strip():
                st.error('Ingrese código y descripción.')
            else:
                def ins() -> None:
                    with transaccion() as cur:
                        cur.execute('SELECT IF(MAX(orden) IS NULL, 1, MAX(orden) + 1) FROM PARTIDA')
                        orden = cur.fetchone()[0]
                        cur.execute('INSERT INTO PARTIDA (codigo, id_capitulo, descripcion, codigo_unidad, precio_unitario_referencial, '
                                    'ultima_actualizacion, origen_precio, pct_mano_obra, fuente, orden) '
                                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                                    (codigo.strip(), int(id_cap), desc.strip().upper(), unidad, precio or None,
                                     dt.date.today() if precio else None, 'Sistema' if precio else None, mo, 'Sistema', orden))
                if ejecutar(ins, 'Partida creada.'):
                    st.rerun()
    with t3:
        con_hist = cat[cat.precio.notna()]
        id_h = st.selectbox('Partida', con_hist['id_partida'].tolist(), key='ch_part',
                            format_func=lambda i: '{} · {}'.format(*con_hist.loc[con_hist.id_partida == i, ['codigo', 'descripcion']].iloc[0]))
        if id_h is not None:
            h = consultar('SELECT fecha_desde AS Desde, fecha_hasta AS Hasta, precio AS Precio, tipo AS Tipo '
                          'FROM v_precio_en_el_tiempo WHERE id_partida = %s ORDER BY fecha_desde', (int(id_h),))
            tabla(h, column_config={'Precio': st.column_config.NumberColumn(format='$%,.0f')})
            if len(h) > 1:
                st.line_chart(h.set_index('Desde')['Precio'])


def pagina_clientes() -> None:
    st.title('Clientes')
    avisar()
    cl = consultar("""SELECT c.id_cliente, c.rut AS RUT, c.razon_social AS 'Razón social', c.direccion AS Dirección,
                             c.email_contacto AS Correo, COUNT(p.id_presupuesto) AS Presupuestos
                      FROM CLIENTE c LEFT JOIN PRESUPUESTO p ON p.id_cliente = c.id_cliente
                      GROUP BY c.id_cliente, c.rut, c.razon_social, c.direccion, c.email_contacto
                      ORDER BY c.razon_social""")
    tel = consultar("""SELECT id_cliente, numero, tipo_telefono, es_preferido FROM TELEFONO_CLIENTE
                       ORDER BY id_cliente, es_preferido DESC, nro_telefono""")
    if not cl.empty:
        cl.insert(5, 'Teléfonos', cl.id_cliente.map(lambda i: ' · '.join(
            f"{t.numero} ({t.tipo_telefono}{', preferido' if t.es_preferido else ''})"
            for t in tel[tel.id_cliente == i].itertuples())))
    tabla(cl.drop(columns=['id_cliente']))
    c1, c2 = st.columns(2)
    with c1, st.form('cli_nuevo', clear_on_submit=True):
        st.markdown('**Nuevo cliente**')
        rut = st.text_input('RUT', key='cl_rut', placeholder='76.123.456-0')
        razon = st.text_input('Razón social', key='cl_razon')
        dirc = st.text_input('Dirección', key='cl_dir')
        mail = st.text_input('Correo de contacto', key='cl_mail')
        if st.form_submit_button('Guardar cliente', type='primary'):
            rut_ok = normalizar_rut(rut)
            if not rut_ok:
                st.error('RUT inválido (revise el dígito verificador).')
            elif not razon.strip():
                st.error('Ingrese la razón social.')
            elif mail and not email_valido(mail):
                st.error('Correo inválido.')
            else:
                def ins() -> None:
                    with transaccion() as cur:
                        cur.execute('INSERT INTO CLIENTE (rut, razon_social, direccion, email_contacto) VALUES (%s, %s, %s, %s)',
                                    (rut_ok, razon.strip(), dirc.strip() or None, mail.strip().lower() or None))
                if ejecutar(ins, f'Cliente {razon.strip()} creado.'):
                    st.rerun()
    with c2, st.form('cli_tel', clear_on_submit=True):
        st.markdown('**Agregar teléfono**')
        id_c = st.selectbox('Cliente', cl['id_cliente'].tolist(), key='ct_cli',
                            format_func=lambda i: cl.loc[cl.id_cliente == i, 'Razón social'].iloc[0])
        num = st.text_input('Número', key='ct_num', placeholder='+56 9 1234 5678')
        tipo = st.text_input('Tipo', key='ct_tipo', placeholder='Celular, oficina...')
        pref = st.checkbox('Preferido', key='ct_pref')
        if st.form_submit_button('Agregar teléfono') and id_c is not None:
            if not num.strip() or not tipo.strip():
                st.error('Ingrese número y tipo.')
            else:
                def tel() -> None:
                    with transaccion() as cur:
                        if pref:
                            cur.execute('UPDATE TELEFONO_CLIENTE SET es_preferido = FALSE WHERE id_cliente = %s', (int(id_c),))
                        cur.execute('SELECT IF(MAX(nro_telefono) IS NULL, 1, MAX(nro_telefono) + 1) FROM TELEFONO_CLIENTE WHERE id_cliente = %s', (int(id_c),))
                        n = cur.fetchone()[0]
                        cur.execute('INSERT INTO TELEFONO_CLIENTE VALUES (%s, %s, %s, %s, %s)', (int(id_c), n, num.strip(), tipo.strip(), pref))
                if ejecutar(tel, 'Teléfono agregado.'):
                    st.rerun()


def pagina_contratistas() -> None:
    st.title('Especialidades y contratistas')
    avisar()
    co = consultar("""SELECT e.nombre AS Especialidad, c.nombre AS Contratista, c.rut AS RUT, c.email AS Correo, c.telefono AS Teléfono,
                             COUNT(x.nro_cotizacion) AS Cotizaciones, SUM(IF(x.seleccionada, 1, 0)) AS Seleccionadas,
                             ROUND(AVG(DATEDIFF(x.fecha_recepcion, x.fecha_solicitud)), 1) AS 'Días de respuesta (prom.)'
                      FROM CONTRATISTA c JOIN ESPECIALIDAD e ON e.id_especialidad = c.id_especialidad
                      LEFT JOIN COTIZACION_EXTERNA x ON x.id_contratista = c.id_contratista
                      WHERE c.activo = TRUE
                      GROUP BY e.nombre, c.nombre, c.rut, c.email, c.telefono ORDER BY e.nombre, c.nombre""")
    tabla(co)
    esp = consultar('SELECT id_especialidad, nombre FROM ESPECIALIDAD ORDER BY nombre')
    with st.form('contr_nuevo', clear_on_submit=True):
        st.markdown('**Nuevo contratista**')
        c1, c2 = st.columns(2)
        rut = c1.text_input('RUT', key='co_rut')
        nombre = c2.text_input('Nombre / razón social', key='co_nombre')
        id_e = c1.selectbox('Especialidad', esp['id_especialidad'].tolist(), key='co_esp',
                            format_func=lambda i: esp.loc[esp.id_especialidad == i, 'nombre'].iloc[0])
        mail = c2.text_input('Correo', key='co_mail')
        fono = c1.text_input('Teléfono', key='co_fono')
        if st.form_submit_button('Guardar contratista', type='primary'):
            rut_ok = normalizar_rut(rut)
            if not rut_ok:
                st.error('RUT inválido (revise el dígito verificador).')
            elif not nombre.strip():
                st.error('Ingrese el nombre.')
            elif mail and not email_valido(mail):
                st.error('Correo inválido.')
            else:
                def ins() -> None:
                    with transaccion() as cur:
                        cur.execute('INSERT INTO CONTRATISTA (rut, nombre, id_especialidad, email, telefono) VALUES (%s, %s, %s, %s, %s)',
                                    (rut_ok, nombre.strip(), int(id_e), mail.strip().lower() or None, fono.strip() or None))
                if ejecutar(ins, 'Contratista creado.'):
                    st.rerun()


def pagina_obras() -> None:
    st.title('Obras y plazos de entrega')
    st.caption('Pregunta 3.3 del Gerente: plazo ofrecido vs. plazo real. Según la empresa, una obra completa de oficina toma 5-6 meses '
               'o más y depende de la disponibilidad de materiales. La planificación detallada sigue en la carta Gantt.')
    avisar()
    ob = consultar("""SELECT o.id_presupuesto AS id, p.nombre_proyecto, p.plazo_ejecucion_dias AS plazo_ofrecido,
                             o.fecha_inicio_obra, o.fecha_termino_obra,
                             IF(o.fecha_termino_obra IS NULL, DATEDIFF(NOW(), o.fecha_inicio_obra),
                                DATEDIFF(o.fecha_termino_obra, o.fecha_inicio_obra)) AS dias
                      FROM OBRA o JOIN PRESUPUESTO p ON p.id_presupuesto = o.id_presupuesto ORDER BY o.fecha_inicio_obra DESC""")
    if not ob.empty:
        ob['Situación'] = ob.fecha_termino_obra.isna().map({True: 'En ejecución', False: 'Terminada'})
        ob['Desviación (días)'] = (ob.dias - ob.plazo_ofrecido).where(ob['Situación'] == 'Terminada')
        ob['% plazo consumido'] = (100 * ob.dias / ob.plazo_ofrecido).round(1)
        for _, o in ob[(ob['Situación'] == 'En ejecución') & (ob['% plazo consumido'] > 100)].iterrows():
            st.warning(f"La obra {o['id']} «{o['nombre_proyecto']}» ya superó su plazo ofrecido ({int(o['plazo_ofrecido'])} días).")
        term = ob[ob['Situación'] == 'Terminada']
        c = st.columns(3)
        c[0].metric('Obras terminadas', len(term))
        c[1].metric('Plazo real promedio', f'{term.dias.mean():.1f} días' if len(term) else '—',
                    help=f'Plazo ofrecido promedio: {term.plazo_ofrecido.mean():.1f} días' if len(term) else None)
        c[2].metric('Desviación promedio', f'{(100 * (term.dias - term.plazo_ofrecido) / term.plazo_ofrecido).mean():.1f} %' if len(term) else '—')
        tabla(ob.rename(columns={'nombre_proyecto': 'Proyecto', 'plazo_ofrecido': 'Plazo ofrecido', 'fecha_inicio_obra': 'Inicio',
                                 'fecha_termino_obra': 'Término', 'dias': 'Días reales / transcurridos'}))
    c1, c2 = st.columns(2)
    sin_obra = consultar("SELECT p.id_presupuesto, p.nombre_proyecto FROM PRESUPUESTO p "      # anti-join (Ayudantía 6)
                         "LEFT JOIN OBRA o ON o.id_presupuesto = p.id_presupuesto "
                         "WHERE p.estado = 'Emitido' AND o.id_presupuesto IS NULL")
    with c1, st.form('obra_ini', clear_on_submit=True):
        st.markdown('**Registrar inicio de obra** (presupuesto emitido y aceptado por el cliente)')
        idp = st.selectbox('Presupuesto', sin_obra['id_presupuesto'].tolist(), key='ob_ppto',
                           format_func=lambda i: '{} · {}'.format(i, sin_obra.loc[sin_obra.id_presupuesto == i, 'nombre_proyecto'].iloc[0]))
        f = st.date_input('Fecha de inicio', value=dt.date.today(), key='ob_ini', format='DD-MM-YYYY')
        if st.form_submit_button('Registrar inicio') and idp is not None:
            def ini() -> None:
                with transaccion() as cur:
                    exigir_emitido(cur, int(idp), 'registrarse como obra')
                    cur.execute('INSERT INTO OBRA (id_presupuesto, fecha_inicio_obra) VALUES (%s, %s)', (int(idp), f))
            if ejecutar(ini, 'Inicio de obra registrado.'):
                st.rerun()
    en_ej = ob[ob['Situación'] == 'En ejecución'] if not ob.empty else ob
    with c2, st.form('obra_fin', clear_on_submit=True):
        st.markdown('**Registrar término de obra**')
        idt = st.selectbox('Obra en ejecución', en_ej['id'].tolist() if not en_ej.empty else [], key='ob_term',
                           format_func=lambda i: '{} · {}'.format(i, en_ej.loc[en_ej.id == i, 'nombre_proyecto'].iloc[0]))
        f2 = st.date_input('Fecha de término', value=dt.date.today(), key='ob_fin', format='DD-MM-YYYY')
        if st.form_submit_button('Registrar término') and idt is not None:
            def fin() -> None:
                with transaccion() as cur:
                    cur.execute('UPDATE OBRA SET fecha_termino_obra = %s WHERE id_presupuesto = %s', (f2, int(idt)))
            if ejecutar(fin, 'Término de obra registrado.'):
                st.rerun()


def pagina_indicadores() -> None:
    st.title('Indicadores y preguntas de oro')
    corte = st.date_input('Fecha de corte', value=dt.date.today(), key='ind_corte', format='DD-MM-YYYY')
    prm = {'corte': corte}

    st.header('Preguntas de oro del Gerente General')
    st.subheader('3.1 ¿Qué tipo de precio se está usando en los presupuestos?')
    g1 = consultar("""
        SELECT d.id_presupuesto AS Presupuesto,
               CASE WHEN d.precio_aplicado = v.precio THEN 'Último precio registrado'
                    WHEN h.precio IS NOT NULL THEN 'Precio antiguo'
                    ELSE 'Otro (ajustado)' END AS tipo_precio,
               COUNT(*) AS Líneas, ROUND(SUM(d.cantidad * d.precio_aplicado), 0) AS Monto,
               ROUND(100 * SUM(d.cantidad * (d.precio_aplicado - pp.precio_promedio)) / SUM(d.cantidad * pp.precio_promedio), 1)
                   AS '% sobre precio promedio'
        FROM DETALLE_PRESUPUESTO d
        JOIN PRESUPUESTO pr ON pr.id_presupuesto = d.id_presupuesto
        LEFT JOIN v_precio_en_el_tiempo v ON v.id_partida = d.id_partida AND v.fecha_desde <= pr.fecha_inicio
                                         AND (v.fecha_hasta IS NULL OR v.fecha_hasta > pr.fecha_inicio)
        LEFT JOIN HISTORIAL_PRECIO h ON h.id_partida = d.id_partida AND h.precio = d.precio_aplicado
                                    AND h.fecha_hasta <= pr.fecha_inicio
        LEFT JOIN v_precio_promedio pp ON pp.id_partida = d.id_partida
        GROUP BY d.id_presupuesto, tipo_precio ORDER BY d.id_presupuesto, tipo_precio""").rename(columns={'tipo_precio': 'Tipo'})
    if not g1.empty:
        tabla(g1, column_config={'Monto': st.column_config.NumberColumn(format='$%,.0f')})
        piv = g1.pivot_table(index='Presupuesto', columns='Tipo', values='Monto', aggfunc='sum').fillna(0)
        st.bar_chart(piv, y_label='Monto ($)')

    st.subheader('3.2 ¿Qué % del costo total son remuneraciones y qué % materiales?')
    st.caption('El % de mano de obra de cada partida es una estimación por tipo de partida (jornada diurna). El recargo por '
               'jornada nocturna y fines de semana usa los parámetros de costo; la empresa lo cubre con los gastos generales.')
    g2 = consultar("""
        SELECT id_presupuesto AS Presupuesto, estado AS Estado, tipo_jornada AS Jornada,
               IF(trabajo_fin_semana, 'Sí', 'No') AS 'Fin de semana',
               ROUND(100 * remuneraciones_base / total_neto, 1) AS 'Remuneraciones base',
               ROUND(100 * recargo_jornada / total_neto, 1) AS 'Recargo jornada',
               ROUND(100 * materiales / total_neto, 1) AS Materiales,
               ROUND(100 * costo_externos / total_neto, 1) AS Subcontratos,
               ROUND(100 * proyectos_y_seguros / total_neto, 1) AS 'Proyectos y seguros',
               ROUND(100 * gg_neto / total_neto, 1) AS 'GG neto',
               ROUND(100 * utilidad / total_neto, 1) AS Utilidad,
               IF(recargo_jornada = 0, '—', IF(gg_neto >= gg_minimo, 'Alcanza', 'No alcanza')) AS 'GG cubre recargo'
        FROM v_presupuesto_composicion WHERE total_neto > 0 ORDER BY id_presupuesto""")
    if not g2.empty:
        tabla(g2)
        st.bar_chart(g2.drop(columns=['Estado', 'Jornada', 'Fin de semana', 'GG cubre recargo']).set_index('Presupuesto'),
                     y_label='% del total neto', horizontal=True)
        n = int((g2['GG cubre recargo'] == 'No alcanza').sum())
        if n:
            st.warning(f'En {n} presupuesto(s) con jornada nocturna o fines de semana, el % de gastos generales no alcanza a cubrir '
                       'el recargo de mano de obra (GG neto negativo o bajo el mínimo de una obra diurna).')

    st.subheader('3.3 ¿Cuáles son los plazos promedio de entrega de las obras?')
    g3 = consultar("""SELECT COUNT(*) AS 'Obras terminadas', ROUND(AVG(p.plazo_ejecucion_dias), 1) AS 'Plazo ofrecido (días)',
                             ROUND(AVG(DATEDIFF(o.fecha_termino_obra, o.fecha_inicio_obra)), 1) AS 'Plazo real (días)',
                             ROUND(AVG(100 * (DATEDIFF(o.fecha_termino_obra, o.fecha_inicio_obra) - p.plazo_ejecucion_dias)
                                   / p.plazo_ejecucion_dias), 1) AS 'Desviación promedio (%)'
                      FROM OBRA o JOIN PRESUPUESTO p ON p.id_presupuesto = o.id_presupuesto
                      WHERE o.fecha_termino_obra IS NOT NULL AND o.fecha_termino_obra <= %(corte)s""", prm)
    tabla(g3)

    st.header('KPI de la Entrega 1')
    c1, c2 = st.columns(2)
    with c1:
        st.subheader('Vigencia de precios del catálogo')
        k = consultar(f"""SELECT COUNT(*) - COUNT(precio_unitario_referencial) AS 'Sin precio',
                                 SUM(IF(DATEDIFF(%(corte)s, ultima_actualizacion) < {DIAS_POR_REVISAR}, 1, 0)) AS Vigentes,
                                 SUM(IF(DATEDIFF(%(corte)s, ultima_actualizacion) BETWEEN {DIAS_POR_REVISAR} AND {DIAS_VENCIDO}, 1, 0)) AS 'Por revisar',
                                 SUM(IF(DATEDIFF(%(corte)s, ultima_actualizacion) > {DIAS_VENCIDO}, 1, 0)) AS Vencidas
                          FROM PARTIDA WHERE activo = TRUE""", prm)
        tabla(k)
        st.subheader('Tiempo de elaboración (meta ≤ 4 h)')
        t = consultar("""SELECT p.id_presupuesto AS Presupuesto,
                                IF(COUNT(x.nro_cotizacion) > 0, 'Sí', 'No') AS 'Con externos',
                                ROUND(TIMESTAMPDIFF(MINUTE, p.fecha_inicio, p.fecha_emision) / 60, 1) AS Horas
                         FROM PRESUPUESTO p LEFT JOIN COTIZACION_EXTERNA x ON x.id_presupuesto = p.id_presupuesto
                         WHERE p.estado = 'Emitido' AND DATEDIFF(p.fecha_emision, %(corte)s) <= 0
                         GROUP BY p.id_presupuesto, p.fecha_inicio, p.fecha_emision ORDER BY Horas""", prm)
        tabla(t)
    with c2:
        st.subheader('Correcciones y % de error de costo (meta ≤ 5 %)')
        e = consultar("""SELECT k.id_presupuesto AS Presupuesto, COUNT(*) AS Correcciones,
                                ROUND(100 * IF(i.costo_directo_antes > t.costo_directo, i.costo_directo_antes - t.costo_directo,
                                               t.costo_directo - i.costo_directo_antes) / t.costo_directo, 2) AS '% error'
                         FROM CORRECCION_PRESUPUESTO k
                         JOIN CORRECCION_PRESUPUESTO i ON i.id_presupuesto = k.id_presupuesto AND i.nro_correccion = 1
                         JOIN v_presupuesto_totales t ON t.id_presupuesto = k.id_presupuesto
                         GROUP BY k.id_presupuesto, i.costo_directo_antes, t.costo_directo ORDER BY Presupuesto""")
        tabla(e)
        st.subheader('Espera de cotizaciones externas')
        w = consultar("""SELECT e.nombre AS Especialidad, COUNT(*) AS Solicitadas, COUNT(x.fecha_recepcion) AS Recibidas,
                                ROUND(AVG(DATEDIFF(x.fecha_recepcion, x.fecha_solicitud)), 1) AS 'Días promedio',
                                COUNT(*) - COUNT(x.fecha_recepcion) AS Pendientes
                         FROM COTIZACION_EXTERNA x JOIN ESPECIALIDAD e ON e.id_especialidad = x.id_especialidad
                         GROUP BY e.nombre ORDER BY e.nombre""")
        tabla(w)


def pagina_parametros() -> None:
    st.title('Parámetros y reglas del sistema')
    st.markdown(f"""
| Regla | Valor | Origen |
|---|---|---|
| RN-4 Vigencia de precios | vigente < {MESES_POR_REVISAR} meses · por revisar {MESES_POR_REVISAR}–{MESES_VENCIDO} · vencido > {MESES_VENCIDO} | Empresa: se actualizan con cada obra (3 a 6 meses) |
| RN-5 Gastos generales | {GG_MIN:g}–{GG_MAX:g} % (habituales 5, 8, 10 %); justificación sobre {GG_SIN_JUSTIFICAR:g} % | Entrevista 15-11-2026 |
| RN-8 Utilidad | habitual {UTIL_MIN:g}–{UTIL_MAX:g} %; fuera de ese rango con justificación (mín. {UTIL_MIN_ABS:g}, máx. {UTIL_MAX_ABS:g} %) | Entrevista 15-11-2026; planilla real con 11 % |
| RN-9 IVA | {IVA_DEFECTO:g} % | Se incorpora en cada presupuesto |
| Base de cálculo | GG y utilidad sobre el costo directo | Planilla de la empresa |
| RN-7 Aprobación | Solo el Gerente General aprueba o rechaza | Entrega 1 |
""")
    st.caption('Los rangos de RN-5 y RN-8 y la coherencia de estados y fechas (RN-7) los hace cumplir la base con CHECK, aunque se use '
               'otra aplicación. El flujo de estados, quién aprueba y el historial de precios los controla esta app dentro de transacciones.')
    st.subheader('Parámetros de costo (composición de remuneraciones)')
    prm = consultar('SELECT clave, valor, descripcion, fuente FROM PARAMETRO_COSTO ORDER BY clave')
    if es_gerente():
        editado = st.data_editor(prm, key='prm_editor', hide_index=True, width='stretch',
                                 disabled=['clave', 'descripcion', 'fuente'],
                                 column_config={'valor': st.column_config.NumberColumn('Valor (%)', min_value=0.0, max_value=100.0, step=0.5)})
        if st.button('Guardar parámetros', key='prm_guardar'):
            def guardar() -> None:
                with transaccion() as cur:
                    for _, r in editado.iterrows():
                        cur.execute('UPDATE PARAMETRO_COSTO SET valor = %s WHERE clave = %s', (float(r['valor']), r['clave']))
            if ejecutar(guardar, 'Parámetros guardados.'):
                st.rerun()
    else:
        tabla(prm)
        st.caption('Solo el Gerente General puede modificar estos parámetros.')
    st.subheader('Conexiones')
    try:
        version = valor('SELECT VERSION()')
        st.success(f"Base de datos: MySQL {version} · base «{config_mysql()['database']}»")
    except Exception as e:  # noqa: BLE001
        st.error(mensaje_error(e))
    st.write('n8n (envío por Outlook):', '✅ URL configurada' if url_n8n() else '⚠️ sin configurar (n8n.webhook_url)')


# =============================================================================
# 9. Navegación
# =============================================================================
PAGINAS: dict[str, Callable[[], None]] = {
    'Inicio': pagina_inicio,
    'Nuevo presupuesto': pagina_nuevo,
    'Presupuestos': pagina_presupuestos,
    'Catálogo de partidas': pagina_catalogo,
    'Clientes': pagina_clientes,
    'Contratistas': pagina_contratistas,
    'Obras': pagina_obras,
    'Indicadores': pagina_indicadores,
    'Parámetros': pagina_parametros,
}
ICONOS = {'Inicio': '🏠', 'Nuevo presupuesto': '📝', 'Presupuestos': '📋', 'Catálogo de partidas': '📦', 'Clientes': '👥',
          'Contratistas': '🔧', 'Obras': '🏗️', 'Indicadores': '📊', 'Parámetros': '⚙️'}


def main() -> None:
    if 'usuario' not in st.session_state:
        pantalla_login()
        return
    if '_ir_a' in st.session_state:                     # navegación programática (antes de crear el menú)
        st.session_state['pagina'] = st.session_state.pop('_ir_a')
    u = st.session_state['usuario']
    with st.sidebar:
        st.title('🏗️ Constructora Altura')
        st.caption('Inversiones Rumay Ltda.')
        st.radio('Navegación', list(PAGINAS), key='pagina', format_func=lambda p: f'{ICONOS[p]} {p}')
        st.divider()
        st.caption(f"👤 {u['nombre']}  \n{u['rol']}")
        if st.button('Cerrar sesión', key='logout'):
            st.session_state.clear()
            st.rerun()
    try:
        PAGINAS[st.session_state.get('pagina', 'Inicio')]()
    except mysql.connector.Error as e:
        st.error(mensaje_error(e))


main()
