"""Image Pre-processor: validate, resize, normalize (Req24, NfReq16-17)."""
import io
from PIL import Image

ALLOWED_TYPES = {"image/jpeg", "image/png"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_BYTES = 15 * 1024 * 1024  # 15 MB (NfReq16)
MAX_SIDE = 1024  # resize before passing to YOLO


class ImageValidationError(ValueError):
    pass


def validate_and_preprocess(raw_bytes: bytes, filename: str = "") -> Image.Image:
    """Validate file size/type and return a PIL Image ready for inference.

    The image is processed entirely in memory — never written to disk (NfReq10).
    """
    if len(raw_bytes) > MAX_BYTES:
        raise ImageValidationError(
            f"File too large ({len(raw_bytes) // 1024} KB). Maximum is 15 MB."
        )

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageValidationError(
            "Unsupported file type. Please upload a JPG or PNG image."
        )

    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img.verify()  # checks for corruption
        img = Image.open(io.BytesIO(raw_bytes))  # re-open after verify
    except Exception:
        raise ImageValidationError("Could not open image. Please try a different file.")

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    elif img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg

    # Resize so the longest side is MAX_SIDE (preserves aspect ratio)
    w, h = img.size
    if max(w, h) > MAX_SIDE:
        scale = MAX_SIDE / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    return img
