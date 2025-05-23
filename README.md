# Lively Ageing - Fitbit Device Linking Dashboard
![image](https://github.com/user-attachments/assets/2b9f24e7-29c4-4f7a-b693-48fc0ea7b6e6)

A web application designed to help elderly users monitor their health and activity data through Fitbit devices. This dashboard provides an intuitive interface for managing Fitbit device connections and viewing health metrics.

## Features

### Core Functionality
- Fitbit device linking and management
- Real-time health data synchronization
- Multi-user support with role-based access
- Secure authentication and authorization

### Data Tracking
- Heart rate monitoring
- Step counting
- Sleep patterns
- Activity levels
- Daily health statistics

### User Interface
- Clean, intuitive dashboard
- Responsive design
- Multi-language support (English and Spanish)
- Easy device linking process

### Security
- Secure OAuth2 authentication with Fitbit
- Role-based access control
- Environment-based configuration
- Secure session management

## Technologies Used

### Backend
- Python Flask
- SQLite Database
- Flask-Login for authentication
- Flask-Babel for internationalization

### Frontend
- HTML5 & CSS3
- JavaScript
- Bootstrap 5
- Chart.js for data visualization

### APIs & Services
- Fitbit Web API
- OAuth2 Authentication

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/lively-ageing-fitbit.git
cd lively-ageing-fitbit
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables in `.env`:
```
FITBIT_CLIENT_ID=your_client_id
FITBIT_CLIENT_SECRET=your_client_secret
FLASK_SECRET_KEY=your_secret_key
```

5. Initialize the database:
```bash
python db.py
```

6. Compile translations:
```bash
pybabel compile -d translations
```

7. Run the application:
```bash
python app.py
```

## Usage Guide

### Dashboard Navigation

The dashboard provides an intuitive interface for managing Fitbit devices and viewing health data. Here's how to navigate through the main features:

![Home Dashboard](static/img/screenshots/home_dashboard.png)

1. **Home Screen**: The main dashboard displays an overview of connected devices and active users.
2. **Navigation Bar**: Access different sections using the top navigation menu.
3. **Language Selection**: Switch between English and Spanish using the language dropdown.

### Device Management

#### Linking a New Device

![Device Linking](static/img/screenshots/device_linking.png)

1. Click on "Link Device" in the navigation bar
2. Follow the Fitbit authorization process
3. Grant necessary permissions
4. Confirm device connection

#### Reassigning Devices

![Device Reassignment](static/img/screenshots/reassign_device.png)

1. Navigate to user management
2. Select the device to reassign
3. Choose the new user
4. Confirm the reassignment

### User Statistics

![User Stats](static/img/screenshots/user_stats.png)

View detailed health metrics including:
- Daily step count
- Heart rate data
- Sleep patterns
- Activity levels

### Administrative Tasks

![Admin Panel](static/img/screenshots/admin_panel.png)

Administrators can:
- Manage user accounts
- Monitor device connections
- View system logs
- Configure application settings

## Internationalization

The application supports multiple languages:

- English (default)
- Spanish

To add a new language:

1. Extract messages:
```bash
pybabel extract -F babel.cfg -o messages.pot .
```

2. Initialize the new language:
```bash
pybabel init -i messages.pot -d translations -l [LANG_CODE]
```

3. Edit translations in `translations/[LANG_CODE]/LC_MESSAGES/messages.po`

4. Compile translations:
```bash
pybabel compile -d translations
```

## Project Structure
```
lively-ageing-fitbit/
├── app.py
├── db.py
├── config.py
├── requirements.txt
├── babel.cfg
├── .env
├── static/
│   ├── css/
│   ├── js/
│   └── img/
├── templates/
│   ├── home.html
│   ├── dashboard.html
│   ├── link_auth.html
│   └── ...
└── translations/
    ├── en/
    └── es/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Acknowledgments

- Fitbit for providing the API
- The Flask team for the excellent framework
- Bootstrap team for the UI components
- Chart.js for data visualization

## Screenshots

### Home Dashboard
![Home Dashboard](static/img/screenshots/home_dashboard.png)
*Main dashboard showing device overview and quick stats*

### Device Linking
![Device Linking](static/img/screenshots/device_linking.png)
*Fitbit device authorization and linking process*

### User Statistics
![User Stats](static/img/screenshots/user_stats.png)
*Detailed view of user health metrics and activity data*

### Administrative Panel
![Admin Panel](static/img/screenshots/admin_panel.png)
*Administrative interface for managing users and devices*

## Fitbit Data Collection Project

## Descripción

Este proyecto recopila y analiza datos de dispositivos Fitbit para monitorear actividad física y bienestar, diseñado como parte de un sistema para ayudar a adultos mayores a mantener un estilo de vida saludable.

## Funcionalidades principales

- Recopilación automática de datos diarios de dispositivos Fitbit
- Recopilación de datos intradía (cuando esté disponible)
- Sistema de alertas basado en cambios significativos en patrones de actividad
- Dashboard para visualización y análisis de datos
- Notificaciones para cuidadores o profesionales de la salud

## Arquitectura del sistema

El sistema consta de los siguientes componentes:

1. **Scripts de recolección de datos**:
   - `fitbit.py`: Recopila resúmenes diarios de actividad
   - `fitbit_intraday.py`: Recopila datos intradía (minuto a minuto)
   - `run_fitbit.sh` y `run_fitbit_intraday.sh`: Scripts para ejecución programada

2. **Base de datos**:
   - PostgreSQL con TimescaleDB para almacenamiento eficiente de series temporales
   - Tablas para usuarios, métricas diarias, métricas intradía y alertas

3. **Sistema de alertas**:
   - `alert_rules.py`: Reglas para detección de anomalías y generación de alertas
   - Alertas basadas en cambios en patrones de actividad, sueño y frecuencia cardíaca

4. **Interfaz web**:
   - Dashboard para visualización de datos y gestión de alertas
   - Paneles administrativos para configuración del sistema

## Configuración del acceso a datos intradía de Fitbit

### Importante: Restricciones de la API de Fitbit

Fitbit restringe el acceso a los datos intradía (minuto a minuto) y requiere una autorización especial según el tipo de aplicación:

- **Aplicaciones personales**: Pueden acceder a datos intradía solo del propietario de la aplicación.
- **Aplicaciones en modo servidor**: Necesitan solicitar acceso especial a Fitbit para acceder a datos intradía de múltiples usuarios.

### Solicitud de acceso a datos intradía

Para obtener acceso a los datos intradía de múltiples usuarios, siga estos pasos:

1. **Regístrese como desarrollador** en [dev.fitbit.com](https://dev.fitbit.com/)

2. **Cree una aplicación** en [dev.fitbit.com/apps](https://dev.fitbit.com/apps) con la siguiente configuración:
   - **Tipo de OAuth**: Client
   - **URL de Callback**: La URL donde los usuarios serán redirigidos después de autorizar su aplicación
   - **Permisos solicitados**: Marque todos los permisos necesarios

3. **Solicite acceso a datos intradía** a través del [Issue Tracker de Fitbit](https://dev.fitbit.com/build/reference/web-api/intraday/)
   - Complete el formulario solicitando acceso a "Intraday Time Series"
   - Proporcione una descripción detallada del propósito de su aplicación y cómo se usarán los datos
   - Indique que esta aplicación es para investigación o para un proyecto sin fines de lucro

4. **Espere la aprobación** de Fitbit (puede tardar varios días o semanas)

5. **Actualice su aplicación** una vez recibida la aprobación:
   - No necesitará modificar el código
   - Las solicitudes comenzarán a devolver datos intradía automáticamente

### Formato de la solicitud de acceso

Al solicitar acceso a Fitbit, proporcione la siguiente información:

```
**ONE CLIENT ID PER REQUEST**

* Additional email addresses to be cc'd on request: [Email del supervisor/colaboradores]
* Contact Name: [Su nombre]
* Organization Name: [Su institución]
* Application Name: Lively Ageing Fitbit Monitor
* Application URL: [URL de su aplicación o repositorio]
* Client ID: [registrado en https://dev.fitbit.com/apps]

**USE CASE: RESEARCH/PERSONAL PROJECT**

* Describe your research study: Este proyecto forma parte de un TFG (Trabajo Fin de Grado) en ingeniería informática, enfocado en desarrollar un sistema de monitoreo para ancianos utilizando dispositivos Fitbit. El objetivo es mejorar la calidad de vida y la independencia de los adultos mayores mediante la detección temprana de cambios en patrones de actividad y salud.

* Who is the intended audience for your application? Adultos mayores, cuidadores, y profesionales de la salud que trabajan con población geriátrica.

* How many people's data will you be querying? Entre 5-20 personas para la fase de prueba inicial.

* How will your application utilize the Fitbit API and the intraday data? Los datos intradía se utilizarán para crear algoritmos de detección de anomalías más precisos, identificando patrones inusuales en la actividad física, sueño y frecuencia cardíaca que podrían indicar problemas de salud.

* Describe how your application will display any of the intraday data: Los datos se mostrarán en un dashboard web con gráficos detallados de actividad y resúmenes diarios. Las anomalías detectadas generarán alertas visuales para cuidadores y familiares.
```

## Configuración del proyecto

### Requisitos previos

- Python 3.8+
- PostgreSQL 12+ con TimescaleDB
- Cuenta de desarrollador de Fitbit

### Instalación

1. Clone el repositorio

```bash
git clone https://github.com/yourusername/fitbit_project.git
cd fitbit_project
```

2. Instale las dependencias

```bash
pip install -r requirements.txt
```

3. Configure las variables de entorno

Cree un archivo `.env` con la siguiente información:

```
CLIENT_ID=your_fitbit_client_id
CLIENT_SECRET=your_fitbit_client_secret
DB_NAME=fitbit_db
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
```

4. Inicialice la base de datos

```bash
python init_db.py
```

5. Configure la ejecución programada

Para recopilar datos automáticamente, configure cron para ejecutar los scripts:

```bash
# Editar crontab
crontab -e

# Añadir estas líneas para ejecutar cada 12 horas
0 */12 * * * /path/to/run_fitbit.sh
0 */6 * * * /path/to/run_fitbit_intraday.sh
```

### Uso

- **Recopilar datos diarios**: `python fitbit.py`
- **Recopilar datos intradía**: `python fitbit_intraday.py`
- **Iniciar el servidor web**: `python app.py`
- **Ejecutar pruebas**: `python -m unittest discover tests`

## Licencia

Este proyecto está licenciado bajo la Licencia MIT - vea el archivo LICENSE para más detalles.

## Contacto

Para más información, contacte con el autor del proyecto o visite el repositorio oficial.