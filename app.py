from logging.handlers import RotatingFileHandler
from flask import Flask, logging, render_template, request, redirect, session, url_for, flash, g, jsonify, Response
from rich import _console
from auth import generate_state, get_tokens, generate_code_verifier, generate_code_challenge, generate_auth_url
from db import DatabaseManager, get_daily_summaries, get_user_alerts, get_user_id_by_email
from config import CLIENT_ID, REDIRECT_URI
from translations import TRANSLATIONS
import os
from flask_login import current_user, login_user, logout_user, login_required
from flask_login import LoginManager, UserMixin
import logging
from datetime import datetime, timedelta, timezone, time
from flask_babel import Babel, get_locale, gettext as _

# Initialize Flask app
app = Flask(__name__, 
           static_url_path='/livelyageing/static',  # Prefix for static files with livelyageing
           static_folder='static')  # Directory where static files are stored
app.secret_key = os.getenv('SECRET_KEY')

# Configuración básica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
    handlers=[
        logging.StreamHandler(),  # Log a consola
        logging.FileHandler('app.log', mode='w')  # Log a archivo, sobrescribiendo cada vez
    ]
)

# Obtener el modo de ejecución
FLASK_ENV = os.getenv('FLASK_ENV', 'development')  # Por defecto, modo desarrollo
USERNAME = os.getenv('log_USERNAME')  
PASSWORD = os.getenv('PASSWORD')

# Language settings
LANGUAGES = {
    'es': 'Español',
    'en': 'English'
}
DEFAULT_LANGUAGE = 'es'

# Initialize Babel
babel = Babel(app)

def get_locale():
    """Get the best language for the user."""
    # First try to get language from the session
    if 'language' in session:
        return session['language']
    # Then try to get it from the user's browser settings
    return request.accept_languages.best_match(LANGUAGES.keys(), DEFAULT_LANGUAGE)

# Configure Babel
app.config['BABEL_DEFAULT_LOCALE'] = DEFAULT_LANGUAGE
app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
babel.init_app(app, locale_selector=get_locale)

@app.context_processor
def inject_globals():
    """Make common variables available to all templates."""
    return {
        'LANGUAGES': LANGUAGES,
        'get_locale': lambda: str(get_locale()),
        'current_language': lambda: session.get('language', DEFAULT_LANGUAGE)
    }

# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Ruta para el inicio de sesión


if FLASK_ENV == 'production':
    # Modo producción: usar IP pública y HTTPS
    HOST = os.getenv('PRODUCTION_HOST','0.0.0.0')
    PORT = int(os.getenv('PRODUCTION_PORT'))
    # SSL_CONTEXT = (
    #     os.getenv('SSL_CERT'),  # Ruta al certificado
    #     os.getenv('SSL_KEY')     # Ruta a la clave privada
    # )
    DEBUG = True
else:
    # Modo desarrollo: usar localhost y HTTP
    HOST = os.getenv('HOST')
    PORT = int(os.getenv('PORT'))
    SSL_CONTEXT = None
    DEBUG = os.getenv('DEBUG').lower() == 'true'
# Modelo de usuario
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Cargar el usuario
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Ruta de inicio de sesión
@app.route('/livelyageing/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))  # Redirigir a home en lugar de index

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print(username)
        print(USERNAME)
        print(password)
        print(PASSWORD)
        if username == USERNAME and password == PASSWORD:
            user = User(username)
            login_user(user)
            return redirect(url_for('home'))  # Redirigir a home en lugar de index
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')

# Ruta de cierre de sesión
@app.route('/livelyageing/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Proteger todas las rutas con @login_required
@app.before_request
def require_login():
    if not current_user.is_authenticated and request.endpoint != 'login':
        return redirect(url_for('login'))

# Route: Root URL redirect
@app.route('/')
def root():
    """
    Redirect from root URL to the home page.
    """
    return redirect(url_for('home'))

# Route: Homepage
@app.route('/livelyageing/')
@login_required
def index():
    """
    Redirect to home page.
    """
    return redirect(url_for('home'))

@app.route('/livelyageing/preload_dashboard')
@login_required
def preload_dashboard():
    """
    Preload dashboard data and store it in session.
    This route should be called via AJAX when the user is likely to access the dashboard.
    """
    db = DatabaseManager()
    if db.connect():
        try:
            # Get the latest daily summary for each user
            daily_summaries = db.execute_query("""
                SELECT u.name, u.email, d.*
                FROM users u
                LEFT JOIN daily_summaries d ON u.id = d.user_id
                WHERE d.date = (SELECT MAX(date) FROM daily_summaries WHERE user_id = u.id)
                OR d.date IS NULL
                ORDER BY d.date DESC NULLS LAST
            """)
            
            # Get the latest intraday metrics for each user
            intraday_metrics = db.execute_query("""
                SELECT u.name, u.email, i.type, i.value, i.time
                FROM users u
                LEFT JOIN intraday_metrics i ON u.id = i.user_id
                WHERE i.time = (SELECT MAX(time) FROM intraday_metrics WHERE user_id = u.id AND type = i.type)
                OR i.time IS NULL
                ORDER BY i.time DESC NULLS LAST
            """)
            
            # Get the latest sleep logs for each user
            sleep_logs = db.execute_query("""
                SELECT u.name, u.email, s.*
                FROM users u
                LEFT JOIN sleep_logs s ON u.id = s.user_id
                WHERE s.start_time = (SELECT MAX(start_time) FROM sleep_logs WHERE user_id = u.id)
                OR s.start_time IS NULL
                ORDER BY s.start_time DESC NULLS LAST
            """)
            
            # Transform intraday_metrics to new 4-column format for dashboard
            intraday_metrics_4col = []
            for metric in intraday_metrics:
                dt = metric[4]
                metric_type = metric[2]
                value = metric[3]
                intraday_metrics_4col.append([
                    dt.date().isoformat(),
                    dt.time().isoformat(timespec='minutes'),
                    metric_type,
                    value
                ])
            
            # Initialize empty filters_dict and alerts
            filters_dict = {}
            alerts = []
            
            # Store the processed data in the session for later use
            session['dashboard_data'] = {
                'daily_summaries': daily_summaries,
                'intraday_metrics': intraday_metrics_4col,
                'sleep_logs': sleep_logs,
                'filters_dict': filters_dict,
                'alerts': alerts,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            return jsonify({'success': True, 'timestamp': session['dashboard_data']['timestamp']})
            
        except Exception as e:
            app.logger.error(f"Error fetching data for dashboard: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            db.close()
    
    return jsonify({'error': 'Database connection error'}), 500

@app.route('/livelyageing/check_dashboard_updates')
@login_required
def check_dashboard_updates():
    """
    Check if there are any updates to the dashboard data since the last preload.
    """
    last_timestamp = request.args.get('timestamp')
    if not last_timestamp:
        return jsonify({'error': 'No timestamp provided'}), 400
        
    try:
        last_timestamp = datetime.fromisoformat(last_timestamp)
        current_time = datetime.now(timezone.utc)
        
        # Check if we need to refresh (more than 5 minutes old)
        if (current_time - last_timestamp).total_seconds() > 300:
            return jsonify({'needs_refresh': True})
            
        # Check for new alerts
        db = DatabaseManager()
        if db.connect():
            try:
                new_alerts = db.execute_query("""
                    SELECT COUNT(*) 
                    FROM alerts 
                    WHERE alert_time > %s
                """, (last_timestamp,))
                
                if new_alerts and new_alerts[0][0] > 0:
                    return jsonify({'needs_refresh': True})
                    
                return jsonify({'needs_refresh': False})
            finally:
                db.close()
                
        return jsonify({'error': 'Database connection error'}), 500
        
    except Exception as e:
        app.logger.error(f"Error checking dashboard updates: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/livelyageing/home')
@login_required
def home():
    """
    Render the home page with recent activity.
    """
    db = DatabaseManager()
    if db.connect():
        try:
            # Get recent users with their latest activity (only users with names AND valid tokens)
            recent_users = db.execute_query("""
                WITH LastUserInstance AS (
                    SELECT 
                        email,
                        MAX(created_at) as last_created
                    FROM users
                    GROUP BY email
                )
                SELECT u.id, u.name, u.email, 
                       MAX(d.date) as created_at
                FROM users u
                LEFT JOIN daily_summaries d ON u.id = d.user_id
                INNER JOIN LastUserInstance lui ON u.email = lui.email 
                    AND u.created_at = lui.last_created
                WHERE u.name != '' 
                    AND u.access_token IS NOT NULL 
                    AND u.refresh_token IS NOT NULL
                GROUP BY u.id, u.name, u.email
                ORDER BY created_at DESC NULLS LAST
                LIMIT 10
            """)
            
            # Convertir la fecha a datetime para evitar el error de tipo
            now = datetime.now()
            processed_users = []
            for user in recent_users:
                user_list = list(user)  # Convertir tupla a lista para poder modificar
                if user_list[3]:  # Si created_at no es None
                    # Convertir date a datetime usando datetime.combine
                    user_list[3] = datetime.combine(user_list[3], datetime.min.time())
                processed_users.append(tuple(user_list))  # Volver a convertir a tupla
            
            return render_template('home.html', recent_users=processed_users, now=now)
        except Exception as e:
            app.logger.error(f"Error fetching data for home page: {e}")
            return "Error: No se pudieron obtener los datos para la página de inicio.", 500
        finally:
            db.close()
    else:
        return "Error: No se pudo conectar a la base de datos.", 500

@app.route('/livelyageing/user_stats')
@login_required
def user_stats():
    """
    Display statistics for all users, organized into three categories:
    1. Active Users: Have name, tokens, and data
    2. Unassigned Users: Latest instance without name/tokens
    3. Historical Users: Previous instances with name and data
    """
    search = request.args.get('search', '').strip()
    
    db = DatabaseManager()
    if db.connect():
        try:
            # Obtener todos los usuarios con información relevante
            if search:
                users = db.execute_query("""
                    WITH UserInstances AS (
                        SELECT 
                            u.id,
                            u.name,
                            u.email,
                            u.created_at,
                            u.access_token IS NOT NULL AND u.refresh_token IS NOT NULL as has_tokens,
                            (SELECT MAX(date) FROM daily_summaries d WHERE d.user_id = u.id) as last_update,
                            EXISTS(SELECT 1 FROM daily_summaries d WHERE d.user_id = u.id) as has_data,
                            ROW_NUMBER() OVER (PARTITION BY u.email ORDER BY u.created_at DESC) as rn
                        FROM users u
                        WHERE LOWER(u.name) LIKE LOWER(%s) OR LOWER(u.email) LIKE LOWER(%s)
                    )
                    SELECT *
                    FROM UserInstances
                    ORDER BY email, created_at DESC
                """, (f"%{search}%", f"%{search}%"))
            else:
                users = db.execute_query("""
                    WITH UserInstances AS (
                        SELECT 
                            u.id,
                            u.name,
                            u.email,
                            u.created_at,
                            u.access_token IS NOT NULL AND u.refresh_token IS NOT NULL as has_tokens,
                            (SELECT MAX(date) FROM daily_summaries d WHERE d.user_id = u.id) as last_update,
                            EXISTS(SELECT 1 FROM daily_summaries d WHERE d.user_id = u.id) as has_data,
                            ROW_NUMBER() OVER (PARTITION BY u.email ORDER BY u.created_at DESC) as rn
                        FROM users u
                    )
                    SELECT *
                    FROM UserInstances
                    ORDER BY email, created_at DESC
                """)

            # Procesar los usuarios
            processed_users = []
            current_email = None
            
            for user in users:
                user_id, name, email, created_at, has_tokens, last_update, has_data, row_num = user
                
                # Es la instancia más reciente si row_num = 1
                is_latest = (row_num == 1)
                
                # Si cambiamos de email o es el primer usuario
                if email != current_email:
                    current_email = email
                
                # Determinar el estado del usuario
                if is_latest:
                    if not name:
                        # Si no tiene nombre, está sin asignar
                        status = 'unassigned'
                    elif not has_tokens:
                        # Si tiene nombre pero no tokens, está desvinculado
                        status = 'unlinked'
                    elif has_tokens and name:
                        # Si tiene nombre y tokens, está activo
                        status = 'active'
                else:
                    # Las instancias anteriores son históricas si tienen nombre y datos
                    status = 'historical'

                # Añadir el usuario si:
                # 1. Es la instancia más reciente, O
                # 2. Es una instancia histórica que tenía nombre y datos
                if is_latest or (name and has_data):
                    processed_users.append({
                        'id': user_id,
                        'name': name,
                        'email': email,
                        'created_at': created_at,
                        'last_update': last_update,
                        'has_tokens': has_tokens,
                        'has_data': has_data,
                        'is_latest': is_latest,
                        'status': status
                    })

            return render_template('user_stats.html', 
                                users=processed_users,
                                search=search,
                                now=datetime.now())
        except Exception as e:
            app.logger.error(f"Error fetching user statistics: {e}")
            return "Error: No se pudieron obtener las estadísticas de usuarios.", 500
        finally:
            db.close()
    else:
        return "Error: No se pudo conectar a la base de datos.", 500

# Route: Link a new Fitbit device
@app.route('/livelyageing/link', methods=['GET', 'POST'])
@login_required
def link_device():
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash('Please select an email.', 'danger')
            return redirect(url_for('link_device'))

        # Verificar si el correo tiene un nombre asignado
        db = DatabaseManager()
        if db.connect():
            user = db.get_user_by_email(email)
            if not user or not user[1]:  # Si no hay usuario o no tiene nombre asignado
                session['pending_email'] = email
                return redirect(url_for('assign_user'))
            else:
                session['pending_email'] = email
                session['new_user_name'] = user[1]  # Nombre ya asignado           
                return render_template('reassign_device.html', email=email, user_name=user[1])
        else:
            flash('Error de conexión a la base de datos.', 'danger')
            return redirect(url_for('link_device'))

    # GET request - mostrar formulario
    db = DatabaseManager()
    if not db.connect():
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('home'))

    try:
        emails = db.execute_query("SELECT DISTINCT email FROM users")
        return render_template('link_device.html', emails=[email[0] for email in emails])
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('home'))
    finally:
        db.close()

@app.route('/livelyageing/assign', methods=['GET', 'POST'])
@login_required
def assign_user():
    # Si viene el email por GET, lo guardamos en la sesión para preseleccionarlo
    if request.method == 'GET':
        email = request.args.get('email')
        if email:
            session['pending_email'] = email
    if request.method == 'POST':
        user_name = request.form.get('user_name')
        email = session.get('pending_email')  # Get email from session

        if not user_name:
            flash(_('Error: Missing user name.'), 'danger')
            return redirect(url_for('assign_user'))
            
        if not email:
            flash(_('Error: No email in session. Please start from device linking.'), 'danger')
            return redirect(url_for('link_device'))

        # Generar state y almacenarlo en la sesión
        session['state'] = generate_state()
        session['new_user_name'] = user_name
        session['code_verifier'] = generate_code_verifier()

        code_challenge = generate_code_challenge(session['code_verifier'])
        auth_url = generate_auth_url(code_challenge, session['state'])

        app.logger.info(f"Generated auth URL for {email}: {auth_url}")
        app.logger.info(f"Session state: {session['state']}")
        app.logger.info(f"Session code_verifier: {session['code_verifier']}")

        return render_template('link_auth.html', auth_url=auth_url)

    return render_template('assign_user.html')

@app.route('/livelyageing/callback')
@login_required
def callback():
    """
    Handle the callback from Fitbit after the user authorizes the app.
    This route captures the authorization code and exchanges it for access and refresh tokens.
    """
    app.logger.info("Callback route accessed")
    app.logger.info(f"Request args: {request.args}")
    app.logger.info(f"Request path: {request.path}")
    
    try:
        code = request.args.get('code')
        returned_state = request.args.get('state')
        stored_state = session.get('state')
        
        app.logger.info(f"Callback triggered with code: {code} and state: {returned_state}")
        app.logger.info(f"Stored state in session: {stored_state}")

        if returned_state != stored_state:
            app.logger.error("Invalid state parameter. Possible CSRF attack.")
            flash("Error: Invalid state parameter. Possible CSRF attack.", "danger")
            return redirect(url_for('link_device'))
        
        email = session.get('pending_email')
        new_user_name = session.get('new_user_name')
        code_verifier = session.get('code_verifier')
        
        if not all([email, new_user_name, code_verifier, code]):
            app.logger.error("Missing required session variables or authorization code")
            flash("Error: Missing required information. Please try again.", "danger")
            return redirect(url_for('link_device'))

        db = DatabaseManager()
        if db.connect():
            try:
                # Query to check if the email is already in use
                existing_user = db.get_user_by_email(email)

                if existing_user:
                    # Unpack the user data correctly
                    user_id, existing_name, existing_email, existing_access_token, existing_refresh_token = existing_user

                    # Flow 2: Reassign the device to a new user
                    if new_user_name:
                        if not existing_access_token or not existing_refresh_token:
                            if code:
                                try:
                                    access_token, refresh_token = get_tokens(code, code_verifier)
                                    if not access_token or not refresh_token:
                                        raise Exception("No se pudieron obtener los tokens de Fitbit")
                                    db.add_user(new_user_name, email, access_token, refresh_token)
                                    app.logger.info(f"Dispositivo reasignado a {new_user_name} ({email}) con nuevos tokens.")
                                except Exception as e:
                                    app.logger.error(f"Error obteniendo tokens de Fitbit: {e}")
                                    flash("Error: No se pudo obtener la autorización de Fitbit. Por favor, inténtalo de nuevo.", "danger")
                                    return redirect(url_for('link_device'))
                            else:
                                app.logger.error("Se requiere autorización para reasignar el dispositivo.")
                                flash("Error: Se requiere autorización para reasignar el dispositivo.", "danger")
                                return redirect(url_for('link_device'))
                        else:
                            db.add_user(new_user_name, email, existing_access_token, existing_refresh_token)
                            app.logger.info(f"Dispositivo reasignado a {new_user_name} ({email}) sin necesidad de reautorización.")
                    else:
                        app.logger.error("Se requiere un nombre de usuario para reasignar el dispositivo.")
                        flash("Error: Se requiere un nombre de usuario para reasignar el dispositivo.", "danger")
                        return redirect(url_for('assign_user'))
                else:
                    # Flow 1: Link a new email to a user
                    if new_user_name:
                        if code:
                            try:
                                access_token, refresh_token = get_tokens(code, code_verifier)
                                if not access_token or not refresh_token:
                                    raise Exception("No se pudieron obtener los tokens de Fitbit")
                                db.add_user(new_user_name, email, access_token, refresh_token)
                                app.logger.info(f"Nuevo usuario {new_user_name} ({email}) añadido.")
                            except Exception as e:
                                app.logger.error(f"Error obteniendo tokens de Fitbit: {e}")
                                flash("Error: No se pudo obtener la autorización de Fitbit. Por favor, inténtalo de nuevo.", "danger")
                                return redirect(url_for('link_device'))
                        else:
                            app.logger.error("Se requiere autorización para vincular un nuevo correo.")
                            flash("Error: Se requiere autorización para vincular un nuevo correo.", "danger")
                            return redirect(url_for('link_device'))
                    else:
                        app.logger.error("Se requiere un nombre de usuario para vincular un nuevo correo.")
                        flash("Error: Se requiere un nombre de usuario para vincular un nuevo correo.", "danger")
                        return redirect(url_for('assign_user'))

                # Clear the session data
                session.pop('pending_email', None)
                session.pop('new_user_name', None)
                session.pop('code_verifier', None)
                session.pop('state', None)

                return render_template('confirmation.html', user_name=new_user_name, email=email)
            except Exception as e:
                app.logger.error(f"Error during token exchange: {e}")
                flash(f"Error durante el intercambio de tokens: {e}", "danger")
                return redirect(url_for('link_device'))
            finally:
                db.close()
        else:
            app.logger.error("No se pudo conectar a la base de datos.")
            flash("Error: No se pudo conectar a la base de datos.", "danger")
            return redirect(url_for('link_device'))
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        flash(f"Error inesperado: {e}", "danger")
        return redirect(url_for('link_device'))

@app.route('/livelyageing/reassign', methods=['POST'])
@login_required
def reassign_device():
    """
    Handle the reassignment of a Fitbit device to a new user.
    """
    email = request.form['email']
    new_user_name = request.form['new_user_name']

    # Store the email and new user name in the session for later use
    session['pending_email'] = email
    session['new_user_name'] = new_user_name

    # Check if reauthorization is needed
    db = DatabaseManager()
    if db.connect():
        try:
            # Query to check if the email is already in use and has valid tokens
            existing_user = db.execute_query("SELECT access_token, refresh_token FROM users WHERE email = %s ORDER BY created_at DESC LIMIT 1", (email,))
            app.logger.info(f"Database query result for email {email}: {existing_user}")

            if existing_user:
                if len(existing_user[0]) != 2:
                    app.logger.error(f"Unexpected result structure: {existing_user}")
                    return "Error: Unexpected database result structure.", 500

                existing_access_token, existing_refresh_token = existing_user[0]
                if not existing_access_token or not existing_refresh_token:
                    # If tokens are missing, require reauthorization
                    code_verifier = generate_code_verifier()
                    code_challenge = generate_code_challenge(code_verifier)
                    state = generate_state()
                    auth_url = generate_auth_url(code_challenge, state)  # Generar auth_url correctamente
                    app.logger.info(f"Generated valid state: {state}")
                    app.logger.info(f"Generated code verifier: {code_verifier}")
                    app.logger.info(f"Generated code challenge: {code_challenge}")
                    app.logger.info(f"Generated auth URL: {auth_url}")
                    session['code_verifier'] = code_verifier
                    session['state'] = state
                    return render_template('link_auth.html', auth_url=auth_url)  # Pasar auth_url al template
                else:
                    # If tokens are valid, proceed to add the new user without reauthorization
                    db.add_user(new_user_name, email, existing_access_token, existing_refresh_token)
                    app.logger.info(f"Device reassigned to {new_user_name} ({email}) without reauthorization.")
                    return render_template('confirmation.html', user_name=new_user_name, email=email)
            else:
                app.logger.error(f"Email {email} is not in use.")
                return "Error: The email is not in use.", 400
        except Exception as e:
            app.logger.error(f"Unexpected error during reassignment: {e}")
            return f"Error: {e}", 500
        finally:
            db.close()
    else:
        app.logger.error("Failed to connect to the database.")
        return "Error: Could not connect to the database.", 500

# Template filters
@app.template_filter('number')
def format_number(value):
    """Format a number with thousands separator."""
    if value is None:
        return '-'
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return value

@app.template_filter('datetime')
def format_datetime(value):
    """Format a datetime value."""
    if value is None:
        return '-'
    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        elif isinstance(value, int):
            # Convert integer timestamp to datetime
            value = datetime.fromtimestamp(value)
        return value.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return value

def get_text(key):
    """Get the translation for a key in the current language."""
    lang = str(get_locale())
    # Split the key by dots to access nested dictionaries
    keys = key.split('.')
    value = TRANSLATIONS.get(lang, {}).get(keys[0], {})
    for k in keys[1:]:
        value = value.get(k, '')
    return value if value else key

@app.context_processor
def utility_processor():
    """Make translation function and static URL function available in templates."""
    def static_url(filename):
        """Generate full URL for static files."""
        # Use the complete path including /livelyageing prefix
        return url_for('static', filename=filename)
    return {
        'get_text': get_text,
        'current_language': get_locale,
        'static_url': static_url
    }

@app.route('/livelyageing/change_language')
def change_language():
    """Change the application language."""
    lang = request.args.get('lang', DEFAULT_LANGUAGE)
    if lang in LANGUAGES:
        session['language'] = lang
        
    # Get the referrer URL
    referrer = request.referrer
    if not referrer:
        return redirect(url_for('home'))
        
    # Parse the referrer URL to preserve existing query parameters
    from urllib.parse import urlparse, parse_qs, urlencode
    parsed = urlparse(referrer)
    params = parse_qs(parsed.query)
    
    # Update the lang parameter
    params['lang'] = [lang]
    
    # Reconstruct the URL with updated parameters
    new_query = urlencode(params, doseq=True)
    path = parsed.path
    
    return redirect(f"{path}?{new_query}")

@app.route('/livelyageing/refresh_data', methods=['POST'])
@login_required
def refresh_data():
    """
    Refresh Fitbit data for all users.
    """
    try:
        # Get all unique emails from the database
        db = DatabaseManager()
        if not db.connect():
            return jsonify({'error': 'Database connection error'}), 500
            
        try:
            emails = db.execute_query("SELECT DISTINCT email FROM users")
        finally:
            db.close()

        # Process each email to fetch new data
        from fitbit import process_emails
        from fitbit_intraday import process_emails as process_intraday_emails
        
        # Process daily data
        process_emails(emails)
        # Process intraday data
        process_intraday_emails(emails)
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error refreshing data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/livelyageing/api/daily_summary')
@login_required
def get_daily_summary():
    """
    Obtiene el resumen diario más reciente del usuario actual.
    """
    try:
        user_id = get_user_id_by_email(current_user.email)
        if not user_id:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        # Obtener el resumen más reciente
        summaries = get_daily_summaries(
            user_id=user_id,
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now()
        )

        if not summaries:
            return jsonify({'error': 'No hay datos disponibles'}), 404

        latest_summary = summaries[-1]
        
        return jsonify({
            'steps': latest_summary[3],
            'heart_rate': latest_summary[4],
            'sleep_minutes': latest_summary[5],
            'calories': latest_summary[6],
            'distance': latest_summary[7],
            'floors': latest_summary[8],
            'elevation': latest_summary[9],
            'active_minutes': latest_summary[10],
            'sedentary_minutes': latest_summary[11],
            'nutrition_calories': latest_summary[12],
            'water': latest_summary[13],
            'weight': latest_summary[14],
            'bmi': latest_summary[15],
            'fat': latest_summary[16],
            'oxygen_saturation': latest_summary[17],
            'respiratory_rate': latest_summary[18],
            'temperature': latest_summary[19]
        })

    except Exception as e:
        app.logger.error(f"Error al obtener el resumen diario: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/livelyageing/api/alerts')
@login_required
def get_user_alerts_api():
    """
    Obtiene las alertas más recientes del usuario actual.
    """
    try:
        user_id = get_user_id_by_email(current_user.email)
        if not user_id:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        # Obtener alertas de las últimas 24 horas
        alerts = get_user_alerts(
            user_id=user_id,
            start_time=datetime.now() - timedelta(hours=24),
            end_time=datetime.now(),
            acknowledged=False
        )

        return jsonify([{
            'id': alert[0],
            'time': alert[1].isoformat(),
            'type': alert[3],
            'priority': alert[4],
            'triggering_value': alert[5],
            'threshold_value': alert[6],
            'details': alert[7]
        } for alert in alerts])

    except Exception as e:
        app.logger.error(f"Error al obtener las alertas: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/livelyageing/dashboard/alerts')
@login_required
def alerts_dashboard():
    try:
        # Check if we have preloaded data in the session
        if 'dashboard_data' in session:
            dashboard_data = session['dashboard_data']
            # Clear the session data after using it
            session.pop('dashboard_data', None)
            return render_template('alerts_dashboard.html', 
                                daily_summaries=dashboard_data['daily_summaries'],
                                intraday_metrics=dashboard_data['intraday_metrics'],
                                sleep_logs=dashboard_data['sleep_logs'],
                                filters_dict=dashboard_data['filters_dict'],
                                alerts=dashboard_data['alerts'],
                                now=datetime.now(timezone.utc))

        # If no preloaded data, fetch it from the database
        db = DatabaseManager()
        if not db.connect():
            app.logger.error("No se pudo conectar a la base de datos")
            return jsonify({'error': 'Database connection error'}), 500

        # Obtener parámetros de filtrado
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        priority = request.args.get('priority')
        acknowledged = request.args.get('acknowledged')
        user_query = request.args.get('user_query')
        alert_type = request.args.get('alert_type')
        urgent_only = request.args.get('urgent_only') == 'on'
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Número de alertas por página

        app.logger.info(f"Parámetros de filtrado: date_from={date_from}, date_to={date_to}, priority={priority}, acknowledged={acknowledged}, user_query={user_query}, alert_type={alert_type}, urgent_only={urgent_only}")

        # Crear diccionario de filtros para la paginación
        filters_dict = {}
        if date_from:
            filters_dict['date_from'] = date_from
        if date_to:
            filters_dict['date_to'] = date_to
        if priority:
            filters_dict['priority'] = priority
        if acknowledged is not None and acknowledged != '':
            filters_dict['acknowledged'] = acknowledged
        if user_query:
            filters_dict['user_query'] = user_query
        if alert_type:
            filters_dict['alert_type'] = alert_type
        if urgent_only:
            filters_dict['urgent_only'] = 'on'

        # Construir la consulta base
        query = """
            SELECT 
                a.id,
                a.alert_time,
                a.user_id,
                a.alert_type,
                a.priority,
                a.triggering_value,
                a.threshold_value,
                a.details,
                a.acknowledged,
                u.name AS user_name, 
                u.email AS user_email
            FROM alerts a
            JOIN users u ON a.user_id = u.id
            WHERE 1=1
        """
        params = []

        # Aplicar filtros
        if date_from:
            query += " AND a.alert_time >= %s"
            params.append(f"{date_from} 00:00:00")
        if date_to:
            query += " AND a.alert_time <= %s"
            params.append(f"{date_to} 23:59:59")
        if priority:
            query += " AND a.priority = %s"
            params.append(priority)
        if acknowledged is not None and acknowledged != '':
            query += " AND a.acknowledged = %s"
            params.append(acknowledged == 'true')
        if user_query:
            query += " AND (LOWER(u.name) LIKE LOWER(%s) OR LOWER(u.email) LIKE LOWER(%s))"
            search_term = f"%{user_query}%"
            params.extend([search_term, search_term])
        if alert_type:
            query += " AND a.alert_type LIKE %s"
            params.append(f"%{alert_type}%")
        if urgent_only:
            query += " AND a.acknowledged = FALSE AND a.alert_time <= NOW() - INTERVAL '24 hours'"

        # Ordenar por prioridad y fecha descendente
        query += " ORDER BY CASE a.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END, a.alert_time DESC"

        app.logger.info(f"Query: {query}")
        app.logger.info(f"Params: {params}")


        try:
            # Obtener el total de alertas para la paginación
            count_query = f"SELECT COUNT(*) FROM ({query}) AS count_query"
            total = db.execute_query(count_query, params)[0][0]
            app.logger.info(f"Total de alertas encontradas: {total}")

            # Obtener el total de alertas por prioridad y no reconocidas (sin paginación)
            count_priority_query = f"""
                SELECT 
                    SUM(CASE WHEN a.priority = 'high' THEN 1 ELSE 0 END) AS high,
                    SUM(CASE WHEN a.priority = 'medium' THEN 1 ELSE 0 END) AS medium,
                    SUM(CASE WHEN a.priority = 'low' THEN 1 ELSE 0 END) AS low,
                    SUM(CASE WHEN a.acknowledged = FALSE THEN 1 ELSE 0 END) AS unacknowledged
                FROM ({query}) AS a
            """
            alert_counts_result = db.execute_query(count_priority_query, params)[0]
            alert_counts = {
                'high': alert_counts_result[0] or 0,
                'medium': alert_counts_result[1] or 0,
                'low': alert_counts_result[2] or 0,
                'unacknowledged': alert_counts_result[3] or 0
            }

            # Aplicar paginación
            query += " LIMIT %s OFFSET %s"
            params.extend([per_page, (page - 1) * per_page])

            # Ejecutar la consulta
            alerts_data = db.execute_query(query, params)
            app.logger.info(f"Alertas obtenidas: {len(alerts_data) if alerts_data else 0}")

            if not alerts_data:
                app.logger.warning("No se encontraron alertas con los filtros actuales")
                return render_template('alerts_dashboard.html', 
                                    alerts=[], 
                                    pagination=None,
                                    filters_dict=filters_dict,
                                    now=datetime.now(timezone.utc),
                                    alert_counts=alert_counts)

            # Convertir las tuplas en diccionarios con nombres de atributos
            import json  # <--- Añadido para parsear JSON
            alerts = []
            for alert in alerts_data:
                try:
                    # Obtener datos intradía para la alerta
                    intraday_data = {}
                    alert_type = alert[3]
                    base_alert_type = alert_type.split('_')[0] if '_' in alert_type else alert_type

                    # Mapear base_alert_type a la métrica real de intradía
                    intraday_metric_type = None
                    if base_alert_type == 'heart':
                        intraday_metric_type = 'heart_rate'
                    elif base_alert_type == 'activity':
                        # Solo mostrar pasos si el motivo es pasos
                        if alert[7] and 'pasos' in alert[7].lower():
                            intraday_metric_type = 'steps'
                            app.logger.info(f"Alerta {alert[0]}: activity_drop causada por pasos, se buscarán datos intradía de steps.")
                        else:
                            app.logger.info(f"Alerta {alert[0]}: activity_drop NO causada por pasos, no se mostrarán datos intradía.")
                    elif base_alert_type in ['steps', 'calories', 'active_zone_minutes']:
                        intraday_metric_type = base_alert_type
                    elif base_alert_type == 'intraday':
                        # Para alertas de intraday_activity_drop, siempre mostrar datos de pasos
                        intraday_metric_type = 'steps'
                        app.logger.info(f"Alerta {alert[0]}: {alert_type}, se buscarán datos intradía de steps.")

                    if intraday_metric_type:
                        start_time = alert[1] - timedelta(hours=24)
                        end_time = alert[1]
                        app.logger.info(f"Alerta {alert[0]}: buscando datos intradía de {intraday_metric_type} para user_id={alert[2]} entre {start_time} y {end_time}")
                        intraday_metrics = db.execute_query("""
                            SELECT time, value 
                            FROM intraday_metrics 
                            WHERE user_id = %s 
                            AND type = %s 
                            AND time BETWEEN %s AND %s 
                            ORDER BY time
                        """, (alert[2], intraday_metric_type, start_time, end_time))
                        app.logger.info(f"Alerta {alert[0]}: encontrados {len(intraday_metrics) if intraday_metrics else 0} datos intradía de {intraday_metric_type}")
                        if intraday_metrics:
                            intraday_data = {
                                'times': [m[0].strftime('%H:%M') for m in intraday_metrics],
                                'values': [float(m[1]) for m in intraday_metrics]
                            }
                            app.logger.info(f"Datos intradía obtenidos para {intraday_metric_type}: {len(intraday_metrics)} registros")
                        else:
                            app.logger.info(f"No se encontraron datos intradía para {intraday_metric_type}")

                    # Construir el diccionario de la alerta
                    alert_dict = {
                        'id': alert[0],
                        'alert_time': alert[1].strftime('%Y-%m-%d %H:%M'),
                        'raw_alert_time': alert[1],
                        'user_id': alert[2],
                        'alert_type': alert[3],
                        'priority': alert[4],
                        'triggering_value': alert[5],
                        'threshold_value': alert[6],
                        'details': alert[7],
                        'acknowledged': alert[8],
                        'user_name': alert[9],
                        'user_email': alert[10],
                        'intraday_data': intraday_data
                    }

                    # Si es heart_rate_anomaly, calcular y añadir el rango anómalo
                    if alert[3]:
                        app.logger.info(f"DEBUG ALERT: id={alert[0]}, alert_type={alert[3]}")
                        if str(alert[3]).strip().lower() == 'heart_rate_anomaly':
                            app.logger.info(f"DEBUG: Procesando heart_rate_anomaly para alerta id={alert[0]}")
                            import json, re
                            mean = None
                            std_dev = None
                            threshold_de = None
                            upper_bound = None
                            lower_bound = None
                            details_raw = alert[7]
                            details_obj = None
                            app.logger.info(f"DEBUG: details_raw={details_raw}")
                            # 1. Intentar JSON
                            if isinstance(details_raw, str):
                                try:
                                    details_obj = json.loads(details_raw)
                                    app.logger.info(f"DEBUG: details_obj (parsed)={details_obj}")
                                except Exception as e:
                                    app.logger.warning(f"DEBUG: Error parseando details_raw: {e}")
                                    details_obj = None
                            elif isinstance(details_raw, dict):
                                details_obj = details_raw
                                app.logger.info(f"DEBUG: details_obj (dict)={details_obj}")
                            # 2. Si es JSON válido, usarlo
                            if details_obj and isinstance(details_obj, dict):
                                mean = float(details_obj.get('mean', 0))
                                std_dev = float(details_obj.get('std_dev', 0))
                                threshold_de = float(details_obj.get('threshold', 0))
                                app.logger.info(f"DEBUG: mean={mean}, std_dev={std_dev}, threshold_de={threshold_de}")
                                if mean is not None and std_dev is not None and threshold_de is not None and std_dev != 0:
                                    upper_bound = mean + threshold_de * std_dev
                                    lower_bound = mean - threshold_de * std_dev
                            # 3. Si no hay JSON, intentar extraer del string (>X o <Y)
                            if (upper_bound is None or lower_bound is None) and isinstance(details_raw, str):
                                match = re.search(r">\s*([\d\.]+)\s*o\s*<\s*([\d\.]+)", details_raw)
                                if match:
                                    upper_bound = float(match.group(1))
                                    lower_bound = float(match.group(2))
                                    app.logger.info(f"DEBUG: Extraído del string: upper_bound={upper_bound}, lower_bound={lower_bound}")
                            if upper_bound is not None and lower_bound is not None:
                                alert_dict['hr_upper_bound'] = upper_bound
                                alert_dict['hr_lower_bound'] = lower_bound

                    # --- Solución al problema de details ---
                    if isinstance(alert_dict['details'], str):
                        try:
                            details_obj = json.loads(alert_dict['details'])
                            if isinstance(details_obj, dict):
                                alert_dict['details'] = details_obj
                        except Exception:
                            pass  # Si no es un JSON válido, lo dejamos como está

                    alerts.append(alert_dict)
                except Exception as e:
                    app.logger.error(f"Error procesando alerta: {e}")
                    continue

            app.logger.info(f"Alertas procesadas: {len(alerts)}")

            # Crear objeto de paginación
            pagination = {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page,
                'has_prev': page > 1,
                'has_next': page * per_page < total,
                'prev_num': page - 1,
                'next_num': page + 1,
                'iter_pages': lambda: range(1, ((total + per_page - 1) // per_page) + 1)
            }

            # Asegurarse de que now sea timezone-aware
            now = datetime.now(timezone.utc)

            return render_template('alerts_dashboard.html', 
                                alerts=alerts, 
                                pagination=pagination, 
                                filters_dict=filters_dict,
                                now=now,
                                alert_counts=alert_counts)

        except Exception as e:
            app.logger.error(f"Error en la consulta SQL: {e}")
            return render_template('alerts_dashboard.html', 
                                alerts=[], 
                                pagination=None,
                                filters_dict=filters_dict,
                                now=datetime.now(timezone.utc))

    except Exception as e:
        app.logger.error(f"Error al cargar el dashboard de alertas: {e}")
        return render_template('alerts_dashboard.html', 
                            alerts=[], 
                            pagination=None,
                            filters_dict={},
                            now=datetime.now(timezone.utc))

@app.route('/livelyageing/api/alerts/<int:alert_id>')
@login_required
def get_alert_details(alert_id):
    try:
        db = DatabaseManager()
        if not db.connect():
            return jsonify({'error': 'Database connection error'}), 500

        # Obtener detalles de la alerta
        query = """
            SELECT 
                a.id,
                a.alert_time,
                a.user_id,
                a.alert_type,
                a.priority,
                a.triggering_value,
                a.threshold_value,
                a.details,
                a.acknowledged,
                u.name AS user_name, 
                u.email AS user_email
            FROM alerts a
            JOIN users u ON a.user_id = u.id
            WHERE a.id = %s
        """
        result = db.execute_query(query, [alert_id])
        
        if not result:
            return jsonify({'error': 'Alerta no encontrada'}), 404

        alert = {
            'id': result[0][0],
            'alert_time': result[0][1].isoformat(),
            'user_id': result[0][2],
            'alert_type': result[0][3],
            'priority': result[0][4],
            'triggering_value': result[0][5],
            'threshold_value': result[0][6],
            'details': result[0][7],
            'acknowledged': result[0][8],
            'user_name': result[0][9],
            'user_email': result[0][10]
        }

        return jsonify(alert)

    except Exception as e:
        app.logger.error(f"Error al obtener detalles de la alerta: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/livelyageing/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge_alert(alert_id):
    try:
        db = DatabaseManager()
        if not db.connect():
            return jsonify({'success': False, 'error': 'Error de conexión a la base de datos'}), 500

        try:
            # Verificar si la alerta existe y no está reconocida
            check_query = "SELECT acknowledged FROM alerts WHERE id = %s"
            result = db.execute_query(check_query, [alert_id])
            
            if not result:
                return jsonify({'success': False, 'error': 'Alerta no encontrada'}), 404
                
            if result[0][0]:
                return jsonify({'success': False, 'error': 'La alerta ya está reconocida'}), 400
                
            # Actualizar solo el campo acknowledged
            db.execute_query("""
                UPDATE alerts 
                SET acknowledged = TRUE
                WHERE id = %s
            """, [alert_id])
                
            return jsonify({'success': True})
            
        finally:
            db.close()
            
    except Exception as e:
        app.logger.error(f"Error al reconocer alerta: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/livelyageing/user/<int:user_id>')
@login_required
def user_detail(user_id):
    """
    Renderiza la ficha de usuario con la información básica y datos recientes.
    El resto de datos se cargan vía AJAX.
    """
    db = DatabaseManager()
    if not db.connect():
        return "Error: No se pudo conectar a la base de datos.", 500
    try:
        # Obtener datos básicos del usuario
        user_data = db.execute_query(
            """
            SELECT id, name, email, created_at, 
                   access_token, refresh_token,
                   EXTRACT(YEAR FROM AGE(CURRENT_DATE, created_at)) as age
            FROM users 
            WHERE id = %s
            """, (user_id,)
        )
        if not user_data:
            return "Usuario no encontrado", 404
            
        # Convertir la tupla en un diccionario
        user = {
            'id': user_data[0][0],
            'name': user_data[0][1],
            'email': user_data[0][2],
            'created_at': user_data[0][3],
            'access_token': user_data[0][4],
            'refresh_token': user_data[0][5],
            'age': int(user_data[0][6]) if user_data[0][6] else None
        }
        
        # Obtener el último resumen diario para datos actuales
        latest_summary = db.execute_query(
            """
            SELECT * FROM daily_summaries 
            WHERE user_id = %s 
            ORDER BY date DESC 
            LIMIT 1
            """, (user_id,)
        )
        last_update_datetime = None
        if latest_summary:
            columns = [desc[0] for desc in db.cursor.description]
            latest_summary = dict(zip(columns, latest_summary[0]))
            last_update_datetime = datetime.combine(latest_summary['date'], time(23, 59))
        else:
            last_update_datetime = None
        
        # Obtener alertas recientes no reconocidas
        recent_alerts = db.execute_query(
            """
            SELECT * FROM alerts 
            WHERE user_id = %s 
            AND alert_time >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY alert_time DESC
            """, (user_id,)
        )
        
        # Convertir las alertas en diccionarios
        if recent_alerts:
            alert_columns = [desc[0] for desc in db.cursor.description]
            recent_alerts = [dict(zip(alert_columns, alert)) for alert in recent_alerts]
            
            # Procesar alertas activas para los indicadores visuales
            alerts = {
                'activity_drop': False,
                'heart_rate_anomaly': False,
                'sleep_duration_change': False,
                'sedentary_increase': False
            }
            
            for alert in recent_alerts:
                if not alert['acknowledged'] and alert['alert_time'].date() == datetime.now().date():
                    alert_type = alert['alert_type']
                    if alert_type in alerts:
                        alerts[alert_type] = True
        else:
            alerts = {
                'activity_drop': False,
                'heart_rate_anomaly': False,
                'sleep_duration_change': False,
                'sedentary_increase': False
            }
        
        return render_template('user_detail.html', 
                             user=user,
                             latest_summary=latest_summary,
                             recent_alerts=recent_alerts,
                             alerts=alerts,
                             now=datetime.now(),
                             last_update_datetime=last_update_datetime)
    except Exception as e:
        app.logger.error(f"Error al cargar la ficha de usuario: {e}")
        return "Error interno del servidor", 500
    finally:
        db.close()

@app.route('/livelyageing/api/user/<int:user_id>/daily_summary')
@login_required
def api_user_daily_summary(user_id):
    """
    Devuelve el resumen diario para un usuario y una fecha (por defecto hoy).
    """
    date_str = request.args.get('date')
    if date_str:
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return jsonify({'error': 'Formato de fecha inválido'}), 400
    else:
        date = datetime.now().date()
    db = DatabaseManager()
    if not db.connect():
        return jsonify({'error': 'DB error'}), 500
    try:
        summary = db.execute_query(
            """
            SELECT 
                date,
                steps,
                heart_rate,
                sleep_minutes,
                calories,
                distance,
                floors,
                elevation,
                active_minutes,
                sedentary_minutes,
                nutrition_calories,
                water,
                weight,
                bmi,
                fat,
                oxygen_saturation,
                respiratory_rate,
                temperature
            FROM daily_summaries 
            WHERE user_id = %s AND date = %s
            """, (user_id, date)
        )
        if not summary:
            return jsonify({'error': 'No hay datos para ese día'}), 404
        # Mapear los campos a nombres legibles
        columns = [desc[0] for desc in db.cursor.description]
        summary_dict = dict(zip(columns, summary[0]))
        # Calcular valores adicionales
        if summary_dict.get('sleep_minutes'):
            summary_dict['sleep_hours'] = round(summary_dict['sleep_minutes'] / 60, 1)
        if summary_dict.get('sedentary_minutes'):
            summary_dict['sedentary_hours'] = round(summary_dict['sedentary_minutes'] / 60, 1)
        return jsonify({'summary': summary_dict})
    finally:
        db.close()

@app.route('/livelyageing/api/user/<int:user_id>/intraday')
@login_required
def api_user_intraday(user_id):
    """
    Devuelve los datos intradía para un usuario, fecha y tipo de métrica.
    """
    date_str = request.args.get('date')
    metric_type = request.args.get('type')
    if not metric_type:
        return jsonify({'error': 'Falta el tipo de métrica'}), 400
    if date_str:
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return jsonify({'error': 'Formato de fecha inválido'}), 400
    else:
        date = datetime.now().date()
    db = DatabaseManager()
    if not db.connect():
        return jsonify({'error': 'DB error'}), 500
    try:
        start_time = datetime.combine(date, datetime.min.time())
        end_time = datetime.combine(date, datetime.max.time())
        data = db.execute_query(
            """
            SELECT time, value 
            FROM intraday_metrics 
            WHERE user_id = %s 
            AND type = %s 
            AND time BETWEEN %s AND %s 
            ORDER BY time
            """, (user_id, metric_type, start_time, end_time)
        )
        return jsonify({
            'intraday': [
                {
                    'time': row[0].strftime('%H:%M'),
                    'value': float(row[1])
                } for row in data
            ]
        })
    finally:
        db.close()

@app.route('/livelyageing/api/user/<int:user_id>/weekly_summary')
@login_required
def api_user_weekly_summary(user_id):
    """
    Devuelve los resúmenes diarios de los últimos 7 días para el usuario.
    """
    db = DatabaseManager()
    if not db.connect():
        return jsonify({'error': 'DB error'}), 500
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=6)
        data = db.execute_query(
            """
            SELECT 
                date,
                steps,
                heart_rate,
                sleep_minutes,
                calories,
                sedentary_minutes,
                active_minutes,
                distance,
                floors,
                elevation,
                nutrition_calories,
                water,
                weight,
                bmi,
                fat,
                oxygen_saturation,
                respiratory_rate,
                temperature
            FROM daily_summaries 
            WHERE user_id = %s 
            AND date BETWEEN %s AND %s 
            ORDER BY date DESC
            """, (user_id, start_date, end_date)
        )
        return jsonify({
            'weekly': [
                {
                    'date': row[0].strftime('%d/%m'),
                    'steps': row[1],
                    'heart_rate': row[2],
                    'sleep_hours': round(row[3] / 60, 1) if row[3] else None,
                    'calories': row[4],
                    'sedentary_hours': round(row[5] / 60, 1) if row[5] else None,
                    'active_minutes': row[6],
                    'distance': row[7],
                    'floors': row[8],
                    'elevation': row[9],
                    'nutrition_calories': row[10],
                    'water': row[11],
                    'weight': row[12],
                    'bmi': row[13],
                    'fat': row[14],
                    'oxygen_saturation': row[15],
                    'respiratory_rate': row[16],
                    'temperature': row[17]
                } for row in data
            ]
        })
    finally:
        db.close()

@app.route('/livelyageing/api/user/<int:user_id>/alerts')
@login_required
def api_user_alerts(user_id):
    """
    Devuelve las alertas de los últimos 7 días para el usuario.
    """
    db = DatabaseManager()
    if not db.connect():
        return jsonify({'error': 'DB error'}), 500
    try:
        since = datetime.now() - timedelta(days=7)
        data = db.execute_query(
            """
            SELECT 
                alert_time,
                alert_type,
                priority,
                triggering_value,
                threshold_value,
                details,
                acknowledged
            FROM alerts 
            WHERE user_id = %s 
            AND alert_time >= %s 
            ORDER BY alert_time DESC
            """, (user_id, since)
        )
        
        return jsonify({
            'alerts': [
                {
                    'alert_time': row[0].strftime('%d/%m %H:%M'),
                    'type': row[1],
                    'priority': row[2],
                    'triggering_value': row[3],
                    'threshold_value': row[4],
                    'details': row[5],
                    'acknowledged': row[6]
                } for row in data
            ]
        })
    finally:
        db.close()

@app.route('/livelyageing/dashboard/alerts/export')
@login_required
def export_alerts():
    import csv
    from io import StringIO
    db = DatabaseManager()
    if not db.connect():
        return "Error de conexión a la base de datos", 500
    try:
        # Obtener filtros igual que en alerts_dashboard
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        priority = request.args.get('priority')
        acknowledged = request.args.get('acknowledged')
        user_query = request.args.get('user_query')
        # Construir la consulta base
        query = """
            SELECT 
                a.alert_time,
                u.name AS user_name,
                u.email AS user_email,
                a.alert_type,
                a.priority,
                a.triggering_value,
                a.threshold_value,
                a.details,
                a.acknowledged
            FROM alerts a
            JOIN users u ON a.user_id = u.id
            WHERE 1=1
        """
        params = []
        if date_from:
            query += " AND a.alert_time >= %s"
            params.append(f"{date_from} 00:00:00")
        if date_to:
            query += " AND a.alert_time <= %s"
            params.append(f"{date_to} 23:59:59")
        if priority:
            query += " AND a.priority = %s"
            params.append(priority)
        if acknowledged is not None and acknowledged != '':
            query += " AND a.acknowledged = %s"
            params.append(acknowledged == 'true')
        if user_query:
            query += " AND (LOWER(u.name) LIKE LOWER(%s) OR LOWER(u.email) LIKE LOWER(%s))"
            search_term = f"%{user_query}%"
            params.extend([search_term, search_term])
        query += " ORDER BY a.alert_time DESC"
        alerts = db.execute_query(query, params)
        # Crear CSV con BOM UTF-8 para compatibilidad con Excel
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(["Fecha/Hora", "Usuario", "Email", "Tipo de Alerta", "Prioridad", "Valor Disparador", "Umbral", "Detalles", "Reconocida"])
        for a in alerts:
            cw.writerow([
                a[0].strftime('%Y-%m-%d %H:%M'),
                a[1], a[2], a[3], a[4], a[5], a[6], a[7], "Sí" if a[8] else "No"
            ])
        output = '\ufeff' + si.getvalue()  # Añadir BOM UTF-8
        si.close()
        fecha = datetime.now().strftime('%Y%m%d')
        return Response(
            output,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment;filename=alertas_{fecha}.csv"}
        )
    finally:
        db.close()

@app.route('/livelyageing/user/<int:user_id>/export_alerts')
@login_required
def export_user_alerts(user_id):
    import csv
    from io import StringIO
    db = DatabaseManager()
    if not db.connect():
        return "Error de conexión a la base de datos", 500
    try:
        since = datetime.now() - timedelta(days=7)
        query = """
            SELECT 
                a.alert_time,
                u.name AS user_name,
                u.email AS user_email,
                a.alert_type,
                a.priority,
                a.triggering_value,
                a.threshold_value,
                a.details,
                a.acknowledged
            FROM alerts a
            JOIN users u ON a.user_id = u.id
            WHERE a.user_id = %s AND a.alert_time >= %s
            ORDER BY a.alert_time DESC
        """
        alerts = db.execute_query(query, (user_id, since))
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(["Fecha/Hora", "Usuario", "Email", "Tipo de Alerta", "Prioridad", "Valor Disparador", "Umbral", "Detalles", "Reconocida"])
        for a in alerts:
            cw.writerow([
                a[0].strftime('%Y-%m-%d %H:%M'),
                a[1], a[2], a[3], a[4], a[5], a[6], a[7], "Sí" if a[8] else "No"
            ])
        output = '\ufeff' + si.getvalue()
        si.close()
        fecha = datetime.now().strftime('%Y%m%d')
        return Response(
            output,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment;filename=alertas_usuario_{user_id}_{fecha}.csv"}
        )
    finally:
        db.close()

@app.route('/livelyageing/user/<int:user_id>/export_intraday')
@login_required
def export_user_intraday(user_id):
    import csv
    from io import StringIO
    db = DatabaseManager()
    if not db.connect():
        return "Error de conexión a la base de datos", 500
    try:
        # Obtener fechas y métricas seleccionadas
        dates = request.args.getlist('dates')
        metrics = request.args.getlist('metrics')
        if not dates or not metrics:
            return "Debe seleccionar al menos una fecha y una métrica", 400
        # Preparar consulta
        rows = []
        for date_str in dates:
            for metric in metrics:
                start_time = datetime.strptime(date_str, "%Y-%m-%d")
                end_time = start_time + timedelta(days=1)
                query = """
                    SELECT time, type, value
                    FROM intraday_metrics
                    WHERE user_id = %s AND type = %s AND time >= %s AND time < %s
                    ORDER BY time
                """
                data = db.execute_query(query, (user_id, metric, start_time, end_time))
                for row in data:
                    rows.append((row[0].date().strftime('%Y-%m-%d'), row[0].strftime('%H:%M'), row[1], row[2]))
        # Crear CSV
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(["Fecha", "Hora", "Métrica", "Valor"])
        for r in rows:
            cw.writerow(r)
        output = '\ufeff' + si.getvalue()
        si.close()
        fecha = datetime.now().strftime('%Y%m%d')
        return Response(
            output,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment;filename=intradia_usuario_{user_id}_{fecha}.csv"}
        )
    finally:
        db.close()

@app.route('/livelyageing/unlink_user', methods=['POST'])
@login_required
def unlink_user():
    """
    Handles unlinking a user from their Fitbit device.
    When unlinking:
    1. The original instance is preserved with its name and data (becomes historical)
    2. A new instance is created with the same email but no name/tokens (becomes unassigned)
    """
    user_id = request.form.get('user_id')
    if not user_id:
        flash('ID de usuario no proporcionado', 'danger')
        return redirect(url_for('user_stats'))

    db = DatabaseManager()
    if db.connect():
        try:
            # First, get the email of the user being unlinked
            user_email = db.execute_query("""
                SELECT email FROM users WHERE id = %s
            """, (user_id,))
            
            if not user_email:
                flash('Usuario no encontrado', 'danger')
                return redirect(url_for('user_stats'))
                
            email = user_email[0][0]
            
            # Start a transaction
            db.execute_query("BEGIN")
            
            try:
                # 1. Create a new unassigned instance with the same email
                db.execute_query("""
                    INSERT INTO users (name, email, access_token, refresh_token)
                    VALUES ('', %s, NULL, NULL)
                """, (email,))
                
                # 2. Remove tokens from the original instance (but keep name and data)
                db.execute_query("""
                    UPDATE users 
                    SET access_token = NULL, 
                        refresh_token = NULL
                    WHERE id = %s
                """, (user_id,))
                
                # Commit the transaction
                db.execute_query("COMMIT")
                
                flash('Dispositivo desvinculado correctamente. El usuario y sus datos históricos se mantienen.', 'success')
            except Exception as e:
                # If anything fails, rollback the transaction
                db.execute_query("ROLLBACK")
                app.logger.error(f"Error en la transacción de desvincular: {e}")
                flash('Error al desvincular usuario', 'danger')
                raise
                
        except Exception as e:
            app.logger.error(f"Error desvinculando usuario: {e}")
            flash('Error al desvincular usuario', 'danger')
        finally:
            db.close()
    else:
        flash('Error de conexión a la base de datos', 'danger')
    
    return redirect(url_for('user_stats'))

@app.route('/livelyageing/debug_static')
def debug_static():
    """Temporary route to debug static file URLs"""
    style_url = url_for('static', filename='css/style.css', _external=True)
    styles_url = url_for('static', filename='css/styles.css', _external=True)
    app.logger.info(f"style.css URL: {style_url}")
    app.logger.info(f"styles.css URL: {styles_url}")
    return {
        'style_url': style_url,
        'styles_url': styles_url
    }

@app.route('/livelyageing/add_email', methods=['GET', 'POST'])
@login_required
def add_email():
    """
    Handle adding a new email to the system.
    """
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash(_('Please provide an email address.'), 'danger')
            return redirect(url_for('add_email'))

        db = DatabaseManager()
        if not db.connect():
            flash(_('Database connection error.'), 'danger')
            return redirect(url_for('add_email'))

        try:
            # Check if email already exists
            existing_user = db.get_user_by_email(email)
            if existing_user:
                flash(_('This email is already registered in the system.'), 'warning')
                return redirect(url_for('add_email'))

            # Add the email to the database without tokens (they'll be added during linking)
            db.add_user(name="", email=email)
            flash(_('Email added successfully. You can now link a device to it.'), 'success')
            return redirect(url_for('link_device'))

        except Exception as e:
            app.logger.error(f"Error adding email: {e}")
            flash(_('An error occurred while adding the email.'), 'danger')
            return redirect(url_for('add_email'))
        finally:
            db.close()

    return render_template('add_email.html')

# Run the Flask app
if __name__ == '__main__':
    # app.run(host=HOST, port=PORT, debug=DEBUG)
    app.run(debug=True)
