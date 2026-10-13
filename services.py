from PIL import Image
from config import supabase

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# ==========================================
# 1. FILE VALIDATION SERVICE
# ==========================================
def validate_image_files(files):
    """
    Validates a list of uploaded files:
    - Max 5 files
    - Max 5MB per file
    - Verifies actual image header integrity using Pillow
    """
    if len(files) > 5:
        return False, "You can upload a maximum of 5 images."

    for file in files:
        if not file.filename:
            continue

        # Check extension
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Invalid file type '{ext}'. Allowed: png, jpg, jpeg, webp."

        # Check file size (5MB cap)
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > MAX_FILE_SIZE_BYTES:
            return False, f"File '{file.filename}' exceeds the 5MB size limit."

        # Validate image integrity
        try:
            image = Image.open(file)
            image.verify()
            file.seek(0)
        except Exception:
            return False, f"File '{file.filename}' is corrupted or not a valid image."

    return True, "Valid"


# ==========================================
# 2. NOTIFICATION TRIGGER SERVICE
# ==========================================
def create_notification(user_id, title, message):
    """
    Inserts a live notification for a specific user into the notifications table.
    """
    try:
        data = {
            "user_id": user_id,
            "title": title,
            "message": message,
            "is_read": False
        }
        res = supabase.table('notifications').insert(data).execute()
        return True, res.data
    except Exception as e:
        return False, str(e)

# ==========================================
# 3. SUPABASE IMAGE STORAGE SERVICE
# ==========================================
import uuid
from werkzeug.utils import secure_filename


def upload_image_to_storage(file, item_id):
    """
    Uploads one image to the existing Supabase
    Storage bucket named item-images.
    Returns the public image URL.
    """
    if not file or not file.filename:
        return None

    filename = secure_filename(file.filename)

    if "." not in filename:
        raise ValueError("Invalid image filename.")

    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported image format.")

    unique_filename = f"{item_id}/{uuid.uuid4().hex}.{extension}"

    try:
        file.seek(0)
        file_bytes = file.read()

        supabase.storage.from_("item-images").upload(
            path=unique_filename,
            file=file_bytes,
            file_options={
                "content-type": file.mimetype or "application/octet-stream",
                "upsert": "false"
            }
        )

        public_url = supabase.storage.from_("item-images").get_public_url(
            unique_filename
        )

        return public_url

    except Exception:
        # Keep the original error available in the Flask logs.
        raise
