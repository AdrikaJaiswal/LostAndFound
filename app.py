from flask import Flask, jsonify, session, render_template, Response
import csv
import io
from datetime import date, datetime
from config import supabase, SECRET_KEY
from auth import auth_bp
from decorators import login_required, role_required
from routes.faculty import faculty_bp
from routes.student import student_bp

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(student_bp)
app.register_blueprint(faculty_bp)

@app.route('/')

@app.route('/login')
def login_page():
    return render_template('login.html')

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

@app.route('/admin/dashboard')
@role_required(['Admin'])
def admin_dashboard():
    return render_template('admin.html')

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


# ADMIN ANALYTICS API

@app.route('/api/admin/analytics')
@role_required(['Admin'])
def admin_analytics():
    try:
        # Items grouped by category
        category_result = supabase.table('items').select(
            'category_id, categories(category_name)'
        ).execute()

        category_counts = {}
        for item in category_result.data:
            category = item.get('categories')
            name = category.get('category_name', 'Unknown') if category else 'Unknown'
            category_counts[name] = category_counts.get(name, 0) + 1

        # Items uploaded by month
        upload_result = supabase.table('items').select(
            'created_at'
        ).execute()

        monthly_counts = {}
        for item in upload_result.data:
            created = item.get('created_at')
            if created:
                month = created[:7]
                monthly_counts[month] = monthly_counts.get(month, 0) + 1

        # Claims grouped by status
        claim_result = supabase.table('claims').select(
            'claim_status'
        ).execute()

        claim_counts = {}
        for claim in claim_result.data:
            status = claim.get('claim_status', 'Unknown')
            claim_counts[status] = claim_counts.get(status, 0) + 1

        return jsonify({
            'status': 'Success',
            'items_by_category': category_counts,
            'uploads_by_month': dict(sorted(monthly_counts.items())),
            'claims_by_status': claim_counts
        }), 200

    except Exception as e:
        print('Analytics error:', e)
        return jsonify({
            'status': 'Error',
            'message': 'Unable to retrieve analytics.'
        }), 500


# ADMIN CSV REPORTS

@app.route('/api/admin/report/<report_type>')
@role_required(['Admin'])
def admin_csv_report(report_type):
    report_tables = {
        'users': ('users', 'user_id,full_name,email,registration_no,department,created_at'),
        'items': ('items', 'item_id,title,item_type,status,category_id,location_id,reported_by,date_reported,created_at'),
        'claims': ('claims', 'claim_id,item_id,claimant_id,claim_status,reviewed_by,created_at,updated_at'),
        'returns': ('returned_items', 'return_id,item_id,claim_id,verified_by_faculty_id,claimant_registration_no,return_date')
    }

    if report_type not in report_tables:
        return jsonify({
            'status': 'Error',
            'message': 'Invalid report type. Use users, items, claims, or returns.'
        }), 400

    table_name, columns = report_tables[report_type]

    try:
        response = supabase.table(table_name).select(columns).execute()

        output = io.StringIO()
        writer = csv.writer(output)

        # CSV column headers
        writer.writerow(columns.split(','))

        # Database rows
        for row in response.data:
            writer.writerow([row.get(column, '') for column in columns.split(',')])

        filename = f'{report_type}_report.csv'

        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )

    except Exception as e:
        print('CSV report error:', e)
        return jsonify({
            'status': 'Error',
            'message': 'Unable to generate report.'
        }), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)