from flask import Blueprint, jsonify, request, session

from config import supabase
from decorators import role_required

faculty_bp = Blueprint("faculty", __name__, url_prefix="/api/faculty")


@faculty_bp.post("/claims/<int:claim_id>/decision")
@role_required(["Faculty", "Admin"])
def decide_claim(claim_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "status": "Error",
            "message": "A JSON object is required."
        }), 400

    decision = data.get("decision")
    if decision not in ("Approved", "Rejected"):
        return jsonify({
            "status": "Error",
            "message": "Decision must be 'Approved' or 'Rejected'."
        }), 400

    review_remarks = data.get("review_remarks")
    if review_remarks is not None and not isinstance(review_remarks, str):
        return jsonify({
            "status": "Error",
            "message": "Review remarks must be a string or null."
        }), 400

    try:
        response = (
            supabase.table("claims")
            .update({
                "claim_status": decision,
                "reviewed_by": session["user_id"],
                "review_remarks": review_remarks,
            })
            .eq("claim_id", claim_id)
            .eq("claim_status", "Pending")
            .select("*")
            .execute()
        )
        if response.data:
            return jsonify({
                "status": "Success",
                "claim": response.data[0]
            })

        existing_claim = (
            supabase.table("claims")
            .select("claim_id, claim_status")
            .eq("claim_id", claim_id)
            .execute()
        )
        if not existing_claim.data:
            return jsonify({
                "status": "Error",
                "message": "Claim not found."
            }), 404

        return jsonify({
            "status": "Error",
            "message": "Claim is no longer pending."
        }), 409
    except Exception:
        return jsonify({
            "status": "Error",
            "message": "Unable to update claim."
        }), 500


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
