import numpy as np
from datetime import datetime, timedelta
from db import get_daily_summaries, get_intraday_metrics, DatabaseManager

def check_activity_drop(user_id, current_date):
    """Verifica si hay una caída significativa en la actividad física."""
    try:
        # Obtener datos de los últimos 7 días
        start_date = current_date - timedelta(days=7)
        daily_summaries = get_daily_summaries(user_id, start_date, current_date)
        
        if not daily_summaries or len(daily_summaries) < 2:
            return False
            
        # Obtener el promedio de los últimos 7 días (excluyendo hoy)
        previous_days = [s for s in daily_summaries if s[2] < current_date.date()]
        if not previous_days:
            return False
            
        # Calcular promedios solo con valores no nulos y mayores que cero
        valid_steps = [s[3] for s in previous_days if s[3] is not None and s[3] > 0]
        valid_active_minutes = [s[9] for s in previous_days if s[9] is not None and s[9] > 0]
        
        if not valid_steps or not valid_active_minutes:
            return False
            
        avg_steps = sum(valid_steps) / len(valid_steps)
        avg_active_minutes = sum(valid_active_minutes) / len(valid_active_minutes)
        
        # Obtener los valores de hoy
        today_data = next((s for s in daily_summaries if s[2] == current_date.date()), None)
        if not today_data:
            return False
            
        today_steps = today_data[3] or 0
        today_active_minutes = today_data[9] or 0
        
        # Solo generar alertas si hay datos significativos
        if avg_steps < 100 or avg_active_minutes < 5:  # Ignorar si los promedios son muy bajos
            return False
            
        # Calcular porcentajes de caída
        steps_drop = ((avg_steps - today_steps) / avg_steps * 100)
        active_minutes_drop = ((avg_active_minutes - today_active_minutes) / avg_active_minutes * 100)
        
        db = DatabaseManager()
        if not db.connect():
            return False
            
        try:
            # Determinar la prioridad y el mensaje
            if steps_drop > 50 or active_minutes_drop > 50:
                priority = "high"
                details = f"Caída severa en la actividad: {steps_drop:.1f}% menos pasos, {active_minutes_drop:.1f}% menos minutos activos"
                db.insert_alert(
                    user_id=user_id,
                    alert_type="activity_drop",
                    priority=priority,
                    triggering_value=min(steps_drop, active_minutes_drop),
                    threshold="50",
                    timestamp=current_date
                )
                return True
                
            elif steps_drop > 30 or active_minutes_drop > 30:
                priority = "medium"
                details = f"Caída moderada en la actividad: {steps_drop:.1f}% menos pasos, {active_minutes_drop:.1f}% menos minutos activos"
                db.insert_alert(
                    user_id=user_id,
                    alert_type="activity_drop",
                    priority=priority,
                    triggering_value=min(steps_drop, active_minutes_drop),
                    threshold="30",
                    timestamp=current_date
                )
                return True
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error al verificar caída de actividad: {e}")
    return False

def check_sedentary_increase(user_id, current_date):
    """Verifica aumentos en el tiempo sedentario."""
    try:
        # Obtener datos de los últimos 7 días
        start_date = current_date - timedelta(days=7)
        daily_summaries = get_daily_summaries(user_id, start_date, current_date)
        
        if not daily_summaries or len(daily_summaries) < 2:
            print(f"No hay suficientes datos sedentarios para el usuario {user_id} para generar alertas.")
            return False
            
        # Obtener el promedio de los últimos 7 días (excluyendo hoy)
        previous_days = [s for s in daily_summaries if s[2] < current_date.date()]
        if not previous_days:
            print(f"No hay datos históricos de tiempo sedentario para el usuario {user_id} para comparar.")
            return False
            
        # Calcular promedio solo con valores no nulos y mayores que cero
        valid_sedentary = [s[10] for s in previous_days if s[10] is not None and s[10] > 0]
        if not valid_sedentary:
            print(f"No hay datos válidos de tiempo sedentario para el usuario {user_id} para analizar.")
            return False
            
        avg_sedentary = sum(valid_sedentary) / len(valid_sedentary)
        
        # Protección contra promedios muy bajos que podrían causar alertas falsas
        if avg_sedentary < 60:  # Ignorar si el promedio es menor a 1 hora
            print(f"Promedio de tiempo sedentario demasiado bajo ({avg_sedentary} minutos) para generar alertas fiables.")
            return False
            
        # Obtener los valores de hoy
        today_data = next((s for s in daily_summaries if s[2] == current_date.date()), None)
        if not today_data or today_data[10] is None:
            print(f"No hay datos de tiempo sedentario para hoy para el usuario {user_id}.")
            return False
            
        today_sedentary = today_data[10]
        
        # Evitar dividir por cero
        if avg_sedentary == 0:
            print("Error: Promedio de tiempo sedentario es cero, no se puede calcular el aumento porcentual.")
            return False
            
        # Calcular el aumento porcentual
        sedentary_increase = ((today_sedentary - avg_sedentary) / avg_sedentary * 100)
        
        db = DatabaseManager()
        if not db.connect():
            return False
            
        try:
            if sedentary_increase > 50:
                priority = "high"
                threshold = str(avg_sedentary * 1.5)
                details = f"Aumento significativo en tiempo sedentario: +{sedentary_increase:.1f}%"
                db.insert_alert(
                    user_id=user_id,
                    alert_type="sedentary_increase",
                    priority=priority,
                    triggering_value=sedentary_increase,
                    threshold=threshold,
                    timestamp=current_date
                )
                return True
                
            elif sedentary_increase > 30:
                priority = "medium"
                threshold = str(avg_sedentary * 1.3)
                details = f"Aumento moderado en tiempo sedentario: +{sedentary_increase:.1f}%"
                db.insert_alert(
                    user_id=user_id,
                    alert_type="sedentary_increase",
                    priority=priority,
                    triggering_value=sedentary_increase,
                    threshold=threshold,
                    timestamp=current_date
                )
                return True
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error al verificar aumento en tiempo sedentario: {e}")
    return False

def check_sleep_duration_change(user_id, current_date):
    """Verifica cambios significativos en la duración del sueño."""
    try:
        # Obtener datos de los últimos 7 días
        start_date = current_date - timedelta(days=7)
        daily_summaries = get_daily_summaries(user_id, start_date, current_date)
        
        if not daily_summaries or len(daily_summaries) < 2:
            print(f"No hay suficientes datos de sueño para el usuario {user_id} para generar alertas.")
            return False
            
        # Obtener el promedio de los últimos 7 días (excluyendo hoy)
        previous_days = [s for s in daily_summaries if s[2] < current_date.date()]
        if not previous_days:
            print(f"No hay datos históricos de sueño para el usuario {user_id} para comparar.")
            return False
            
        # Calcular promedio solo con valores no nulos y mayores que cero
        valid_sleep = [s[4] for s in previous_days if s[4] is not None and s[4] > 0]
        if not valid_sleep:
            print(f"No hay datos válidos de sueño para el usuario {user_id} para analizar.")
            return False
            
        avg_sleep = sum(valid_sleep) / len(valid_sleep)
        
        # Protección contra promedios muy bajos que podrían causar alertas falsas
        if avg_sleep < 60:  # Ignorar si el promedio es menor a 1 hora
            print(f"Promedio de sueño demasiado bajo ({avg_sleep} minutos) para generar alertas fiables.")
            return False
            
        # Obtener los valores de hoy
        today_data = next((s for s in daily_summaries if s[2] == current_date.date()), None)
        if not today_data or today_data[4] is None:
            print(f"No hay datos de sueño para hoy para el usuario {user_id}.")
            return False
            
        today_sleep = today_data[4]
        
        # Evitar dividir por cero
        if avg_sleep == 0:
            print("Error: Promedio de sueño es cero, no se puede calcular el cambio porcentual.")
            return False
            
        # Calcular el cambio porcentual
        sleep_change = ((today_sleep - avg_sleep) / avg_sleep * 100)
        
        db = DatabaseManager()
        if not db.connect():
            return False
            
        try:
            if abs(sleep_change) > 30:
                priority = "high"
                threshold = f"{avg_sleep*0.7:.0f}-{avg_sleep*1.3:.0f}"
                details = f"Cambio significativo en duración del sueño: {sleep_change:+.1f}%"
                db.insert_alert(
                    user_id=user_id,
                    alert_type="sleep_duration_change",
                    priority=priority,
                    triggering_value=sleep_change,
                    threshold=threshold,
                    timestamp=current_date
                )
                return True
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error al verificar cambios en el sueño: {e}")
    return False

def check_heart_rate_anomaly(user_id, current_date):
    """Verifica anomalías en la frecuencia cardíaca."""
    try:
        # Obtener datos intradía de las últimas 24 horas
        start_time = current_date - timedelta(hours=24)
        heart_rate_data = get_intraday_metrics(user_id, 'heart_rate', start_time, current_date)
        
        if not heart_rate_data:
            return False
            
        # Calcular estadísticas
        values = [hr[1] for hr in heart_rate_data]
        avg_hr = sum(values) / len(values)
        std_dev = (sum((x - avg_hr) ** 2 for x in values) / len(values)) ** 0.5
        
        # Detectar valores atípicos (más de 2 desviaciones estándar)
        anomalies = [hr for hr in heart_rate_data if abs(hr[1] - avg_hr) > 2 * std_dev]
        
        if anomalies:
            # Calcular el porcentaje de lecturas anómalas
            anomaly_percentage = (len(anomalies) / len(heart_rate_data)) * 100
            max_anomaly = max(abs(hr[1] - avg_hr) for hr in anomalies)
            
            db = DatabaseManager()
            if not db.connect():
                return False
                
            try:
                if anomaly_percentage > 20 or max_anomaly > 3 * std_dev:
                    priority = "high"
                    threshold = f"{avg_hr-2*std_dev:.0f}-{avg_hr+2*std_dev:.0f}"
                    details = f"Anomalía severa en frecuencia cardíaca: {anomaly_percentage:.1f}% de lecturas anómalas"
                    db.insert_alert(
                        user_id=user_id,
                        alert_type="heart_rate_anomaly",
                        priority=priority,
                        triggering_value=max_anomaly,
                        threshold=threshold,
                        timestamp=current_date
                    )
                    return True
                    
                elif anomaly_percentage > 10:
                    priority = "medium"
                    threshold = f"{avg_hr-2*std_dev:.0f}-{avg_hr+2*std_dev:.0f}"
                    details = f"Anomalía moderada en frecuencia cardíaca: {anomaly_percentage:.1f}% de lecturas anómalas"
                    db.insert_alert(
                        user_id=user_id,
                        alert_type="heart_rate_anomaly",
                        priority=priority,
                        triggering_value=max_anomaly,
                        threshold=threshold,
                        timestamp=current_date
                    )
                    return True
            finally:
                db.close()
                
    except Exception as e:
        print(f"Error al verificar anomalías en frecuencia cardíaca: {e}")
    return False

def check_data_quality(user_id, current_date):
    """
    Evalúa la calidad de los datos y genera alertas si hay problemas.
    """
    # Obtener datos del día actual
    end_date = current_date
    start_date = current_date - timedelta(days=1)
    summaries = get_daily_summaries(user_id, start_date, end_date)
    
    if not summaries:
        return False
        
    current_data = summaries[-1]
    alerts_generated = False
    
    db = DatabaseManager()
    if not db.connect():
        return False
        
    try:
        # Verificar valores imposibles o faltantes
        checks = [
            (current_data[3], 'steps', 0, 50000),  # pasos
            (current_data[4], 'heart_rate', 30, 200),  # frecuencia cardíaca
            (current_data[5], 'sleep_minutes', 0, 1440),  # minutos de sueño
            (current_data[10], 'sedentary_minutes', 0, 1440),  # minutos sedentarios
            (current_data[16], 'oxygen_saturation', 80, 100),  # saturación de oxígeno
        ]
        
        for value, metric, min_val, max_val in checks:
            if value is None:
                # Generar alertas para datos faltantes críticos
                if metric in ['heart_rate', 'steps', 'sleep_minutes']:
                    db.insert_alert(
                        user_id=user_id,
                        alert_type='data_quality',
                        priority='medium',
                        triggering_value=None,
                        threshold=None,
                        timestamp=current_date
                    )
                    alerts_generated = True
            elif value < min_val or value > max_val:
                db.insert_alert(
                    user_id=user_id,
                    alert_type='data_quality',
                    priority='high' if metric in ['heart_rate', 'oxygen_saturation'] else 'medium',
                    triggering_value=value,
                    threshold=f"{min_val}-{max_val}",
                    timestamp=current_date
                )
                alerts_generated = True
    finally:
        db.close()
    
    return alerts_generated

def check_intraday_anomalies(user_id, current_date):
    """
    Detecta anomalías en datos intradía usando la tabla intraday_metrics.
    """
    # Obtener datos de las últimas 24 horas
    end_time = current_date
    start_time = current_date - timedelta(hours=24)
    
    # Tipos de métricas a verificar
    metric_types = ['heart_rate', 'steps', 'active_zone_minutes', 'calories']
    alerts_generated = False
    
    db = DatabaseManager()
    if not db.connect():
        return False
        
    try:
        for metric_type in metric_types:
            metrics = get_intraday_metrics(user_id, metric_type, start_time, end_time)
            
            if not metrics or len(metrics) < 10:  # Necesitamos suficientes datos
                continue
                
            values = [m[1] for m in metrics if m[1] is not None]  # m[1] es el valor
            
            if len(values) < 10:
                continue
                
            mean_value = float(np.mean(values))
            std_value = float(np.std(values))
            
            # Detectar valores fuera de 2 desviaciones estándar
            threshold_high = mean_value + 2 * std_value
            threshold_low = mean_value - 2 * std_value
            
            anomalies = [v for v in values if v > threshold_high or v < threshold_low]
            
            if anomalies:
                # Determinar la prioridad basada en la severidad de la anomalía
                priority = 'high' if any(v > threshold_high * 1.2 or v < threshold_low * 0.8 for v in anomalies) else 'medium'
                
                # Crear mensaje descriptivo
                if metric_type == 'heart_rate':
                    message = f'Anomalía en frecuencia cardíaca: {anomalies[-1]} bpm (rango normal: {threshold_low:.0f}-{threshold_high:.0f})'
                elif metric_type == 'steps':
                    message = f'Anomalía en pasos: {anomalies[-1]} pasos (rango normal: {threshold_low:.0f}-{threshold_high:.0f})'
                elif metric_type == 'active_zone_minutes':
                    message = f'Anomalía en minutos activos: {anomalies[-1]} minutos (rango normal: {threshold_low:.0f}-{threshold_high:.0f})'
                else:
                    message = f'Anomalía en {metric_type}: {anomalies[-1]} (rango normal: {threshold_low:.0f}-{threshold_high:.0f})'
                
                db.insert_alert(
                    user_id=user_id,
                    alert_type=f'{metric_type}_anomaly',
                    priority=priority,
                    triggering_value=float(anomalies[-1]),
                    threshold=f"{threshold_low:.0f}-{threshold_high:.0f}",
                    timestamp=current_date
                )
                alerts_generated = True
    finally:
        db.close()
    
    return alerts_generated

def evaluate_all_alerts(user_id, current_date):
    """Evalúa todas las reglas de alerta para un usuario."""
    try:
        alerts_triggered = False
        
        # Verificar caída en actividad física
        if check_activity_drop(user_id, current_date):
            alerts_triggered = True
            
        # Verificar anomalías en frecuencia cardíaca
        if check_heart_rate_anomaly(user_id, current_date):
            alerts_triggered = True
            
        # Verificar cambios en el sueño
        if check_sleep_duration_change(user_id, current_date):
            alerts_triggered = True
            
        # Verificar aumento en tiempo sedentario
        if check_sedentary_increase(user_id, current_date):
            alerts_triggered = True
            
        return alerts_triggered
        
    except Exception as e:
        print(f"Error al evaluar alertas: {e}")
        return False 