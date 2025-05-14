import unittest
from datetime import datetime, timedelta
from db import DatabaseManager, insert_daily_summary, init_db, insert_intraday_metric
from alert_rules import evaluate_all_alerts

class TestAllAlertTypes(unittest.TestCase):
    def setUp(self):
        # Inicializar la base de datos y limpiar datos
        init_db()
        self.db = DatabaseManager()
        self.db.connect()
        # Borrar primero las tablas hijas para evitar errores de integridad referencial
        self.db.execute_query("DELETE FROM intraday_metrics")
        self.db.execute_query("DELETE FROM alerts")
        self.db.execute_query("DELETE FROM daily_summaries")
        self.db.execute_query("DELETE FROM users WHERE email = 'test@example.com'")
        self.db.commit()
        # Crear usuario de prueba
        result = self.db.execute_query("""
            INSERT INTO users (name, email, created_at)
            VALUES ('Usuario Test', 'test@example.com', NOW())
            RETURNING id;
        """)
        self.user_id = result[0][0]
        self.base_date = datetime.now().date()

    def tearDown(self):
        self.db.close()

    def test_all_alerts(self):
        print("\n[TEST] Insertando datos normales para 6 días previos (espera: NO alertas)")
        for i in range(6):
            date = self.base_date - timedelta(days=i+1)
            print(f"  Día {date}: 10000 pasos, 800 min sedentario, 70 bpm, 480 min sueño")
            insert_daily_summary(
                user_id=self.user_id,
                date=date,
                steps=10000,
                heart_rate=70,
                sleep_minutes=480,
                calories=2000,
                distance=8.5,
                floors=10,
                elevation=100.5,
                active_minutes=60,
                sedentary_minutes=800,  # 13.3 horas para asegurar alerta de sedentarismo
                nutrition_calories=1800,
                water=2.5,
                weight=70.5,
                bmi=22.5,
                fat=18.5,
                oxygen_saturation=98.0,
                respiratory_rate=16.5,
                temperature=36.5
            )
        print("\n[TEST] Insertando día anómalo (espera: activity_drop, sedentary_increase, sleep_duration_change, heart_rate_anomaly, data_quality fuera de rango)")
        insert_daily_summary(
            user_id=self.user_id,
            date=self.base_date,
            steps=2000,  # Caída significativa en pasos
            heart_rate=120,  # Frecuencia cardíaca elevada
            sleep_minutes=300,  # Menos horas de sueño
            calories=1200,
            distance=1.5,
            floors=2,
            elevation=20.5,
            active_minutes=15,  # Menos minutos activos
            sedentary_minutes=1200,  # Mucho más tiempo sedentario
            nutrition_calories=1800,
            water=2.0,
            weight=70.5,
            bmi=22.5,
            fat=18.5,
            oxygen_saturation=75.0,  # Valor fuera de rango para calidad de datos
            respiratory_rate=16.5,
            temperature=36.5
        )
        print("[TEST] Insertando datos intradía anómalos para heart_rate (espera: heart_rate_anomaly)")
        for h in range(24):
            t = datetime.combine(self.base_date, datetime.min.time()) + timedelta(hours=h)
            value = 70 if h < 20 else 150  # Últimas 4 horas anómalas
            insert_intraday_metric(self.user_id, t, 'heart_rate', value)
        print("[TEST] Insertando día con datos faltantes (espera: data_quality por faltantes)")
        insert_daily_summary(
            user_id=self.user_id,
            date=self.base_date + timedelta(days=1),
            steps=None,  # Faltante
            heart_rate=None,  # Faltante
            sleep_minutes=None,  # Faltante
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
        print("[TEST] Insertando datos intradía de pasos para el día anómalo (espera: gráfica de pasos en activity_drop)")
        for h in range(24):
            t = datetime.combine(self.base_date, datetime.min.time()) + timedelta(hours=h)
            value = 800 if h < 20 else 0  # 20 horas normales, 4 horas con caída total
            insert_intraday_metric(self.user_id, t, 'steps', value)
        print("[TEST] Evaluando alertas para día anómalo (espera: activity_drop, sedentary_increase, sleep_duration_change, heart_rate_anomaly, data_quality fuera de rango)")
        evaluate_all_alerts(self.user_id, datetime.combine(self.base_date, datetime.min.time()))
        print("[TEST] Evaluando alertas para día con datos faltantes (espera: data_quality por faltantes)")
        evaluate_all_alerts(self.user_id, datetime.combine(self.base_date + timedelta(days=1), datetime.min.time()))
        alerts = self.db.execute_query(
            "SELECT alert_type, alert_time FROM alerts WHERE user_id = %s ORDER BY alert_time DESC",
            (self.user_id,)
        )
        print("\n[RESULTADO] Alertas generadas (tipo, fecha):")
        for a in alerts:
            print(f"- {a[0]} | {a[1]}")
        tipos_alerta = set(a[0] for a in alerts)
        esperado = {'activity_drop', 'sedentary_increase', 'sleep_duration_change', 'heart_rate_anomaly', 'data_quality'}
        for tipo in esperado:
            print(f"[CHECK] Comprobando alerta: {tipo}")
            self.assertIn(tipo, tipos_alerta, f"FALTA alerta de tipo: {tipo}")
        print("\n¡Todas las alertas esperadas fueron generadas correctamente!")
        print(f"Alertas generadas: {tipos_alerta}")
        print("[TEST] Insertando datos intradía de pasos con intervalo largo de inactividad (espera: alerta intraday_activity_drop)")
        for h in range(24):
            t = datetime.combine(self.base_date, datetime.min.time()) + timedelta(hours=h)
            if 8 <= h < 12:
                value = 0  # 4 horas de inactividad
            else:
                value = 500
            insert_intraday_metric(self.user_id, t, 'steps', value)
        print("[TEST] Evaluando alertas para caídas de actividad intradía (espera: intraday_activity_drop)")
        evaluate_all_alerts(self.user_id, datetime.combine(self.base_date, datetime.min.time()))
        alerts = self.db.execute_query(
            "SELECT alert_type, details, priority, alert_time FROM alerts WHERE user_id = %s ORDER BY alert_time DESC",
            (self.user_id,)
        )
        print("\n[RESULTADO] Alertas generadas (tipo, detalles, prioridad, hora):")
        for a in alerts:
            print(f"- {a[0]} | {a[1]} | {a[2]} | {a[3]}")
        tipos_alerta = set(a[0] for a in alerts)
        self.assertIn('intraday_activity_drop', tipos_alerta, "FALTA alerta de tipo: intraday_activity_drop")
        # Comprobar detalles y prioridad
        intraday_alert = next(a for a in alerts if a[0] == 'intraday_activity_drop')
        self.assertIn('sin pasos entre', intraday_alert[1])
        
        # Verificar que la prioridad sea válida (medium o high, dependiendo de la duración)
        self.assertIn(intraday_alert[2], ['medium', 'high'], 
                      f"La prioridad de intraday_activity_drop debe ser 'medium' o 'high', pero es '{intraday_alert[2]}'")
        
        # Verificar que si la descripción menciona períodos >4h, la prioridad sea 'high'
        if 'períodos >4h' in intraday_alert[1]:
            self.assertEqual(intraday_alert[2], 'high', 
                            "Para períodos >4h de inactividad, la prioridad debe ser 'high'")
        
        print("\n¡Alerta intraday_activity_drop generada y validada correctamente!")

if __name__ == "__main__":
    unittest.main() 