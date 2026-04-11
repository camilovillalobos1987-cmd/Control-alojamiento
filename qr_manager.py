import base64
import io
import secrets
import qrcode
from qrcode.image.pil import PilImage


def generar_token_qr(_trabajador: dict) -> str:
    """
    Genera un token corto único (16 hex chars) para identificar al trabajador.
    Al ser corto, produce un QR versión 1-2 (mínima densidad) que se lee
    perfectamente incluso impreso en tarjeta pequeña.
    """
    return secrets.token_hex(8)   # 16 chars, 64 bits de entropía


def validar_token_qr(token: str) -> bool:
    """Compatibilidad: siempre True, la validez se verifica por DB lookup."""
    return bool(token)


def generar_imagen_qr(contenido: str) -> bytes:
    """
    Genera un PNG del QR en memoria y retorna los bytes.
    ERROR_CORRECT_M (15%) + token corto → QR versión 1-2, módulos grandes,
    legible a cualquier tamaño de impresión.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=12,
        border=4,
    )
    qr.add_data(contenido)
    qr.make(fit=True)
    img: PilImage = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def generar_qr_base64(contenido: str) -> str:
    """Retorna el QR como string base64 para embeber en HTML."""
    img_bytes = generar_imagen_qr(contenido)
    return base64.b64encode(img_bytes).decode()
