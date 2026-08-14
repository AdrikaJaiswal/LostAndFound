import bcrypt
from flask import Blueprint, request, jsonify, session
from config import supabase

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# ==========================================
# 1. REGISTER ENDPOINT
# ==========================================
@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json() or {}
        full_name = data.get('full_name')
        email = data.get('email')
        password = data.get('password')
        role_name = data.get('role', 'Student')  # Default to Student
        registration_no = data.get('registration_no')
        phone_number = data.get('phone_number')
        department = data.get('department')

        if not full_name or not email or not password:
            return jsonify({"status": "Error", "message": "Name, email, and password are required."}), 400

        # Check if user already exists
        existing_user = supabase.table('users').select('user_id').eq('email', email).execute()
        if existing_user.data:
            return jsonify({"status": "Error", "message": "A user with this email already exists."}), 409

        # Fetch role_id
        role_res = supabase.table('roles').select('role_id').eq('role_name', role_name).execute()
        if not role_res.data:
            return jsonify({"status": "Error", "message": f"Invalid role: {role_name}"}), 400
        role_id = role_res.data[0]['role_id']

        # Secure password hashing with salt using bcrypt
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

        # Insert user into database
        new_user = {
            "full_name": full_name,
            "email": email,
            "password_hash": hashed_password,
            "role_id": role_id,
            "registration_no": registration_no,
            "phone_number": phone_number,
            "department": department
        }
        insert_res = supabase.table('users').insert(new_user).execute()

        return jsonify({
            "status": "Success",
            "message": "User registered successfully!",
            "user": {
                "user_id": insert_res.data[0]['user_id'],
                "full_name": full_name,
                "email": email,
                "role": role_name
            }
        }), 201

    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500


# ==========================================
# 2. LOGIN ENDPOINT
# ==========================================
@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({"status": "Error", "message": "Email and password are required."}), 400

        # Fetch user details along with role
        user_res = supabase.table('users').select('user_id, full_name, email, password_hash, role_id, roles(role_name)').eq('email', email).execute()

        if not user_res.data:
            return jsonify({"status": "Error", "message": "Invalid email or password."}), 401

        user = user_res.data[0]
        stored_hash = user['password_hash'].encode('utf-8')

        # Verify password hash
        if not bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return jsonify({"status": "Error", "message": "Invalid email or password."}), 401

        # Establish server-side session
        role_name = user['roles']['role_name'] if 'roles' in user and user['roles'] else 'Student'
        session['user_id'] = user['user_id']
        session['user_name'] = user['full_name']
        session['role'] = role_name

        return jsonify({
            "status": "Success",
            "message": "Login successful!",
            "user": {
                "user_id": user['user_id'],
                "full_name": user['full_name'],
                "email": user['email'],
                "role": role_name
            }
        }), 200

    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500


# ==========================================
# 3. LOGOUT ENDPOINT
# ==========================================
@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"status": "Success", "message": "Logged out successfully."}), 200