from datetime import datetime, timedelta
from db import DatabaseManager, insert_daily_summary, insert_alert, init_db
from alert_rules import evaluate_all_alerts

def create_test_data():
    """Crear datos de prueba y generar alertas"""
    # Primero, asegurarnos de que la base de datos está inicializada
    if not init_db():
        print("Error al inicializar la base de datos")
        return

    db = DatabaseManager()
    if not db.connect():
        print("Error al conectar con la base de datos")
        return

    try:
        # Limpiar datos existentes
        print("\nLimpiando datos existentes...")
        db.execute_query("DELETE FROM alerts")
        db.execute_query("DELETE FROM daily_summaries")
        db.execute_query("DELETE FROM users WHERE email = 'test@example.com'")
        db.commit()

        # Crear un usuario de prueba
        print("\nCreando usuario de prueba...")
        result = db.execute_query("""
            INSERT INTO users (name, email, created_at)
            VALUES ('Usuario Test', 'test@example.com', NOW())
            RETURNING id;
        """)
        
        if not result:
            print("Error: No se pudo crear el usuario de prueba")
            return
            
        user_id = result[0][0]
        print(f"Usuario de prueba creado con ID: {user_id}")
        
        # Fecha base para los datos
        base_date = datetime.now().date()
        
        # Generar datos normales para 6 días previos
        print("\nGenerando datos normales para los últimos 6 días...")
        for i in range(6):
            date = base_date - timedelta(days=i+1)
            print(f"Insertando datos para {date}")
            success = insert_daily_summary(
                user_id=user_id,
                date=date,
                steps=10000,
                heart_rate=70,
                sleep_minutes=480,
                calories=2000,
                distance=8.5,
                floors=10,
                elevation=100.5,
                active_minutes=60,
                sedentary_minutes=300,
                nutrition_calories=1800,
                water=2.5,
                weight=70.5,
                bmi=22.5,
                fat=18.5,
                oxygen_saturation=98.0,
                respiratory_rate=16.5,
                temperature=36.5
            )
            if not success:
                print(f"Error al insertar datos para {date}")
        
        # Generar datos anómalos para el día actual
        print("\nGenerando datos anómalos para el día actual...")
        success = insert_daily_summary(
            user_id=user_id,
            date=base_date,
            steps=2000,  # Caída significativa en pasos
            heart_rate=120,  # Frecuencia cardíaca elevada
            sleep_minutes=300,  # Menos horas de sueño
            calories=1200,
            distance=1.5,
            floors=2,
            elevation=20.5,
            active_minutes=15,  # Menos minutos activos
            sedentary_minutes=800,  # Más tiempo sedentario
            nutrition_calories=1800,
            water=2.0,
            weight=70.5,
            bmi=22.5,
            fat=18.5,
            oxygen_saturation=95.0,
            respiratory_rate=16.5,
            temperature=36.5
        )
        
        if not success:
            print("Error al insertar datos anómalos")
            return
        
        # Evaluar alertas
        print("\nEvaluando alertas...")
        alerts = evaluate_all_alerts(user_id, datetime.now())
        print(f"Alertas generadas: {alerts}")
        
        # Verificar las alertas en la base de datos
        alerts_count = db.execute_query("SELECT COUNT(*) FROM alerts")
        if alerts_count:
            print(f"\nTotal de alertas en la base de datos: {alerts_count[0][0]}")
        
        # Mostrar las alertas generadas
        alerts = db.execute_query("""
            SELECT a.*, u.name, u.email
            FROM alerts a
            JOIN users u ON a.user_id = u.id
            ORDER BY a.alert_time DESC
        """)
        
        if alerts:
            print("\nAlertas generadas:")
            for alert in alerts:
                print(f"- Tipo: {alert[3]}, Prioridad: {alert[4]}, Detalles: {alert[7]}")
        else:
            print("\nNo se encontraron alertas")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_data() 