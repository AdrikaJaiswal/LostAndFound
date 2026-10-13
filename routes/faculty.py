from datetime import date

from flask import Blueprint, jsonify, render_template, request, session

from config import supabase
from decorators import role_required

faculty_bp = Blueprint("faculty", __name__, url_prefix="/api/faculty")

ITEM_STATUSES = ("Available", "Claimed", "Returned", "Archived")
ITEM_TYPES = ("Lost", "Found")


@faculty_bp.get("/portal")
@role_required(["Faculty", "Admin"])
def faculty_portal():
    return render_template("faculty_portal.html")


@faculty_bp.get("/search-options")
@role_required(["Faculty", "Admin"])
def search_options():
    try:
        categories = (
            supabase.table("categories")
            .select("category_id, category_name")
            .order("category_name")
            .execute()
        )
        locations = (
            supabase.table("locations")
            .select("location_id, location_name")
            .order("location_name")
            .execute()
        )
        return jsonify({
            "status": "Success",
            "categories": categories.data,
            "locations": locations.data,
        })
    except Exception:
        return jsonify({
            "status": "Error",
            "message": "Unable to load search filters."
        }), 500


@faculty_bp.get("/items")
@role_required(["Faculty", "Admin"])
def search_items():
    filters = {}
    for field in ("category_id", "location_id"):
        value = request.args.get(field)
        if value:
            if not value.isdecimal() or int(value) <= 0:
                return jsonify({
                    "status": "Error",
                    "message": f"{field} must be a positive integer."
                }), 400
            filters[field] = int(value)

    for field, allowed in (("status", ITEM_STATUSES), ("item_type", ITEM_TYPES)):
        value = request.args.get(field)
        if value and value not in allowed:
            return jsonify({
                "status": "Error",
                "message": f"Invalid {field} filter."
            }), 400
        if value:
            filters[field] = value

    for field, operator in (("date_from", "gte"), ("date_to", "lte")):
        value = request.args.get(field)
        if value:
            try:
                parsed_date = date.fromisoformat(value)
            except ValueError:
                return jsonify({
                    "status": "Error",
                    "message": f"{field} must use YYYY-MM-DD format."
                }), 400
            if parsed_date.isoformat() != value:
                return jsonify({
                    "status": "Error",
                    "message": f"{field} must use YYYY-MM-DD format."
                }), 400
            filters["date_reported__" + operator] = parsed_date.isoformat()

    if (
        filters.get("date_reported__gte")
        and filters.get("date_reported__lte")
        and filters["date_reported__gte"] > filters["date_reported__lte"]
    ):
        return jsonify({
            "status": "Error",
            "message": "date_from must be on or before date_to."
        }), 400

    search_term = request.args.get("q", "").strip()
    if len(search_term) > 100:
        return jsonify({
            "status": "Error",
            "message": "Search text must be 100 characters or fewer."
        }), 400

    try:
        query = supabase.table("items").select(
            "item_id, title, description, item_type, status, category_id, "
            "location_id, date_reported, created_at, "
            "categories(category_name), locations(location_name)"
        )
        for key, value in filters.items():
            if key.endswith("__gte"):
                query = query.gte(key[:-5], value)
            elif key.endswith("__lte"):
                query = query.lte(key[:-5], value)
            else:
                query = query.eq(key, value)
        if search_term:
            query = query.ilike("title", f"%{search_term}%")

        response = query.order("date_reported", desc=True).execute()
        return jsonify({"status": "Success", "items": response.data})
    except Exception:
        return jsonify({
            "status": "Error",
            "message": "Unable to search items."
        }), 500


@faculty_bp.get("/items/<int:item_id>")
@role_required(["Faculty", "Admin"])
def item_details(item_id):
    try:
        item_response = (
            supabase.table("items")
            .select(
                "item_id, title, description, item_type, status, category_id, "
                "location_id, date_reported, created_at, "
                "categories(category_name), locations(location_name), "
                "item_images(image_id, image_url, uploaded_at)"
            )
            .eq("item_id", item_id)
            .execute()
        )
        if not item_response.data:
            return jsonify({
                "status": "Error",
                "message": "Item not found."
            }), 404

        claims_response = (
            supabase.table("claims")
            .select(
                "claim_id, claim_status, claimant_id, proof_description, "
                "claimant:users!claims_claimant_id_fkey(user_id, full_name)"
            )
            .eq("item_id", item_id)
            .eq("claim_status", "Approved")
            .execute()
        )
        return jsonify({
            "status": "Success",
            "item": item_response.data[0],
            "approved_claims": claims_response.data,
        })
    except Exception:
        return jsonify({
            "status": "Error",
            "message": "Unable to retrieve item details."
        }), 500


@faculty_bp.get("/returns")
@role_required(["Faculty", "Admin"])
def return_history():
    try:
        response = (
            supabase.table("returned_items")
            .select("*")
            .order("return_date", desc=True)
            .execute()
        )
        return jsonify({
            "status": "Success",
            "returns": response.data
        })
    except Exception:
        return jsonify({
            "status": "Error",
            "message": "Unable to retrieve return history."
        }), 500


@faculty_bp.post("/returns")
@role_required(["Faculty", "Admin"])
def record_return():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "status": "Error",
            "message": "A JSON object is required."
        }), 400

    claim_id = data.get("claim_id")
    if type(claim_id) is not int or claim_id <= 0:
        return jsonify({
            "status": "Error",
            "message": "A positive integer claim_id is required."
        }), 400

    required_fields = {
        "claimant_registration_no": 30,
        "claimant_phone": 15,
        "claimant_programme": 100,
    }
    receiver_details = {}
    for field, max_length in required_fields.items():
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            return jsonify({
                "status": "Error",
                "message": f"{field} is required and must be a non-blank string."
            }), 400
        if len(value) > max_length:
            return jsonify({
                "status": "Error",
                "message": f"{field} exceeds the maximum length of {max_length}."
            }), 400
        receiver_details[field] = value.strip()

    verification_notes = data.get("verification_notes")
    if verification_notes is not None and not isinstance(verification_notes, str):
        return jsonify({
            "status": "Error",
            "message": "verification_notes must be a string or null."
        }), 400
    if verification_notes is not None and len(verification_notes) > 10000:
        return jsonify({
            "status": "Error",
            "message": "verification_notes exceeds the maximum length of 10000."
        }), 400
    if verification_notes is not None:
        verification_notes = verification_notes.strip() or None

    try:
        response = supabase.rpc(
            "record_item_return",
            {
                "p_claim_id": claim_id,
                "p_verified_by_faculty_id": session["user_id"],
                "p_claimant_registration_no": receiver_details["claimant_registration_no"],
                "p_claimant_phone": receiver_details["claimant_phone"],
                "p_claimant_programme": receiver_details["claimant_programme"],
                "p_verification_notes": verification_notes,
            },
        ).execute()
        if (
            not isinstance(response.data, list)
            or len(response.data) != 1
            or not isinstance(response.data[0], dict)
        ):
            return jsonify({
                "status": "Error",
                "message": "Unable to record item return."
            }), 500
        return jsonify({
            "status": "Success",
            "returned_item": response.data[0]
        }), 201
    except Exception as error:
        error_code = getattr(error, "code", None)
        error_message = getattr(error, "message", "")
        if not error_code and error.args and isinstance(error.args[0], dict):
            error_payload = error.args[0]
            error_code = error_payload.get("code")
            error_message = error_payload.get("message", "")
        if not isinstance(error_message, str):
            error_message = ""
        error_message = error_message.lower()

        if error_code == "P0002":
            if "item_not_found" in error_message:
                message = "Item not found."
                return jsonify({"status": "Error", "message": message}), 404
            if "claim_not_found" in error_message:
                message = "Claim not found."
                return jsonify({"status": "Error", "message": message}), 404
        if error_code == "P0001":
            if "claim_not_approved" in error_message:
                message = "Claim is not approved."
                return jsonify({"status": "Error", "message": message}), 409
            elif "item_not_returnable" in error_message:
                message = "Item is not in a returnable status."
                return jsonify({"status": "Error", "message": message}), 409
            elif "return_already_recorded" in error_message:
                message = "A return has already been recorded for this claim or item."
                return jsonify({"status": "Error", "message": message}), 409
        if error_code == "23505":
            return jsonify({
                "status": "Error",
                "message": "A return has already been recorded for this claim or item."
            }), 409
        if error_code == "22023":
            return jsonify({
                "status": "Error",
                "message": "Return details are invalid."
            }), 400
        if error_code == "42501":
            if "invalid_return_verifier" in error_message:
                return jsonify({
                    "status": "Error",
                    "message": "The verifier is not authorized to record returns."
                }), 403

        return jsonify({
            "status": "Error",
            "message": "Unable to record item return."
        }), 500


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
            .select(
                "*, items(item_id, title, description, item_type, status, "
                "date_reported, categories(category_name), "
                "locations(location_name)), "
                "claimant:users!claims_claimant_id_fkey"
                "(user_id, full_name, registration_no, department)"
            )
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
