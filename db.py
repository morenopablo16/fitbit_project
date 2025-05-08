import psycopg2
from psycopg2 import sql
from config import DB_CONFIG
from encryption import encrypt_token, decrypt_token
import random
from datetime import datetime, timedelta

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.cursor = None

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
            self.cursor = self.connection.cursor()
            return True
        except Exception as e:
            print(f"Error al conectar a la base de datos: {e}")
            return False

    def close(self):
        """Cierra la conexión con la base de datos."""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
        except Exception as e:
            print(f"Error al cerrar la conexión: {e}")
        finally:
            self.cursor = None
            self.connection = None

    def commit(self):
        """Realiza commit de la transacción actual."""
        if self.connection:
            self.connection.commit()

    def rollback(self):
        """Realiza rollback de la transacción actual."""
        if self.connection:
            self.connection.rollback()

    def execute_query(self, query, params=None):
        """Ejecuta una consulta y retorna los resultados."""
        try:
            self.cursor.execute(query, params or ())
            if self.cursor.description:  # Si la consulta retorna resultados
                result = self.cursor.fetchall()
                self.commit()
                return result
            self.commit()
            return True
        except Exception as e:
            print(f"Error al ejecutar consulta: {e}")
            self.rollback()
            return None

    def execute_many(self, query, params_list):
        """Ejecuta una consulta múltiple veces con diferentes parámetros."""
        try:
            self.cursor.executemany(query, params_list)
            self.commit()
            return True
        except Exception as e:
            print(f"Error al ejecutar consulta múltiple: {e}")
            self.rollback()
            return False

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
        """
        Obtiene los resúmenes diarios de un usuario en un rango de fechas.
        
        Args:
            user_id (int): ID del usuario
            start_date (datetime): Fecha de inicio (inclusive)
            end_date (datetime): Fecha de fin (inclusive)
            
        Returns:
            list: Lista de tuplas con los datos diarios, ordenados por fecha
        """
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
        
        result = self.execute_query(query, params)
        return result if result else []

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
            RETURNING id
        """
        result = self.execute_query(query, (
            user_id, alert_type, priority,
            triggering_value, threshold_value, details
        ))
        
        if result:
            print(f"Alerta {alert_type} insertada para usuario {user_id}")
            return True
        return False

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

    def get_alert_by_id(self, alert_id):
        """Obtiene una alerta específica por su ID"""
        if not self.connect():
            return None
            
        try:
            query = """
                SELECT a.*, u.name as user_name, u.email as user_email
                FROM alerts a
                JOIN users u ON a.user_id = u.id
                WHERE a.id = %s
            """
            result = self.execute_query(query, [alert_id])
            if result and len(result) > 0:
                # Convertir el resultado a un diccionario
                columns = [desc[0] for desc in self.cursor.description]
                alert = dict(zip(columns, result[0]))
                return alert
            return None
        except Exception as e:
            print(f"Error al obtener alerta por ID: {str(e)}")
            return None
        finally:
            self.close()

# Función de conveniencia para mantener compatibilidad con el código existente
def connect_to_db():
    """Función de conveniencia para mantener compatibilidad con el código existente."""
    try:
        connection = psycopg2.connect(
            host=DB_CONFIG["host"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
            sslmode=DB_CONFIG["sslmode"]
        )
        return connection
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

def init_db():
    """
    Inicializa la base de datos creando las tablas si no existen y configurando TimeScaleDB.
    """
    db = DatabaseManager()
    if not db.connect():
        print("Error al conectar a la base de datos")
        return False

    try:
        # Verificar si TimeScaleDB está instalado
        result = db.execute_query("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';")
        if not result:
            print("TimeScaleDB no está instalado. Por favor, instala la extensión primero.")
            print("Visita: https://docs.timescale.com/install/latest/self-hosted/windows/installation/")
            return False
        
        # Enable TimeScaleDB extension
        db.execute_query("CREATE EXTENSION IF NOT EXISTS timescaledb;")
        
        # Crear tabla de usuarios
        db.execute_query("""
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
        db.execute_query("""
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
        db.execute_query("""
            SELECT create_hypertable('daily_summaries', 'date', 
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """)
        
        # Crear tabla de métricas intradía
        db.execute_query("""
            CREATE TABLE IF NOT EXISTS intraday_metrics (
                id SERIAL,
                user_id INTEGER REFERENCES users(id),
                time TIMESTAMPTZ NOT NULL,
                type VARCHAR(50) NOT NULL,
                value FLOAT NOT NULL
            );
        """)
        
        # Convertir a hipertabla
        db.execute_query("""
            SELECT create_hypertable('intraday_metrics', 'time',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """)

        # Crear tabla de registros de sueño
        db.execute_query("""
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
        db.execute_query("""
            SELECT create_hypertable('sleep_logs', 'start_time',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """)

        # Crear tabla de alertas
        db.execute_query("""
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
                acknowledged_at TIMESTAMPTZ,
                acknowledged_by INTEGER REFERENCES users(id),
                PRIMARY KEY (id, alert_time)
            );
        """)
        
        # Convertir a hipertabla
        db.execute_query("""
            SELECT create_hypertable('alerts', 'alert_time',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """)
        
        print("Base de datos inicializada correctamente con TimeScaleDB.")
        return True
                
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
        return False
    finally:
        db.close()

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
    db = DatabaseManager()
    if not db.connect():
        print("Error al conectar a la base de datos")
        return False

    try:
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
        ON CONFLICT (user_id, date) DO UPDATE SET
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
        
        db.execute_query(insert_query, (
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
        
        return True
    except Exception as e:
        print(f"Error al guardar el resumen diario: {e}")
        return False
    finally:
        db.close()

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
    db = DatabaseManager()
    if not db.connect():
        print("Error al conectar a la base de datos")
        return False

    try:
        query = """
            INSERT INTO alerts (
                user_id, alert_type, priority,
                triggering_value, threshold_value, details
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        result = db.execute_query(query, (
            user_id, alert_type, priority,
            triggering_value, threshold_value, details
        ))
        
        if result:
            print(f"Alerta {alert_type} insertada para usuario {user_id}")
            return True
        return False
    except Exception as e:
        print(f"Error al insertar alerta: {e}")
        return False
    finally:
        db.close()

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
    db = DatabaseManager()
    if not db.connect():
        print("Error al conectar a la base de datos")
        return []

    try:
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
        
        result = db.execute_query(query, params)
        return result if result else []
    except Exception as e:
        print(f"Error al obtener resúmenes diarios: {e}")
        return []
    finally:
        db.close()

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
    """Crea datos de prueba para desarrollo"""
    conn = connect_to_db()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO users (name, email, access_token, refresh_token)
                VALUES ('Test User', 'test@example.com', 'test_token', 'test_refresh')
                RETURNING id
            """)
            user_id = cursor.fetchone()[0]
            
            # Fecha de la alerta (hoy)
            alert_date = datetime.now().date()
            
            # Crear datos de actividad para los últimos 7 días
            for i in range(7):
                date = alert_date - timedelta(days=i)
                cursor.execute("""
                    INSERT INTO daily_summaries (
                        user_id, date, steps, heart_rate, sleep_minutes,
                        calories, distance, floors, elevation, active_minutes,
                        sedentary_minutes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, date) DO UPDATE SET
                        steps = EXCLUDED.steps,
                        heart_rate = EXCLUDED.heart_rate,
                        sleep_minutes = EXCLUDED.sleep_minutes,
                        calories = EXCLUDED.calories,
                        distance = EXCLUDED.distance,
                        floors = EXCLUDED.floors,
                        elevation = EXCLUDED.elevation,
                        active_minutes = EXCLUDED.active_minutes,
                        sedentary_minutes = EXCLUDED.sedentary_minutes
                """, (
                    user_id, date,
                    8000 + random.randint(-500, 500),  # steps
                    70 + random.randint(-5, 5),        # heart_rate
                    420 + random.randint(-30, 30),     # sleep_minutes
                    2000 + random.randint(-200, 200),  # calories
                    5.5 + random.uniform(-0.5, 0.5),   # distance
                    10 + random.randint(-2, 2),        # floors
                    100 + random.randint(-10, 10),     # elevation
                    45 + random.randint(-10, 10),      # active_minutes
                    600 + random.randint(-30, 30)      # sedentary_minutes
                ))
                
                # Crear datos intradía SOLO para el día de la alerta (hoy)
                if date == alert_date:
                    for hour in range(24):
                        # Pasos cada hora
                        time = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour)
                        steps = random.randint(0, 1000)
                        cursor.execute("""
                            INSERT INTO intraday_metrics (user_id, time, type, value)
                            VALUES (%s, %s, %s, %s)
                        """, (user_id, time, 'steps', steps))
                        # Frecuencia cardíaca cada hora
                        hr = random.randint(60, 120)
                        cursor.execute("""
                            INSERT INTO intraday_metrics (user_id, time, type, value)
                            VALUES (%s, %s, %s, %s)
                        """, (user_id, time, 'heart_rate', hr))
                        # Calorías cada hora
                        calories = random.randint(50, 200)
                        cursor.execute("""
                            INSERT INTO intraday_metrics (user_id, time, type, value)
                            VALUES (%s, %s, %s, %s)
                        """, (user_id, time, 'calories', calories))
            
            # Crear alertas de prueba para la fecha de hoy
            alert_types = [
                ('activity_drop', 'Bajo nivel de actividad detectado'),
                ('sedentary_increase', 'Aumento significativo en tiempo sedentario'),
                ('sleep_duration_change', 'Cambio significativo en la duración del sueño'),
                ('heart_rate_anomaly', 'Anomalía en la frecuencia cardíaca detectada')
            ]
            for i in range(3):
                alert_time = datetime.combine(alert_date, datetime.min.time()) + timedelta(hours=8*i)
                alert_type, message = random.choice(alert_types)
                cursor.execute("""
                    INSERT INTO alerts (
                        user_id, alert_time, alert_type, priority, details
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    user_id, alert_time, alert_type,
                    random.choice(['low', 'medium', 'high']),
                    message
                ))
            # Alerta de alta prioridad no reconocida para hoy
            cursor.execute("""
                INSERT INTO alerts (
                    user_id, alert_time, alert_type, priority, details, acknowledged
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                user_id, datetime.combine(alert_date, datetime.min.time()) + timedelta(hours=17),
                'heart_rate_anomaly', 'high',
                'Frecuencia cardíaca anormalmente alta',
                False
            ))
            conn.commit()
            print("Datos de prueba creados exitosamente")
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error creando datos de prueba: {str(e)}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    # Reset and reinitialize the database
    reset_database()
    # Create test data
    create_test_data()