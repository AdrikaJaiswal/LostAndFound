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