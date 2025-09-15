try:
    from flask import Flask, render_template, request, redirect, url_for, flash, session
    from werkzeug.security import generate_password_hash, check_password_hash
    from functools import wraps
    import os
    from dotenv import load_dotenv
    from models import db, User, Course, Student, Enrollment
except ImportError as e:
    print(f"Import error: {e}")
    print("Please make sure all required packages are installed:")
    print("pip install flask flask-sqlalchemy python-dotenv werkzeug")
    exit(1)

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///course_management.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize db with app
db.init_app(app)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Role required decorator
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] != role:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_role'] = user.role
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role', 'student')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')
        
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(name=name, email=email, password=hashed_password, role=role)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Get some stats for the dashboard
    total_courses = Course.query.count()
    total_students = Student.query.count()
    
    if session['user_role'] == 'instructor':
        user_courses = Course.query.filter_by(instructor_id=session['user_id']).count()
    elif session['user_role'] == 'student':
        # For students, show how many courses they're enrolled in
        student = Student.query.filter_by(email=session.get('user_email')).first()
        user_courses = Enrollment.query.filter_by(student_id=student.id).count() if student else 0
    else:
        user_courses = 0
    
    return render_template('dashboard.html', 
                          total_courses=total_courses,
                          total_students=total_students,
                          user_courses=user_courses)

@app.route('/courses')
@login_required
def courses():
    if session['user_role'] == 'instructor':
        course_list = Course.query.filter_by(instructor_id=session['user_id']).all()
    else:
        course_list = Course.query.all()
    
    return render_template('courses.html', courses=course_list)

@app.route('/course/create', methods=['GET', 'POST'])
@login_required
@role_required('instructor')
def create_course():
    if request.method == 'POST':
        title = request.form.get('title')
        code = request.form.get('code')
        description = request.form.get('description')
        credits = request.form.get('credits', 3)
        
        if Course.query.filter_by(code=code).first():
            flash('Course code already exists.', 'danger')
            return render_template('create_course.html')
        
        new_course = Course(
            title=title,
            code=code,
            description=description,
            credits=credits,
            instructor_id=session['user_id']
        )
        
        db.session.add(new_course)
        db.session.commit()
        
        flash('Course created successfully!', 'success')
        return redirect(url_for('courses'))
    
    return render_template('create_course.html')

@app.route('/students')
@login_required
def students():
    student_list = Student.query.all()
    return render_template('students.html', students=student_list)

@app.route('/student/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_student():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        student_id = request.form.get('student_id')
        major = request.form.get('major')
        
        if Student.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('create_student.html')
        
        if Student.query.filter_by(student_id=student_id).first():
            flash('Student ID already exists.', 'danger')
            return render_template('create_student.html')
        
        new_student = Student(
            name=name,
            email=email,
            student_id=student_id,
            major=major
        )
        
        db.session.add(new_student)
        db.session.commit()
        
        flash('Student created successfully!', 'success')
        return redirect(url_for('students'))
    
    return render_template('create_student.html')

@app.route('/enroll', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def enroll_student():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        course_id = request.form.get('course_id')
        
        # Check if enrollment already exists
        existing_enrollment = Enrollment.query.filter_by(
            student_id=student_id, course_id=course_id
        ).first()
        
        if existing_enrollment:
            flash('Student is already enrolled in this course.', 'danger')
            return redirect(url_for('enroll_student'))
        
        new_enrollment = Enrollment(
            student_id=student_id,
            course_id=course_id
        )
        
        db.session.add(new_enrollment)
        db.session.commit()
        
        flash('Student enrolled successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    students = Student.query.all()
    courses = Course.query.all()
    return render_template('enroll_student.html', students=students, courses=courses)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)