"""
Prueba las reglas de negocio que no caben en un CHECK y que hace
cumplir app.py (flujo de estados, quién aprueba, cotizaciones pendientes, presupuestos
cerrados, obra y envío solo de emitidos, historial de precios).

Uso (con la base recién cargada con schema.sql + seed.sql, desde la carpeta de la app):
    python pruebas_reglas_app.py
"""
import types, sys
import pathlib
APP = pathlib.Path(__file__).with_name('app.py')
src = APP.read_text(encoding='utf-8').rsplit('\nmain()', 1)[0]
src = src.replace("if __name__ == '__main__':", "if False:")
ns = {'__name__': 'reglas', '__file__': str(APP)}
exec(compile(src, str(APP), 'exec'), ns)
import mysql.connector
con = mysql.connector.connect(**ns['config_mysql']())
R = ns['ReglaNegocio']
def prueba(nombre, f, debe_fallar=True):
    cur = con.cursor()
    try:
        f(cur)
        res = 'OK' if not debe_fallar else 'NO FALLÓ (mal)'
    except R as e:
        res = f'falla como debe: {e}' if debe_fallar else f'FALLÓ (mal): {e}'
    con.rollback()
    print(f'{nombre:62s} {res}')
c = ns
prueba('R1 asistente aprueba el 6 (En revisión)', lambda cur: c['cambiar_estado'](cur, 6, 'Aprobado', 2))
prueba('R2 gerente aprueba el 6 con cotización pendiente', lambda cur: c['cambiar_estado'](cur, 6, 'Aprobado', 1))
prueba('R3 saltar de Borrador a Emitido (7)', lambda cur: c['cambiar_estado'](cur, 7, 'Emitido', 1))
prueba('R4 pasar a revisión un borrador sin partidas', lambda cur: (cur.execute("INSERT INTO PRESUPUESTO (id_presupuesto,id_cliente,id_usuario,nombre_proyecto,fecha_inicio,valor_uf_dia,ubicacion,tipo_jornada,pct_gastos_generales,pct_utilidad) VALUES (99,1,2,'vacío',NOW(),41000,'Santiago','Diurna',5,15)"), c['cambiar_estado'](cur, 99, 'En revision', 2)))
prueba('R5 modificar el detalle de un emitido (1)', lambda cur: c['exigir_abierto'](cur, 1))
prueba('R6 registrar obra de un aprobado (5)', lambda cur: c['exigir_emitido'](cur, 5, 'registrarse como obra'))
prueba('R7 enviar al cliente un aprobado (5)', lambda cur: c['exigir_emitido'](cur, 5, 'enviarse al cliente'))
prueba('R8 OK: gerente emite el 5 (Aprobado)', lambda cur: c['cambiar_estado'](cur, 5, 'Emitido', 1), debe_fallar=False)
def r9(cur):
    c['actualizar_precio_partida'](cur, 3, 99999)
    cur.execute('SELECT COUNT(*) FROM HISTORIAL_PRECIO WHERE id_partida = 3'); n = cur.fetchone()[0]
    assert n == 3, n
prueba('R9 OK: cambiar precio deja el anterior en el historial', r9, debe_fallar=False)
