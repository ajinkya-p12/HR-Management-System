from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re
import MySQLdb

app = Flask(__name__)
app.secret_key = '1234'  # Change this to a secure secret key

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'tiger'  # Replace with your MySQL password
app.config['MYSQL_DB'] = 'hospital_hrms'

mysql = MySQL(app)

# Password validation function
def is_password_valid(password):
    if len(password) < 8:
        return False
    if not re.search("[a-z]", password):
        return False
    if not re.search("[A-Z]", password):
        return False
    if not re.search("[0-9]", password):
        return False
    return True

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND is_active = true", (username,))
        user = cur.fetchone()
        
        if user and user[2] == password:  # In production, use check_password_hash
            session['logged_in'] = True
            session['username'] = username
            session['user_id'] = user[0]
            session['role'] = user[4]
            
            # Update last login
            cur.execute("UPDATE users SET last_login = %s WHERE id = %s", 
                       (datetime.now(), user[0]))
            mysql.connection.commit()
            
            cur.close()
            return redirect(url_for('employees_page'))
        else:
            cur.close()
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/employees_page')
@login_required
def employees_page():
    return render_template('employees.html', username=session.get('username'), role=session.get('role'))

@app.route('/employees')
@login_required
def get_employees():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM employees")
    rows = cur.fetchall()
    employees = []
    for row in rows:
        employees.append({
            'id': row[0],
            'name': row[1],
            'position': row[2],
            'department': row[3],
            'salary': float(row[4])
        })
    cur.close()
    return jsonify(employees)

@app.route('/add_employee', methods=['POST'])
@login_required
def add_employee():
    if session.get('role') != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    name = data['name']
    position = data['position']
    department = data['department']
    salary = data['salary']

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO employees (name, position, department, salary) VALUES (%s, %s, %s, %s)",
                (name, position, department, salary))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Employee added successfully!'})

@app.route('/delete_employee/<int:emp_id>', methods=['DELETE'])
@login_required
def delete_employee(emp_id):
    if session.get('role') != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM employees WHERE id = %s", (emp_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Employee deleted successfully!'})

@app.route('/edit_employee/<int:emp_id>', methods=['PUT'])
@login_required
def edit_employee(emp_id):
    if session.get('role') != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE employees 
        SET name = %s, position = %s, department = %s, salary = %s 
        WHERE id = %s
    """, (data['name'], data['position'], data['department'], data['salary'], emp_id))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Employee updated successfully!'})

@app.route('/attendance_page')
@login_required
def attendance_page():
    return render_template('attendance.html', username=session.get('username'), role=session.get('role'))

@app.route('/payroll_page')
@login_required
def payroll_page():
    return render_template('payroll.html', username=session.get('username'), role=session.get('role'))

@app.route('/attendance/today')
@login_required
def get_today_attendance():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT a.*, e.name as employee_name 
        FROM attendance a 
        JOIN employees e ON a.employee_id = e.id 
        WHERE DATE(a.check_in) = CURDATE()
    """)
    rows = cur.fetchall()
    attendance = []
    for row in rows:
        attendance.append({
            'id': row[0],
            'employee_id': row[1],
            'employee_name': row[5],
            'check_in': row[2].strftime('%Y-%m-%d %H:%M:%S') if row[2] else None,
            'check_out': row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else None,
            'status': row[4]
        })
    cur.close()
    return jsonify(attendance)

@app.route('/attendance/mark', methods=['POST'])
@login_required
def mark_attendance():
    if session.get('role') != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    employee_id = data['employee_id']
    status = data['status']
    
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO attendance (employee_id, check_in, status) 
        VALUES (%s, %s, %s)
    """, (employee_id, datetime.now(), status))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Attendance marked successfully'})

@app.route('/attendance/checkout/<int:attendance_id>', methods=['POST'])
@login_required
def mark_checkout(attendance_id):
    if session.get('role') != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE attendance 
        SET check_out = %s 
        WHERE id = %s AND check_out IS NULL
    """, (datetime.now(), attendance_id))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Check-out marked successfully'})

@app.route('/leave_page')
@login_required
def leave_page():
    return render_template('leave.html', 
                         username=session.get('username'), 
                         role=session.get('role'),
                         employee_id=session.get('user_id'))

@app.route('/leave/requests')
@login_required
def get_leave_requests():
    cur = mysql.connection.cursor()
    if session.get('role') == 'admin':
        cur.execute("""
            SELECT l.*, e.name as employee_name 
            FROM leave_requests l 
            JOIN employees e ON l.employee_id = e.id 
            ORDER BY l.created_at DESC
        """)
    else:
        cur.execute("""
            SELECT l.*, e.name as employee_name 
            FROM leave_requests l 
            JOIN employees e ON l.employee_id = e.id 
            WHERE l.employee_id = %s 
            ORDER BY l.created_at DESC
        """, (session.get('user_id'),))
    
    rows = cur.fetchall()
    leaves = []
    for row in rows:
        leaves.append({
            'id': row[0],
            'employee_id': row[1],
            'employee_name': row[8],
            'start_date': row[2].strftime('%Y-%m-%d'),
            'end_date': row[3].strftime('%Y-%m-%d'),
            'leave_type': row[4],
            'reason': row[5],
            'status': row[6],
            'created_at': row[7].strftime('%Y-%m-%d %H:%M:%S')
        })
    cur.close()
    return jsonify(leaves)

@app.route('/leave/request', methods=['POST'])
@login_required
def submit_leave_request():
    data = request.get_json()
    
    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO leave_requests 
        (employee_id, start_date, end_date, leave_type, reason) 
        VALUES (%s, %s, %s, %s, %s)
    """, (data['employee_id'], data['start_date'], data['end_date'], 
          data['leave_type'], data['reason']))
    
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'Leave request submitted successfully'})

@app.route('/leave/update/<int:leave_id>', methods=['PUT'])
@login_required
def update_leave_status(leave_id):
    if session.get('role') != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    status = data['status']
    
    cur = mysql.connection.cursor()
    cur.execute("UPDATE leave_requests SET status = %s WHERE id = %s", 
                (status, leave_id))
    mysql.connection.commit()
    cur.close()
    
    return jsonify({'message': f'Leave request {status}'})

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            return render_template('change_password.html', error='New passwords do not match')
            
        if not is_password_valid(new_password):
            return render_template('change_password.html', 
                error='Password must be at least 8 characters long and contain uppercase, lowercase, and numbers')
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT password FROM users WHERE username = %s", (session['username'],))
        user = cur.fetchone()
        
        if user and user[0] == current_password:  # In production, use check_password_hash
            cur.execute("UPDATE users SET password = %s WHERE username = %s",
                       (new_password, session['username']))
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('employees_page'))
        else:
            cur.close()
            return render_template('change_password.html', error='Current password is incorrect')
    
    return render_template('change_password.html')

@app.route('/manage_users')
@login_required
def manage_users():
    if session.get('role') != 'admin':
        return redirect(url_for('employees_page'))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, email, role, last_login, is_active FROM users")
    users = cur.fetchall()
    cur.close()
    
    return render_template('manage_users.html', users=users)

@app.route('/add_user', methods=['POST'])
@login_required
def add_user():
    if session.get('role') != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    username = data['username']
    password = data['password']
    email = data['email']
    role = data['role']
    
    if not is_password_valid(password):
        return jsonify({'message': 'Invalid password format'}), 400
    
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            INSERT INTO users (username, password, email, role)
            VALUES (%s, %s, %s, %s)
        """, (username, password, email, role))
        mysql.connection.commit()
        cur.close()
        return jsonify({'message': 'User added successfully'})
    except Exception as e:
        cur.close()
        return jsonify({'message': 'Username or email already exists'}), 400

@app.route('/toggle_user/<int:user_id>', methods=['PUT'])
@login_required
def toggle_user(user_id):
    if session.get('role') != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    
    cur = mysql.connection.cursor()
    cur.execute("UPDATE users SET is_active = NOT is_active WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()
    
    return jsonify({'message': 'User status updated successfully'})

@app.route('/analytics_dashboard')
def analytics_dashboard():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Get total employee count
    cursor.execute('SELECT COUNT(*) as total_employees FROM employees')
    total_employees = cursor.fetchone()['total_employees']
    
    # Get department-wise distribution
    cursor.execute('''
        SELECT department, COUNT(*) as count 
        FROM employees 
        GROUP BY department
    ''')
    dept_distribution = cursor.fetchall()
    
    # Get attendance statistics
    cursor.execute('''
        SELECT 
            DATE_FORMAT(date, '%Y-%m') as month,
            COUNT(*) as total_attendance,
            SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_count
        FROM attendance
        GROUP BY DATE_FORMAT(date, '%Y-%m')
        ORDER BY month DESC
        LIMIT 6
    ''')
    attendance_stats = cursor.fetchall()
    
    # Get leave statistics
    cursor.execute('''
        SELECT 
            leave_type,
            COUNT(*) as count
        FROM leaves
        WHERE YEAR(start_date) = YEAR(CURRENT_DATE)
        GROUP BY leave_type
    ''')
    leave_stats = cursor.fetchall()
    
    # Get recent hires
    cursor.execute('''
        SELECT name, department, hire_date
        FROM employees
        ORDER BY hire_date DESC
        LIMIT 5
    ''')
    recent_hires = cursor.fetchall()
    
    cursor.close()
    
    return render_template('analytics_dashboard.html',
                         total_employees=total_employees,
                         dept_distribution=dept_distribution,
                         attendance_stats=attendance_stats,
                         leave_stats=leave_stats,
                         recent_hires=recent_hires)

if __name__ == '__main__':
    app.run(debug=True)