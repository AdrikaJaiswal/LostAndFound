from flask import Flask, jsonify, session
from config import supabase, SECRET_KEY
from auth import auth_bp
from decorators import login_required, role_required

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Register Blueprints
app.register_blueprint(auth_bp)

@app.route('/')
def home():
    try:
        response = supabase.table('roles').select('*').execute()
        return jsonify({
            "status": "Success",
            "message": "Connected to Supabase successfully!",
            "roles": response.data
        })
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

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
    try:
        users = supabase.table('users').select(
            'user_id', count='exact', head=True
        ).execute()

        lost_items = supabase.table('items').select(
            'item_id', count='exact', head=True
        ).eq('item_type', 'Lost').execute()

        found_items = supabase.table('items').select(
            'item_id', count='exact', head=True
        ).eq('item_type', 'Found').execute()

        claims = supabase.table('claims').select(
            'claim_id', count='exact', head=True
        ).execute()

        pending_claims = supabase.table('claims').select(
            'claim_id', count='exact', head=True
        ).eq('claim_status', 'Pending').execute()

        returned_items = supabase.table('returned_items').select(
            'return_id', count='exact', head=True
        ).execute()

        status_counts = {}

        for status in ['Available', 'Claimed', 'Returned', 'Archived']:
            result = supabase.table('items').select(
                'item_id', count='exact', head=True
            ).eq('status', status).execute()

            status_counts[status.lower()] = result.count or 0

        return jsonify({
            "status": "Success",
            "statistics": {
                "total_users": users.count or 0,
                "lost_items": lost_items.count or 0,
                "found_items": found_items.count or 0,
                "total_claims": claims.count or 0,
                "pending_claims": pending_claims.count or 0,
                "returned_items": returned_items.count or 0,
                "items_by_status": status_counts
            }
        }), 200

    except Exception as e:
        print(f"Admin statistics error: {e}")
        return jsonify({
            "status": "Error",
            "message": "Unable to retrieve admin statistics."
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)