from logging.handlers import RotatingFileHandler
from flask import Flask, logging, render_template, request, redirect, session, url_for, flash
from auth import generate_state, get_tokens, generate_code_verifier, generate_code_challenge, generate_auth_url
from db import connect_to_db, add_user
from config import CLIENT_ID, REDIRECT_URI
import os
from flask_login import current_user, login_user, logout_user, login_required
from flask_login import LoginManager, UserMixin
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
# Obtener el modo de ejecución
FLASK_ENV = os.getenv('FLASK_ENV', 'development')  # Por defecto, modo desarrollo
USERNAME = os.getenv('log_USERNAME')  
PASSWORD = os.getenv('PASSWORD')


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
        return redirect(url_for('index'))  # Si ya está autenticado, redirige al inicio

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
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos')
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
    Redirect from root URL to the dashboard.
    """
    return redirect(url_for('index'))

# Route: Homepage (Dashboard)
@app.route('/livelyageing/')
@login_required
def index():
    """
    Render the dashboard homepage.
    This will display the Fitbit data stored in the database.
    """
    # Fetch data from the database
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cur:
                # Get the latest daily summary for each user
                cur.execute("""
                    SELECT u.name, u.email, d.*
                    FROM users u
                    LEFT JOIN daily_summaries d ON u.id = d.user_id
                    WHERE d.date = (SELECT MAX(date) FROM daily_summaries WHERE user_id = u.id)
                    OR d.date IS NULL
                    ORDER BY d.date DESC NULLS LAST
                """)
                daily_summaries = cur.fetchall()
                
                # Get the latest intraday metrics for each user
                cur.execute("""
                    SELECT u.name, u.email, i.type, i.value, i.time
                    FROM users u
                    LEFT JOIN intraday_metrics i ON u.id = i.user_id
                    WHERE i.time = (SELECT MAX(time) FROM intraday_metrics WHERE user_id = u.id AND type = i.type)
                    OR i.time IS NULL
                    ORDER BY i.time DESC NULLS LAST
                """)
                intraday_metrics = cur.fetchall()
                
                # Get the latest sleep logs for each user
                cur.execute("""
                    SELECT u.name, u.email, s.*
                    FROM users u
                    LEFT JOIN sleep_logs s ON u.id = s.user_id
                    WHERE s.start_time = (SELECT MAX(start_time) FROM sleep_logs WHERE user_id = u.id)
                    OR s.start_time IS NULL
                    ORDER BY s.start_time DESC NULLS LAST
                """)
                sleep_logs = cur.fetchall()
                
                return render_template('dashboard.html', 
                                      daily_summaries=daily_summaries,
                                      intraday_metrics=intraday_metrics,
                                      sleep_logs=sleep_logs)
        except Exception as e:
            app.logger.error(f"Error fetching data for dashboard: {e}")
            # Return a more user-friendly error page instead of just an error message
            return render_template('dashboard.html', 
                                  daily_summaries=[],
                                  intraday_metrics=[],
                                  sleep_logs=[],
                                  error="No se pudieron obtener los datos para el dashboard.")
        finally:
            conn.close()
    else:
        # Return a more user-friendly error page instead of just an error message
        return render_template('dashboard.html', 
                              daily_summaries=[],
                              intraday_metrics=[],
                              sleep_logs=[],
                              error="No se pudo conectar a la base de datos.")

@app.route('/livelyageing/home')
@login_required
def home():
    """
    Render the home page with recent activity.
    """
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cur:
                # Get recent users with their latest activity
                cur.execute("""
                    SELECT u.id, u.name, u.email, 
                           MAX(d.date) as last_updated
                    FROM users u
                    LEFT JOIN daily_summaries d ON u.id = d.user_id
                    GROUP BY u.id, u.name, u.email
                    ORDER BY last_updated DESC NULLS LAST
                    LIMIT 10
                """)
                recent_users = cur.fetchall()
                
                return render_template('home.html', recent_users=recent_users)
        except Exception as e:
            app.logger.error(f"Error fetching data for home page: {e}")
            return "Error: No se pudieron obtener los datos para la página de inicio.", 500
        finally:
            conn.close()
    else:
        return "Error: No se pudo conectar a la base de datos.", 500

@app.route('/livelyageing/user_stats')
@login_required
def user_stats():
    """
    Display statistics for all users.
    """
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cur:
                # Get all users
                cur.execute("""
                    SELECT id, name, email, created_at
                    FROM users
                    ORDER BY name
                """)
                users = cur.fetchall()
                
                return render_template('user_stats.html', users=users)
        except Exception as e:
            app.logger.error(f"Error fetching user statistics: {e}")
            return "Error: No se pudieron obtener las estadísticas de usuarios.", 500
        finally:
            conn.close()
    else:
        return "Error: No se pudo conectar a la base de datos.", 500

@app.route('/livelyageing/user/<int:user_id>')
@login_required
def user_detail(user_id):
    """
    Display detailed information for a specific user.
    """
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cur:
                # Get user information
                cur.execute("""
                    SELECT id, name, email, created_at
                    FROM users
                    WHERE id = %s
                """, (user_id,))
                user = cur.fetchone()
                
                if not user:
                    flash('Usuario no encontrado.', 'danger')
                    return redirect(url_for('user_stats'))
                
                # Get daily summaries for the user
                cur.execute("""
                    SELECT date, steps, heart_rate, sleep_minutes, calories, 
                           distance, floors, elevation, active_minutes, sedentary_minutes
                    FROM daily_summaries
                    WHERE user_id = %s
                    ORDER BY date DESC
                    LIMIT 30
                """, (user_id,))
                daily_summaries = cur.fetchall()
                
                # Get intraday metrics for the user
                cur.execute("""
                    SELECT time, type, value
                    FROM intraday_metrics
                    WHERE user_id = %s
                    ORDER BY time DESC
                    LIMIT 100
                """, (user_id,))
                intraday_metrics = cur.fetchall()
                
                return render_template('user_detail.html', 
                                      user=user, 
                                      daily_summaries=daily_summaries,
                                      intraday_metrics=intraday_metrics)
        except Exception as e:
            app.logger.error(f"Error fetching user details: {e}")
            return "Error: No se pudieron obtener los detalles del usuario.", 500
        finally:
            conn.close()
    else:
        return "Error: No se pudo conectar a la base de datos.", 500

# Route: Link a new Fitbit device
@app.route('/livelyageing/link', methods=['GET', 'POST'])
@login_required
def link_device():
    """
    Handle the linking of a new Fitbit device.
    """
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash('Por favor, proporciona un email.', 'danger')
            return redirect(url_for('link_device'))
            
        # Store email in session and redirect to assign_user
        session['pending_email'] = email
        return redirect(url_for('assign_user'))
    
    # GET request - show form with available emails
    conn = connect_to_db()
    if not conn:
        flash('Error de conexión a la base de datos.', 'danger')
        return redirect(url_for('index'))
        
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT email FROM users")
            emails = [row[0] for row in cur.fetchall()]
            return render_template('link_device.html', emails=emails)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/livelyageing/assign', methods=['GET', 'POST'])
@login_required
def assign_user():
    """
    Handle the assignment of a new user.
    """
    if request.method == 'POST':
        user_name = request.form['user_name']
        
        # Check if the user name already exists in the database (case-insensitive)
        conn = connect_to_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Query to check if the user name already exists (case-insensitive)
                    cur.execute("SELECT name FROM users WHERE LOWER(name) = LOWER(%s)", (user_name,))
                    existing_user = cur.fetchone()
                    
                    if existing_user:
                        # If the user name already exists, show an error message
                        error = f"El nombre de usuario '{user_name}' ya está en uso."
                        return render_template('assign_user.html', error=error)
                    else:
                        # If the user name is not in use, proceed to authorization
                        # Store the new name in the session for later use
                        session['new_user_name'] = user_name
                        
                        # Make sure we have a pending_email in the session
                        if 'pending_email' not in session:
                            # If no pending_email, redirect back to link_device
                            return redirect(url_for('link_device'))
                        
                        code_verifier = generate_code_verifier()
                        code_challenge = generate_code_challenge(code_verifier)
                        state = generate_state()
                        print(f"Generated valid state: {state}")
                        print(f"Generated code verifier: {code_verifier}")
                        print(f"Generated code challenge: {code_challenge}")
                        auth_url = generate_auth_url(code_challenge, state)
                        print(f"Generated auth URL: {auth_url}")
                        session['code_verifier'] = code_verifier
                        session['state'] = state
                        return render_template('link_auth.html', auth_url=auth_url)
            except Exception as e:
                print(f"Error checking user name in database: {e}")
                return "Error: No se pudo verificar el nombre de usuario.", 500
            finally:
                conn.close()
        else:
            return "Error: No se pudo conectar a la base de datos.", 500
    
    else:
        # If it's a GET request, check if we have a pending_email in the session
        if 'pending_email' not in session:
            # If no pending_email, redirect back to link_device
            return redirect(url_for('link_device'))
        
        # Render the assign_user.html template
        return render_template('assign_user.html')

# Configurar el registro
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
handler.setFormatter(formatter)
app.logger.addHandler(handler)

# Route: Fitbit OAuth callback
@app.route('/livelyageing/callback')
@login_required
def callback():
    """
    Handle the callback from Fitbit after the user authorizes the app.
    This route captures the authorization code and exchanges it for access and refresh tokens.
    """
    try:
        # Get the authorization code from the query parameters
        code = request.args.get('code')
        returned_state = request.args.get('state')
        
        # Get the stored state from the session
        stored_state = session.get('state')
        
        # Verify that the returned state matches the stored state
        if returned_state != stored_state:
            app.logger.error("Invalid state parameter. Possible CSRF attack.")
            flash("Error: Invalid state parameter. Possible CSRF attack.", "danger")
            return redirect(url_for('link_device'))
        
        # Get the pending email and new user name from the session
        email = session.get('pending_email')
        new_user_name = session.get('new_user_name')
        code_verifier = session.get('code_verifier')
        
        # Check if we have all the required session variables
        if not email:
            app.logger.error("No se proporcionó un correo electrónico en la sesión.")
            flash("Error: No se proporcionó un correo electrónico. Por favor, inténtalo de nuevo.", "danger")
            return redirect(url_for('link_device'))
        
        if not new_user_name:
            app.logger.error("No se proporcionó un nombre de usuario en la sesión.")
            flash("Error: No se proporcionó un nombre de usuario. Por favor, inténtalo de nuevo.", "danger")
            return redirect(url_for('assign_user'))
        
        if not code_verifier:
            app.logger.error("No se proporcionó un code_verifier en la sesión.")
            flash("Error: Problema de autorización. Por favor, inténtalo de nuevo.", "danger")
            return redirect(url_for('link_device'))
        
        if not code:
            app.logger.error("No se proporcionó un código de autorización.")
            flash("Error: No se proporcionó un código de autorización. Por favor, inténtalo de nuevo.", "danger")
            return redirect(url_for('link_device'))

        conn = connect_to_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Query to check if the email is already in use
                    cur.execute("SELECT id, access_token, refresh_token FROM users WHERE email = %s ORDER BY created_at DESC LIMIT 1", (email,))
                    existing_user = cur.fetchone()

                    if existing_user:
                        user_id, existing_access_token, existing_refresh_token = existing_user

                        # Flow 2: Reassign the device to a new user
                        if new_user_name:
                            if not existing_access_token or not existing_refresh_token:
                                # If tokens are missing, require reauthorization
                                if code:
                                    # Exchange the authorization code for new tokens
                                    access_token, refresh_token = get_tokens(code, code_verifier)
                                    # Add a new user with the same email and new name
                                    add_user(new_user_name, email, access_token, refresh_token)
                                    app.logger.info(f"Dispositivo reasignado a {new_user_name} ({email}) con nuevos tokens.")
                                else:
                                    app.logger.error("Se requiere autorización para reasignar el dispositivo.")
                                    flash("Error: Se requiere autorización para reasignar el dispositivo.", "danger")
                                    return redirect(url_for('link_device'))
                            else:
                                # If tokens are valid, simply add a new user with the same email and new name
                                add_user(new_user_name, email, existing_access_token, existing_refresh_token)
                                app.logger.info(f"Dispositivo reasignado a {new_user_name} ({email}) sin necesidad de reautorización.")
                        else:
                            app.logger.error("Se requiere un nombre de usuario para reasignar el dispositivo.")
                            flash("Error: Se requiere un nombre de usuario para reasignar el dispositivo.", "danger")
                            return redirect(url_for('assign_user'))
                    else:
                        # Flow 1: Link a new email to a user
                        if new_user_name:
                            if code:
                                # Exchange the authorization code for new tokens
                                access_token, refresh_token = get_tokens(code, code_verifier)
                                # Add a new user with the new email and name
                                add_user(new_user_name, email, access_token, refresh_token)
                                app.logger.info(f"Nuevo usuario {new_user_name} ({email}) añadido.")
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

                    # Redirect to the confirmation page
                    return render_template('confirmation.html', user_name=new_user_name, email=email)
            except Exception as e:
                app.logger.error(f"Error during token exchange: {e}")
                flash(f"Error durante el intercambio de tokens: {e}", "danger")
                return redirect(url_for('link_device'))
            finally:
                conn.close()
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
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cur:
                # Query to check if the email is already in use and has valid tokens
                cur.execute("SELECT access_token, refresh_token FROM users WHERE email = %s ORDER BY created_at DESC LIMIT 1", (email,))
                existing_user = cur.fetchone()
                
                if existing_user:
                    existing_access_token, existing_refresh_token = existing_user
                    if not existing_access_token or not existing_refresh_token:
                        # If tokens are missing, require reauthorization
                        code_verifier = generate_code_verifier()
                        code_challenge = generate_code_challenge(code_verifier)
                        state = generate_state()
                        print(f"Generated valid state: {state}")
                        print(f"Generated code verifier: {code_verifier}")
                        print(f"Generated code challenge: {code_challenge}")
                        auth_url = generate_auth_url(code_challenge, state)
                        print(f"Generated auth URL: {auth_url}")
                        session['code_verifier'] = code_verifier
                        session['state'] = state
                        return render_template('link_auth.html', auth_url=auth_url)
                    else:
                        # If tokens are valid, proceed to add the new user without reauthorization
                        add_user(new_user_name, email, existing_access_token, existing_refresh_token)
                        print(f"Dispositivo reasignado a {new_user_name} ({email}) sin necesidad de reautorización.")
                        return redirect('/')
                else:
                    return "Error: El correo no está en uso.", 400
        except Exception as e:
            return f"Error: {e}", 400
        finally:
            conn.close()
    else:
        return "Error: No se pudo conectar a la base de datos.", 500

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
        return value.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return value

# Run the Flask app
if __name__ == '__main__':
    # app.run(host=HOST, port=PORT, debug=DEBUG)
    app.run(debug=True)
