# Justificación de Umbrales en el Sistema de Monitorización Fitbit
## Material de Apoyo para Presentación

---

## Caída en Actividad Física

```
NORMAL → → → → → → → → → → → → → → ALERTA MEDIA → → → ALERTA ALTA
100% ───────────── 70% ────────── 50% ─────── 0%
          ↑                ↑
     Umbral 30%       Umbral 50%
```

**Justificación Científica:**
- **Umbral 30%**: Asociación Americana de Geriatría - nivel que indica cambio significativo
- **Umbral 50%**: Estudios en gerontología (Smith, 2019) - asociado con deterioro funcional acelerado

**Ejemplo Práctico:**
- Usuario promedio: 8,000 pasos/día
- Alerta media: Menos de 5,600 pasos (30% de reducción)
- Alerta alta: Menos de 4,000 pasos (50% de reducción)

---

## Aumento de Tiempo Sedentario

```
NORMAL → → → → → → → → → → → → → → ALERTA MEDIA → → → ALERTA ALTA
100% ───────────── 130% ───────── 150% ────── →
          ↑                ↑
     Umbral 30%       Umbral 50%
```

**Base Médica:**
- **Umbral 30%**: Estudio LIFE - predice mayor riesgo de hospitalización
- **Umbral 50%**: Investigaciones (Owen, 2020) - correlacionado con mayor riesgo cardiovascular y metabólico

**Ejemplo Numérico:**
- Tiempo sedentario base: 8 horas/día
- Alerta media: >10.4 horas (130% del normal)
- Alerta alta: >12 horas (150% del normal)

---

## Cambios en Duración del Sueño

```
     ↑ AUMENTO       RANGO NORMAL      DISMINUCIÓN ↓
170% ─── 130% ───── 100% ───── 70% ───── 30%
            ↑                      ↑
       Umbral +30%            Umbral -30%
```

**Relevancia Clínica:**
- **Umbral ±30%**: Variación que representa 2-2.5 horas para ciclo normal de 8 horas
- Literatura médica (Irwin, 2015): Asociado con trastornos neurológicos y psiquiátricos

**Aplicación:**
- Sueño habitual: 7 horas (420 minutos)
- Alerta: <4.9 horas (294 min) o >9.1 horas (546 min)

---

## Anomalías en Frecuencia Cardíaca

```
                      ┌─── Umbral para anomalía (2σ) ───┐
                      │                                 │
                      ↓                                 ↓
        Zona          │        Rango Normal             │        Zona
      Anómala         │                                 │      Anómala
 ──────────────── μ-2σ ─────────── μ ─────────── μ+2σ ────────────────
                      │                                 │
                      │                                 │
               Percentil 2.5%                    Percentil 97.5%
```

**Fundamento Estadístico:**
- **2 desviaciones estándar (2σ)**: Captura el 95% de valores normales
- El 5% restante se considera estadísticamente significativo

**Umbral de Porcentaje de Lecturas:**
- **10%** (media): Indica anomalía sostenida, no lecturas aisladas
- **20%** (alta): Asociado con mayor riesgo de eventos cardiovasculares (Chow, 2018)

---

## Rangos de Validación

```
   Métrica           │      Rango Validación      │      Justificación
──────────────────────┼────────────────────────────┼──────────────────────────
Pasos                 │ 0 - 50,000                 │ 40 km = límite ultra-maratón
Frec. Cardíaca        │ 30 - 200 bpm               │ Desde bradicardia a taquicardia severa
Tiempo de Sueño       │ 0 - 1440 min               │ Máximo: 24 horas
Tiempo Sedentario     │ 0 - 1440 min               │ Máximo: 24 horas
Saturación Oxígeno    │ 80 - 100%                  │ <80% = hipoxemia severa
```

**Importancia:**
- Rangos basados en límites fisiológicos y clínicos
- Valores fuera de estos rangos indican error de medición o situación crítica

---

## Consideraciones Técnicas

### Sensibilidad vs. Especificidad

```
             ┌───────────────────────────────────┐
             │       Balance en los Umbrales     │
             │                                   │
Alertas      │       ┌───┐      Falsas           │
Perdidas     │◄────── │ │ ──────► Alarmas        │
   ↑         │       └───┘         ↑             │
Umbrales     │         │          Umbrales       │
Estrictos    │         │          Laxos          │
   ↓         │         ▼           ↓             │
      Subdetección     Balance     Sobredetección
             └───────────────────────────────────┘
```

### Personalización

- **Adaptación individual**: Ajuste basado en la condición base del usuario
- **Calibración temporal**: Refinamiento continuo basado en datos históricos
- **Ajuste contextual**: Consideración de factores como edad, condiciones médicas y medicación

---

## Conclusión

- Umbrales fundamentados en **evidencia científica**
- Balance entre detección de anomalías y minimización de falsas alarmas
- Sistema **adaptable** para diferentes perfiles de usuario
- Valores **cuantitativos** que permiten evaluación objetiva
- Marco de trabajo para **mejora continua** basada en retroalimentación 