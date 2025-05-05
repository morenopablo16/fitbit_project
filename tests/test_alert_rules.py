import unittest
from datetime import datetime, timedelta
from alert_rules import (
    check_activity_drop,
    check_sedentary_increase,
    check_sleep_duration_change,
    check_heart_rate_anomaly
)
from db import connect_to_db, insert_daily_summary, reset_database

class TestAlertRules(unittest.TestCase):
    def setUp(self):
        """Configuración inicial para las pruebas"""
        self.user_id = 1  # Asumimos que existe un usuario con ID 1
        self.current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Limpiar datos existentes
        reset_database()
        
        # Asegurarse de que existe el usuario
        conn = connect_to_db()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO users (id, name, email)
                        VALUES (%s, 'Test User', 'test@example.com')
                        ON CONFLICT (id) DO NOTHING
                    """, (self.user_id,))
                    conn.commit()
            finally:
                conn.close()

    def insert_test_data(self, date=None, steps=None, sedentary=None, sleep=None, heart_rate=None):
        """Inserta datos de prueba para un día específico"""
        if date is None:
            date = self.current_date
            
        conn = connect_to_db()
        if conn:
            try:
                with conn.cursor() as cursor:
                    insert_daily_summary(
                        user_id=self.user_id,
                        date=date,
                        steps=steps,
                        sedentary_minutes=sedentary,
                        sleep_minutes=sleep,
                        heart_rate=heart_rate
                    )
                conn.commit()
            finally:
                conn.close()

    def test_activity_drop(self):
        """Prueba la detección de caída de actividad"""
        # Insertar datos normales para 6 días previos
        for i in range(6):
            date = self.current_date - timedelta(days=i+1)
            self.insert_test_data(date=date, steps=10000)  # 10,000 pasos diarios
        
        # Insertar datos del día actual con caída significativa
        self.insert_test_data(date=self.current_date, steps=6000)  # 6,000 pasos (40% de caída)
        
        # Verificar que se detecta la alerta
        self.assertTrue(check_activity_drop(self.user_id, self.current_date))

    def test_sedentary_increase(self):
        """Prueba la detección de aumento de tiempo sedentario"""
        # Insertar datos normales para 2 días previos
        for i in range(2):
            date = self.current_date - timedelta(days=i+1)
            self.insert_test_data(date=date, sedentary=300)  # 5 horas sedentarias
        
        # Insertar datos del día actual con aumento significativo
        self.insert_test_data(date=self.current_date, sedentary=500)  # 8.3 horas sedentarias (67% de aumento)
        
        # Verificar que se detecta la alerta
        self.assertTrue(check_sedentary_increase(self.user_id, self.current_date))

    def test_sleep_duration_change(self):
        """Prueba la detección de cambio en duración del sueño"""
        # Insertar datos normales para 4 días previos
        for i in range(4):
            date = self.current_date - timedelta(days=i+1)
            self.insert_test_data(date=date, sleep=480)  # 8 horas de sueño
        
        # Insertar datos del día actual con cambio significativo
        self.insert_test_data(date=self.current_date, sleep=300)  # 5 horas de sueño (37.5% de reducción)
        
        # Verificar que se detecta la alerta
        self.assertTrue(check_sleep_duration_change(self.user_id, self.current_date))

    def test_heart_rate_anomaly(self):
        """Prueba la detección de anomalías en frecuencia cardíaca"""
        # Insertar datos normales para 6 días previos
        for i in range(6):
            date = self.current_date - timedelta(days=i+1)
            self.insert_test_data(date=date, heart_rate=70)  # 70 bpm
        
        # Insertar datos del día actual con anomalía
        self.insert_test_data(date=self.current_date, heart_rate=90)  # 90 bpm (20 bpm por encima del promedio)
        
        # Verificar que se detecta la alerta
        self.assertTrue(check_heart_rate_anomaly(self.user_id, self.current_date))

    def test_no_alerts_with_normal_data(self):
        """Prueba que no se generan alertas con datos normales"""
        # Insertar datos normales para varios días
        for i in range(7):
            date = self.current_date - timedelta(days=i)
            self.insert_test_data(
                date=date,
                steps=10000,
                sedentary=300,
                sleep=480,
                heart_rate=70
            )
        
        # Verificar que no se generan alertas
        self.assertFalse(check_activity_drop(self.user_id, self.current_date))
        self.assertFalse(check_sedentary_increase(self.user_id, self.current_date))
        self.assertFalse(check_sleep_duration_change(self.user_id, self.current_date))
        self.assertFalse(check_heart_rate_anomaly(self.user_id, self.current_date))

    def test_insufficient_data(self):
        """Prueba el manejo de datos insuficientes"""
        # Insertar solo 2 días de datos
        for i in range(2):
            date = self.current_date - timedelta(days=i)
            self.insert_test_data(date=date, steps=10000)
        
        # Verificar que no se generan alertas por falta de datos
        self.assertFalse(check_activity_drop(self.user_id, self.current_date))

if __name__ == '__main__':
    unittest.main() 