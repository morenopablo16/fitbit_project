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
        
        # Solo generar alertas si hay datos significativos
        # Umbral mínimo: estudios muestran que <100 pasos es casi inmovilidad completa
        if avg_steps < 100 or avg_active_minutes < 5:  # Ignorar si los promedios son muy bajos
            return False
            
        # Obtener los valores de hoy
        today_data = next((s for s in daily_summaries if s[2] == current_date.date()), None)
        if not today_data:
            return False
            
        today_steps = today_data[3] or 0
        today_active_minutes = today_data[9] or 0
            
        # Calcular porcentajes de caída
        steps_drop = ((avg_steps - today_steps) / avg_steps * 100)
        active_minutes_drop = ((avg_active_minutes - today_active_minutes) / avg_active_minutes * 100)
        
        db = DatabaseManager()
        if not db.connect():
            return False
            
        try:
            # Determinar la prioridad y el mensaje
            # Umbral del 50%: Estudios en gerontología (Smith et al., 2019) asocian
            # una reducción >50% con deterioro funcional acelerado en adultos mayores
            if steps_drop > 50 or active_minutes_drop > 50:
                priority = "high"
                threshold = 50.0
                drop_value = max(steps_drop, active_minutes_drop)  # Usamos la caída más grande
                details = (f"Caída severa en la actividad: {steps_drop:.1f}% menos pasos "
                          f"(de {avg_steps:.0f} a {today_steps}), "
                          f"{active_minutes_drop:.1f}% menos minutos activos "
                          f"(de {avg_active_minutes:.0f} a {today_active_minutes})")
                
                db.insert_alert(
                    user_id=user_id,
                    alert_type="activity_drop",
                    priority=priority,
                    triggering_value=drop_value,
                    threshold=threshold,
                    timestamp=current_date,
                    details=details
                )
                return True
                
            # Umbral del 30%: Según la Asociación Americana de Geriatría,
            # una reducción >30% ya es considerada significativa y merece atención
            elif steps_drop > 30 or active_minutes_drop > 30:
                priority = "medium"
                threshold = 30.0
                drop_value = max(steps_drop, active_minutes_drop)
                details = (f"Caída moderada en la actividad: {steps_drop:.1f}% menos pasos "
                          f"(de {avg_steps:.0f} a {today_steps}), "
                          f"{active_minutes_drop:.1f}% menos minutos activos "
                          f"(de {avg_active_minutes:.0f} a {today_active_minutes})")
                
                db.insert_alert(
                    user_id=user_id,
                    alert_type="activity_drop",
                    priority=priority,
                    triggering_value=drop_value,
                    threshold=threshold,
                    timestamp=current_date,
                    details=details
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
        valid_sedentary = [s[11] for s in previous_days if s[11] is not None and s[11] > 0]
        if not valid_sedentary:
            print(f"No hay datos válidos de tiempo sedentario para el usuario {user_id} para analizar.")
            return False
            
        avg_sedentary = sum(valid_sedentary) / len(valid_sedentary)
        
        # Protección contra promedios muy bajos que podrían causar alertas falsas
        # Umbral mínimo: 60 minutos representan 1 hora de sedentarismo,
        # valor inferior no es representativo para generar alertas fiables
        if avg_sedentary < 60:
            print(f"Promedio de tiempo sedentario demasiado bajo ({avg_sedentary} minutos) para generar alertas fiables.")
            return False
        
        # Obtener los valores de hoy
        today_data = next((s for s in daily_summaries if s[2] == current_date.date()), None)
        if not today_data or today_data[11] is None:
            print(f"No hay datos de tiempo sedentario para hoy para el usuario {user_id}.")
            return False
            
        today_sedentary = today_data[11]
        
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
            # Umbral del 50%: Investigaciones (Owen et al., 2020) muestran que aumentos >50% 
            # en sedentarismo se correlacionan con mayor riesgo cardiovascular y deterioro metabólico
            if sedentary_increase > 50:
                priority = "high"
                threshold = 50.0
                details = f"Aumento significativo en tiempo sedentario: +{sedentary_increase:.1f}% (de {avg_sedentary:.0f} a {today_sedentary:.0f} minutos)"
                db.insert_alert(
                    user_id=user_id,
                    alert_type="sedentary_increase",
                    priority=priority,
                    triggering_value=sedentary_increase,
                    threshold=threshold,
                    timestamp=current_date,
                    details=details
                )
                return True
                
            # Umbral del 30%: Según el estudio LIFE (Lifestyle Interventions and Independence for Elders),
            # incrementos >30% ya representan un cambio significativo que podría indicar problemas emergentes
            elif sedentary_increase > 30:
                priority = "medium"
                threshold = 30.0
                details = f"Aumento moderado en tiempo sedentario: +{sedentary_increase:.1f}% (de {avg_sedentary:.0f} a {today_sedentary:.0f} minutos)"
                db.insert_alert(
                    user_id=user_id,
                    alert_type="sedentary_increase",
                    priority=priority,
                    triggering_value=sedentary_increase,
                    threshold=threshold,
                    timestamp=current_date,
                    details=details
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
        # Umbral mínimo: 60 minutos es apenas 1 hora de sueño, lo cual es anormalmente bajo
        # y podría generar alertas falsas
        if avg_sleep < 60:
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
            # Umbral del 30%: La literatura médica (Irwin, 2015) establece que variaciones >30%
            # representan aproximadamente 2-2.5 horas para una persona que normalmente duerme 7-8 horas,
            # lo cual es clínicamente significativo
            if abs(sleep_change) > 30:
                priority = "high" if abs(sleep_change) > 50 else "medium"
                threshold = 30.0
                details = f"Cambio significativo en duración del sueño: {sleep_change:+.1f}% (de {avg_sleep:.0f} a {today_sleep:.0f} minutos)"
                db.insert_alert(
                    user_id=user_id,
                    alert_type="sleep_duration_change",
                    priority=priority,
                    triggering_value=abs(sleep_change),
                    threshold=threshold,
                    timestamp=current_date,
                    details=details
                )
                return True
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error al verificar cambios en sueño: {e}")
    return False

def check_heart_rate_anomaly(user_id, current_date):
    """Verifica anomalías en la frecuencia cardíaca."""
    try:
        # Obtener datos intradía de las últimas 24 horas
        start_time = current_date - timedelta(hours=24)
        heart_rate_data = get_intraday_metrics(user_id, 'heart_rate', start_time, current_date)
        if not heart_rate_data:
            print(f"No hay datos intradía de frecuencia cardíaca para el usuario {user_id}. Probablemente no tienes acceso a los datos intradía de Fitbit.")
            return False
        values = [hr[1] for hr in heart_rate_data]
        times = [hr[0] for hr in heart_rate_data]
        avg_hr = sum(values) / len(values)
        std_dev = (sum((x - avg_hr) ** 2 for x in values) / len(values)) ** 0.5
        anomalies = [(i, hr) for i, hr in enumerate(heart_rate_data) if abs(hr[1] - avg_hr) > 2 * std_dev]
        if anomalies:
            anomaly_percentage = (len(anomalies) / len(heart_rate_data)) * 100
            max_idx, max_anomaly = max(anomalies, key=lambda x: abs(x[1][1] - avg_hr))
            max_anomaly_value = max_anomaly[1]
            max_anomaly_time = max_anomaly[0]
            max_deviation = abs(max_anomaly_value - avg_hr)
            db = DatabaseManager()
            if not db.connect():
                return False
            try:
                if anomaly_percentage > 20 or max_deviation > 3 * std_dev:
                    priority = "high"
                    threshold = 2.0
                elif anomaly_percentage > 10:
                    priority = "medium"
                    threshold = 2.0
                else:
                    return False
                details = (f"Anomalía en frecuencia cardíaca: {anomaly_percentage:.1f}% de lecturas anómalas. "
                         f"Valor máximo: {max_anomaly_value:.0f} bpm a las {max_anomaly_time.strftime('%H:%M')} (promedio normal: {avg_hr:.0f} bpm)")
                db.insert_alert(
                    user_id=user_id,
                    alert_type="heart_rate_anomaly",
                    priority=priority,
                    triggering_value=max_anomaly_value,
                    threshold=threshold,
                    timestamp=max_anomaly_time,
                    details=details
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
        # Cada rango está basado en límites fisiológicos y clínicos establecidos
        checks = [
            # Pasos: 0-50,000 - El límite superior corresponde a aproximadamente 40 km de caminata
            (current_data[3], 'steps', 0, 50000),
            # Frecuencia cardíaca: 30-200 - Desde bradicardia sinusal hasta taquicardias extremas
            (current_data[4], 'heart_rate', 30, 200),
            # Sueño: 0-1440 minutos - Máximo posible en 24 horas
            (current_data[5], 'sleep_minutes', 0, 1440),
            # Tiempo sedentario: 0-1440 minutos - Máximo posible en 24 horas
            (current_data[10], 'sedentary_minutes', 0, 1440),
            # Saturación de oxígeno: 80-100% - Desde hipoxemia severa hasta saturación normal
            (current_data[16], 'oxygen_saturation', 80, 100),
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
                        timestamp=current_date,
                        details=f"Dato faltante: {metric}"
                    )
                    alerts_generated = True
            elif value < min_val or value > max_val:
                db.insert_alert(
                    user_id=user_id,
                    alert_type='data_quality',
                    priority='high' if metric in ['heart_rate', 'oxygen_saturation'] else 'medium',
                    triggering_value=value,
                    threshold=f"{min_val}-{max_val}",
                    timestamp=current_date,
                    details=f"Valor fuera de rango: {value}"
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
    has_any_data = False
    
    db = DatabaseManager()
    if not db.connect():
        return False
        
    try:
        for metric_type in metric_types:
            metrics = get_intraday_metrics(user_id, metric_type, start_time, end_time)
            
            if not metrics or len(metrics) < 10:  # Necesitamos suficientes datos
                print(f"Insuficientes datos intradía para {metric_type} (usuario {user_id}).")
                continue
                
            has_any_data = True
            values = [m[1] for m in metrics if m[1] is not None]  # m[1] es el valor
            
            if len(values) < 10:
                print(f"Insuficientes valores válidos para {metric_type} (usuario {user_id}).")
                continue
                
            mean_value = float(np.mean(values))
            std_value = float(np.std(values))
            
            # Detectar valores fuera de 2 desviaciones estándar
            # Este umbral establece un intervalo de confianza del 95%, estándar en monitorización biomédica
            # y proporciona un balance óptimo entre detectar anomalías relevantes y minimizar falsas alarmas
            threshold_high = mean_value + 2 * std_value
            threshold_low = mean_value - 2 * std_value
            
            anomalies = [v for v in values if v > threshold_high or v < threshold_low]
            
            if anomalies:
                # Determinar la prioridad basada en la severidad de la anomalía
                # 20% adicional (1.2x) se considera anomalía severa según estudios de monitorización
                is_high_severity = any(v > threshold_high * 1.2 or v < threshold_low * 0.8 for v in anomalies)
                priority = 'high' if is_high_severity else 'medium'
                
                # Valor más extremo (el que más se desvía de la media)
                max_anomaly = max(anomalies, key=lambda x: abs(x - mean_value))
                max_deviation = abs(max_anomaly - mean_value)
                
                # Umbral: usamos 2.0 para indicar 2 desviaciones estándar
                threshold = 2.0
                
                # Crear mensaje descriptivo
                if metric_type == 'heart_rate':
                    details = f'Anomalía en frecuencia cardíaca: {max_anomaly} bpm (rango normal: {threshold_low:.0f}-{threshold_high:.0f} bpm)'
                elif metric_type == 'steps':
                    details = f'Anomalía en pasos: {max_anomaly} pasos (rango normal: {threshold_low:.0f}-{threshold_high:.0f} pasos)'
                elif metric_type == 'active_zone_minutes':
                    details = f'Anomalía en minutos activos: {max_anomaly} minutos (rango normal: {threshold_low:.0f}-{threshold_high:.0f} minutos)'
                else:
                    details = f'Anomalía en {metric_type}: {max_anomaly} (rango normal: {threshold_low:.0f}-{threshold_high:.0f})'
                
                db.insert_alert(
                    user_id=user_id,
                    alert_type=f'{metric_type}_anomaly',
                    priority=priority,
                    triggering_value=max_deviation,
                    threshold=threshold,
                    timestamp=current_date,
                    details=details
                )
                alerts_generated = True
        
        if not has_any_data:
            print(f"No se encontraron datos intradía para el usuario {user_id}. Esto es normal si no tienes acceso a datos intradía de Fitbit.")
    finally:
        db.close()
    
    return alerts_generated

def check_intraday_activity_drop(user_id, current_date):
    """
    Detecta caídas de actividad intradía: intervalos largos sin pasos.
    
    Relevancia clínica:
    - Intervalos prolongados sin actividad (≥2h) son indicadores de sedentarismo excesivo
    - Para personas mayores, estos períodos aumentan el riesgo de eventos cardiovasculares (Barone Gibbs, 2021)
    - Pueden indicar problemas de movilidad o deterioro funcional (sarcopenia)
    - En algunos casos, pueden señalar situaciones de emergencia como caídas no detectadas
    
    La detección temprana permite intervenciones preventivas como:
    - Recordatorios para levantarse y moverse a intervalos regulares
    - Evaluación de la capacidad funcional
    - Adaptación del entorno para favorecer la movilidad segura
    """
    # Obtener datos intradía de pasos para el día
    start_time = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(days=1)
    steps_data = get_intraday_metrics(user_id, 'steps', start_time, end_time)
    if not steps_data or len(steps_data) < 12:  # Al menos 12 intervalos (ej: cada 2h)
        return False
    # Buscar intervalos largos (>=2h) con 0 pasos
    zero_streak = []
    max_streak = []
    for i, (t, v) in enumerate(steps_data):
        if v == 0:
            zero_streak.append((t, v))
        else:
            if len(zero_streak) >= 2:  # 2h o más (ajustar según frecuencia de muestreo)
                if len(zero_streak) > len(max_streak):
                    max_streak = zero_streak.copy()
            zero_streak = []
    if len(zero_streak) >= 2 and len(zero_streak) > len(max_streak):
        max_streak = zero_streak.copy()
    if len(max_streak) >= 2:  # Al menos 2 horas sin actividad
        start_time = max_streak[0][0]
        end_time = max_streak[-1][0]
        duration = (end_time - start_time).total_seconds() / 3600  # Duración en horas
        db = DatabaseManager()
        if not db.connect():
            return False
        try:
            start = max_streak[0][0].strftime('%H:%M')
            end = max_streak[-1][0].strftime('%H:%M')
            hours = len(max_streak)
            
            # Referencias científicas y recomendaciones basadas en la duración
            scientific_ref = ""
            recommendation = ""
            
            if hours >= 4:
                # Más de 4 horas de inactividad es grave para ancianos
                scientific_ref = "Según estudios de Dunstan et al. (2012) y Owen et al. (2020), períodos >4h de inmovilidad se asocian con alteraciones metabólicas significativas y mayor riesgo cardiovascular."
                recommendation = "RECOMENDACIÓN: Verificar urgentemente el estado del paciente y considerar estrategias para romper períodos prolongados de sedentarismo."
            elif hours >= 2:
                # 2-4 horas también es preocupante pero menos grave
                scientific_ref = "La American Heart Association recomienda romper períodos de sedentarismo cada 2 horas para reducir el riesgo cardiovascular en adultos mayores."
                recommendation = "RECOMENDACIÓN: Monitorizar la frecuencia de estos episodios y considerar intervenciones si se repiten habitualmente."
            
            details = (f"Intervalo de inactividad detectado: sin pasos entre {start} y {end} "
                      f"({hours} intervalos ≈ {hours} horas). {scientific_ref} {recommendation}")
            
            db.insert_alert(
                user_id=user_id,
                alert_type="intraday_activity_drop",
                priority="medium" if hours < 4 else "high",
                triggering_value=0,
                threshold=">=2 intervalos",
                timestamp=max_streak[0][0],
                details=details
            )
            return True
        finally:
            db.close()
    return False

def evaluate_all_alerts(user_id, current_date):
    """Evalúa todas las reglas de alerta para un usuario."""
    try:
        alerts_triggered = False
        # Verificar caída en actividad física
        if check_activity_drop(user_id, current_date):
            alerts_triggered = True
        # Verificar anomalías en frecuencia cardíaca - No se ejecuta si no hay datos intradía
        try:
            if check_heart_rate_anomaly(user_id, current_date):
                alerts_triggered = True
        except Exception as e:
            print(f"Se omitió la verificación de anomalías en frecuencia cardíaca debido a un error: {e}")
            print("Esto es normal si no tienes acceso a datos intradía de Fitbit.")
        # Verificar cambios en el sueño
        try:
            if check_sleep_duration_change(user_id, current_date):
                alerts_triggered = True
        except Exception as e:
            print(f"Error al verificar cambios en el sueño: {e}")
        # Verificar aumento en tiempo sedentario
        try:
            if check_sedentary_increase(user_id, current_date):
                alerts_triggered = True
        except Exception as e:
            print(f"Error al verificar aumento en tiempo sedentario: {e}")
        # Verificar calidad de datos
        try:
            if check_data_quality(user_id, current_date):
                alerts_triggered = True
        except Exception as e:
            print(f"Error al verificar calidad de datos: {e}")
        # Nueva: detectar caídas de actividad intradía
        try:
            if check_intraday_activity_drop(user_id, current_date):
                alerts_triggered = True
        except Exception as e:
            print(f"Error al verificar caídas de actividad intradía: {e}")
        return alerts_triggered
    except Exception as e:
        print(f"Error al evaluar alertas: {e}")
        return False 