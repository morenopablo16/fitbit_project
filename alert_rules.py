import numpy as np
from datetime import datetime, timedelta
from db import get_daily_summaries, get_intraday_metrics, insert_alert

def check_activity_drop(user_id, current_date):
    """
    Evalúa si ha habido una caída significativa en la actividad física.
    
    Args:
        user_id (int): ID del usuario
        current_date (datetime): Fecha actual
        
    Returns:
        bool: True si se detecta una alerta, False en caso contrario
    """
    # Obtener datos de los últimos 7 días
    end_date = current_date
    start_date = current_date - timedelta(days=7)
    summaries = get_daily_summaries(user_id, start_date, end_date)
    
    if not summaries:
        return False
        
    # Extraer pasos diarios, ignorando valores None o negativos
    steps = [s[3] for s in summaries if s[3] is not None and s[3] >= 0]
    
    if len(steps) < 2:  # Necesitamos al menos 2 días de datos
        return False
        
    # Calcular media de los días previos
    current_steps = steps[-1]
    prev_avg = float(np.mean(steps[:-1]))
    
    # Umbral de caída: 25%
    if current_steps < prev_avg * 0.75:
        insert_alert(
            user_id=user_id,
            alert_type='activity_drop',
            priority='high' if current_steps < prev_avg * 0.5 else 'medium',
            triggering_value=float(current_steps),
            threshold_value=float(prev_avg * 0.75),
            details=f'Caída de actividad detectada: {current_steps} pasos vs promedio de {prev_avg:.0f}'
        )
        return True
    return False

def check_sedentary_increase(user_id, current_date):
    """
    Evalúa si ha habido un aumento significativo en el tiempo sedentario.
    
    Args:
        user_id (int): ID del usuario
        current_date (datetime): Fecha actual
        
    Returns:
        bool: True si se detecta una alerta, False en caso contrario
    """
    # Obtener datos de los últimos 3 días
    end_date = current_date
    start_date = current_date - timedelta(days=3)
    summaries = get_daily_summaries(user_id, start_date, end_date)
    
    if not summaries:
        return False
        
    # Extraer minutos sedentarios, ignorando valores None o negativos
    # El índice 11 corresponde a sedentary_minutes en la tabla daily_summaries
    sedentary = [s[11] for s in summaries if s[11] is not None and s[11] >= 0 and s[11] <= 1440]
    
    if len(sedentary) < 2:
        return False
        
    # Calcular media de los días previos
    current_sedentary = sedentary[-1]
    prev_avg = float(np.mean(sedentary[:-1]))
    
    # Umbral de aumento: 30%
    if current_sedentary > prev_avg * 1.3:
        insert_alert(
            user_id=user_id,
            alert_type='sedentary_increase',
            priority='high' if current_sedentary > prev_avg * 1.5 else 'medium',
            triggering_value=float(current_sedentary),
            threshold_value=float(prev_avg * 1.3),
            details=f'Aumento de tiempo sedentario: {current_sedentary} minutos vs promedio de {prev_avg:.0f}'
        )
        return True
    return False

def check_sleep_duration_change(user_id, current_date):
    """
    Evalúa si ha habido un cambio significativo en la duración del sueño.
    
    Args:
        user_id (int): ID del usuario
        current_date (datetime): Fecha actual
        
    Returns:
        bool: True si se detecta una alerta, False en caso contrario
    """
    # Obtener datos de los últimos 5 días
    end_date = current_date
    start_date = current_date - timedelta(days=5)
    summaries = get_daily_summaries(user_id, start_date, end_date)
    
    if not summaries or len(summaries) < 3:
        return False
        
    # Extraer minutos de sueño
    # El índice 5 corresponde a sleep_minutes en la tabla daily_summaries
    sleep = [s[5] for s in summaries if s[5] is not None]
    
    if len(sleep) < 3:
        return False
        
    # Calcular media de los días previos
    prev_avg = float(np.mean(sleep[:-1]))
    current_sleep = sleep[-1]
    
    # Umbral de cambio: 25%
    if abs(current_sleep - prev_avg) > prev_avg * 0.25:
        insert_alert(
            user_id=user_id,
            alert_type='sleep_duration_change',
            priority='medium',
            triggering_value=float(current_sleep),
            threshold_value=float(prev_avg * 1.25 if current_sleep > prev_avg else prev_avg * 0.75),
            details=f'Cambio significativo en duración del sueño: {current_sleep} minutos vs promedio de {prev_avg:.0f}'
        )
        return True
    return False

def check_heart_rate_anomaly(user_id, current_date):
    """
    Evalúa si hay anomalías en la frecuencia cardíaca.
    
    Args:
        user_id (int): ID del usuario
        current_date (datetime): Fecha actual
        
    Returns:
        bool: True si se detecta una alerta, False en caso contrario
    """
    # Obtener datos de los últimos 7 días
    end_date = current_date
    start_date = current_date - timedelta(days=7)
    summaries = get_daily_summaries(user_id, start_date, end_date)
    
    if not summaries:
        return False
        
    # Extraer frecuencia cardíaca, ignorando valores None o fuera de rango
    heart_rates = [s[4] for s in summaries if s[4] is not None and 30 <= s[4] <= 200]  # rango normal de FC
    
    if len(heart_rates) < 2:
        return False
        
    # Calcular media y desviación estándar de los días previos
    current_hr = heart_rates[-1]
    prev_avg = float(np.mean(heart_rates[:-1]))
    prev_std = float(np.std(heart_rates[:-1]))
    
    # Umbral: 1.5 desviaciones estándar
    threshold = 1.5 * prev_std
    if abs(current_hr - prev_avg) > threshold:
        insert_alert(
            user_id=user_id,
            alert_type='heart_rate_anomaly',
            priority='high',
            triggering_value=float(current_hr),
            threshold_value=float(prev_avg + threshold if current_hr > prev_avg else prev_avg - threshold),
            details=f'Anomalía en frecuencia cardíaca: {current_hr} bpm vs promedio de {prev_avg:.0f} ± {prev_std:.0f}'
        )
        return True
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
                insert_alert(
                    user_id=user_id,
                    alert_type='data_quality',
                    priority='medium',
                    triggering_value=None,
                    threshold_value=None,
                    details=f'Datos faltantes para {metric}'
                )
                alerts_generated = True
        elif value < min_val or value > max_val:
            insert_alert(
                user_id=user_id,
                alert_type='data_quality',
                priority='high' if metric in ['heart_rate', 'oxygen_saturation'] else 'medium',
                triggering_value=value,
                threshold_value=f"{min_val}-{max_val}",
                details=f'Valor anormal detectado para {metric}: {value} (rango válido: {min_val}-{max_val})'
            )
            alerts_generated = True
    
    return alerts_generated

def check_intraday_anomalies(user_id, current_date):
    """
    Detecta anomalías en datos intradía usando la tabla intraday_metrics.
    
    Args:
        user_id (int): ID del usuario
        current_date (datetime): Fecha actual
        
    Returns:
        bool: True si se detecta una alerta, False en caso contrario
    """
    # Obtener datos de las últimas 24 horas
    end_time = current_date
    start_time = current_date - timedelta(hours=24)
    
    # Tipos de métricas a verificar
    metric_types = ['heart_rate', 'steps', 'active_zone_minutes', 'calories']
    alerts_generated = False
    
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
            
            insert_alert(
                user_id=user_id,
                alert_type=f'{metric_type}_anomaly',
                priority=priority,
                triggering_value=float(anomalies[-1]),
                threshold_value=float(threshold_high if anomalies[-1] > threshold_high else threshold_low),
                details=message
            )
            alerts_generated = True
    
    return alerts_generated

def evaluate_all_alerts(user_id, current_date):
    """
    Evalúa todas las reglas de alerta para un usuario en una fecha específica.
    
    Args:
        user_id (int): ID del usuario
        current_date (datetime): Fecha actual
        
    Returns:
        bool: True si se generó al menos una alerta, False en caso contrario
    """
    alerts_generated = False
    
    # Evaluar cada regla de alerta
    if check_activity_drop(user_id, current_date):
        alerts_generated = True
    if check_sedentary_increase(user_id, current_date):
        alerts_generated = True
    if check_sleep_duration_change(user_id, current_date):
        alerts_generated = True
    if check_heart_rate_anomaly(user_id, current_date):
        alerts_generated = True
    if check_data_quality(user_id, current_date):
        alerts_generated = True
    if check_intraday_anomalies(user_id, current_date):
        alerts_generated = True
    
    return alerts_generated 