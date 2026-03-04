-- Create the database first, then connect to it before running the below commands
-- CREATE DATABASE smart_hr_db;

CREATE TABLE Admin (
    admin_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL
);

INSERT INTO Admin (username, password_hash) VALUES ('admin', 'admin123');

CREATE TABLE Employee (
    employee_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    designation VARCHAR(50),
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(15),
    basic_salary NUMERIC(10, 2) NOT NULL,
    -- Added password for the Employee Portal login
    password_hash VARCHAR(255) DEFAULT 'emp123' 
);

CREATE TABLE Leave_Requests (
    leave_id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES Employee(employee_id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    leave_type VARCHAR(20) CHECK (leave_type IN ('Sick', 'Vacation', 'Unpaid')),
    status VARCHAR(20) DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected')),
    reason TEXT
);

CREATE TABLE Attendance (
    attendance_id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES Employee(employee_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status VARCHAR(20) CHECK (status IN ('Present', 'Absent', 'Half-Day')),
    working_hours INT,
    UNIQUE(employee_id, date) -- Prevents marking attendance twice for the same day
);

CREATE TABLE Payroll (
    payroll_id SERIAL PRIMARY KEY,
    employee_id INT REFERENCES Employee(employee_id) ON DELETE CASCADE,
    payroll_month VARCHAR(7) NOT NULL, -- e.g., '2023-10'
    basic_pay NUMERIC(10, 2) NOT NULL,
    allowances NUMERIC(10, 2) DEFAULT 0,
    deductions NUMERIC(10, 2) DEFAULT 0,
    tax_pt NUMERIC(10, 2) DEFAULT 200, -- Professional Tax
    net_salary NUMERIC(10, 2) NOT NULL,
    generated_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);