from flask import Blueprint, jsonify

from config import supabase
from decorators import role_required

faculty_bp = Blueprint("faculty", __name__, url_prefix="/api/faculty")


@faculty_bp.get("/claims/pending")
@role_required(["Faculty", "Admin"])
def pending_claims():
    try:
        response = (
            supabase.table("claims")
            .select("*")
            .eq("claim_status", "Pending")
            .execute()
        )
        return jsonify({
            "status": "Success",
            "claims": response.data
        })
    except Exception:
        return jsonify({
            "status": "Error",
            "message": "Unable to retrieve pending claims."
        }), 500


@faculty_bp.get("/dashboard")
@role_required(["Faculty", "Admin"])
def dashboard():
    return jsonify({
        "status": "Success",
        "message": "Faculty dashboard route is ready."
    })
