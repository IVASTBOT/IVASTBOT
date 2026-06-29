from .recognizer import VisionRecognizer


def enroll_member(member_id: str, image_path: str, dev_allow_without_consent: bool | None = None) -> dict:
    return VisionRecognizer().enroll(member_id, image_path, dev_allow_without_consent=dev_allow_without_consent)
