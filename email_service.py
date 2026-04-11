import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import GMAIL_USER, GMAIL_APP_PASSWORD, NOMBRE_EMPRESA
from database import log_notificacion


def _enviar_email(destinatario: str, asunto: str, cuerpo_html: str) -> bool:
    """Función base para envío de emails via Gmail."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("[EMAIL] Gmail no configurado. Omitiendo envío.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"] = f"{NOMBRE_EMPRESA} <{GMAIL_USER}>"
        msg["To"] = destinatario
        msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=5) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def notificar_llegada(trabajador: dict) -> bool:
    """
    Envía notificación de llegada al trabajador informando su habitación asignada.
    """
    if not trabajador.get("email"):
        return False

    modulo = trabajador.get("modulo", "—")
    piso = trabajador.get("piso", "—")
    pieza = trabajador.get("pieza", "—")

    asunto = f"[{NOMBRE_EMPRESA}] Información para tu próximo turno"
    cuerpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#f5f5f5;padding:20px;border-radius:12px;">
      <div style="background:#1e3a5f;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:22px;">🏕️ {NOMBRE_EMPRESA}</h1>
        <p style="color:#a8c8f0;margin:4px 0 0;">Sistema de Gestión de Campamento</p>
      </div>
      <div style="background:#fff;padding:30px;border-radius:0 0 8px 8px;">
        <h2 style="color:#1e3a5f;">Hola, {trabajador["nombre"]}</h2>
        <p>Te informamos que tu próximo turno está próximo a comenzar. A continuación encontrarás los detalles de tu alojamiento asignado:</p>

        <div style="background:#f0f7ff;border-left:4px solid #3b82f6;padding:16px;border-radius:4px;margin:20px 0;">
          <p style="margin:4px 0;"><strong>📦 Módulo:</strong> {modulo}</p>
          <p style="margin:4px 0;"><strong>🏢 Piso:</strong> {piso}</p>
          <p style="margin:4px 0;"><strong>🚪 Pieza N°:</strong> {pieza}</p>
          <p style="margin:4px 0;"><strong>👷 Cargo:</strong> {trabajador.get("cargo", "—")}</p>
          <p style="margin:4px 0;"><strong>🔄 Turno:</strong> {trabajador.get("turno", "—")}</p>
        </div>

        <p>Recuerda presentar tu <strong>código QR</strong> al ingresar al campamento.</p>
        <p style="color:#888;font-size:12px;margin-top:20px;">Este es un mensaje automático. Por favor no respondas a este correo.</p>
      </div>
    </div>
    """
    ok = _enviar_email(trabajador["email"], asunto, cuerpo)
    log_notificacion(trabajador["id"], "Llegada", trabajador["email"], "Enviado" if ok else "Error")
    return ok


def notificar_cambio_habitacion(trabajador: dict, hab_anterior: str, hab_nueva: str) -> bool:
    """Notifica al trabajador un cambio de habitación por razones operativas."""
    if not trabajador.get("email"):
        return False

    asunto = f"[{NOMBRE_EMPRESA}] Actualización de tu habitación asignada"
    cuerpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;background:#f5f5f5;padding:20px;border-radius:12px;">
      <div style="background:#1e3a5f;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
        <h1 style="color:#fff;margin:0;font-size:22px;">🏕️ {NOMBRE_EMPRESA}</h1>
      </div>
      <div style="background:#fff;padding:30px;border-radius:0 0 8px 8px;">
        <h2 style="color:#1e3a5f;">Hola, {trabajador["nombre"]}</h2>
        <p>Informamos que <strong>tu habitación ha sido actualizada</strong> por motivos operativos:</p>

        <div style="background:#fff8e1;border-left:4px solid #f59e0b;padding:16px;border-radius:4px;margin:16px 0;">
          <p style="margin:4px 0;text-decoration:line-through;color:#888;">❌ Habitación anterior: {hab_anterior}</p>
          <p style="margin:4px 0;font-size:18px;"><strong>✅ Nueva habitación: {hab_nueva}</strong></p>
        </div>

        <p>Tu código QR ha sido actualizado automáticamente con la nueva información. Si tienes dudas, contacta a la administración.</p>
        <p style="color:#888;font-size:12px;margin-top:20px;">Mensaje automático del sistema. No responder.</p>
      </div>
    </div>
    """
    ok = _enviar_email(trabajador["email"], asunto, cuerpo)
    log_notificacion(trabajador["id"], "Cambio Habitación", trabajador["email"], "Enviado" if ok else "Error")
    return ok
