# app.py
import os
import sqlite3 
import psycopg2
import psycopg2.extras # Para DictCursor
from flask import Flask, render_template, request, redirect, url_for, flash 
import datetime 
import random 
import secrets

app = Flask(__name__)

# --- CONFIGURACIÓN DE SEGURIDAD ---
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    # Si estamos en desarrollo local, generamos una llave temporal.
    print("ADVERTENCIA: La variable de entorno SECRET_KEY no está configurada. Usando una llave temporal para desarrollo.")
    SECRET_KEY = secrets.token_hex(16)
app.secret_key = SECRET_KEY


# Configuración para fallback a SQLite local
USE_SQLITE_LOCALLY_IF_NO_DB_URL = True 
DATABASE_FOLDER_SQLITE = os.path.join(os.path.dirname(__file__), 'database_sqlite_local')
DATABASE_PATH_SQLITE = os.path.join(DATABASE_FOLDER_SQLITE, 'inventario_local.db')

if USE_SQLITE_LOCALLY_IF_NO_DB_URL and not os.path.exists(DATABASE_FOLDER_SQLITE):
    os.makedirs(DATABASE_FOLDER_SQLITE)

def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        try:
            conn = psycopg2.connect(db_url)
            return conn
        except psycopg2.OperationalError as e:
            print(f"ERROR CRÍTICO: No se pudo conectar a PostgreSQL con DATABASE_URL: {e}")
            raise
    elif USE_SQLITE_LOCALLY_IF_NO_DB_URL:
        conn_sqlite = sqlite3.connect(DATABASE_PATH_SQLITE)
        conn_sqlite.row_factory = sqlite3.Row
        conn_sqlite.execute("PRAGMA foreign_keys = ON")
        return conn_sqlite
    else:
        raise ValueError("DATABASE_URL no está configurada y el fallback a SQLite local está deshabilitado.")

# Helper para adaptar placeholders de SQL
def _adapt_query(query_str, is_postgres_conn):
    if is_postgres_conn:
        return query_str.replace("?", "%s")
    return query_str

# Helper para ejecutar consultas y manejar cursores
def _ejecutar_consulta_db(query, params=None, fetchall=False, fetchone=False, DML=False, returning_id=False):
    conn = get_db_connection()
    is_postgres = not isinstance(conn, sqlite3.Connection)
    
    if is_postgres and DML and returning_id and "RETURNING ID" not in query.upper():
        query += " RETURNING id"

    adapted_query = _adapt_query(query, is_postgres)
    resultado = None
    cur = None 

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) if is_postgres else conn.cursor()
        cur.execute(adapted_query, params if params else tuple())
        
        if DML:
            if is_postgres and returning_id:
                resultado_row = cur.fetchone()
                if resultado_row: resultado = resultado_row[0] 
            elif not is_postgres and query.strip().upper().startswith("INSERT") and returning_id:
                resultado = cur.lastrowid 
            conn.commit()
        elif fetchone:
            resultado = cur.fetchone()
        elif fetchall:
            resultado = cur.fetchall()
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error en base de datos ejecutando: {adapted_query} con params {params}. Error: {e}")
    finally:
        if cur: cur.close() 
        if conn: conn.close()
    return resultado

def init_db(add_sample_data=False):
    conn = get_db_connection()
    is_postgres = not isinstance(conn, sqlite3.Connection)
    
    print(f"DEBUG (init_db): Inicializando DB. Es PostgreSQL: {is_postgres}")
    cur = None 
    try:
        cur = conn.cursor()

        sql_create_producto = 'CREATE TABLE IF NOT EXISTS producto (id {id_pk_type} PRIMARY KEY {autoinc}, nombre TEXT NOT NULL UNIQUE, descripcion TEXT, precio_venta REAL NOT NULL, codigo_barras TEXT UNIQUE)'
        sql_create_inventario = 'CREATE TABLE IF NOT EXISTS inventario (id {id_pk_type} PRIMARY KEY {autoinc}, producto_id INTEGER NOT NULL UNIQUE, cantidad INTEGER NOT NULL DEFAULT 0, stock_minimo INTEGER NOT NULL DEFAULT 5, FOREIGN KEY (producto_id) REFERENCES producto (id) ON DELETE CASCADE)'
        sql_create_entrada = 'CREATE TABLE IF NOT EXISTS entrada (id {id_pk_type} PRIMARY KEY {autoinc}, producto_id INTEGER NOT NULL, cantidad INTEGER NOT NULL, fecha TIMESTAMP {ts_default}, precio_compra_unitario REAL, FOREIGN KEY (producto_id) REFERENCES producto (id) ON DELETE CASCADE)'
        sql_create_salida = 'CREATE TABLE IF NOT EXISTS salida (id {id_pk_type} PRIMARY KEY {autoinc}, producto_id INTEGER NOT NULL, cantidad INTEGER NOT NULL, fecha TIMESTAMP {ts_default}, precio_venta_unitario_momento REAL, FOREIGN KEY (producto_id) REFERENCES producto (id) ON DELETE CASCADE)'
        sql_create_proveedor = 'CREATE TABLE IF NOT EXISTS proveedor (id {id_pk_type} PRIMARY KEY {autoinc}, nombre TEXT NOT NULL UNIQUE, telefono TEXT NOT NULL, correo TEXT, descripcion TEXT, fecha_registro TIMESTAMP {ts_default})'

        if is_postgres:
            id_pk_type, autoinc, ts_default = "SERIAL", "", "WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
            sql_create_inventario = sql_create_inventario.replace("REFERENCES producto (id)", "REFERENCES producto (id)")
            sql_create_entrada = sql_create_entrada.replace("REFERENCES producto (id)", "REFERENCES producto (id)")
            sql_create_salida = sql_create_salida.replace("REFERENCES producto (id)", "REFERENCES producto (id)")
        else:
            id_pk_type, autoinc, ts_default = "INTEGER", "AUTOINCREMENT", "DEFAULT CURRENT_TIMESTAMP"

        cur.execute(sql_create_producto.format(id_pk_type=id_pk_type, autoinc=autoinc))
        cur.execute(sql_create_inventario.format(id_pk_type=id_pk_type, autoinc=autoinc))
        cur.execute(sql_create_entrada.format(id_pk_type=id_pk_type, autoinc=autoinc, ts_default=ts_default))
        cur.execute(sql_create_salida.format(id_pk_type=id_pk_type, autoinc=autoinc, ts_default=ts_default))
        cur.execute(sql_create_proveedor.format(id_pk_type=id_pk_type, autoinc=autoinc, ts_default=ts_default))
        print("Tablas creadas o ya existentes (en minúsculas).")

        if add_sample_data:
            # Lógica para añadir datos de ejemplo
            pass
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error inicializando base de datos o añadiendo datos de ejemplo: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if cur: cur.close() 
        if conn: conn.close()


@app.route('/')
def dashboard():
    return render_template('dashboard.html', 
                           ingresos_mensuales_valor="COP 0", 
                           valor_stock_actual="COP 0", 
                           ingresos_anuales_valor="COP 0", 
                           productos_bajo_stock_alerta=0, 
                           productos_stock_critico=[], 
                           sales_trend_data = [],
                           ultimos_movimientos=[])

@app.route('/productos')
def productos():
    search_query = request.args.get('q', '').strip()
    filtro_stock_bajo_str = request.args.get('filtro_stock_bajo', 'false') 
    filtro_stock_bajo_activo = filtro_stock_bajo_str == 'true'
    base_query_sql = ''' SELECT p.id, p.nombre, p.descripcion, p.precio_venta, p.codigo_barras, COALESCE(i.cantidad, 0) as cantidad, COALESCE(i.stock_minimo, 5) as stock_minimo FROM producto p LEFT JOIN inventario i ON p.id = i.producto_id '''
    conditions = []
    params = []
    if search_query:
        conditions.append("(p.nombre LIKE ? OR p.descripcion LIKE ? OR p.codigo_barras LIKE ?)")
        like_query = f"%{search_query}%"
        params.extend([like_query, like_query, like_query])
    if filtro_stock_bajo_activo:
        conditions.append("(COALESCE(i.cantidad, 0) <= COALESCE(i.stock_minimo, 5) AND i.producto_id IS NOT NULL)")
    if conditions: base_query_sql += " WHERE " + " AND ".join(conditions)
    base_query_sql += " ORDER BY p.nombre ASC"
    lista_productos_raw = _ejecutar_consulta_db(base_query_sql, tuple(params), fetchall=True) or []
    lista_productos_procesada = []
    for prod_row in lista_productos_raw:
        prod_dict = dict(prod_row)
        cantidad = prod_dict.get('cantidad', 0)
        stock_minimo = prod_dict.get('stock_minimo', 5)
        if cantidad == 0: prod_dict['estado_texto'] = "SOLD OUT"
        elif cantidad <= stock_minimo: prod_dict['estado_texto'] = "BAJO STOCK"
        else: prod_dict['estado_texto'] = "OK"
        lista_productos_procesada.append(prod_dict)
    return render_template('productos.html', productos=lista_productos_procesada, search_query=search_query, filtro_stock_bajo_activo=filtro_stock_bajo_activo )

@app.route('/productos/nuevo', methods=['GET', 'POST'])
def agregar_producto():
    form_data_to_render = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        nombre = form_data_to_render.get('nombre')
        descripcion = form_data_to_render.get('descripcion')
        precio_venta_str = form_data_to_render.get('precio_venta')
        codigo_barras = form_data_to_render.get('codigo_barras')
        cantidad_inicial_str = form_data_to_render.get('cantidad_inicial')
        stock_minimo_str = form_data_to_render.get('stock_minimo')
        if not nombre or not precio_venta_str or not cantidad_inicial_str or not stock_minimo_str:
            flash('Los campos Nombre, Precio, Cantidad Inicial y Stock Mínimo son obligatorios.', 'error')
            return render_template('agregar_producto.html', form_data=form_data_to_render)
        try:
            precio_venta = float(precio_venta_str)
            cantidad_inicial = int(cantidad_inicial_str)
            stock_minimo = int(stock_minimo_str)
            if precio_venta < 0 or cantidad_inicial < 0 or stock_minimo < 0: raise ValueError("Valores numéricos no negativos.")
        except ValueError as e:
            flash(f'Error en valores numéricos: {e}.', 'error')
            return render_template('agregar_producto.html', form_data=form_data_to_render)
        try:
            sql_insert_producto = "INSERT INTO producto (nombre, descripcion, precio_venta, codigo_barras) VALUES (?, ?, ?, ?)"
            producto_id = _ejecutar_consulta_db(sql_insert_producto, (nombre, descripcion, precio_venta, codigo_barras if codigo_barras else None), DML=True, returning_id=True)
            if producto_id:
                _ejecutar_consulta_db("INSERT INTO inventario (producto_id, cantidad, stock_minimo) VALUES (?, ?, ?)", (producto_id, cantidad_inicial, stock_minimo), DML=True)
                flash(f'¡Producto "{nombre}" añadido!', 'success')
                return redirect(url_for('productos'))
            else: flash('Error al crear producto.', 'error')
        except (sqlite3.IntegrityError, psycopg2.IntegrityError): flash('Error: Producto ya existe.', 'error')
        except Exception as e: flash(f'Error al guardar: {e}', 'error')
        return render_template('agregar_producto.html', form_data=form_data_to_render)
    return render_template('agregar_producto.html', form_data=form_data_to_render)

@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    producto_query = 'SELECT p.id, p.nombre, p.descripcion, p.precio_venta, p.codigo_barras, COALESCE(i.cantidad, 0) as cantidad, COALESCE(i.stock_minimo, 5) as stock_minimo FROM producto p LEFT JOIN inventario i ON p.id = i.producto_id WHERE p.id = ?'
    producto_a_editar = _ejecutar_consulta_db(producto_query, (id,), fetchone=True)
    if not producto_a_editar:
        flash('Producto no encontrado.', 'error')
        return redirect(url_for('productos'))
    form_data_to_render = dict(producto_a_editar) if request.method == 'GET' and producto_a_editar else request.form.to_dict()
    if request.method == 'POST':
        nombre = form_data_to_render.get('nombre')
        descripcion = form_data_to_render.get('descripcion')
        precio_venta_str = form_data_to_render.get('precio_venta')
        codigo_barras = form_data_to_render.get('codigo_barras')
        cantidad_str = form_data_to_render.get('cantidad')
        stock_minimo_str = form_data_to_render.get('stock_minimo')

        if not nombre or not precio_venta_str or not cantidad_str or not stock_minimo_str:
            flash('Todos los campos marcados con * son obligatorios.', 'error')
            return render_template('editar_producto.html', producto=producto_a_editar, form_data=form_data_to_render)
        try:
            precio_venta = float(precio_venta_str)
            cantidad = int(cantidad_str)
            stock_minimo = int(stock_minimo_str)
            if precio_venta < 0 or cantidad < 0 or stock_minimo < 0: raise ValueError("Valores numéricos no negativos.")
        except ValueError as e:
            flash(f'Error en valores numéricos: {e}.', 'error')
            return render_template('editar_producto.html', producto=producto_a_editar, form_data=form_data_to_render)
        try:
            _ejecutar_consulta_db("UPDATE producto SET nombre = ?, descripcion = ?, precio_venta = ?, codigo_barras = ? WHERE id = ?", 
                                (nombre, descripcion, precio_venta, codigo_barras if codigo_barras else None, id), DML=True)
            inventario_existente = _ejecutar_consulta_db("SELECT id FROM inventario WHERE producto_id = ?", (id,), fetchone=True)
            if inventario_existente:
                _ejecutar_consulta_db("UPDATE inventario SET cantidad = ?, stock_minimo = ? WHERE producto_id = ?", 
                                    (cantidad, stock_minimo, id), DML=True)
            else:
                 _ejecutar_consulta_db("INSERT INTO inventario (producto_id, cantidad, stock_minimo) VALUES (?, ?, ?)",
                                    (id, cantidad, stock_minimo), DML=True)
            flash(f'Producto "{nombre}" actualizado.', 'success')
            return redirect(url_for('productos'))
        except (sqlite3.IntegrityError, psycopg2.IntegrityError): flash('Error: Nombre o código de barras duplicado.', 'error')
        except Exception as e: flash(f'Error al actualizar: {e}', 'error')
    return render_template('editar_producto.html', producto=producto_a_editar, form_data=form_data_to_render)

@app.route('/productos/eliminar/<int:id>', methods=['POST'])
def eliminar_producto(id):
    try:
        producto_nombre_row = _ejecutar_consulta_db("SELECT nombre FROM producto WHERE id = ?", (id,), fetchone=True)
        if producto_nombre_row:
            producto_nombre = producto_nombre_row['nombre']
            _ejecutar_consulta_db("DELETE FROM producto WHERE id = ?", (id,), DML=True)
            flash(f'Producto "{producto_nombre}" eliminado.', 'success')
        else: flash('Producto no encontrado.', 'error')
    except Exception as e: flash(f'Error al eliminar: {e}', 'error')
    return redirect(url_for('productos'))

@app.route('/movimientos')
def movimientos():
    search_query_mov = request.args.get('q_mov', '').strip()
    filtro_tipo_mov_header = request.args.get('tipo_mov_header', '') 
    filtro_fecha_exacta_header = request.args.get('fecha_exacta_header', '')
    base_sql = ''' SELECT m.id as movimiento_id, p.nombre as nombre_producto, m.cantidad, m.fecha, m.tipo, m.precio_unitario, CASE WHEN m.tipo = 'Salida' THEN (SELECT e.precio_compra_unitario FROM entrada e WHERE e.producto_id = m.producto_id ORDER BY e.fecha DESC, e.id DESC LIMIT 1) ELSE NULL END as costo_unitario_estimado FROM (SELECT id, producto_id, cantidad, fecha, precio_compra_unitario as precio_unitario, 'Entrada' as tipo FROM entrada UNION ALL SELECT id, producto_id, cantidad, fecha, precio_venta_unitario_momento as precio_unitario, 'Salida' as tipo FROM salida) m JOIN producto p ON m.producto_id = p.id '''
    conditions_mov = []
    params_mov = []
    if search_query_mov:
        conditions_mov.append("(p.nombre LIKE ?)")
        params_mov.append(f"%{search_query_mov}%")
    if filtro_tipo_mov_header:
        conditions_mov.append("(m.tipo = ?)")
        params_mov.append(filtro_tipo_mov_header)
    if filtro_fecha_exacta_header: 
        conditions_mov.append("(date(m.fecha) = date(?))")
        params_mov.append(filtro_fecha_exacta_header)
    if conditions_mov: base_sql += " WHERE " + " AND ".join(conditions_mov)
    base_sql += " ORDER BY m.fecha DESC, m.id DESC" 
    movimientos_raw = _ejecutar_consulta_db(base_sql, tuple(params_mov), fetchall=True) or []
    lista_movimientos_procesada = []
    for mov_row in movimientos_raw:
        mov_dict = dict(mov_row) 
        total_movimiento = 0
        ganancia_neta = None 
        if mov_dict['tipo'] == 'Entrada' and mov_dict['precio_unitario'] is not None:
            total_movimiento = mov_dict['cantidad'] * mov_dict['precio_unitario']
            ganancia_neta = 0 
        elif mov_dict['tipo'] == 'Salida' and mov_dict['precio_unitario'] is not None:
            total_movimiento = mov_dict['cantidad'] * mov_dict['precio_unitario']
            if mov_dict['costo_unitario_estimado'] is not None:
                ganancia_neta = (mov_dict['precio_unitario'] - mov_dict['costo_unitario_estimado']) * mov_dict['cantidad']
        mov_dict['total_movimiento'] = total_movimiento
        mov_dict['ganancia_neta'] = ganancia_neta
        lista_movimientos_procesada.append(mov_dict)
    return render_template('movimientos.html', movimientos=lista_movimientos_procesada, search_query_mov=search_query_mov, filtro_tipo_mov_header=filtro_tipo_mov_header, filtro_fecha_exacta_header=filtro_fecha_exacta_header)

@app.route('/movimientos/salida', methods=['GET', 'POST'])
def registrar_salida():
    productos_disponibles = _ejecutar_consulta_db('SELECT p.id, p.nombre, i.cantidad as stock_actual FROM producto p JOIN inventario i ON p.id = i.producto_id WHERE i.cantidad > 0 ORDER BY p.nombre ASC', fetchall=True) or []
    form_data_to_render = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        try:
            producto_id_str = request.form.get('producto_id')
            cantidad_str = request.form.get('cantidad_salida')
            if not producto_id_str or not cantidad_str:
                flash('Debe seleccionar un producto y especificar la cantidad.', 'error')
                return render_template('registrar_salida.html', productos=productos_disponibles, form_data=form_data_to_render)
            producto_id = int(producto_id_str)
            cantidad_salida = int(cantidad_str)
            if cantidad_salida <= 0: raise ValueError("La cantidad debe ser un número positivo.")
            producto_info = _ejecutar_consulta_db('SELECT p.nombre, p.precio_venta, i.cantidad as stock_actual FROM producto p JOIN inventario i ON p.id = i.producto_id WHERE p.id = ?', (producto_id,), fetchone=True)
            if not producto_info:
                flash('Producto no encontrado o sin inventario registrado.', 'error')
                return render_template('registrar_salida.html', productos=productos_disponibles, form_data=form_data_to_render)
            if producto_info['stock_actual'] < cantidad_salida:
                flash(f"No hay suficiente stock para '{producto_info['nombre']}'. Stock actual: {producto_info['stock_actual']}.", 'error')
                return render_template('registrar_salida.html', productos=productos_disponibles, form_data=form_data_to_render)
            nuevo_stock = producto_info['stock_actual'] - cantidad_salida
            _ejecutar_consulta_db('UPDATE inventario SET cantidad = ? WHERE producto_id = ?', (nuevo_stock, producto_id), DML=True)
            _ejecutar_consulta_db('INSERT INTO salida (producto_id, cantidad, precio_venta_unitario_momento) VALUES (?, ?, ?)', (producto_id, cantidad_salida, producto_info['precio_venta']), DML=True)
            flash(f'Salida de {cantidad_salida} unidad(es) de "{producto_info["nombre"]}" registrada.', 'success')
            return redirect(url_for('movimientos'))
        except ValueError as e: flash(f'Error en los valores ingresados: {e}.', 'error')
        except Exception as e: flash(f'Un error inesperado ocurrió: {e}', 'error')
        return render_template('registrar_salida.html', productos=productos_disponibles, form_data=form_data_to_render)
    return render_template('registrar_salida.html', productos=productos_disponibles, form_data=form_data_to_render)

@app.route('/movimientos/entrada', methods=['GET', 'POST'])
def registrar_entrada():
    lista_todos_productos = _ejecutar_consulta_db('SELECT id, nombre FROM producto ORDER BY nombre ASC', fetchall=True) or []
    form_data_to_render = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        try:
            producto_id_str = request.form.get('producto_id')
            cantidad_comprada_str = request.form.get('cantidad_comprada')
            costo_total_lote_str = request.form.get('costo_total_lote')
            if not producto_id_str or not cantidad_comprada_str or not costo_total_lote_str:
                flash('Debe seleccionar un producto, cantidad y costo total.', 'error')
                return render_template('registrar_entrada.html', productos=lista_todos_productos, form_data=form_data_to_render)
            producto_id = int(producto_id_str)
            cantidad_comprada = int(cantidad_comprada_str)
            costo_total_lote = float(costo_total_lote_str)
            if cantidad_comprada <= 0 or costo_total_lote < 0: raise ValueError("Cantidad debe ser positiva y costo no negativo.")
            costo_unitario = costo_total_lote / cantidad_comprada if cantidad_comprada > 0 else 0
            producto_nombre_row = _ejecutar_consulta_db('SELECT nombre FROM producto WHERE id = ?', (producto_id,), fetchone=True)
            if not producto_nombre_row:
                flash('Producto no válido.', 'error')
                return render_template('registrar_entrada.html', productos=lista_todos_productos, form_data=form_data_to_render)
            producto_nombre = producto_nombre_row['nombre']
            inventario_actual = _ejecutar_consulta_db('SELECT cantidad FROM inventario WHERE producto_id = ?', (producto_id,), fetchone=True)
            if inventario_actual:
                nuevo_stock = inventario_actual['cantidad'] + cantidad_comprada
                _ejecutar_consulta_db('UPDATE inventario SET cantidad = ? WHERE producto_id = ?', (nuevo_stock, producto_id), DML=True)
            else:
                _ejecutar_consulta_db('INSERT INTO inventario (producto_id, cantidad, stock_minimo) VALUES (?, ?, ?)', (producto_id, cantidad_comprada, 5), DML=True)
            _ejecutar_consulta_db('INSERT INTO entrada (producto_id, cantidad, precio_compra_unitario) VALUES (?, ?, ?)', (producto_id, cantidad_comprada, costo_unitario), DML=True)
            flash(f'Entrada de "{producto_nombre}" registrada (Costo Unit: {costo_unitario:,.0f} COP).', 'success')
            return redirect(url_for('movimientos'))
        except ValueError as e: flash(f'Error en valores: {e}.', 'error')
        except Exception as e: flash(f'Error al registrar entrada: {e}', 'error')
        return render_template('registrar_entrada.html', productos=lista_todos_productos, form_data=form_data_to_render)
    return render_template('registrar_entrada.html', productos=lista_todos_productos, form_data=form_data_to_render)

@app.route('/proveedores', endpoint='proveedores_lista') 
def proveedores_lista():
    search_query_proveedor = request.args.get('q_proveedor', '').strip()
    query_sql = 'SELECT id, nombre, telefono, correo, descripcion, fecha_registro FROM proveedor'
    conditions = []
    params = []
    if search_query_proveedor:
        conditions.append("(nombre LIKE ? OR telefono LIKE ? OR correo LIKE ?)")
        like_query = f"%{search_query_proveedor}%"
        params.extend([like_query, like_query, like_query])
    if conditions: query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY nombre ASC"
    lista_proveedores = _ejecutar_consulta_db(query_sql, tuple(params), fetchall=True) or []
    return render_template('proveedores.html', proveedores=lista_proveedores, search_query=search_query_proveedor)

@app.route('/proveedores/nuevo', methods=['GET', 'POST'])
def agregar_proveedor():
    form_data_to_render = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        nombre = form_data_to_render.get('nombre_proveedor')
        telefono = form_data_to_render.get('telefono_proveedor')
        if not nombre or not telefono:
            flash('Nombre y teléfono son obligatorios.', 'error')
            return render_template('agregar_proveedor.html', form_data=form_data_to_render)
        try:
            _ejecutar_consulta_db("INSERT INTO proveedor (nombre, telefono, correo, descripcion) VALUES (?, ?, ?, ?)",
                                (nombre, telefono, form_data_to_render.get('correo_proveedor'), form_data_to_render.get('descripcion_proveedor')), DML=True)
            flash(f'Proveedor "{nombre}" añadido.', 'success')
            return redirect(url_for('proveedores_lista'))
        except (sqlite3.IntegrityError, psycopg2.IntegrityError): flash('Error: Proveedor ya existe.', 'error')
        except Exception as e: flash(f'Error al guardar: {e}', 'error')
    return render_template('agregar_proveedor.html', form_data=form_data_to_render)

@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
def editar_proveedor(id):
    proveedor_a_editar = _ejecutar_consulta_db("SELECT * FROM proveedor WHERE id = ?", (id,), fetchone=True)
    if not proveedor_a_editar:
        flash('Proveedor no encontrado.', 'error')
        return redirect(url_for('proveedores_lista'))
    
    form_data_to_render = dict(proveedor_a_editar) if request.method == 'GET' and proveedor_a_editar else request.form.to_dict()
    if request.method == 'GET' and proveedor_a_editar: 
        form_data_to_render['nombre_proveedor'] = proveedor_a_editar['nombre']
        form_data_to_render['telefono_proveedor'] = proveedor_a_editar['telefono']
        form_data_to_render['correo_proveedor'] = proveedor_a_editar['correo']
        form_data_to_render['descripcion_proveedor'] = proveedor_a_editar['descripcion']

    if request.method == 'POST':
        nombre = form_data_to_render.get('nombre_proveedor')
        telefono = form_data_to_render.get('telefono_proveedor')
        if not nombre or not telefono:
            flash('Nombre y teléfono son obligatorios.', 'error')
            return render_template('editar_proveedor.html', proveedor=proveedor_a_editar, form_data=form_data_to_render)
        try:
            _ejecutar_consulta_db("UPDATE proveedor SET nombre = ?, telefono = ?, correo = ?, descripcion = ? WHERE id = ?",
                                (nombre, telefono, form_data_to_render.get('correo_proveedor'), form_data_to_render.get('descripcion_proveedor'), id), DML=True)
            flash(f'Proveedor "{nombre}" actualizado.', 'success')
            return redirect(url_for('proveedores_lista'))
        except (sqlite3.IntegrityError, psycopg2.IntegrityError): flash('Error: Nombre de proveedor duplicado.', 'error')
        except Exception as e: flash(f'Error al actualizar: {e}', 'error')
    return render_template('editar_proveedor.html', proveedor=proveedor_a_editar, form_data=form_data_to_render)

@app.route('/proveedores/eliminar/<int:id>', methods=['POST'])
def eliminar_proveedor(id):
    try:
        proveedor_nombre_row = _ejecutar_consulta_db("SELECT nombre FROM proveedor WHERE id = ?", (id,), fetchone=True)
        if proveedor_nombre_row:
            proveedor_nombre = proveedor_nombre_row['nombre']
            _ejecutar_consulta_db("DELETE FROM proveedor WHERE id = ?", (id,), DML=True)
            flash(f'Proveedor "{proveedor_nombre}" eliminado.', 'success')
        else: flash('Proveedor no encontrado.', 'error')
    except Exception as e: flash(f'Error al eliminar: {e}', 'error')
    return redirect(url_for('proveedores_lista'))

@app.route('/settings')
def settings():
    current_year = datetime.datetime.now().year
    return render_template('settings.html', current_year=current_year)

if __name__ == '__main__':
    db_type = "PostgreSQL Remota" if os.environ.get('DATABASE_URL') else "SQLite local"
    print(f"La base de datos se creará/estará en: {db_type}")
    init_db(add_sample_data= not bool(os.environ.get('DATABASE_URL'))) 
    is_production = bool(os.environ.get('DATABASE_URL'))
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=not is_production)

