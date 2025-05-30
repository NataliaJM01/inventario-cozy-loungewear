# app.py
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash 
import datetime 

app = Flask(__name__)
app.secret_key = "mi_llave_super_secreta_y_femenina_loungewear_v8_settings" 

DATABASE_FOLDER = os.path.join(os.path.dirname(__file__), 'database')
DATABASE_PATH = os.path.join(DATABASE_FOLDER, 'inventario.db')

if not os.path.exists(DATABASE_FOLDER):
    os.makedirs(DATABASE_FOLDER)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(add_sample_data=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla Producto
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Producto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            descripcion TEXT,
            precio_venta REAL NOT NULL,
            codigo_barras TEXT UNIQUE
        )
    ''')
    print("Tabla Producto creada o ya existente.")
    
    # Tabla Inventario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL UNIQUE,
            cantidad INTEGER NOT NULL DEFAULT 0,
            stock_minimo INTEGER NOT NULL DEFAULT 5,
            FOREIGN KEY (producto_id) REFERENCES Producto (id) ON DELETE CASCADE 
        )
    ''')
    print("Tabla Inventario creada o ya existente.")
    
    # Tabla Entrada
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Entrada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            precio_compra_unitario REAL,
            FOREIGN KEY (producto_id) REFERENCES Producto (id) ON DELETE CASCADE
        )
    ''')
    print("Tabla Entrada creada o ya existente.")
    
    # Tabla Salida
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Salida (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            precio_venta_unitario_momento REAL,
            FOREIGN KEY (producto_id) REFERENCES Producto (id) ON DELETE CASCADE
        )
    ''')
    print("Tabla Salida creada o ya existente.")

    # Tabla Proveedor
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Proveedor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            telefono TEXT NOT NULL,
            correo TEXT,
            descripcion TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("Tabla Proveedor creada o ya existente.")

    if add_sample_data:
        try:
            cursor.execute("SELECT COUNT(id) FROM Producto")
            productos_existentes = cursor.fetchone()[0]
            
            if productos_existentes == 0:
                print("Añadiendo datos de ejemplo para Productos, Inventario, Entradas y Salidas...")
                productos_ejemplo = [
                    ('Pijama "Sueño de Algodón"', 'Pijama de dos piezas, 100% algodón orgánico.', 150000, 'PIJ001'),
                    ('Bata "Abrazo de Seda"', 'Bata larga de seda sintética, color perla.', 220000, 'BAT001'),
                    ('Conjunto "Relax Total"', 'Conjunto de pantalón y sudadera de felpa.', 180000, 'CON001'),
                    ('Pantuflas "Nube Rosa"', 'Pantuflas extra suaves.', 75000, 'PAN001'),
                    ('Vela Aromática "Lavanda"', 'Vela de soja con aceite esencial.', 55000, 'VEL001')
                ]
                cursor.executemany('INSERT INTO Producto (nombre, descripcion, precio_venta, codigo_barras) VALUES (?, ?, ?, ?)', productos_ejemplo)
                
                inventario_ejemplo = [ (1, 15, 5), (2, 8, 3), (3, 2, 5), (4, 20, 8), (5, 3, 6) ]
                cursor.executemany('INSERT INTO Inventario (producto_id, cantidad, stock_minimo) VALUES (?, ?, ?)', inventario_ejemplo)
                
                today = datetime.date.today()
                entradas_ejemplo = [
                    (1, 10, (today - datetime.timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S'), 90000), 
                    (2, 5,  (today - datetime.timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S'), 150000),
                    (3, 5, today.strftime('%Y-%m-%d %H:%M:%S'), 120000)
                ]
                cursor.executemany('INSERT INTO Entrada (producto_id, cantidad, fecha, precio_compra_unitario) VALUES (?, ?, ?, ?)', entradas_ejemplo)

                salidas_ejemplo = [
                    (1, 2, (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S'), 150000), 
                    (2, 1, today.strftime('%Y-%m-%d %H:%M:%S'), 220000), 
                ]
                cursor.executemany('INSERT INTO Salida (producto_id, cantidad, fecha, precio_venta_unitario_momento) VALUES (?, ?, ?, ?)', salidas_ejemplo)
                print("Datos de ejemplo para productos, inventario, entradas y salidas añadidos.")

            cursor.execute("SELECT COUNT(id) FROM Proveedor")
            proveedores_existentes = cursor.fetchone()[0]
            if proveedores_existentes == 0:
                print("Añadiendo datos de ejemplo para Proveedores...")
                proveedores_ejemplo = [
                    ('Telas El Encanto', '3001234567', 'ventas@telasencanto.com', 'Proveedor principal de algodones y sedas.'),
                    ('Insumos Creativos SAS', '3109876543', 'contacto@insumoscreativos.co', 'Botones, cierres, y adornos especiales.'),
                ]
                cursor.executemany('INSERT INTO Proveedor (nombre, telefono, correo, descripcion) VALUES (?, ?, ?, ?)', proveedores_ejemplo)
                print("Datos de ejemplo para Proveedores añadidos.")

        except sqlite3.IntegrityError as e:
            print(f"Error de integridad al añadir datos de ejemplo: {e}")
        except Exception as e:
            print(f"Otro error al añadir datos de ejemplo: {e}")
    conn.commit()
    conn.close()

@app.route('/')
def dashboard():
    conn = get_db_connection()
    
    productos_bajo_stock_alerta_row = conn.execute('SELECT COUNT(*) FROM Inventario WHERE cantidad <= stock_minimo AND cantidad > 0').fetchone()
    productos_bajo_stock_alerta = productos_bajo_stock_alerta_row[0] if productos_bajo_stock_alerta_row else 0
    
    productos_stock_critico = conn.execute("SELECT p.nombre, i.cantidad, i.stock_minimo FROM Producto p JOIN Inventario i ON p.id = i.producto_id WHERE i.cantidad > 0 ORDER BY (i.cantidad <= i.stock_minimo) DESC, i.cantidad ASC LIMIT 10").fetchall()
    
    current_month_str = datetime.datetime.now().strftime("%Y-%m")
    salidas_del_mes_con_costo_for_cards = conn.execute("SELECT s.cantidad, s.precio_venta_unitario_momento, (SELECT e.precio_compra_unitario FROM Entrada e WHERE e.producto_id = s.producto_id ORDER BY e.fecha DESC, e.id DESC LIMIT 1) as costo_unitario_estimado FROM Salida s WHERE strftime('%Y-%m', s.fecha) = ?", (current_month_str,)).fetchall()
    ingresos_mensuales_valor = 0.0
    for salida_card in salidas_del_mes_con_costo_for_cards:
        if salida_card['precio_venta_unitario_momento'] is not None and salida_card['costo_unitario_estimado'] is not None:
            ingresos_mensuales_valor += (salida_card['precio_venta_unitario_momento'] - salida_card['costo_unitario_estimado']) * salida_card['cantidad']

    valor_stock_actual_row = conn.execute(
        "SELECT SUM(p.precio_venta * i.cantidad) FROM Producto p JOIN Inventario i ON p.id = i.producto_id WHERE i.cantidad > 0"
    ).fetchone()
    valor_stock_actual = valor_stock_actual_row[0] if valor_stock_actual_row and valor_stock_actual_row[0] is not None else 0.0

    current_year_str = datetime.datetime.now().strftime("%Y")
    salidas_del_ano_con_costo = conn.execute("SELECT s.cantidad, s.precio_venta_unitario_momento, (SELECT e.precio_compra_unitario FROM Entrada e WHERE e.producto_id = s.producto_id ORDER BY e.fecha DESC, e.id DESC LIMIT 1) as costo_unitario_estimado FROM Salida s WHERE strftime('%Y', s.fecha) = ?", (current_year_str,)).fetchall()
    ingresos_anuales_valor = 0.0
    for salida_anual in salidas_del_ano_con_costo:
        if salida_anual['precio_venta_unitario_momento'] is not None and salida_anual['costo_unitario_estimado'] is not None:
            ingresos_anuales_valor += (salida_anual['precio_venta_unitario_momento'] - salida_anual['costo_unitario_estimado']) * salida_anual['cantidad']
    
    ultimos_movimientos = conn.execute('''
        SELECT 
            p.nombre as nombre_producto, 
            m.cantidad, 
            m.fecha, 
            m.tipo,
            m.id as movimiento_id 
        FROM (
            SELECT id, producto_id, cantidad, fecha, 'Entrada' as tipo FROM Entrada
            UNION ALL
            SELECT id, producto_id, cantidad, fecha, 'Salida' as tipo FROM Salida
        ) m 
        JOIN Producto p ON m.producto_id = p.id
        ORDER BY m.fecha DESC, m.id DESC 
        LIMIT 5 
    ''').fetchall()
    
    conn.close()    
    return render_template(
        'dashboard.html',
        mensaje_flask="Dashboard cargado.",
        ingresos_mensuales_valor = "COP {:,.0f}".format(ingresos_mensuales_valor).replace(",", "."), 
        valor_stock_actual = "COP {:,.0f}".format(valor_stock_actual).replace(",", "."),
        ingresos_anuales_valor = "COP {:,.0f}".format(ingresos_anuales_valor).replace(",", "."),
        productos_bajo_stock_alerta = productos_bajo_stock_alerta,
        productos_stock_critico = productos_stock_critico,
        sales_trend_data = [], 
        ultimos_movimientos = ultimos_movimientos
    )

@app.route('/productos')
def productos():
    conn = get_db_connection()
    search_query = request.args.get('q', '').strip()
    filtro_stock_bajo_str = request.args.get('filtro_stock_bajo', 'false') 
    filtro_stock_bajo_activo = filtro_stock_bajo_str == 'true'

    base_query = '''
        SELECT 
            p.id, p.nombre, p.descripcion, p.precio_venta, p.codigo_barras,
            COALESCE(i.cantidad, 0) as cantidad,
            COALESCE(i.stock_minimo, 5) as stock_minimo 
        FROM Producto p
        LEFT JOIN Inventario i ON p.id = i.producto_id
    '''
    conditions = []
    params = []

    if search_query:
        conditions.append("(p.nombre LIKE ? OR p.descripcion LIKE ? OR p.codigo_barras LIKE ?)")
        like_query = f"%{search_query}%"
        params.extend([like_query, like_query, like_query])
    
    if filtro_stock_bajo_activo:
        conditions.append("(COALESCE(i.cantidad, 0) <= COALESCE(i.stock_minimo, 5) AND i.producto_id IS NOT NULL)")

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)
    
    base_query += " ORDER BY p.nombre ASC"
    
    lista_productos = conn.execute(base_query, params).fetchall()
    conn.close()
    
    return render_template(
        'productos.html', 
        productos=lista_productos, 
        search_query=search_query,
        filtro_stock_bajo_activo=filtro_stock_bajo_activo 
    )

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
            if precio_venta < 0 or cantidad_inicial < 0 or stock_minimo < 0:
                raise ValueError("Los valores numéricos no pueden ser negativos.")
        except ValueError as e:
            flash(f'Error en los valores numéricos: {e}. Por favor, ingrésalos correctamente.', 'error')
            return render_template('agregar_producto.html', form_data=form_data_to_render)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO Producto (nombre, descripcion, precio_venta, codigo_barras) VALUES (?, ?, ?, ?)',
                (nombre, descripcion, precio_venta, codigo_barras if codigo_barras else None)
            )
            producto_id = cursor.lastrowid 
            cursor.execute(
                'INSERT INTO Inventario (producto_id, cantidad, stock_minimo) VALUES (?, ?, ?)',
                (producto_id, cantidad_inicial, stock_minimo)
            )
            conn.commit()
            flash(f'¡Producto "{nombre}" añadido exitosamente!', 'success')
            return redirect(url_for('productos')) 
        except sqlite3.IntegrityError:
            conn.rollback() 
            flash('Error: Ya existe un producto con ese nombre o código de barras.', 'error')
        except Exception as e:
            conn.rollback()
            flash(f'Ocurrió un error al guardar el producto: {e}', 'error')
        finally:
            conn.close()
        return render_template('agregar_producto.html', form_data=form_data_to_render)
    return render_template('agregar_producto.html', form_data=form_data_to_render)

@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    conn = get_db_connection() 
    producto_a_editar_query = '''
        SELECT p.id, p.nombre, p.descripcion, p.precio_venta, p.codigo_barras, 
               COALESCE(i.cantidad, 0) as cantidad, 
               COALESCE(i.stock_minimo, 5) as stock_minimo 
        FROM Producto p 
        LEFT JOIN Inventario i ON p.id = i.producto_id 
        WHERE p.id = ?
    '''
    producto_a_editar = conn.execute(producto_a_editar_query, (id,)).fetchone()

    if not producto_a_editar:
        flash('Producto no encontrado.', 'error')
        conn.close() 
        return redirect(url_for('productos'))

    form_data_to_render = {}
    if request.method == 'POST':
        form_data_to_render = request.form.to_dict()
    elif producto_a_editar: 
        form_data_to_render = dict(producto_a_editar)

    if request.method == 'POST':
        nombre = form_data_to_render.get('nombre')
        descripcion = form_data_to_render.get('descripcion')
        precio_venta_str = form_data_to_render.get('precio_venta')
        codigo_barras = form_data_to_render.get('codigo_barras')
        cantidad_str = form_data_to_render.get('cantidad')
        stock_minimo_str = form_data_to_render.get('stock_minimo')

        if not nombre or not precio_venta_str or not cantidad_str or not stock_minimo_str:
            flash('Todos los campos marcados con * son obligatorios.', 'error')
            conn.close()
            return render_template('editar_producto.html', producto=producto_a_editar, form_data=form_data_to_render)
        try:
            precio_venta = float(precio_venta_str)
            cantidad = int(cantidad_str)
            stock_minimo = int(stock_minimo_str)
            if precio_venta < 0 or cantidad < 0 or stock_minimo < 0:
                raise ValueError("Los valores numéricos no pueden ser negativos.")
        except ValueError as e:
            flash(f'Error en los valores numéricos: {e}.', 'error')
            conn.close()
            return render_template('editar_producto.html', producto=producto_a_editar, form_data=form_data_to_render)

        db_success = False
        try:
            conn.execute(
                'UPDATE Producto SET nombre = ?, descripcion = ?, precio_venta = ?, codigo_barras = ? WHERE id = ?',
                (nombre, descripcion, precio_venta, codigo_barras if codigo_barras else None, id)
            )
            inventario_existente = conn.execute('SELECT id FROM Inventario WHERE producto_id = ?', (id,)).fetchone()
            if inventario_existente:
                conn.execute(
                    'UPDATE Inventario SET cantidad = ?, stock_minimo = ? WHERE producto_id = ?',
                    (cantidad, stock_minimo, id)
                )
            else:
                conn.execute(
                    'INSERT INTO Inventario (producto_id, cantidad, stock_minimo) VALUES (?, ?, ?)',
                    (id, cantidad, stock_minimo)
                )
            conn.commit()
            flash(f'Producto "{nombre}" actualizado exitosamente.', 'success')
            db_success = True 
        except sqlite3.IntegrityError:
            conn.rollback()
            flash('Error: Ya existe otro producto con ese nombre o código de barras.', 'error')
        except Exception as e:
            conn.rollback()
            flash(f'Ocurrió un error al actualizar el producto: {e}', 'error')
        finally:
            if conn: conn.close()
        
        if db_success:
             return redirect(url_for('productos'))
        else: 
             return render_template('editar_producto.html', producto=producto_a_editar, form_data=form_data_to_render)

    conn.close() 
    return render_template('editar_producto.html', producto=producto_a_editar, form_data=form_data_to_render)

@app.route('/productos/eliminar/<int:id>', methods=['POST'])
def eliminar_producto(id):
    conn = get_db_connection()
    try:
        producto_nombre_row = conn.execute('SELECT nombre FROM Producto WHERE id = ?', (id,)).fetchone()
        if producto_nombre_row:
            producto_nombre = producto_nombre_row['nombre']
            conn.execute('DELETE FROM Producto WHERE id = ?', (id,))
            conn.commit()
            flash(f'Producto "{producto_nombre}" eliminado exitosamente.', 'success')
        else:
            flash('Error: Producto no encontrado.', 'error')
    except sqlite3.Error as e:
        conn.rollback()
        flash(f'Error al eliminar el producto: {e}', 'error')
    finally:
        conn.close()
    return redirect(url_for('productos'))

@app.route('/movimientos')
def movimientos():
    conn = get_db_connection()
    search_query_mov = request.args.get('q_mov', '').strip()
    filtro_tipo_mov_header = request.args.get('tipo_mov_header', '') 
    filtro_fecha_exacta_header = request.args.get('fecha_exacta_header', '')

    base_sql = '''
        SELECT 
            m.id as movimiento_id, 
            p.nombre as nombre_producto, 
            m.cantidad, 
            m.fecha, 
            m.tipo,
            m.precio_unitario,
            CASE 
                WHEN m.tipo = 'Salida' THEN (
                    SELECT e.precio_compra_unitario FROM Entrada e 
                    WHERE e.producto_id = m.producto_id ORDER BY e.fecha DESC, e.id DESC LIMIT 1
                ) ELSE NULL 
            END as costo_unitario_estimado
        FROM (
            SELECT id, producto_id, cantidad, fecha, precio_compra_unitario as precio_unitario, 'Entrada' as tipo FROM Entrada
            UNION ALL
            SELECT id, producto_id, cantidad, fecha, precio_venta_unitario_momento as precio_unitario, 'Salida' as tipo FROM Salida
        ) m
        JOIN Producto p ON m.producto_id = p.id
    '''
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

    if conditions_mov:
        base_sql += " WHERE " + " AND ".join(conditions_mov)
    base_sql += " ORDER BY m.fecha DESC, m.id DESC" 
    
    movimientos_raw = conn.execute(base_sql, params_mov).fetchall()
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
    conn.close()
    return render_template(
        'movimientos.html', 
        movimientos=lista_movimientos_procesada,
        search_query_mov=search_query_mov,
        filtro_tipo_mov_header=filtro_tipo_mov_header,
        filtro_fecha_exacta_header=filtro_fecha_exacta_header
    )

@app.route('/movimientos/salida', methods=['GET', 'POST'])
def registrar_salida():
    conn_get = get_db_connection() 
    productos_disponibles = conn_get.execute(
        'SELECT p.id, p.nombre, i.cantidad as stock_actual FROM Producto p JOIN Inventario i ON p.id = i.producto_id WHERE i.cantidad > 0 ORDER BY p.nombre ASC'
    ).fetchall()
    form_data_to_render = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        conn_post = get_db_connection() 
        try:
            producto_id_str = request.form.get('producto_id')
            cantidad_str = request.form.get('cantidad_salida')

            if not producto_id_str or not cantidad_str:
                flash('Debe seleccionar un producto y especificar la cantidad.', 'error')
                return render_template('registrar_salida.html', productos=productos_disponibles, form_data=form_data_to_render)
            
            producto_id = int(producto_id_str)
            cantidad_salida = int(cantidad_str)
            if cantidad_salida <= 0:
                raise ValueError("La cantidad debe ser un número positivo.")

            producto_info = conn_post.execute( 
                'SELECT p.nombre, p.precio_venta, i.cantidad as stock_actual FROM Producto p JOIN Inventario i ON p.id = i.producto_id WHERE p.id = ?',
                (producto_id,)
            ).fetchone()

            if not producto_info:
                flash('Producto no encontrado o sin inventario registrado.', 'error')
                return render_template('registrar_salida.html', productos=productos_disponibles, form_data=form_data_to_render)

            if producto_info['stock_actual'] < cantidad_salida:
                flash(f"No hay suficiente stock para '{producto_info['nombre']}'. Stock actual: {producto_info['stock_actual']}.", 'error')
                return render_template('registrar_salida.html', productos=productos_disponibles, form_data=form_data_to_render)

            nuevo_stock = producto_info['stock_actual'] - cantidad_salida
            conn_post.execute('UPDATE Inventario SET cantidad = ? WHERE producto_id = ?', (nuevo_stock, producto_id))
            conn_post.execute(
                'INSERT INTO Salida (producto_id, cantidad, precio_venta_unitario_momento) VALUES (?, ?, ?)',
                (producto_id, cantidad_salida, producto_info['precio_venta'])
            )
            conn_post.commit()
            flash(f'Salida de {cantidad_salida} unidad(es) de "{producto_info["nombre"]}" registrada exitosamente.', 'success')
            return redirect(url_for('movimientos'))
        except ValueError as e: 
            flash(f'Error en los valores ingresados: {e}.', 'error')
        except sqlite3.Error as e:
            if conn_post: conn_post.rollback()
            flash(f'Error al registrar la salida: {e}', 'error')
        except Exception as e: 
             if conn_post: conn_post.rollback()
             flash(f'Un error inesperado ocurrió: {e}', 'error')
        finally:
            if conn_post: conn_post.close()
        
        conn_get_error = get_db_connection() 
        productos_disponibles_error = conn_get_error.execute(
             'SELECT p.id, p.nombre, i.cantidad as stock_actual FROM Producto p JOIN Inventario i ON p.id = i.producto_id WHERE i.cantidad > 0 ORDER BY p.nombre ASC'
        ).fetchall()
        conn_get_error.close()
        return render_template('registrar_salida.html', productos=productos_disponibles_error, form_data=form_data_to_render)
    
    conn_get.close() 
    return render_template('registrar_salida.html', productos=productos_disponibles, form_data=form_data_to_render)

@app.route('/movimientos/entrada', methods=['GET', 'POST'])
def registrar_entrada():
    conn_get = get_db_connection()
    lista_todos_productos = conn_get.execute('SELECT id, nombre FROM Producto ORDER BY nombre ASC').fetchall()
    form_data_to_render = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        conn_post = get_db_connection()
        try:
            producto_id_str = request.form.get('producto_id')
            cantidad_comprada_str = request.form.get('cantidad_comprada')
            costo_total_lote_str = request.form.get('costo_total_lote')

            if not producto_id_str or not cantidad_comprada_str or not costo_total_lote_str:
                flash('Debe seleccionar un producto y especificar la cantidad y el costo total del lote.', 'error')
                return render_template('registrar_entrada.html', productos=lista_todos_productos, form_data=form_data_to_render)
            
            producto_id = int(producto_id_str)
            cantidad_comprada = int(cantidad_comprada_str)
            costo_total_lote = float(costo_total_lote_str)
            if cantidad_comprada <= 0 or costo_total_lote < 0:
                raise ValueError("La cantidad comprada debe ser positiva y el costo total no puede ser negativo.")
            costo_unitario = costo_total_lote / cantidad_comprada if cantidad_comprada > 0 else 0
            
            producto_nombre_row = conn_post.execute('SELECT nombre FROM Producto WHERE id = ?', (producto_id,)).fetchone()
            if not producto_nombre_row:
                flash('Producto seleccionado no válido.', 'error')
                return render_template('registrar_entrada.html', productos=lista_todos_productos, form_data=form_data_to_render)
            producto_nombre = producto_nombre_row['nombre']

            inventario_actual = conn_post.execute('SELECT cantidad FROM Inventario WHERE producto_id = ?', (producto_id,)).fetchone()
            if inventario_actual:
                nuevo_stock = inventario_actual['cantidad'] + cantidad_comprada
                conn_post.execute('UPDATE Inventario SET cantidad = ? WHERE producto_id = ?', (nuevo_stock, producto_id))
            else:
                stock_minimo_default = 5 
                conn_post.execute('INSERT INTO Inventario (producto_id, cantidad, stock_minimo) VALUES (?, ?, ?)', 
                             (producto_id, cantidad_comprada, stock_minimo_default))
            conn_post.execute(
                'INSERT INTO Entrada (producto_id, cantidad, precio_compra_unitario) VALUES (?, ?, ?)',
                (producto_id, cantidad_comprada, costo_unitario)
            )
            conn_post.commit()
            flash(f'Entrada de {cantidad_comprada} unidad(es) de "{producto_nombre}" registrada exitosamente (Costo Unit: {costo_unitario:,.0f} COP).', 'success')
            return redirect(url_for('movimientos'))
        except ValueError as e:
             flash(f'Error en los valores ingresados: {e}.', 'error')
        except sqlite3.Error as e:
            if conn_post: conn_post.rollback()
            flash(f'Error al registrar la entrada: {e}', 'error')
        except Exception as e:
            if conn_post: conn_post.rollback()
            flash(f'Un error inesperado ocurrió: {e}', 'error')
        finally:
            if conn_post: conn_post.close()
        
        conn_error_get = get_db_connection()
        lista_todos_productos_error = conn_error_get.execute('SELECT id, nombre FROM Producto ORDER BY nombre ASC').fetchall()
        conn_error_get.close()
        return render_template('registrar_entrada.html', productos=lista_todos_productos_error, form_data=form_data_to_render)
        
    conn_get.close() 
    return render_template('registrar_entrada.html', productos=lista_todos_productos, form_data=form_data_to_render)

@app.route('/proveedores', endpoint='proveedores_lista') 
def proveedores_lista():
    conn = get_db_connection()
    search_query_proveedor = request.args.get('q_proveedor', '').strip()
    # Filtro por correo eliminado de la lógica de Python
    # filtro_con_correo = request.args.get('filtro_con_correo', '') 

    query_sql = 'SELECT id, nombre, telefono, correo, descripcion, fecha_registro FROM Proveedor'
    conditions = []
    params = []

    if search_query_proveedor:
        conditions.append("(nombre LIKE ? OR telefono LIKE ? OR correo LIKE ?)")
        like_query = f"%{search_query_proveedor}%"
        params.extend([like_query, like_query, like_query])
    
    # Lógica del filtro por correo eliminada
    # if filtro_con_correo == 'si':
    #     conditions.append("(correo IS NOT NULL AND correo != '')")
    # elif filtro_con_correo == 'no':
    #     conditions.append("(correo IS NULL OR correo = '')")

    if conditions:
        query_sql += " WHERE " + " AND ".join(conditions)
        
    query_sql += " ORDER BY nombre ASC"
    
    lista_proveedores = conn.execute(query_sql, params).fetchall()
    conn.close()
    
    return render_template(
        'proveedores.html', 
        proveedores=lista_proveedores, 
        search_query=search_query_proveedor 
        # filtro_con_correo_activo ya no es necesario
    )

@app.route('/proveedores/nuevo', methods=['GET', 'POST'])
def agregar_proveedor():
    form_data_to_render = request.form.to_dict() if request.method == 'POST' else {}
    if request.method == 'POST':
        nombre = form_data_to_render.get('nombre_proveedor')
        telefono = form_data_to_render.get('telefono_proveedor')
        correo = form_data_to_render.get('correo_proveedor')
        descripcion = form_data_to_render.get('descripcion_proveedor')

        if not nombre or not telefono:
            flash('El nombre y el teléfono del proveedor son obligatorios.', 'error')
            return render_template('agregar_proveedor.html', form_data=form_data_to_render)
        
        conn = None 
        try:
            conn = get_db_connection() 
            conn.execute(
                'INSERT INTO Proveedor (nombre, telefono, correo, descripcion) VALUES (?, ?, ?, ?)',
                (nombre, telefono, correo if correo else None, descripcion if descripcion else None)
            )
            conn.commit()
            flash(f'Proveedor "{nombre}" añadido exitosamente.', 'success')
            return redirect(url_for('proveedores_lista')) 
        except sqlite3.IntegrityError:
            if conn: conn.rollback()
            flash(f'Error: Ya existe un proveedor con el nombre "{nombre}".', 'error')
        except Exception as e:
            if conn: conn.rollback()
            flash(f'Ocurrió un error al guardar el proveedor: {e}', 'error')
        finally:
            if conn: conn.close() 
    
    return render_template('agregar_proveedor.html', form_data=form_data_to_render)

@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
def editar_proveedor(id):
    conn = get_db_connection()
    proveedor_a_editar = conn.execute('SELECT * FROM Proveedor WHERE id = ?', (id,)).fetchone()

    if not proveedor_a_editar:
        flash('Proveedor no encontrado.', 'error')
        conn.close()
        return redirect(url_for('proveedores_lista'))

    form_data_to_render = {}
    if request.method == 'POST':
        form_data_to_render = request.form.to_dict()
    elif proveedor_a_editar:
        form_data_to_render = dict(proveedor_a_editar)
        form_data_to_render['nombre_proveedor'] = proveedor_a_editar['nombre']
        form_data_to_render['telefono_proveedor'] = proveedor_a_editar['telefono']
        form_data_to_render['correo_proveedor'] = proveedor_a_editar['correo']
        form_data_to_render['descripcion_proveedor'] = proveedor_a_editar['descripcion']


    if request.method == 'POST':
        nombre = form_data_to_render.get('nombre_proveedor') 
        telefono = form_data_to_render.get('telefono_proveedor')
        correo = form_data_to_render.get('correo_proveedor')
        descripcion = form_data_to_render.get('descripcion_proveedor')

        if not nombre or not telefono: 
            flash('El nombre y el teléfono son obligatorios.', 'error')
            conn.close() 
            return render_template('editar_proveedor.html', proveedor=proveedor_a_editar, form_data=form_data_to_render)

        db_success = False
        try:
            conn.execute('''
                UPDATE Proveedor SET nombre = ?, telefono = ?, correo = ?, descripcion = ?
                WHERE id = ?
            ''', (nombre, telefono, correo if correo else None, descripcion if descripcion else None, id))
            conn.commit()
            flash(f'Proveedor "{nombre}" actualizado exitosamente.', 'success')
            db_success = True
        except sqlite3.IntegrityError:
            conn.rollback()
            flash(f'Error: Ya existe otro proveedor con el nombre "{nombre}".', 'error')
        except Exception as e:
            conn.rollback()
            flash(f'Ocurrió un error al actualizar el proveedor: {e}', 'error')
        finally:
            if conn: conn.close()
        
        if db_success:
            return redirect(url_for('proveedores_lista'))
        else:
            return render_template('editar_proveedor.html', proveedor=proveedor_a_editar, form_data=form_data_to_render)

    conn.close()
    return render_template('editar_proveedor.html', proveedor=proveedor_a_editar, form_data=form_data_to_render)


@app.route('/proveedores/eliminar/<int:id>', methods=['POST'])
def eliminar_proveedor(id):
    conn = get_db_connection()
    try:
        proveedor_nombre_row = conn.execute('SELECT nombre FROM Proveedor WHERE id = ?', (id,)).fetchone()
        if proveedor_nombre_row:
            proveedor_nombre = proveedor_nombre_row['nombre']
            conn.execute('DELETE FROM Proveedor WHERE id = ?', (id,))
            conn.commit()
            flash(f'Proveedor "{proveedor_nombre}" eliminado exitosamente.', 'success')
        else:
            flash('Error: Proveedor no encontrado.', 'error')
    except sqlite3.Error as e:
        conn.rollback()
        flash(f'Error al eliminar el proveedor: {e}', 'error')
    finally:
        conn.close()
    return redirect(url_for('proveedores_lista'))

# RUTA PARA CONFIGURACIÓN
@app.route('/settings')
def settings():
    current_year = datetime.datetime.now().year
    return render_template('settings.html', current_year=current_year)


if __name__ == '__main__':
    print(f"La base de datos se creará/estará en: {DATABASE_PATH}")
    init_db(add_sample_data=False) # O False si ya no quieres datos de ejemplo por defecto

    # Render usa la variable de entorno PORT. 
    # Si no está definida (ej. al correr localmente), usa 5000 por defecto.
    port = int(os.environ.get("PORT", 5000)) 

    # Para producción (como en Render), debug debe ser False.
    # host='0.0.0.0' hace que sea accesible desde fuera del contenedor de Render.
    app.run(host='0.0.0.0', port=port, debug=False) 
