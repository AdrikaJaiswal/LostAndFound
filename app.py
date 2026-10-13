feature/student-public-module
from flask import Flask, jsonify, session, render_template, request
from flask import Flask, jsonify, session, render_template, Response
import csv
import io
from datetime import date, datetime
main
from config import supabase, SECRET_KEY
from auth import auth_bp
from decorators import login_required, role_required
from services import validate_image_files, upload_image_to_storage
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Register Blueprints
app.register_blueprint(auth_bp)

@app.route('/')

@app.route('/login')
def login_page():
    return render_template('login.html')

def home():
    return render_template('home.html')
@app.route('/login')
def login_page():
    return render_template('login.html')
@app.route('/register')
def register_page():
    return render_template('register.html')
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    return render_template('student_dashboard.html')



@app.route('/student/upload', methods=['GET', 'POST'])
@login_required
def student_upload():
    if request.method == 'POST':
        try:
            # Validate the uploaded images
            image_files = request.files.getlist("images")
            image_files = [f for f in image_files if f and f.filename]

            valid, message = validate_image_files(image_files)

            if not valid:
                return f"""
                    <h2>Image validation failed</h2>
                    <p>{message}</p>
                    <a href="/student/upload">Go back</a>
                """, 400

            # Prepare item details
            item_data = {
                "title": request.form.get("title", "").strip(),
                "description": request.form.get("description", "").strip(),
                "item_type": request.form.get("item_type"),
                "category_id": int(request.form.get("category_id")),
                "location_id": int(request.form.get("location_id")),
                "reported_by": session.get("user_id"),
                "date_reported": request.form.get("date_reported")
            }

            # Save the item first to get its database ID
            result = supabase.table("items").insert(item_data).execute()

            if not result.data:
                raise RuntimeError("The item was not saved.")

            item_id = result.data[0]["item_id"]

            # Upload each image and save its URL
            for image_file in image_files:
                image_url = upload_image_to_storage(image_file, item_id)

                if image_url:
                    supabase.table("item_images").insert({
                        "item_id": item_id,
                        "image_url": image_url
                    }).execute()

            return """
                <h2>Item saved successfully!</h2>
                <p>Your item details and images have been processed.</p>
                <a href="/student/my-uploads">View My Uploads</a>
            """

        except Exception:
            app.logger.exception("Failed to save item or upload images")
            return """
                <h2>Could not complete the upload</h2>
                <p>Please check the application logs and try again.</p>
                <a href="/student/upload">Try again</a>
            """, 400

    return render_template('upload.html')



@app.route('/student/my-uploads')
@login_required
def my_uploads():
    try:
        result = (
            supabase.table("items")
            .select("*")
            .eq("reported_by", session.get("user_id"))
            .order("created_at", desc=True)
            .execute()
        )

        items = result.data or []

        # Fetch image URLs for each item
        for item in items:
            image_result = (
                supabase.table("item_images")
                .select("image_url")
                .eq("item_id", item["item_id"])
                .execute()
            )
            item["images"] = image_result.data or []

        return render_template("my_uploads.html", items=items)

    except Exception:
        app.logger.exception("Failed to load student uploads")
        return "Could not load your uploads. Please try again.", 500



# EDIT AN ITEM — only its owner can edit it
@app.route('/student/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    try:
        query = (
            supabase.table("items")
            .select("*")
            .eq("item_id", item_id)
            .eq("reported_by", session.get("user_id"))
            .execute()
        )

        if not query.data:
            return "Item not found or you do not have permission to edit it.", 404

        item = query.data[0]

        if request.method == 'POST':
            updates = {
                "title": request.form.get("title", "").strip(),
                "description": request.form.get("description", "").strip(),
                "item_type": request.form.get("item_type"),
                "date_reported": request.form.get("date_reported")
            }

            supabase.table("items").update(updates).eq(
                "item_id", item_id
            ).eq("reported_by", session.get("user_id")).execute()

            return """
                <h2>Item updated successfully!</h2>
                <a href="/student/my-uploads">Return to My Uploads</a>
            """

        return render_template("edit_item.html", item=item)

    except Exception:
        app.logger.exception("Failed to edit item")
        return "Could not edit the item. Please try again.", 500


# DELETE AN ITEM — only its owner can delete it
@app.route('/student/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    try:
        result = (
            supabase.table("items")
            .delete()
            .eq("item_id", item_id)
            .eq("reported_by", session.get("user_id"))
            .execute()
        )

        if not result.data:
            return "Item not found or you do not have permission to delete it.", 404

        return """
            <h2>Item deleted successfully!</h2>
            <a href="/student/my-uploads">Return to My Uploads</a>
        """

    except Exception:
        app.logger.exception("Failed to delete item")
        return "Could not delete the item. It may have related records.", 500

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