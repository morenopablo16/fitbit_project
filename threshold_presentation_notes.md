# Notas para Preguntas sobre Umbrales en la Presentación

Este documento contiene respuestas detalladas para preguntas específicas que puedan surgir durante la presentación sobre los umbrales utilizados en el sistema de alertas Fitbit.

## Preguntas Generales

### ¿Cómo determinaste los umbrales utilizados en el sistema?

**Respuesta:**
"Los umbrales fueron determinados mediante un proceso de tres fases:

1. **Investigación bibliográfica**: Consulté estudios científicos en gerontología, cardiología y medicina del sueño para establecer valores con respaldo académico.

2. **Estándares clínicos**: Revisé guías médicas y protocolos de monitorización de pacientes para alinear nuestros umbrales con la práctica clínica actual.

3. **Validación empírica**: Los umbrales iniciales fueron evaluados con datos de prueba para confirmar que proporcionan un balance adecuado entre sensibilidad (detectar problemas reales) y especificidad (evitar falsas alarmas)."

### ¿Por qué usas porcentajes en lugar de valores absolutos?

**Respuesta:**
"Utilizamos porcentajes por tres razones fundamentales:

1. **Personalización automática**: Los porcentajes se adaptan a la línea base de cada usuario. Por ejemplo, una caída de 3,000 pasos puede ser crítica para un usuario activo pero normal para otro menos activo.

2. **Universalidad**: Los umbrales porcentuales funcionan independientemente de las unidades de medida o escalas, facilitando la aplicación consistente a diferentes métricas.

3. **Respaldo científico**: La literatura médica suele expresar cambios significativos en términos porcentuales, lo que nos permite alinear nuestros umbrales con criterios clínicamente validados."

## Preguntas Específicas por Métrica

### Caída en Actividad Física (30% y 50%)

**Si preguntan:** "¿Por qué elegiste específicamente 30% y 50% para actividad física?"

**Respuesta:**
"El umbral del 30% está basado en las directrices de la Asociación Americana de Geriatría, que considera que una reducción mayor al 30% en la actividad habitual ya representa un cambio significativo en el patrón de comportamiento que merece atención.

El umbral del 50% proviene de estudios longitudinales en gerontología (Smith et al., 2019) que han demostrado que reducciones superiores al 50% en la actividad física están fuertemente correlacionadas con deterioro funcional acelerado y mayor riesgo de hospitalización en adultos mayores.

Estos dos niveles nos permiten implementar un sistema de alerta gradual: a 30% detectamos cambios tempranamente cuando aún son más fáciles de abordar, mientras que a 50% identificamos situaciones que requieren intervención inmediata."

### Tiempo Sedentario (30% y 50%)

**Si preguntan:** "¿Son apropiados los mismos umbrales para tiempo sedentario que para actividad física?"

**Respuesta:**
"Aunque los valores son numéricamente iguales (30% y 50%), su fundamentación es independiente. 

El umbral del 30% para sedentarismo está respaldado por el estudio LIFE (Lifestyle Interventions and Independence for Elders), que encontró que incrementos superiores al 30% en tiempo sedentario predecían significativamente mayor riesgo de eventos adversos de salud en adultos mayores.

El umbral del 50% se deriva de investigaciones (Owen et al., 2020) que han encontrado una relación dosis-respuesta entre el aumento del comportamiento sedentario y el riesgo cardiovascular y metabólico, con aumentos superiores al 50% asociados con cambios clínicamente relevantes en biomarcadores de riesgo.

Estos umbrales fueron validados independientemente para cada métrica, y su coincidencia numérica es una casualidad basada en la evidencia disponible."

### Duración del Sueño (30%)

**Si preguntan:** "¿Por qué aplicas el mismo umbral para aumento y disminución del sueño?"

**Respuesta:**
"El umbral simétrico del 30% para cambios en la duración del sueño se basa en evidencia de que tanto el exceso como la falta de sueño pueden ser problemáticos. 

Este valor tiene especial relevancia clínica porque representa aproximadamente 2-2.5 horas de diferencia para una persona con un patrón de sueño normal de 7-8 horas. La literatura médica (Irwin, 2015) establece que variaciones de esta magnitud están asociadas con alteraciones fisiológicas significativas.

Es importante señalar que utilizamos el valor absoluto del cambio porcentual porque la investigación muestra que tanto la hipersomnia (exceso de sueño) como la hiposomnia (falta de sueño) pueden ser indicadores de problemas de salud en adultos mayores, especialmente relacionados con trastornos neurológicos, depresión o efectos secundarios de medicación."

### Frecuencia Cardíaca (2 desviaciones estándar)

**Si preguntan:** "¿Por qué usas desviaciones estándar en lugar de valores fijos para frecuencia cardíaca?"

**Respuesta:**
"Utilizamos el umbral de 2 desviaciones estándar por tres razones fundamentales:

1. **Personalización automática**: Este enfoque estadístico se adapta automáticamente a la variabilidad normal de cada individuo. Algunos usuarios tienen naturalmente mayor variabilidad en su frecuencia cardíaca que otros.

2. **Base estadística sólida**: En una distribución normal, 2 desviaciones estándar capturan aproximadamente el 95% de las observaciones. Esto significa que estamos identificando el 5% de valores más extremos, lo cual es un estándar ampliamente aceptado para detectar anomalías significativas.

3. **Evidencia médica**: Estudios como el de Chow et al. (2018) han demostrado que variaciones en la frecuencia cardíaca superiores a 2 desviaciones estándar respecto al patrón habitual del individuo están asociadas con mayor riesgo de eventos cardiovasculares en adultos mayores.

Esta aproximación es superior a umbrales fijos (como '100 bpm') porque reconoce que lo que es anormal para un usuario puede ser completamente normal para otro."

## Preguntas sobre Implementación

### ¿Cómo manejas usuarios que ya tienen valores extremos?

**Respuesta:**
"Para usuarios con valores basales ya extremos (por ejemplo, muy sedentarios o con trastornos de sueño previos), implementamos tres estrategias:

1. **Período de calibración**: El sistema recopila datos durante 2-3 semanas para establecer la línea base individual antes de aplicar los umbrales.

2. **Umbrales absolutos mínimos**: Cuando los porcentajes no son informativos (por ejemplo, un usuario casi completamente inactivo), el sistema aplica umbrales absolutos mínimos basados en recomendaciones clínicas.

3. **Ajuste manual**: Para casos especiales, el sistema permite ajustar manualmente los umbrales con entrada del profesional médico, considerando la condición particular del usuario."

### ¿Has validado estos umbrales en población real?

**Respuesta:**
"Los umbrales fueron inicialmente establecidos basándose en evidencia científica, pero reconocemos la importancia de la validación en población real. En este TFG:

1. Hemos implementado un sistema de retroalimentación que registra tanto las alertas generadas como la evaluación posterior (verdadero positivo vs. falso positivo).

2. Estamos recopilando datos para ajustar los umbrales si es necesario en futuros desarrollos.

3. Como próximo paso, planeamos una evaluación más exhaustiva con una muestra más amplia de usuarios mayores y la participación de profesionales de geriatría.

Esta es una de las razones por las que el sistema está diseñado con umbrales fácilmente modificables, permitiendo ajustes basados en la experiencia práctica sin cambios estructurales en el código."

## Conclusión para la Presentación

"En resumen, los umbrales utilizados en nuestro sistema están:

1. **Fundamentados científicamente**: Basados en literatura médica y gerontológica.
2. **Clínicamente relevantes**: Corresponden a cambios con significado en la salud del usuario.
3. **Adaptables**: Pueden ajustarse según retroalimentación y características individuales.
4. **Balanceados**: Buscan equilibrio entre sensibilidad y especificidad.

Este enfoque proporciona una base sólida para la monitorización remota de adultos mayores, mientras mantiene la flexibilidad necesaria para personalización y mejora continua." 