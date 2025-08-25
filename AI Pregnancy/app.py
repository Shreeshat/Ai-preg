from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from flask_cors import CORS
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
import os
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask_cors import CORS
import phonenumbers  # Import the phonenumbers library
from datetime import datetime # Import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Define the upload folder and allowed extensions
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Update Flask app configuration
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # Limit file size to 2MB

# Secret key for sessions and token serializer
app.secret_key = os.getenv('FLASK_SECRET_KEY')  # Use env var, default for dev

# URL serializer for generating secure tokens
s = URLSafeTimedSerializer(app.secret_key)

# MongoDB setup (using MongoClient directly)
client = MongoClient(os.getenv('MONGO_URI'))  # Connect to MongoDB instance using the URI from .env
db = client['pregnancy_app']  # Select your database

# MongoDB collections
users_collection = db['users']  # Collection for users
doctors_collection = db['doctors']  # Collection for doctors
appointments_collection = db['appointments']  # Collection for appointments

# Flask-Mail configuration (use environment variables for better security)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')  # Email username from .env
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')  # Email password from .env

mail = Mail(app)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Index route
@app.route('/')
def index():
    user = None
    if 'user_id' in session:
        user_id = session['user_id']
        user = users_collection.find_one({"_id": ObjectId(user_id)})
    return render_template('index.html', user=user)

# About Us route
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to view your profile.', 'warning')
        return redirect(url_for('login'))

    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('index'))

    return render_template('profile.html', user=user)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to edit your profile.', 'warning')
        return redirect(url_for('login'))
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        age = request.form.get('age')
        address = request.form.get('address')
        phone_number = request.form.get('phone_number')
        state = request.form.get('state')
        country = request.form.get('country')

        is_valid_phone = True
        if phone_number:  # Only validate if a phone number is provided
            try:
                parsed_number = phonenumbers.parse(phone_number, "IN")  # Assuming India
                if not phonenumbers.is_valid_number(parsed_number):
                    is_valid_phone = False
            except phonenumbers.NumberParseException:
                is_valid_phone = False

        if not is_valid_phone:
            flash('Please enter a valid Indian phone number.', 'danger')
            return render_template('edit_profile.html', user=user)

        update_data = {}
        if age:
            update_data['age'] = int(age) if age.isdigit() else None # Store as integer if valid
        if address:
            update_data['address'] = address
        if phone_number:
            update_data['phonenumber'] = phone_number # Use 'phonenumber' to match profile.html
        if state:
            update_data['state'] = state
        if country:
            update_data['country'] = country

        if update_data:
            users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('No changes were made.', 'info')
            return redirect(url_for('edit_profile'))

    return render_template('edit_profile.html', user=user)

@app.route('/upload_profile_picture', methods=['POST'])
def upload_profile_picture():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to upload a profile picture.', 'warning')
        return redirect(url_for('login'))
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('index'))

    if 'profile_picture' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('profile'))
    file = request.files['profile_picture']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('profile'))
    if file and allowed_file(file.filename):
        filename = os.path.join(app.config['UPLOAD_FOLDER'], f"{user_id}_{datetime.utcnow().timestamp()}.{file.filename.rsplit('.', 1)[1].lower()}")
        file.save(filename)
        users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": {"profile_picture": os.path.basename(filename)}})
        flash('Profile picture uploaded successfully!', 'success')
        return redirect(url_for('profile'))
    else:
        flash('Allowed file types are png, jpg, jpeg, gif', 'danger')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', user=user)


# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')

        # Validate form fields
        if not email or not username or not password:
            flash('Please fill in all fields!', 'danger')
            return redirect('/signup')

        # Check if email or username already exists
        if users_collection.find_one({"email": email}):
            flash('Email already in use!', 'danger')
            return redirect('/signup')

        if users_collection.find_one({"username": username}):
            flash('Username already taken!', 'danger')
            return redirect('/signup')

        # Hash the password before storing it
        hashed_password = generate_password_hash(password)

        try:
            # Create the user with the hashed password
            user_data = {
                "email": email,
                "username": username,
                "password": hashed_password
            }
            user_id = users_collection.insert_one(user_data).inserted_id

            # Optionally, log the user in after signup by creating a session
            user = users_collection.find_one({"_id": user_id})
            session['user_id'] = str(user['_id'])  # Store MongoDB _id in session
            session['username'] = user['username']
            session['email'] = user['email']

            flash('Signup successful. You are now logged in.', 'success')
            return redirect(url_for('index'))  # Redirect to the user's dashboard or main page after signup

        except Exception as e:
            flash(f"An error occurred while creating the user: {e}", 'danger')
            return redirect('/signup')

    return render_template('signup.html')


# login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Fetch the user from the database
        user = users_collection.find_one({"username": username})

        if user and check_password_hash(user['password'], password):
            flash('Login successful!', 'success')  # Flash success message
            session['user_id'] = str(user['_id'])  # Store the user ID in the session
            session['username'] = user['username']
            session['email'] = user['email']
            return redirect(url_for('index'))  # Redirect to the index.html page
        else:
            flash('Invalid credentials. Please try again.', 'danger')  # Flash error message
            return redirect(url_for('login'))  # Redirect back to the login page

    return render_template('login.html')


# Dashboard route
@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        return render_template('dashboard.html')
    else:
        flash('Please log in to access the dashboard.', 'warning')
        return redirect(url_for('login'))

# Forgot password route
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = users_collection.find_one({"email": email})

        if user:
            # Generate a token for the user
            token = s.dumps(email, salt='email-confirm')
            reset_link = url_for('reset_password', token=token, _external=True)

            # Send the reset link via email
            send_email(email, reset_link)
            flash("A password reset link has been sent to your email.", "success")
        else:
            flash("No account found with that email address.", "danger")

        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')

# Reset password route
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600)  # Token valid for 1 hour
    except SignatureExpired:
        flash("The password reset link has expired.", "danger")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form['password']
        hashed_password = generate_password_hash(new_password)

        # Update the user's password in the database
        users_collection.update_one({"email": email}, {"$set": {"password": hashed_password}})
        flash("Your password has been reset successfully. Please login.", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)

# Helper function to send emails
def send_email(to_email, reset_link):
    try:
        msg = Message("Password Reset Request",
                        sender=app.config['MAIL_USERNAME'],
                        recipients=[to_email])
        msg.body = f"Click the link to reset your password: {reset_link}"
        mail.send(msg)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

# Logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Remove user ID from session
    session.pop('username', None) # Remove username from session
    session.pop('email', None)    # Remove email from session
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# View available doctors route
@app.route('/view_available_doctors')
def view_available_doctors():
    doctors_list = doctors_collection.find()  # Query to fetch doctors from MongoDB
    return render_template('view_available_doctors.html', doctors=doctors_list)

@app.route('/view_doctors')
def view_doctors():
    return render_template('view_doctors.html')


# NurtureNest route
@app.route('/nurturenest')
def nurturenest():
    return render_template('nurturenest.html')

# Weight Tracker route
@app.route('/weight-tracker')
def weight_tracker():
    return render_template('weight_tracker.html')


@app.route('/Fertility-Beacon')
def Fertility_Beacon():
    return render_template('Fertility_Beacon.html')

# Kegel Exercises route
@app.route('/kegel-exercise')
def kegel_exercise():
    return render_template('kegel_exercise.html')

# Pregnancy Items route
@app.route('/pregnancy-items')
def pregnancy_items():
    return render_template('pregnancy_items.html')

# Calendar and Diary route
@app.route('/calendar-and-diary')
def calendar_and_diary():
    return render_template('calendar_and_diary.html')

# View Cart route
@app.route('/view_cart')
def view_cart():
    return render_template('view_cart.html')  # The cart page template

@app.route('/schedule_appointment/<doctor_id>', methods=['GET', 'POST'])
def schedule_appointment(doctor_id):
    if request.method == 'POST':
        # Fetch form data
        patient_name = request.form['patient_name']
        patient_email = request.form['patient_email']
        patient_phone = request.form['patient_phone']
        appointment_date = request.form['appointment_date']

        # Save appointment details to the database
        appointment = {
            "doctor_id": doctor_id,
            "patient_name": patient_name,
            "patient_email": patient_email,
            "patient_phone": patient_phone,
            "appointment_date": appointment_date,
        }

        try:
            appointments_collection.insert_one(appointment)
            flash("Your appointment has been successfully booked!", "success")
            return redirect(url_for('appointment_success'))
        except Exception as e:
            flash(f"An error occurred while booking your appointment: {e}", "danger")
            return redirect(url_for('schedule_appointment', doctor_id=doctor_id))

    # Render the appointment form for GET requests
    return render_template('schedule_appointment.html', doctor_id=doctor_id)

@app.route('/confirm_appointment', methods=['POST'])
def confirm_appointment():
    patient_name = request.form['patient_name']
    patient_email = request.form['patient_email']
    patient_phone = request.form['patient_phone']
    appointment_date = request.form['appointment_date']

    # Save appointment in the database
    try:
        appointment = {
            "patient_name": patient_name,
            "patient_email": patient_email,
            "patient_phone": patient_phone,
            "appointment_date": appointment_date,
        }
        appointments_collection.insert_one(appointment)  # Save appointment to MongoDB

        # Optionally, send confirmation email
        flash("Appointment confirmed successfully.", "success")
        return redirect(url_for('appointment_success'))  # Redirect to a success page after confirming appointment
    except Exception as e:
        flash(f"Failed to confirm appointment: {e}", "danger")
        return redirect(url_for('schedule_appointment'))


@app.route('/appointment_success')
def appointment_success():
    return render_template('appointment_success.html')


pregnancy_tips = {
    "hello": "Hello! How can I assist you today? I'm here to provide tips and guidance to support you during your pregnancy journey.",
    "morning sickness": "Try eating small, frequent meals and avoiding spicy foods. Ginger tea or crackers may help.",
    "hydration": "It’s important to drink at least 8-10 glasses of water daily to stay hydrated during pregnancy.",
    "exercise": "Staying active with prenatal-safe exercises like swimming, stretching, or walking can boost your energy and reduce pregnancy discomfort. Visit the 'Kegel exercises' section to get more details.",
    "backpain": "Maintain good posture, use a pregnancy pillow while sleeping, and consider gentle stretching exercises.",
    "diet": "Eat a balanced diet with fruits, vegetables, whole grains, lean protein, and prenatal vitamins.",
    "weight tracker": "Monitor your pregnancy weight with a tracking tool to ensure healthy weight gain based on your trimester. Speak to your doctor if you notice significant changes.",
    "doctors": "Our expert gynecologists are here to support your pregnancy journey. Visit the 'Top Gynecologists' section to book an appointment.",
    "protiens": "Proteins are crucial during pregnancy for your baby’s growth. Include lean meats, eggs, dairy products, beans, nuts, and seeds in your diet. Visit 'Nuturenest' for more details.",
    "calendar": "Keep track of your pregnancy milestones with a calendar. It helps you plan appointments, monitor trimester changes, and prepare for your baby’s arrival.",
    "fatigue": "Feeling tired is common during pregnancy. Rest when needed, eat iron-rich foods, and stay hydrated to maintain your energy levels.",
    "constipation": "Increase your fiber intake with fruits, vegetables, and whole grains, and drink plenty of water to ease constipation.",
    "heartburn": "To reduce heartburn, avoid large meals, spicy foods, and eating right before bedtime. Sleeping with your upper body slightly elevated may also help.",
    "swelling": "Mild swelling in the feet and ankles is normal. Rest with your feet elevated"
}

if __name__ == '__main__':
    app.run(debug=True, port=5000)
