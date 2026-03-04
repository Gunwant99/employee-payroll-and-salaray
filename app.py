from flask import Flask, render_template, request, redirect, session, Response
import psycopg2
import psycopg2.extras
import datetime

app = Flask(__name__)
app.secret_key = "enterprise_secret_123"

# ---------- POSTGRESQL DATABASE CONFIGURATION ----------
DB_HOST = "localhost"
DB_NAME = "smart_hr_db"
DB_USER = "postgres"
DB_PASS = "gunwant" # <--- UPDATE THIS

def get_db():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)

# ---------- LOGIN ----------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form['username'], request.form['password']
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute("SELECT * FROM Admin WHERE username=%s AND password_hash=%s", (u, p))
        admin = cur.fetchone()
        if admin:
            session.update({'user_id': admin['admin_id'], 'role': 'admin', 'name': 'System Admin'})
            return redirect('/dashboard')

        cur.execute("SELECT * FROM Employee WHERE email=%s AND password_hash=%s", (u, p))
        employee = cur.fetchone()
        if employee:
            session.update({'user_id': employee['employee_id'], 'role': 'employee', 'name': employee['name']})
            return redirect('/employee_dashboard')
        
        cur.close(); conn.close()
        return "Invalid Credentials"
    return render_template("login.html")

# ---------- ADMIN: DASHBOARD & EXPORT ----------
@app.route('/dashboard')
def dashboard():
    if session.get('role') != 'admin': return redirect('/')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM Employee")
    total_emp = cur.fetchone()[0]
    today = datetime.date.today().strftime('%Y-%m-%d')
    cur.execute("SELECT COUNT(*) FROM Attendance WHERE date=%s AND status='Present'", (today,))
    present_today = cur.fetchone()[0]
    month = datetime.date.today().strftime('%Y-%m')
    cur.execute("SELECT COALESCE(SUM(net_salary), 0) FROM Payroll WHERE payroll_month=%s", (month,))
    monthly_payroll = cur.fetchone()[0]
    cur.close(); conn.close()
    return render_template("dashboard.html", total_emp=total_emp, present_today=present_today, monthly_payroll=monthly_payroll)

@app.route('/export_payroll')
def export_payroll():
    if session.get('role') != 'admin': return redirect('/')
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT e.name, p.payroll_month, p.net_salary FROM Payroll p JOIN Employee e ON p.employee_id = e.employee_id")
    records = cur.fetchall()
    def generate():
        yield 'Name,Month,Net Salary\n'
        for r in records: yield f"{r['name']},{r['payroll_month']},{r['net_salary']}\n"
    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=payroll.csv"})

# ---------- ADMIN: EMPLOYEE & ATTENDANCE ----------
@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if session.get('role') != 'admin': return redirect('/')
    error = None
    if request.method == 'POST':
        try:
            conn = get_db(); cur = conn.cursor()
            cur.execute("INSERT INTO Employee (name, department, designation, email, phone, basic_salary, password_hash) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (request.form['name'], request.form['department'], request.form['designation'], request.form['email'], request.form['phone'], request.form['salary'], 'emp123'))
            conn.commit(); cur.close(); conn.close()
            return redirect('/employees')
        except psycopg2.IntegrityError:
            error = "Email already exists!"
    return render_template("add_employee.html", error=error)

@app.route('/employees')
def employees():
    if session.get('role') != 'admin': return redirect('/')
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM Employee ORDER BY employee_id ASC")
    data = cur.fetchall(); cur.close(); conn.close()
    return render_template("employees.html", data=data)

@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    if session.get('role') != 'admin': return redirect('/')
    if request.method == 'POST':
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO Attendance (employee_id, date, status, working_hours) VALUES (%s,%s,%s,%s)",
            (request.form['employee_id'], request.form['date'], request.form['status'], request.form['hours']))
        conn.commit(); cur.close(); conn.close()
        return redirect('/dashboard')
    return render_template("attendance.html")

# ---------- ADMIN: PAYROLL & LEAVES ----------
@app.route('/payroll', methods=['GET', 'POST'])
def payroll():
    if session.get('role') != 'admin': return redirect('/')
    if request.method == 'POST':
        emp_id, month, allowance = request.form['employee_id'], request.form['month'], float(request.form['allowance'])
        conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT basic_salary FROM Employee WHERE employee_id=%s", (emp_id,))
        basic = float(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM Attendance WHERE employee_id=%s AND status='Absent' AND CAST(date AS TEXT) LIKE %s", (emp_id, f"{month}%"))
        deduction = cur.fetchone()[0] * (basic / 30.0)
        final = (basic + allowance) - (deduction + 200)
        cur.execute("INSERT INTO Payroll (employee_id, payroll_month, basic_pay, allowances, deductions, net_salary) VALUES (%s,%s,%s,%s,%s,%s)",
            (emp_id, month, basic, allowance, deduction, final))
        conn.commit(); cur.close(); conn.close()
        return redirect(f'/salary_slip/{emp_id}')
    return render_template("payroll.html")

@app.route('/manage_leaves', methods=['GET', 'POST'])
def manage_leaves():
    if session.get('role') != 'admin': return redirect('/')
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        cur.execute("UPDATE Leave_Requests SET status=%s WHERE leave_id=%s", (request.form['status'], request.form['leave_id']))
        conn.commit()
    cur.execute("SELECT l.*, e.name FROM Leave_Requests l JOIN Employee e ON l.employee_id = e.employee_id ORDER BY l.leave_id DESC")
    leaves = cur.fetchall(); cur.close(); conn.close()
    return render_template("manage_leaves.html", leaves=leaves)

# ---------- EMPLOYEE: PORTAL, LEAVE, SETTINGS ----------
@app.route('/employee_dashboard')
def employee_dashboard():
    if session.get('role') != 'employee': 
        return redirect('/')
        
    emp_id = session['user_id']
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Fetch Payslips
    cur.execute("SELECT * FROM Payroll WHERE employee_id=%s ORDER BY payroll_id DESC", (emp_id,))
    payslips = cur.fetchall()
    
    # Fetch Leave Requests for the UI
    cur.execute("SELECT * FROM Leave_Requests WHERE employee_id=%s ORDER BY leave_id DESC", (emp_id,))
    leaves = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template("employee_dashboard.html", payslips=payslips, leaves=leaves, name=session['name'])
@app.route('/request_leave', methods=['GET', 'POST'])
def request_leave():
    if session.get('role') != 'employee': return redirect('/')
    if request.method == 'POST':
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO Leave_Requests (employee_id, start_date, end_date, leave_type, reason) VALUES (%s,%s,%s,%s,%s)",
            (session['user_id'], request.form['start_date'], request.form['end_date'], request.form['leave_type'], request.form['reason']))
        conn.commit(); cur.close(); conn.close()
        return redirect('/employee_dashboard')
    return render_template("request_leave.html", name=session['name'])

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if session.get('role') != 'employee': return redirect('/')
    conn = get_db(); cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        cur.execute("UPDATE Employee SET phone=%s, password_hash=%s WHERE employee_id=%s", (request.form['phone'], request.form['password'], session['user_id']))
        conn.commit(); cur.close(); conn.close()
        return redirect('/employee_dashboard')
    cur.execute("SELECT * FROM Employee WHERE employee_id=%s", (session['user_id'],))
    emp = cur.fetchone(); cur.close(); conn.close()
    return render_template("settings.html", emp=emp, name=session['name'])

@app.route('/salary_slip/<int:id>')
def salary_slip(id):
    conn = get_db(); cur = conn.cursor(); cur.execute("SELECT e.name, p.payroll_month, p.net_salary FROM Employee e JOIN Payroll p ON e.employee_id = p.employee_id WHERE e.employee_id=%s ORDER BY p.payroll_id DESC LIMIT 1", (id,))
    data = cur.fetchone(); cur.close(); conn.close()
    return render_template("salary_slip.html", data=data)

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

if __name__ == "__main__":
    app.run(debug=True)