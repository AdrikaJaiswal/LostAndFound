from flask import Flask, jsonify, session, render_template
from config import supabase, SECRET_KEY
from auth import auth_bp
from decorators import login_required, role_required

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Register Blueprints
app.register_blueprint(auth_bp)

@app.route('/')
def home():
    return render_template('home.html')

# TEST ROUTE: Anyone logged in
@app.route('/api/profile')
@login_required
def profile():
    return jsonify({
        "status": "Success",
        "message": f"Welcome {session.get('user_name')}! You are logged in as {session.get('role')}."
    })

# TEST ROUTE: Faculty and Admin only
@app.route('/api/faculty/review-claims')
@role_required(['Faculty', 'Admin'])
def faculty_review():
    return jsonify({
        "status": "Success",
        "message": "Access granted to Faculty Claims Review portal."
    })

# TEST ROUTE: Admin only
@app.route('/api/admin/system-stats')
@role_required(['Admin'])
def admin_stats():
    return jsonify({
        "status": "Success",
        "message": "Access granted to Admin Analytics portal."
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)