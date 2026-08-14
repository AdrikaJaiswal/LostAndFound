from functools import wraps
from flask import session, jsonify

# 1. Ensure user is logged in
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({
                "status": "Error",
                "message": "Authentication required. Please log in first."
            }), 401
        return f(*args, **kwargs)
    return decorated_function

# 2. Restrict route access to specific roles (e.g. ['Faculty', 'Admin'])
def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({
                    "status": "Error",
                    "message": "Authentication required. Please log in first."
                }), 401
            user_role = session.get('role')
            if user_role not in allowed_roles:
                return jsonify({
                    "status": "Forbidden",
                    "message": f"Access denied. Required role: {allowed_roles}, but your role is '{user_role}'."
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator