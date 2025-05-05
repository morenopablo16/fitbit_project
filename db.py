import psycopg2
from psycopg2 import sql
from config import DB_CONFIG
from encryption import encrypt_token, decrypt_token
import random
from datetime import datetime, timedelta

class DatabaseManager:
    def __init__(self):
        self.connection = None

    def connect(self):
        """Establece la conexión con la base de datos."""
        try:
            self.connection = psycopg2.connect(
                host=DB_CONFIG["host"],
                database=DB_CONFIG["database"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                port=DB_CONFIG["port"],
                sslmode=DB_CONFIG["sslmode"]
            )
            return True
        except Exception as e:
            print(f"Error al conectar a la base de datos: {e}")
            return False

    def close(self):
        """Cierra la conexión con la base de datos."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute_query(self, query, params=None):
        """Ejecuta una consulta y retorna los resultados."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                if cursor.description:  # Si la consulta retorna resultados
                    return cursor.fetchall()
                self.connection.commit()
                return True
        except Exception as e:
            print(f"Error al ejecutar consulta: {e}")
            self.connection.rollback()
            return None

    def get_user_by_email(self, email):
        """Obtiene un usuario por su email."""
        query = """
            SELECT id, name, email, access_token, refresh_token 
            FROM users 
            WHERE email = %s 
            ORDER BY created_at DESC 
            LIMIT 1
        """
        result = self.execute_query(query, (email,))
        return result[0] if result else None

    def add_user(self, name, email, access_token=None, refresh_token=None):
        """Añade un nuevo usuario a la base de datos."""
        if access_token and refresh_token:
            encrypted_access_token = encrypt_token(access_token)
            encrypted_refresh_token = encrypt_token(refresh_token)
        else:
            encrypted_access_token = None
            encrypted_refresh_token = None

        query = """
            INSERT INTO users (name, email, access_token, refresh_token)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """
        result = self.execute_query(query, (name, email, encrypted_access_token, encrypted_refresh_token))
        return result[0][0] if result else None

    def get_daily_summaries(self, user_id, start_date=None, end_date=None):
        """Obtiene los resúmenes diarios de un usuario."""
        query = """
            SELECT * FROM daily_summaries 
            WHERE user_id = %s
        """
        params = [user_id]
        
        if start_date:
            query += " AND date >= %s"
            params.append(start_date.date())
        if end_date:
            query += " AND date <= %s"
            params.append(end_date.date())
            
        query += " ORDER BY date ASC"
        
        return self.execute_query(query, params)

    def get_intraday_metrics(self, user_id, metric_type, start_time=None, end_time=None):
        """Obtiene las métricas intradía de un usuario."""
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
        
        query += " ORDER BY time"
        
        return self.execute_query(query, params)

    def get_sleep_logs(self, user_id, start_date=None, end_date=None):
        """Obtiene los registros de sueño de un usuario."""
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
        
        query += " ORDER BY start_time DESC"
        
        return self.execute_query(query, params)

    def get_user_alerts(self, user_id, start_time=None, end_time=None, acknowledged=None):
        """Obtiene las alertas de un usuario."""
        query = """
            SELECT * FROM alerts
            WHERE user_id = %s
        """
        params = [user_id]

        if start_time:
            query += " AND alert_time >= %s"
            params.append(start_time)
        if end_time:
            query += " AND alert_time <= %s"
            params.append(end_time)
        if acknowledged is not None:
            query += " AND acknowledged = %s"
            params.append(acknowledged)

        query += " ORDER BY alert_time DESC"
        
        return self.execute_query(query, params)

    def insert_alert(self, user_id, alert_type, priority, triggering_value=None, threshold_value=None, details=None):
        """Inserta una nueva alerta."""
        query = """
            INSERT INTO alerts (
                user_id, alert_type, priority,
                triggering_value, threshold_value, details
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        return self.execute_query(query, (
            user_id, alert_type, priority,
            triggering_value, threshold_value, details
        ))

    def update_user_tokens(self, email, access_token, refresh_token):
        """Actualiza los tokens de un usuario."""
        encrypted_access_token = encrypt_token(access_token)
        encrypted_refresh_token = encrypt_token(refresh_token)
        
        query = """
            UPDATE users
            SET access_token = %s, refresh_token = %s
            WHERE email = %s
        """
        return self.execute_query(query, (encrypted_access_token, encrypted_refresh_token, email))

# Función de conveniencia para mantener compatibilidad con el código existente
def connect_to_db():
    """Función de conveniencia para mantener compatibilidad con el código existente."""
    db = DatabaseManager()
    if db.connect():
        return db
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

                # Crear tabla de registros de sueño
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sleep_logs (
                        id SERIAL,
                        user_id INTEGER REFERENCES users(id),
                        start_time TIMESTAMPTZ NOT NULL,
                        end_time TIMESTAMPTZ NOT NULL,
                        duration_ms INTEGER,
                        efficiency INTEGER,
                        minutes_asleep INTEGER,
                        minutes_awake INTEGER,
                        minutes_in_rem INTEGER,
                        minutes_in_light INTEGER,
                        minutes_in_deep INTEGER
                    );
                """)
                
                # Convertir a hipertabla
                cursor.execute("""
                    SELECT create_hypertable('sleep_logs', 'start_time',
                        if_not_exists => TRUE,
                        migrate_data => TRUE
                    );
                """)

                # Crear tabla de alertas
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS alerts (
                        id SERIAL,
                        alert_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        user_id INTEGER REFERENCES users(id),
                        alert_type VARCHAR(100) NOT NULL,
                        priority VARCHAR(20) NOT NULL,
                        triggering_value DOUBLE PRECISION,
                        threshold_value DOUBLE PRECISION,
                        details TEXT,
                        acknowledged BOOLEAN DEFAULT FALSE,
                        PRIMARY KEY (id, alert_time)
                    );
                """)
                
                # Convertir a hipertabla
                cursor.execute("""
                    SELECT create_hypertable('alerts', 'alert_time',
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
    Ejecuta pruebas de inserción y consulta para verificar el funcionamiento de la base de datos.
    Incluye casos de prueba para:
    - Datos normales
    - Caídas que generan alertas
    - Datos erróneos o faltantes
    - Datos inconsistentes
    """
    print("\n=== Iniciando pruebas con datos simulados ===\n")

    # Caso 1: Usuario con datos normales iniciales
    print("1. Creando usuario con datos normales...")
    user_id_1 = add_user(
        name="Juan Pérez",
        email="juan@example.com",
        access_token="token_juan",
        refresh_token="refresh_juan"
    )

    # Insertar 5 días de datos normales
    from datetime import datetime, timedelta
    base_date = datetime.now().date()
    
    print("\n2. Insertando datos normales para los primeros 5 días...")
    for i in range(5):
        date = (base_date - timedelta(days=i)).strftime("%Y-%m-%d")
        save_to_db(
            user_id=user_id_1,
            date=date,
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

    # Caso 2: Caída significativa en actividad física
    print("\n3. Simulando caída en actividad física...")
    date = (base_date + timedelta(days=1)).strftime("%Y-%m-%d")
    save_to_db(
        user_id=user_id_1,
        date=date,
        steps=2000,  # Caída significativa en pasos (80% menos)
        heart_rate=90,  # Aumento en frecuencia cardíaca
        sleep_minutes=420,
        calories=1200,
        distance=1.5,
        floors=2,
        elevation=20.5,
        active_minutes=15,  # Reducción significativa en minutos activos
        sedentary_minutes=900,  # Aumento significativo en tiempo sedentario
        nutrition_calories=1800,
        water=2.0,
        weight=70.5,
        bmi=22.5,
        fat=18.5,
        oxygen_saturation=95.0,
        respiratory_rate=16.5,
        temperature=36.5
    )

    # Caso 3: Datos erróneos o faltantes
    print("\n4. Insertando datos con errores y valores faltantes...")
    date = (base_date + timedelta(days=2)).strftime("%Y-%m-%d")
    save_to_db(
        user_id=user_id_1,
        date=date,
        steps=None,  # Datos faltantes de pasos
        heart_rate=None,  # Datos faltantes de frecuencia cardíaca
        sleep_minutes=None,  # Datos faltantes de sueño
        calories=None,
        distance=None,
        floors=None,
        elevation=None,
        active_minutes=None,
        sedentary_minutes=None,
        nutrition_calories=None,
        water=None,
        weight=None,
        bmi=None,
        fat=None,
        oxygen_saturation=None,
        respiratory_rate=None,
        temperature=None
    )

    # Caso 4: Datos inconsistentes
    print("\n5. Insertando datos inconsistentes...")
    date = (base_date + timedelta(days=3)).strftime("%Y-%m-%d")
    save_to_db(
        user_id=user_id_1,
        date=date,
        steps=15000,  # Alto número de pasos
        heart_rate=95,  # Frecuencia cardíaca elevada
        sleep_minutes=480,
        calories=1200,  # Calorías bajas para la actividad
        distance=2.0,   # Distancia baja para los pasos
        floors=25,      # Número alto de pisos
        elevation=250.5,
        active_minutes=30,  # Minutos activos bajos para los pasos
        sedentary_minutes=600,
        nutrition_calories=3500,  # Calorías de nutrición muy altas
        water=1.0,
        weight=70.5,
        bmi=22.5,
        fat=18.5,
        oxygen_saturation=92.0,  # Saturación de oxígeno ligeramente baja
        respiratory_rate=16.5,
        temperature=36.5
    )

    print("\n6. Evaluando alertas para el usuario...")
    from alert_rules import evaluate_all_alerts
    alerts = evaluate_all_alerts(user_id_1, datetime.now())
    print(f"Alertas generadas: {alerts}")

    print("\n=== Pruebas completadas ===\n")

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
    Inserta un registro de sueño en la base de datos.

    Args:
        user_id (int): ID del usuario.
        start_time (datetime): Hora de inicio del sueño.
        end_time (datetime): Hora de fin del sueño.
        data (dict): Datos adicionales del sueño.
    """
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO sleep_logs (
                        user_id, start_time, end_time, duration_ms,
                        efficiency, minutes_asleep, minutes_awake,
                        minutes_in_rem, minutes_in_light, minutes_in_deep
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id, start_time, end_time,
                    data.get('duration_ms'),
                    data.get('efficiency'),
                    data.get('minutes_asleep'),
                    data.get('minutes_awake'),
                    data.get('minutes_in_rem'),
                    data.get('minutes_in_light'),
                    data.get('minutes_in_deep')
                ))
                conn.commit()
                print(f"Registro de sueño insertado para usuario {user_id}")
        except Exception as e:
            print(f"Error al insertar registro de sueño: {e}")
            conn.rollback()
        finally:
            conn.close()

def insert_alert(user_id, alert_type, priority, triggering_value=None, threshold_value=None, details=None):
    """
    Inserta una alerta en la base de datos.

    Args:
        user_id (int): ID del usuario.
        alert_type (str): Tipo de alerta (ej. 'activity_drop', 'sleep_duration_change', 'heart_rate_anomaly').
        priority (str): Prioridad de la alerta ('low', 'medium', 'high').
        triggering_value (float, optional): Valor que disparó la alerta.
        threshold_value (float, optional): Umbral que se superó/no se alcanzó.
        details (str, optional): Detalles adicionales de la alerta.
    """
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO alerts (
                        user_id, alert_type, priority,
                        triggering_value, threshold_value, details
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    user_id, alert_type, priority,
                    triggering_value, threshold_value, details
                ))
                conn.commit()
                print(f"Alerta {alert_type} insertada para usuario {user_id}")
        except Exception as e:
            print(f"Error al insertar alerta: {e}")
            conn.rollback()
        finally:
            conn.close()

def get_user_alerts(user_id, start_time=None, end_time=None, acknowledged=None):
    """
    Obtiene las alertas de un usuario.

    Args:
        user_id (int): ID del usuario.
        start_time (datetime, optional): Fecha de inicio para filtrar alertas.
        end_time (datetime, optional): Fecha de fin para filtrar alertas.
        acknowledged (bool, optional): Filtrar por estado de reconocimiento.

    Returns:
        list: Lista de alertas del usuario.
    """
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT * FROM alerts
                    WHERE user_id = %s
                """
                params = [user_id]

                if start_time:
                    query += " AND alert_time >= %s"
                    params.append(start_time)
                if end_time:
                    query += " AND alert_time <= %s"
                    params.append(end_time)
                if acknowledged is not None:
                    query += " AND acknowledged = %s"
                    params.append(acknowledged)

                query += " ORDER BY alert_time DESC"
                cursor.execute(query, params)
                alerts = cursor.fetchall()
                return alerts
        except Exception as e:
            print(f"Error al obtener alertas: {e}")
        finally:
            conn.close()
    return []

def get_daily_summaries(user_id, start_date=None, end_date=None):
    """
    Obtiene los resúmenes diarios de un usuario en un rango de fechas.
    
    Args:
        user_id (int): ID del usuario
        start_date (datetime): Fecha de inicio (inclusive)
        end_date (datetime): Fecha de fin (inclusive)
        
    Returns:
        list: Lista de tuplas con los datos diarios, ordenados por fecha
    """
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT * FROM daily_summaries 
                    WHERE user_id = %s
                """
                params = [user_id]
                
                if start_date:
                    query += " AND date >= %s"
                    params.append(start_date.date())
                if end_date:
                    query += " AND date <= %s"
                    params.append(end_date.date())
                    
                query += " ORDER BY date ASC"
                
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            print(f"Error al obtener resúmenes diarios: {e}")
        finally:
            conn.close()
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

def reset_database():
    """
    Resets the database by dropping all tables and recreating them.
    """
    connection = connect_to_db()
    if connection:
        try:
            with connection.cursor() as cursor:
                # Drop all tables in the correct order to handle foreign key constraints
                cursor.execute("DROP TABLE IF EXISTS sleep_logs CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS intraday_metrics CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS daily_summaries CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS users CASCADE;")
                
                connection.commit()
                print("Database tables dropped successfully.")
                
                # Reinitialize the database
                init_db()
                print("Database reinitialized successfully.")
                
                # Add the test user
                add_user(
                    name="",
                    email="Wearable4LivelyAgeign@gmail.com",
                    access_token="",
                    refresh_token=""
                )
                print("Test user added successfully.")
                
        except Exception as e:
            print(f"Error resetting database: {e}")
            connection.rollback()
        finally:
            connection.close()

def create_test_data():
    """Create test data for development and testing purposes."""
    conn = connect_to_db()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            print("Clearing existing test data...")
            # Clear existing test data
            cur.execute("DELETE FROM alerts")
            cur.execute("DELETE FROM daily_summaries")
            cur.execute("DELETE FROM intraday_metrics")
            cur.execute("DELETE FROM sleep_logs")
            cur.execute("DELETE FROM users")

            print("Adding test users...")
            # Add test users
            cur.execute("""
                INSERT INTO users (name, email, access_token, refresh_token, created_at)
                VALUES 
                    ('Test User 1', 'test1@example.com', 'test_token_1', 'test_refresh_1', NOW()),
                    ('Test User 2', 'test2@example.com', 'test_token_2', 'test_refresh_2', NOW()),
                    ('Test User 3', 'test3@example.com', 'test_token_3', 'test_refresh_3', NOW())
                RETURNING id
            """)
            user_ids = [row[0] for row in cur.fetchall()]

            print("Generating test data for the last 7 days...")
            # Generate test data for the last 7 days instead of 30
            base_date = datetime.now().date()
            for user_id in user_ids:
                for i in range(7):  # Changed from 30 to 7 days
                    date = base_date - timedelta(days=i)
                    print(f"Generating data for user {user_id}, date {date}")
                    
                    # Generate daily summary with varying patterns
                    steps = random.randint(5000, 15000)
                    heart_rate = random.randint(60, 100)
                    sleep_minutes = random.randint(360, 540)  # 6-9 hours
                    calories = random.randint(1800, 2500)
                    distance = round(random.uniform(3.0, 8.0), 2)
                    floors = random.randint(5, 20)
                    elevation = random.randint(100, 500)
                    active_minutes = random.randint(30, 120)
                    sedentary_minutes = random.randint(300, 600)
                    
                    # Add some anomalies for testing alerts
                    if i == 0:  # Today
                        steps = 2000  # Low steps for activity drop alert
                        heart_rate = 120  # High heart rate for anomaly
                        sleep_minutes = 300  # Low sleep for pattern change
                        sedentary_minutes = 800  # High sedentary time
                    elif i == 1:  # Yesterday
                        steps = 15000  # High steps for comparison
                        heart_rate = 65  # Normal heart rate
                        sleep_minutes = 480  # Normal sleep
                        sedentary_minutes = 400  # Normal sedentary time
                    
                    cur.execute("""
                        INSERT INTO daily_summaries 
                        (user_id, date, steps, heart_rate, sleep_minutes, calories, 
                         distance, floors, elevation, active_minutes, sedentary_minutes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (user_id, date, steps, heart_rate, sleep_minutes, calories, 
                          distance, floors, elevation, active_minutes, sedentary_minutes))

                    print(f"  - Added daily summary for {date}")
                    
                    # Generate intraday metrics for each hour (only for today and yesterday)
                    if i <= 1:  # Only generate for today and yesterday
                        print(f"  - Adding hourly metrics for {date}")
                        for hour in range(24):
                            time = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour)
                            
                            # Generate different types of metrics
                            # Steps
                            cur.execute("""
                                INSERT INTO intraday_metrics (user_id, time, type, value)
                                VALUES (%s, %s, 'steps', %s)
                            """, (user_id, time, random.randint(100, 1000)))
                            
                            # Heart rate with some anomalies
                            hr_value = random.randint(60, 100)
                            if hour == 12:  # Midday anomaly
                                hr_value = random.randint(120, 150)
                            cur.execute("""
                                INSERT INTO intraday_metrics (user_id, time, type, value)
                                VALUES (%s, %s, 'heart_rate', %s)
                            """, (user_id, time, hr_value))
                            
                            # Activity level (0: sedentary, 1: light, 2: moderate, 3: intense)
                            activity_value = random.randint(0, 3)
                            cur.execute("""
                                INSERT INTO intraday_metrics (user_id, time, type, value)
                                VALUES (%s, %s, 'activity_level', %s)
                            """, (user_id, time, activity_value))
                            
                            # Calories
                            cur.execute("""
                                INSERT INTO intraday_metrics (user_id, time, type, value)
                                VALUES (%s, %s, 'calories', %s)
                            """, (user_id, time, random.randint(50, 200)))

                    # Generate sleep logs
                    print(f"  - Adding sleep data for {date}")
                    sleep_start = datetime.combine(date, datetime.min.time()) + timedelta(hours=22)
                    sleep_end = sleep_start + timedelta(minutes=sleep_minutes)
                    
                    cur.execute("""
                        INSERT INTO sleep_logs 
                        (user_id, start_time, end_time, duration_ms, efficiency, 
                         minutes_asleep, minutes_awake, minutes_in_rem, minutes_in_light, minutes_in_deep)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (user_id, sleep_start, sleep_end, 
                          sleep_minutes * 60000,  # duration_ms (convert minutes to milliseconds)
                          random.randint(80, 95),  # efficiency
                          sleep_minutes - random.randint(30, 60),  # minutes_asleep
                          random.randint(20, 40),  # minutes_awake
                          random.randint(60, 120),  # minutes_in_rem
                          random.randint(120, 240),  # minutes_in_light
                          random.randint(60, 120)))  # minutes_in_deep

            print("Generating test alerts...")
            # Generate test alerts for various scenarios
            alert_types = [
                ('activity_drop', 'high', 'Significant drop in daily steps detected'),
                ('heart_rate_anomaly', 'high', 'Abnormal heart rate detected'),
                ('sleep_duration_change', 'medium', 'Unusual sleep duration detected'),
                ('sedentary_increase', 'medium', 'Increased sedentary time detected'),
                ('data_quality', 'low', 'Missing data points detected')
            ]

            for user_id in user_ids:
                for alert_type, priority, message in alert_types:
                    cur.execute("""
                        INSERT INTO alerts 
                        (user_id, alert_time, alert_type, priority, details)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (user_id, datetime.now(), alert_type, priority, message))

            conn.commit()
            print("Test data generation completed successfully!")
            return True

    except Exception as e:
        print(f"Error creating test data: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    # Reset and reinitialize the database
    reset_database()
    # Create test data
    create_test_data()