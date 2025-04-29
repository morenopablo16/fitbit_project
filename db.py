import psycopg2
from psycopg2 import sql
from config import DB_CONFIG
from encryption import encrypt_token, decrypt_token

def connect_to_db():
    """
    Conecta a la base de datos TimeScaleDB.
    """
    try:
        connection = psycopg2.connect(
            host=DB_CONFIG["host"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
            sslmode=DB_CONFIG["sslmode"]
        )
        print("Conexión exitosa a TimeScaleDB.")
        return connection
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def init_db():
    """
    Inicializa la base de datos creando las tablas si no existen y configurando TimeScaleDB.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                # Verificar si TimeScaleDB está instalado
                cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';")
                if cursor.fetchone() is None:
                    print("TimeScaleDB no está instalado. Por favor, instala la extensión primero.")
                    print("Visita: https://docs.timescale.com/install/latest/self-hosted/windows/installation/")
                    return False
                
                # Enable TimeScaleDB extension
                cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
                
                # Crear tabla de usuarios
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        email VARCHAR(255) NOT NULL,
                        access_token TEXT,
                        refresh_token TEXT,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Crear tabla de resúmenes diarios
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS daily_summaries (
                        id SERIAL,
                        user_id INTEGER REFERENCES users(id),
                        date DATE NOT NULL,
                        steps INTEGER,
                        heart_rate INTEGER,
                        sleep_minutes INTEGER,
                        calories INTEGER,
                        distance FLOAT,
                        floors INTEGER,
                        elevation FLOAT,
                        active_minutes INTEGER,
                        sedentary_minutes INTEGER,
                        nutrition_calories INTEGER,
                        water FLOAT,
                        weight FLOAT,
                        bmi FLOAT,
                        fat FLOAT,
                        oxygen_saturation FLOAT,
                        respiratory_rate FLOAT,
                        temperature FLOAT,
                        UNIQUE(user_id, date)
                    );
                """)
                
                # Convertir a hipertabla
                cursor.execute("""
                    SELECT create_hypertable('daily_summaries', 'date', 
                        if_not_exists => TRUE,
                        migrate_data => TRUE
                    );
                """)
                
                # Crear tabla de métricas intradía
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS intraday_metrics (
                        id SERIAL,
                        user_id INTEGER REFERENCES users(id),
                        time TIMESTAMPTZ NOT NULL,
                        type VARCHAR(50) NOT NULL,
                        value FLOAT NOT NULL
                    );
                """)
                
                # Convertir a hipertabla
                cursor.execute("""
                    SELECT create_hypertable('intraday_metrics', 'time',
                        if_not_exists => TRUE,
                        migrate_data => TRUE
                    );
                """)
                
                connection.commit()
                print("Base de datos inicializada correctamente con TimeScaleDB.")
                return True
                
        except Exception as e:
            print(f"Error al inicializar la base de datos: {e}")
            connection.rollback()
            return False
        finally:
            connection.close()
    return False

def get_latest_user_id_by_email(email):
    """
    Obtiene el user_id más reciente asociado a un correo electrónico.
    """
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM users
                    WHERE email = %s
                    ORDER BY created_at DESC
                    LIMIT 1;
                """, (email,))
                result = cur.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"Error al obtener el user_id más reciente: {e}")
        finally:
            conn.close()
    return None

def insert_intraday_data(user_id, timestamp, data_type, value):
    """
    Inserta datos intradía en la base de datos utilizando el nuevo esquema TimeScaleDB.

    Args:
        user_id (int): ID del usuario.
        timestamp (datetime): Marca de tiempo de los datos.
        data_type (str): Tipo de datos ('steps', 'heart_rate', 'active_zone_minutes').
        value (int/float): Valor de la métrica.
    """
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cursor:
                # Insertar directamente en la tabla intraday_metrics
                cursor.execute("""
                    INSERT INTO intraday_metrics (user_id, time, type, value)
                    VALUES (%s, %s, %s, %s);
                """, (user_id, timestamp, data_type, value))
                
                conn.commit()
                print(f"Datos intradía {data_type} para usuario {user_id} guardados exitosamente en intraday_metrics.")
        except Exception as e:
            print(f"Error al insertar datos intradía: {e}")
            conn.rollback()
        finally:
            conn.close()

def add_user(name, email, access_token=None, refresh_token=None):
    """
    Añade un nuevo usuario a la base de datos.

    Args:
        name (str): Nombre del usuario.
        email (str): Correo electrónico del usuario.
        access_token (str): Token de acceso de Fitbit.
        refresh_token (str): Token de actualización de Fitbit.

    Returns:
        int: ID del usuario recién insertado.
    """

    #If access_token and refresh_token are not None, encrypt them
    if access_token and refresh_token:
         # Encrypt the tokens before storing them
        encrypted_access_token = encrypt_token(access_token)
        encrypted_refresh_token = encrypt_token(refresh_token)
    else:
        encrypted_access_token = None
        encrypted_refresh_token = None
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                # Insertar usuario en la tabla users
                insert_query = """
                INSERT INTO users (name, email, access_token, refresh_token)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
                """
                cursor.execute(insert_query, (name, email, encrypted_access_token, encrypted_refresh_token))
                user_id = cursor.fetchone()[0]  # Obtener el ID del usuario recién insertado
                connection.commit()
                print(f"Usuario {email} añadido exitosamente con ID {user_id}.")
                return user_id
        except Exception as e:
            print(f"Error al añadir usuario: {e}")
        finally:
            connection.close()

def save_to_db(user_id, date, **data):
    """
    Guarda los datos de Fitbit en la base de datos utilizando el nuevo esquema TimeScaleDB.

    Args:
        user_id (int): ID del usuario.
        date (str): Fecha de los datos (YYYY-MM-DD).
        data (dict): Diccionario con los datos de Fitbit.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                # Insertar datos en la tabla daily_summaries
                insert_query = """
                INSERT INTO daily_summaries (
                    user_id, date, steps, heart_rate, sleep_minutes,
                    calories, distance, floors, elevation, active_minutes,
                    sedentary_minutes, nutrition_calories, water, weight,
                    bmi, fat, oxygen_saturation, respiratory_rate, temperature
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (date, user_id) DO UPDATE SET
                    steps = EXCLUDED.steps,
                    heart_rate = EXCLUDED.heart_rate,
                    sleep_minutes = EXCLUDED.sleep_minutes,
                    calories = EXCLUDED.calories,
                    distance = EXCLUDED.distance,
                    floors = EXCLUDED.floors,
                    elevation = EXCLUDED.elevation,
                    active_minutes = EXCLUDED.active_minutes,
                    sedentary_minutes = EXCLUDED.sedentary_minutes,
                    nutrition_calories = EXCLUDED.nutrition_calories,
                    water = EXCLUDED.water,
                    weight = EXCLUDED.weight,
                    bmi = EXCLUDED.bmi,
                    fat = EXCLUDED.fat,
                    oxygen_saturation = EXCLUDED.oxygen_saturation,
                    respiratory_rate = EXCLUDED.respiratory_rate,
                    temperature = EXCLUDED.temperature;
                """
                cursor.execute(insert_query, (
                    user_id, date,
                    data.get("steps"),
                    data.get("heart_rate"),
                    data.get("sleep_minutes"),
                    data.get("calories"),
                    data.get("distance"),
                    data.get("floors"),
                    data.get("elevation"),
                    data.get("active_minutes"),
                    data.get("sedentary_minutes"),
                    data.get("nutrition_calories"),
                    data.get("water"),
                    data.get("weight"),
                    data.get("bmi"),
                    data.get("fat"),
                    data.get("oxygen_saturation"),
                    data.get("respiratory_rate"),
                    data.get("temperature")
                ))
                
                connection.commit()
                print(f"Datos de usuario {user_id} guardados exitosamente en daily_summaries.")
        except Exception as e:
            print(f"Error al guardar los datos: {e}")
            connection.rollback()
        finally:
            connection.close()

def get_user_tokens(email):
    """
    Retrieve and decrypt tokens for the user with the most recent timestamp or highest user_id.
    """
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT access_token, refresh_token 
                    FROM users 
                    WHERE email = %s 
                    ORDER BY created_at DESC, id DESC 
                    LIMIT 1;
                """, (email,))
                result = cur.fetchone()
                if result:
                    encrypted_access_token, encrypted_refresh_token = result
                    # Decrypt the tokens
                    access_token = decrypt_token(encrypted_access_token)
                    refresh_token = decrypt_token(encrypted_refresh_token)
                    return access_token, refresh_token
        except Exception as e:
            print(f"Error retrieving user tokens: {e}")
        finally:
            conn.close()
    return None, None

def get_unique_emails():
    """
    Obtiene una lista de emails únicos de la base de datos.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT DISTINCT email FROM users;")
                emails = [row[0] for row in cursor.fetchall()]
                return emails
        except Exception as e:
            print(f"Error al obtener emails únicos: {e}")
        finally:
            connection.close()
    return []

def get_user_id_by_email(email):
    """
    Obtiene el ID del usuario más reciente a partir de su correo electrónico.

    Args:
        email (str): Correo electrónico del usuario.

    Returns:
        int: ID del usuario más reciente o None si no se encuentra.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM users
                    WHERE email = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1;
                """, (email,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"Error al obtener el ID del usuario: {e}")
        finally:
            connection.close()
    return None

def update_users_tokens(email, access_token, refresh_token):
    """
    Actualiza los tokens de acceso y actualización de un usuario.

    Args:
        email (str): Correo electrónico del usuario.
        access_token (str): Nuevo token de acceso.
        refresh_token (str): Nuevo token de actualización.
    """
    # Encrypt the tokens before storing them
    encrypted_access_token = encrypt_token(access_token)
    encrypted_refresh_token = encrypt_token(refresh_token)
    user_id=get_user_id_by_email(email)

    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE users
                    SET access_token = %s, refresh_token = %s
                    WHERE id = %s;
                """, (encrypted_access_token, encrypted_refresh_token, user_id))
                connection.commit()
                print(f"Tokens actualizados para {email}.")
        except Exception as e:
            print(f"Error al actualizar los tokens: {e}")
        finally:
            connection.close()

def get_user_history(user_id):
    """
    Obtiene el historial completo de un usuario utilizando el nuevo esquema TimeScaleDB.

    Args:
        user_id (int): ID del usuario.

    Returns:
        list: Lista de tuplas con el historial del usuario.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT * FROM daily_summaries
                    WHERE user_id = %s
                    ORDER BY date;
                """, (user_id,))
                history = cursor.fetchall()
                return history
        except Exception as e:
            print(f"Error al obtener el historial: {e}")
        finally:
            connection.close()

def get_email_history(email):
    """
    Obtiene el historial completo de un email (puede tener múltiples usuarios) utilizando el nuevo esquema TimeScaleDB.

    Args:
        email (str): Correo electrónico del usuario.

    Returns:
        list: Lista de tuplas con el historial del email.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT u.name, d.*
                    FROM users u
                    JOIN daily_summaries d ON u.id = d.user_id
                    WHERE u.email = %s
                    ORDER BY u.created_at, d.date;
                """, (email,))
                history = cursor.fetchall()
                return history
        except Exception as e:
            print(f"Error al obtener el historial: {e}")
        finally:
            connection.close()
    return []

def run_tests():
    """
    Ejecuta pruebas de inserción y consulta para verificar el funcionamiento de la base de datos con el nuevo esquema TimeScaleDB.
    """

    # Caso 1: Inserción de un nuevo usuario y sus mediciones
    user_id_1 = add_user(
        name="Juan Pérez",
        email="juan@example.com",
        access_token="token_juan",
        refresh_token="refresh_juan"
    )
    save_to_db(
        user_id=user_id_1,
        date="2023-12-01",
        steps=10000,
        heart_rate=75,
        sleep_minutes=420,
        calories=2000,
        distance=8.5,
        floors=10,
        elevation=100.5,
        active_minutes=60,
        sedentary_minutes=480,
        nutrition_calories=1800,
        water=2.5,
        weight=70.5,
        bmi=22.5,
        fat=18.5,
        oxygen_saturation=98.0,
        respiratory_rate=16.5,
        temperature=36.5
    )
    save_to_db(
        user_id=user_id_1,
        date="2023-12-02",
        steps=12000,
        heart_rate=80,
        sleep_minutes=400
    )

    # Caso 2: Inserción de múltiples mediciones para el mismo usuario
    save_to_db(
        user_id=user_id_1,
        date="2023-12-03",
        steps=11000,
        heart_rate=78,
        sleep_minutes=410,
        calories=2100,
        distance=9.0,
        floors=12,
        elevation=105.0,
        active_minutes=65,
        sedentary_minutes=470,
        nutrition_calories=1900,
        water=2.7,
        weight=71.0,
        bmi=22.7,
        fat=18.7,
        oxygen_saturation=98.2,
        respiratory_rate=16.7,
        temperature=36.6
    )

    # Caso 3: Inserción de un nuevo usuario con el mismo email (reasignación del dispositivo Fitbit)
    user_id_2 = add_user(
        name="María Gómez",
        email="juan@example.com",  # Mismo email que Juan
        access_token="token_maria",
        refresh_token="refresh_maria"
    )

    # Caso 4: Inserción de mediciones para el nuevo usuario con el mismo email
    save_to_db(
        user_id=user_id_2,
        date="2023-12-04",
        steps=9000,
        heart_rate=72,
        sleep_minutes=430,
        calories=1900,
        distance=7.5,
        floors=8,
        elevation=95.0,
        active_minutes=55,
        sedentary_minutes=490,
        nutrition_calories=1700,
        water=2.3,
        weight=69.0,
        bmi=22.0,
        fat=18.0,
        oxygen_saturation=97.8,
        respiratory_rate=16.0,
        temperature=36.4
    )

    # Caso 5: Inserción de datos intradía
    from datetime import datetime, timedelta
    base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(24):
        current_time = base_time + timedelta(hours=i)
        insert_intraday_data(user_id_1, current_time, "steps", 500 + i * 100)
        insert_intraday_data(user_id_1, current_time, "heart_rate", 60 + i)
        insert_intraday_data(user_id_1, current_time, "active_zone_minutes", i * 2)

    # Caso 6: Consulta del historial completo de un usuario
    print("\nHistorial de Juan Pérez:")
    history_juan = get_user_history(user_id_1)
    for record in history_juan:
        print(record)

    print("\nHistorial de María Gómez:")
    history_maria = get_user_history(user_id_2)
    for record in history_maria:
        print(record)

    # Caso 7: Consulta del historial de un email (que puede tener múltiples usuarios)
    print("\nHistorial del email juan@example.com:")
    email_history = get_email_history("juan@example.com")
    for record in email_history:
        print(record)
        
    # Caso 8: Consulta de métricas intradía
    print("\nMétricas intradía de pasos para Juan Pérez:")
    from datetime import datetime, timedelta
    start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(days=1)
    steps_metrics = get_intraday_metrics(user_id_1, "steps", start_time, end_time)
    for metric in steps_metrics:
        print(metric)

def insert_daily_summary(user_id, date, **data):
    """
    Inserta o actualiza un resumen diario en la tabla daily_summaries.
    
    Args:
        user_id (int): ID del usuario.
        date (str): Fecha de los datos (YYYY-MM-DD).
        data (dict): Diccionario con los datos de Fitbit.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                # Insertar datos en la tabla daily_summaries
                insert_query = """
                INSERT INTO daily_summaries (
                    user_id, date, steps, heart_rate, sleep_minutes,
                    calories, distance, floors, elevation, active_minutes,
                    sedentary_minutes, nutrition_calories, water, weight,
                    bmi, fat, oxygen_saturation, respiratory_rate, temperature
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (date, user_id) DO UPDATE SET
                    steps = EXCLUDED.steps,
                    heart_rate = EXCLUDED.heart_rate,
                    sleep_minutes = EXCLUDED.sleep_minutes,
                    calories = EXCLUDED.calories,
                    distance = EXCLUDED.distance,
                    floors = EXCLUDED.floors,
                    elevation = EXCLUDED.elevation,
                    active_minutes = EXCLUDED.active_minutes,
                    sedentary_minutes = EXCLUDED.sedentary_minutes,
                    nutrition_calories = EXCLUDED.nutrition_calories,
                    water = EXCLUDED.water,
                    weight = EXCLUDED.weight,
                    bmi = EXCLUDED.bmi,
                    fat = EXCLUDED.fat,
                    oxygen_saturation = EXCLUDED.oxygen_saturation,
                    respiratory_rate = EXCLUDED.respiratory_rate,
                    temperature = EXCLUDED.temperature;
                """
                cursor.execute(insert_query, (
                    user_id, date,
                    data.get("steps"),
                    data.get("heart_rate"),
                    data.get("sleep_minutes"),
                    data.get("calories"),
                    data.get("distance"),
                    data.get("floors"),
                    data.get("elevation"),
                    data.get("active_minutes"),
                    data.get("sedentary_minutes"),
                    data.get("nutrition_calories"),
                    data.get("water"),
                    data.get("weight"),
                    data.get("bmi"),
                    data.get("fat"),
                    data.get("oxygen_saturation"),
                    data.get("respiratory_rate"),
                    data.get("temperature")
                ))
                connection.commit()
                print(f"Resumen diario para usuario {user_id} guardado exitosamente.")
        except Exception as e:
            print(f"Error al guardar el resumen diario: {e}")
            connection.rollback()
        finally:
            connection.close()

def insert_intraday_metric(user_id, timestamp, metric_type, value):
    """
    Inserta una métrica intradía en la tabla intraday_metrics.
    
    Args:
        user_id (int): ID del usuario.
        timestamp (datetime): Marca de tiempo de la métrica.
        metric_type (str): Tipo de métrica ('heart_rate', 'steps', etc.).
        value (float): Valor de la métrica.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                insert_query = """
                INSERT INTO intraday_metrics (user_id, time, type, value)
                VALUES (%s, %s, %s, %s);
                """
                cursor.execute(insert_query, (user_id, timestamp, metric_type, value))
                connection.commit()
                print(f"Métrica intradía {metric_type} para usuario {user_id} guardada exitosamente.")
        except Exception as e:
            print(f"Error al guardar la métrica intradía: {e}")
            connection.rollback()
        finally:
            connection.close()

def insert_sleep_log(user_id, start_time, end_time, **data):
    """
    Inserta un registro de sueño en la tabla sleep_logs.
    
    Args:
        user_id (int): ID del usuario.
        start_time (datetime): Hora de inicio del sueño.
        end_time (datetime): Hora de fin del sueño.
        data (dict): Diccionario con los datos de sueño.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                insert_query = """
                INSERT INTO sleep_logs (
                    user_id, start_time, end_time, duration_ms,
                    efficiency, minutes_asleep, minutes_awake,
                    minutes_in_rem, minutes_in_light, minutes_in_deep
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                );
                """
                cursor.execute(insert_query, (
                    user_id, start_time, end_time,
                    data.get("duration_ms"),
                    data.get("efficiency"),
                    data.get("minutes_asleep"),
                    data.get("minutes_awake"),
                    data.get("minutes_in_rem"),
                    data.get("minutes_in_light"),
                    data.get("minutes_in_deep")
                ))
                connection.commit()
                print(f"Registro de sueño para usuario {user_id} guardado exitosamente.")
        except Exception as e:
            print(f"Error al guardar el registro de sueño: {e}")
            connection.rollback()
        finally:
            connection.close()

def get_daily_summaries(user_id, start_date=None, end_date=None):
    """
    Obtiene los resúmenes diarios de un usuario en un rango de fechas.
    
    Args:
        user_id (int): ID del usuario.
        start_date (str, optional): Fecha de inicio (YYYY-MM-DD).
        end_date (str, optional): Fecha de fin (YYYY-MM-DD).
        
    Returns:
        list: Lista de tuplas con los resúmenes diarios.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                query = """
                SELECT * FROM daily_summaries
                WHERE user_id = %s
                """
                params = [user_id]
                
                if start_date:
                    query += " AND date >= %s"
                    params.append(start_date)
                
                if end_date:
                    query += " AND date <= %s"
                    params.append(end_date)
                
                query += " ORDER BY date DESC;"
                
                cursor.execute(query, params)
                summaries = cursor.fetchall()
                return summaries
        except Exception as e:
            print(f"Error al obtener los resúmenes diarios: {e}")
        finally:
            connection.close()
    return []

def get_intraday_metrics(user_id, metric_type, start_time=None, end_time=None):
    """
    Obtiene las métricas intradía de un usuario en un rango de tiempo.
    
    Args:
        user_id (int): ID del usuario.
        metric_type (str): Tipo de métrica ('heart_rate', 'steps', etc.).
        start_time (datetime, optional): Hora de inicio.
        end_time (datetime, optional): Hora de fin.
        
    Returns:
        list: Lista de tuplas con las métricas intradía.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                query = """
                SELECT time, value FROM intraday_metrics
                WHERE user_id = %s AND type = %s
                """
                params = [user_id, metric_type]
                
                if start_time:
                    query += " AND time >= %s"
                    params.append(start_time)
                
                if end_time:
                    query += " AND time <= %s"
                    params.append(end_time)
                
                query += " ORDER BY time;"
                
                cursor.execute(query, params)
                metrics = cursor.fetchall()
                return metrics
        except Exception as e:
            print(f"Error al obtener las métricas intradía: {e}")
        finally:
            connection.close()
    return []

def get_sleep_logs(user_id, start_date=None, end_date=None):
    """
    Obtiene los registros de sueño de un usuario en un rango de fechas.
    
    Args:
        user_id (int): ID del usuario.
        start_date (str, optional): Fecha de inicio (YYYY-MM-DD).
        end_date (str, optional): Fecha de fin (YYYY-MM-DD).
        
    Returns:
        list: Lista de tuplas con los registros de sueño.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                query = """
                SELECT * FROM sleep_logs
                WHERE user_id = %s
                """
                params = [user_id]
                
                if start_date:
                    query += " AND start_time >= %s"
                    params.append(start_date)
                
                if end_date:
                    query += " AND start_time <= %s"
                    params.append(end_date)
                
                query += " ORDER BY start_time DESC;"
                
                cursor.execute(query, params)
                logs = cursor.fetchall()
                return logs
        except Exception as e:
            print(f"Error al obtener los registros de sueño: {e}")
        finally:
            connection.close()
    return []

if __name__ == "__main__":
    # Inicializar la base de datos
    init_db()
    
    # Añadir usuario de prueba
    add_user(
        name="",
        email="Wearable4LivelyAgeign@gmail.com",
        access_token="",
        refresh_token=""
    )
    #run_tests()