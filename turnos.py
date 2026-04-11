from datetime import date, timedelta
from config import TURNOS


def calcular_estado_turno(turno: str, fecha_inicio_ciclo, target_date: date = None) -> dict:
    """
    Dado el turno y la fecha de inicio del ciclo actual,
    devuelve el estado del trabajador hoy (o en la fecha indicada) y fechas clave.

    Para turnos calendarizados (14x14-A, 8x6-B, etc.) se puede pasar None como
    fecha_inicio_ciclo; en ese caso se usa ref_inicio del config como base.
    """
    if turno not in TURNOS:
        return {
            "estado_calculado": "Indefinido",
            "fecha_subida": None,
            "fecha_bajada": None,
            "fecha_retorno": None,
            "dias_restantes": None,
        }

    ciclo_cfg = TURNOS[turno]

    # Para turnos calendarizados: si no hay fecha personal, usar ref_inicio del config
    if not fecha_inicio_ciclo:
        ref = ciclo_cfg.get("ref_inicio")
        if ref:
            fecha_inicio_ciclo = ref
        else:
            return {
                "estado_calculado": "Indefinido",
                "fecha_subida": None,
                "fecha_bajada": None,
                "fecha_retorno": None,
                "dias_restantes": None,
            }

    ciclo = TURNOS[turno]
    work_days = ciclo["work"]
    rest_days = ciclo["rest"]

    if isinstance(fecha_inicio_ciclo, str):
        fecha_inicio_ciclo = date.fromisoformat(fecha_inicio_ciclo)

    hoy = target_date or date.today()
    dias_transcurridos = (hoy - fecha_inicio_ciclo).days % (work_days + rest_days)

    fecha_subida = fecha_inicio_ciclo
    fecha_bajada = fecha_inicio_ciclo + timedelta(days=work_days)
    fecha_retorno = fecha_bajada + timedelta(days=rest_days)

    # Calcular el ciclo exacto en el que estamos
    ciclos_completos = (hoy - fecha_inicio_ciclo).days // (work_days + rest_days)
    fecha_subida = fecha_inicio_ciclo + timedelta(days=ciclos_completos * (work_days + rest_days))
    fecha_bajada = fecha_subida + timedelta(days=work_days)
    fecha_retorno = fecha_bajada + timedelta(days=rest_days)

    if dias_transcurridos < work_days:
        estado_calculado = "Activo en campamento"
        dias_restantes = work_days - dias_transcurridos
    else:
        estado_calculado = "En descanso"
        dias_restantes = (work_days + rest_days) - dias_transcurridos

    return {
        "estado_calculado": estado_calculado,
        "fecha_subida": fecha_subida.isoformat(),
        "fecha_bajada": fecha_bajada.isoformat(),
        "fecha_retorno": fecha_retorno.isoformat(),
        "dias_restantes": dias_restantes,
    }


def trabajadores_que_llegan_pronto(trabajadores: list, horas: int = 48) -> list:
    """Retorna lista de trabajadores que llegan en las próximas N horas."""
    hoy = date.today()
    limite = hoy + timedelta(hours=horas / 24)
    resultado = []
    for t in trabajadores:
        if not t.get("fecha_inicio_ciclo") or not t.get("turno"):
            continue
        info = calcular_estado_turno(t["turno"], t["fecha_inicio_ciclo"])
        if info["fecha_retorno"]:
            fecha_retorno = date.fromisoformat(info["fecha_retorno"])
            if hoy <= fecha_retorno <= limite:
                resultado.append({**t, **info})
    return resultado


def get_proxima_subida(turno: str, fecha_inicio_ciclo) -> date | None:
    """Obtiene la próxima fecha de subida (puede ser hoy o en el futuro)."""
    if not fecha_inicio_ciclo or turno not in TURNOS:
        return None
    info = calcular_estado_turno(turno, fecha_inicio_ciclo)
    if info["estado_calculado"] == "En descanso":
        return date.fromisoformat(info["fecha_retorno"])
    return date.fromisoformat(info["fecha_subida"])
