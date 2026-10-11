"""Giải mã response Forge dùng chung cho app Gradio và tab Prompt VN.

Không import requests/torch; Pillow chỉ được import khi thực sự giải mã ảnh.
"""
import base64
import io
import json


def decode_generation_response(data):
    if not isinstance(data, dict) or not isinstance(data.get("images", []), list):
        raise ValueError("API phải trả JSON object với danh sách images.")
    info = data.get("info", {})
    if isinstance(info, str):
        info = json.loads(info) if info.strip() else {}
    if not isinstance(info, dict):
        info = {}
    from PIL import Image
    images = []
    for encoded in data.get("images", []):
        if not isinstance(encoded, str):
            raise ValueError("images phải chứa các chuỗi base64.")
        raw = base64.b64decode(encoded.split(",", 1)[-1], validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            images.append(image.copy())
    if not images:
        raise ValueError("API không trả ảnh nào.")
    return images, info
