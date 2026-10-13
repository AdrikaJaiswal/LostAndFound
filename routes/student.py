from flask import Blueprint, jsonify

from decorators import role_required

student_bp = Blueprint("student", __name__, url_prefix="/api/student")


@student_bp.get("/dashboard")
@role_required(["Student"])
def dashboard():
    return jsonify({
        "status": "Success",
        "message": "Student dashboard route is ready."
    })
