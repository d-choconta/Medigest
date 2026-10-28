from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'clave_secreta_medigest'


# conexion base
def obtener_conexion():
    conexion = psycopg2.connect(
        host="localhost",
        database="2",
        user="postgres",
        password="12345"
    )
    return conexion



@app.route('/')
def inicio():
    return render_template('inicio.html')

@app.route('/funciona')
def funciona():
    return render_template('funciona.html')

@app.route('/beneficios')
def beneficios():
    return render_template('beneficios.html')

@app.route('/ayuda')
def ayuda():
    return render_template('ayuda.html')

@app.route('/ingresar', methods=['GET', 'POST'])
def ingresar():

    if request.method == 'POST':

        accion = request.form.get('accion')

        conexion = obtener_conexion()
        cursor = conexion.cursor()

        if accion == 'registrar':

            tipo_doc = request.form['tipo_documento']
            num_doc = request.form['numero_documento']
            nombres = request.form['nombres']
            apellidos = request.form['apellidos']
            correo = request.form['correo']
            password_plana = request.form['password']
            telefono = request.form['telefono']
            eps = request.form['eps']

            password_segura = generate_password_hash(password_plana)

            try:

                cursor.execute(
                    """INSERT INTO afiliados
                       (tipo_documento, numero_documento, nombres, apellidos,
                        correo, contrasena, telefono, eps)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        tipo_doc,
                        num_doc,
                        nombres,
                        apellidos,
                        correo,
                        password_segura,
                        telefono,
                        eps
                    )
                )

                conexion.commit()

                flash(
                    '¡Registro exitoso! Por favor inicia sesión con tus datos.',
                    'success'
                )

                return redirect(url_for('ingresar'))

            except Exception as e:

                conexion.rollback()

                flash(
                    f'Error en el registro (el correo o número de documento ya existen): {e}',
                    'error'
                )

            finally:

                cursor.close()
                conexion.close()

        elif accion == 'login':

            correo = request.form['correo_login']
            password_ingresada = request.form['password_login']

            try:

                cursor.execute(
                    """SELECT id_afiliado, nombres, apellidos, contrasena,eps
                       FROM afiliados
                       WHERE correo = %s""",
                    (correo,)
                )

                usuario = cursor.fetchone()

                if usuario:

                    password_encriptada = usuario[3]

                    if check_password_hash(
                        password_encriptada,
                        password_ingresada
                    ):

                        session['id_afiliado'] = usuario[0]

                        session['nombre_usuario'] = (
                            f"{usuario[1]} {usuario[2]}"
                        )

                        

                        flash(
                            f'¡Bienvenido de nuevo, {usuario[1]}!',
                            'success'
                        )

                        return redirect(url_for('menu_afiliado'))

                    else:

                        flash(
                            'Contraseña incorrecta. Inténtalo de nuevo.',
                            'error'
                        )

                else:

                    flash(
                        'No existe una cuenta registrada con este correo.',
                        'error'
                    )

            except Exception as e:

                flash(
                    f'Error al iniciar sesión: {e}',
                    'error'
                )

            finally:

                cursor.close()
                conexion.close()

    return render_template('ingresar.html')

@app.route('/menu')
def menu_afiliado():

    if 'id_afiliado' not in session:

        flash(
            'Por favor inicia sesión para acceder a tu menú.',
            'error'
        )

        return redirect(url_for('ingresar'))

    id_afiliado = session['id_afiliado']

    ciudad_seleccionada = request.args.get(
        'ciudad',
        'Bogotá'
    )

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:

        # 0. OBTENER LA EPS DEL AFILIADO LOGUEADO (ESTO DEFINE eps_usuario)
        cursor.execute("SELECT eps FROM afiliados WHERE id_afiliado = %s", (id_afiliado,))
        res_eps = cursor.fetchone()
        eps_usuario = res_eps[0] if res_eps else ""
        
        # 1. formulas del ususario

        cursor.execute(
            """SELECT id_formula,
                      fecha_emision,
                      medico_que_formula,
                      estado_formula,
                      archivo_url
               FROM formulas_medicas
               WHERE id_afiliado = %s
               ORDER BY fecha_emision DESC""",
            (id_afiliado,)
        )

        todas_formulas = cursor.fetchall()

        total_formulas = sum(
            1 for f in todas_formulas
            if f[3] == 'Pendiente'
        )

        formulas_aprobadas_lista = [
            f for f in todas_formulas
            if f[3] == 'Aprobada'
        ]

        tiene_formulas_aprobadas = (
            len(formulas_aprobadas_lista) > 0
        )

        # 2. form que se acaba de registrar

        id_formula_en_validacion = session.get(
            'formula_en_validacion'
        )

        tiene_formula_en_validacion = False

        if id_formula_en_validacion:

            cursor.execute(
                """SELECT estado_formula
                   FROM formulas_medicas
                   WHERE id_formula = %s
                     AND id_afiliado = %s""",
                (
                    id_formula_en_validacion,
                    id_afiliado
                )
            )

            estado_formula = cursor.fetchone()

            if estado_formula and estado_formula[0] == 'Pendiente':

                tiene_formula_en_validacion = True

            else:

                session.pop(
                    'formula_en_validacion',
                    None
                )

                id_formula_en_validacion = None

        # 3. form para consulktar inventario

        id_formula_seleccionada = request.args.get(
            'formula',
            type=int
        )

        # no escogio form la recien aprobada
        # primera aprobada

        if not id_formula_seleccionada:

            if formulas_aprobadas_lista:

                id_formula_seleccionada = (
                    formulas_aprobadas_lista[0][0]
                )

        # 4. tner el medc de la form

        id_medicamento_formula = None

        if id_formula_seleccionada:

            cursor.execute(
                """SELECT id_medicamento
                   FROM formulas_medicas
                   WHERE id_formula = %s
                     AND id_afiliado = %s
                     AND estado_formula = 'Aprobada'""",
                (
                    id_formula_seleccionada,
                    id_afiliado
                )
            )

            resultado_medicamento = cursor.fetchone()

            if resultado_medicamento:

                id_medicamento_formula = (
                    resultado_medicamento[0]
                )

        # 5. turnos agenda

        cursor.execute(
            """SELECT st.codigo_turno,
                      st.fecha_turno,
                      st.estado_solicitud,
                      p.nombre_drogueria,
                      p.direccion,
                      fm.id_formula
               FROM solicitudes_turnos st
               JOIN formulas_medicas fm
                 ON st.id_formula = fm.id_formula
               JOIN puntos_entrega p
                 ON st.id_punto = p.id_punto
               WHERE fm.id_afiliado = %s
               ORDER BY st.fecha_turno DESC""",
            (id_afiliado,)
        )

        turnos_agendados_lista = cursor.fetchall()

        total_turnos = len([
            t for t in turnos_agendados_lista
            if t[2] == 'Agendado'
        ])

        # 6. ciudad

        cursor.execute(
            """SELECT DISTINCT ciudad
               FROM puntos_entrega
               ORDER BY ciudad ASC"""
        )

        ciudades_lista = [
            row[0]
            for row in cursor.fetchall()
        ]

        # 7. puntos con el medc

        # 7. Puntos con el medicamento filtrados por Ciudad, Stock y Convenios de la EPS
        if id_medicamento_formula:

            cursor.execute(
                """SELECT DISTINCT
                          p.id_punto,
                          p.nombre_drogueria,
                          p.direccion,
                          p.ciudad,
                          p.latitud,
                          p.longitud
                   FROM inventario i
                   JOIN puntos_entrega p
                     ON i.id_punto = p.id_punto
                   WHERE p.ciudad = %s
                     AND i.id_medicamento = %s
                     AND i.stock_actual > 0
                     AND (p.convenios ILIKE %s OR p.convenios ILIKE '%%Otra%%')
                   ORDER BY p.nombre_drogueria""",
                (
                    ciudad_seleccionada,
                    id_medicamento_formula,
                    f"%{eps_usuario}%"
                )
            )

            puntos_entrega_lista = cursor.fetchall()

        else:

            puntos_entrega_lista = []

        # 8. Inventario detallado del medicamento filtrado por Convenios de la EPS
        if id_medicamento_formula:

            cursor.execute(
                """SELECT DISTINCT
                          p.id_punto,
                          p.nombre_drogueria,
                          p.direccion,
                          p.ciudad,
                          p.telefono_contacto,
                          m.nombre_medicamento,
                          i.stock_actual
                   FROM inventario i
                   JOIN puntos_entrega p
                     ON i.id_punto = p.id_punto
                   JOIN medicamentos m
                     ON i.id_medicamento = m.id_medicamento
                   WHERE p.ciudad = %s
                     AND i.id_medicamento = %s
                     AND (p.convenios ILIKE %s OR p.convenios ILIKE '%%Otra%%')
                   ORDER BY p.nombre_drogueria""",
                (
                    ciudad_seleccionada,
                    id_medicamento_formula,
                    f"%{eps_usuario}%"
                )
            )

            inventario_puntos = cursor.fetchall()

        else:

            inventario_puntos = []

        # 9. CATÁLOGO DE MEDICAMENTOS

        cursor.execute(
            """SELECT id_medicamento,
                      nombre_medicamento,
                      concentracion,
                      forma_farmaceutica
               FROM medicamentos"""
        )

        catalogo_medicamentos = cursor.fetchall()

        # 10. Consultar facturacion del afiliado
        cursor.execute(
            """SELECT
                   fp.id_pago,
                   st.codigo_turno,
                   m.nombre_medicamento,
                   fp.valor_copago,
                   fp.estado_pago,
                   fp.metodo_pago,
                   fp.fecha_pago
               FROM facturacion_pagos fp
               JOIN solicitudes_turnos st
                   ON fp.id_solicitud = st.id_solicitud
               JOIN formulas_medicas fm
                   ON st.id_formula = fm.id_formula
               JOIN medicamentos m
                   ON st.id_medicamento = m.id_medicamento
               WHERE fm.id_afiliado = %s
               ORDER BY fp.id_pago DESC""",
            (id_afiliado,)
        )

        pagos_lista = cursor.fetchall()


    except Exception as e:

        total_formulas = 0
        todas_formulas = []

        tiene_formulas_aprobadas = False
        formulas_aprobadas_lista = []
        tiene_formula_en_validacion = False
        id_formula_en_validacion = None
        id_formula_seleccionada = None
        id_medicamento_formula = None
        total_turnos = 0
        turnos_agendados_lista = []
        ciudades_lista = []
        puntos_entrega_lista = []
        inventario_puntos = []
        catalogo_medicamentos = []
        pagos_lista = []

        print("Error en /menu:", e)


    finally:

        cursor.close()
        conexion.close()


    return render_template(
        'menu.html',

        total_formulas=total_formulas,

        todas_formulas=todas_formulas,

        tiene_formulas_aprobadas=
            tiene_formulas_aprobadas,

        formulas_aprobadas_lista=
            formulas_aprobadas_lista,

        tiene_formula_en_validacion=
            tiene_formula_en_validacion,

        id_formula_en_validacion=
            id_formula_en_validacion,

        id_formula_seleccionada=
            id_formula_seleccionada,

        id_medicamento_formula=
            id_medicamento_formula,

        total_turnos=total_turnos,

        turnos_agendados_lista=
            turnos_agendados_lista,

        ciudades_lista=
            ciudades_lista,

        ciudad_seleccionada=
            ciudad_seleccionada,

        puntos_entrega_lista=
            puntos_entrega_lista,

        inventario_puntos=
            inventario_puntos,

        catalogo_medicamentos=
            catalogo_medicamentos,

        # enviar pagos a la pagina
        pagos_lista=pagos_lista
    )



# agend turno

@app.route('/agendar_turno', methods=['POST'])
def agendar_turno():

    if 'id_afiliado' not in session:
        return redirect(url_for('ingresar'))

    id_formula = request.form['id_formula']
    id_punto = request.form['id_punto']
    fecha_turno = request.form['fecha_turno']

    import random

    codigo_turno = (
        f"TRN-{random.randint(10000, 99999)}"
    )

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:

        # medic de la formula

        cursor.execute(
            """SELECT id_medicamento
               FROM formulas_medicas
               WHERE id_formula = %s
                 AND id_afiliado = %s
                 AND estado_formula = 'Aprobada'""",
            (
                id_formula,
                session['id_afiliado']
            )
        )

        resultado = cursor.fetchone()

        if not resultado:

            flash(
                'La fórmula no existe, no te pertenece '
                'o todavía no está aprobada.',
                'error'
            )

            cursor.close()
            conexion.close()

            return redirect(
                url_for('menu_afiliado')
            )


        id_med_relacionado = resultado[0]


        # verificar puntos del medc

        cursor.execute(
            """SELECT stock_actual
               FROM inventario
               WHERE id_punto = %s
                 AND id_medicamento = %s""",
            (
                id_punto,
                id_med_relacionado
            )
        )

        stock = cursor.fetchone()

        if not stock or stock[0] <= 0:

            flash(
                'El medicamento seleccionado no tiene '
                'stock disponible en ese punto.',
                'error'
            )

            cursor.close()
            conexion.close()

            return redirect(
                url_for('menu_afiliado')
            )
        
        # guardar turno
        cursor.execute(
            """INSERT INTO solicitudes_turnos
               (
                   id_formula,
                   id_medicamento,
                   id_punto,
                   fecha_solicitud,
                   fecha_turno,
                   estado_solicitud,
                   codigo_turno
               )
               VALUES
               (
                   %s,
                   %s,
                   %s,
                   CURRENT_TIMESTAMP,
                   %s,
                   'Agendado',
                   %s
               )
               RETURNING id_solicitud""",
            (
                id_formula,
                id_med_relacionado,
                id_punto,
                fecha_turno,
                codigo_turno
            )
        )

        # obtener el turno creado
        id_solicitud = cursor.fetchone()[0]

        # verificar si requiere copago
        cursor.execute(
            """SELECT requiere_copago
               FROM medicamentos
               WHERE id_medicamento = %s""",
            (id_med_relacionado,)
        )

        resultado_copago = cursor.fetchone()
        requiere_copago = resultado_copago[0] if resultado_copago else False

        # definir valor de prueba
        valor_copago = 5000 if requiere_copago else 0

        # registrar facturacion
        cursor.execute(
            """INSERT INTO facturacion_pagos
               (id_solicitud, valor_copago, estado_pago)
               VALUES (%s, %s, %s)""",
            (
                id_solicitud,
                valor_copago,
                'Pendiente' if requiere_copago else 'No requerido'
            )
        )

        conexion.commit()

        flash(
            f'¡Turno agendado con éxito! '
            f'Tu código de recogida es {codigo_turno}. '
            f'Preséntate en la sede seleccionada.',
            'success'
        )


    except Exception as e:

        conexion.rollback()

        flash(
            f'Error al agendar el turno: {e}',
            'error'
        )


    finally:

        cursor.close()
        conexion.close()


    return redirect(
        url_for('menu_afiliado')
    )


# registrar form
@app.route('/registrar_formula', methods=['POST'])
def registrar_formula():

    if 'id_afiliado' not in session:
        return redirect(url_for('ingresar'))

    id_afiliado = session['id_afiliado']

    medico = request.form['medico']

    fecha_emision = request.form['fecha_emision']

    id_medicamento = request.form['id_medicamento']


    archivo = request.files['archivo_formula']

    nombre_archivo = (
        archivo.filename
        if archivo
        else 'formula_digital.pdf'
    )


    conexion = obtener_conexion()
    cursor = conexion.cursor()


    try:

        # guardar info del medc

        cursor.execute(
            """INSERT INTO formulas_medicas
               (
                   id_afiliado,
                   id_medicamento,
                   medico_que_formula,
                   fecha_emision,
                   archivo_url,
                   estado_formula
               )
               VALUES
               (
                   %s,
                   %s,
                   %s,
                   %s,
                   %s,
                   'Pendiente'
               )
               RETURNING id_formula""",
            (
                id_afiliado,
                id_medicamento,
                medico,
                fecha_emision,
                nombre_archivo
            )
        )


        id_formula_generada = cursor.fetchone()[0]

        conexion.commit()


        # guarda form en valida

        session['formula_en_validacion'] = (
            id_formula_generada
        )


        flash(
            '¡Fórmula cargada correctamente! '
            'Espera la validación.',
            'success'
        )


    except Exception as e:

        conexion.rollback()

        flash(
            f'Error al registrar la fórmula: {e}',
            'error'
        )

    finally:

        cursor.close()
        conexion.close()


    # al menu
    # 10 segundos

    return redirect(
        url_for(
            'menu_afiliado',
            formula=id_formula_generada
        )
    )


# aprobar la actual

@app.route('/aprobar_formula_automatico', methods=['POST'])
def aprobar_formula_automatico():
    if 'id_afiliado' not in session:
        return {'status': 'error', 'message': 'No autorizado'}, 401

    id_afiliado = session['id_afiliado']
    id_formula = None

    try:
        if request.is_json:
            data = request.get_json()
            if data and 'id_formula' in data:
                id_formula = int(data['id_formula'])
        else:
            val = request.form.get('id_formula')
            if val:
                id_formula = int(val)
    except (ValueError, TypeError):
        id_formula = None

    # Si no llegó por la petición, intentamos sacarlo de la sesión activa
    if not id_formula:
        id_formula = session.get('formula_en_validacion')

    if not id_formula:
        return {'status': 'error', 'message': 'No se recibió la fórmula'}, 400

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute(
            """UPDATE formulas_medicas
               SET estado_formula = 'Aprobada'
               WHERE id_formula = %s
                 AND id_afiliado = %s
                 AND estado_formula = 'Pendiente'""",
            (id_formula, id_afiliado)
        )

        conexion.commit()

        # Limpiamos la variable de validación temporal
        session.pop('formula_en_validacion', None)

        return {'status': 'success', 'id_formula': id_formula}

    except Exception as e:
        conexion.rollback()
        return {'status': 'error', 'message': str(e)}, 500

    finally:
        cursor.close()
        conexion.close()

# Registrar pago simulado
@app.route('/pagar_copago', methods=['POST'])
def pagar_copago():

    # Verificar que el afiliado inició sesión
    if 'id_afiliado' not in session:
        return redirect(url_for('ingresar'))

    id_afiliado = session['id_afiliado']
    id_pago = request.form.get('id_pago', type=int)
    metodo_pago = request.form.get('metodo_pago')

    # Validar los datos recibidos
    if not id_pago or metodo_pago not in ['PSE', 'Tarjeta']:
        flash('Datos de pago no válidos.', 'error')
        return redirect(url_for('menu_afiliado'))

    conexion = None
    cursor = None

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # Verificar que el copago pertenece al afiliado
        cursor.execute(
            """SELECT fp.id_pago
               FROM facturacion_pagos fp
               JOIN solicitudes_turnos st
                   ON fp.id_solicitud = st.id_solicitud
               JOIN formulas_medicas fm
                   ON st.id_formula = fm.id_formula
               WHERE fp.id_pago = %s
                 AND fm.id_afiliado = %s
                 AND fp.estado_pago = 'Pendiente'
                 AND fp.valor_copago > 0
               FOR UPDATE OF fp""",
            (id_pago, id_afiliado)
        )

        pago = cursor.fetchone()

        if not pago:
            conexion.rollback()
            flash('El copago no está disponible para pagar.', 'error')
            return redirect(url_for('menu_afiliado'))

        # Confirmar el pago de prueba
        cursor.execute(
            """UPDATE facturacion_pagos
               SET estado_pago = 'Pagado',
                   metodo_pago = %s,
                   fecha_pago = CURRENT_TIMESTAMP
               WHERE id_pago = %s""",
            (metodo_pago, id_pago)
        )

        conexion.commit()

        flash('Pago simulado realizado correctamente.', 'success')

    except Exception as e:
        if conexion:
            conexion.rollback()

        print('Error en pago simulado:', e)
        flash('No se pudo registrar el pago.', 'error')

    finally:
        if cursor:
            cursor.close()

        if conexion:
            conexion.close()

    return redirect(url_for('menu_afiliado'))

@app.route('/logout')
def logout():

    session.clear()

    flash(
        'Has cerrado sesión correctamente.',
        'success'
    )

    return redirect(
        url_for('ingresar')
    )


if __name__ == '__main__':
    app.run(debug=True)