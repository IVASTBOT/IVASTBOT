from .recognizer import VisionRecognizer


def recognize_image(image_path: str) -> dict:
    return VisionRecognizer().recognize(image_path)

