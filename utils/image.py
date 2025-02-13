import io

from PIL import Image

THUMB_SIZES = ((768, 768),(576, 576),(384, 384))
MAX_ALLOWED_IMAGE_SIZE = int((1024**2) * 0.96)

def resize_image(image_bytes):

    original_length = len(image_bytes)
    final_length = 0
    image = Image.open(io.BytesIO(image_bytes))

    for ts in THUMB_SIZES:
        image.thumbnail(ts)
        image_bytes_out = io.BytesIO()
        image.save(image_bytes_out, format=image.format)
        image_bytes_out = image_bytes_out.getvalue()
        final_length = len(image_bytes_out)
        if len(image_bytes_out) <= MAX_ALLOWED_IMAGE_SIZE:
            return image_bytes_out

    raise Exception(f"failed to resize image to an appropriate size ({original_length} -> {final_length})")
