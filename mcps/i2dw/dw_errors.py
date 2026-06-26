"""Catalogo de errores del Data Warehouse — mapeo por nombre, no por codigo."""
import logging

logger = logging.getLogger("dw-errors")

# Mapeo: nombre_error → mensaje para el usuario
ERRORS = {
    # HTTP
    "BAD_REQUEST": "La solicitud contiene parametros invalidos. Revise los datos enviados.",
    "UNAUTHORIZED": "No tiene autorizacion para acceder a este recurso. Verifique sus credenciales.",
    "FORBIDDEN": "Su rol no tiene permiso para realizar esta operacion.",
    "NOT_FOUND": "El recurso solicitado no existe.",
    "RATE_LIMITED": "Demasiadas solicitudes. Espere un momento e intente nuevamente.",
    "SERVER_ERROR": "Error interno del servidor. Intente nuevamente mas tarde.",
    "SERVICE_UNAVAILABLE": "El servicio no esta disponible en este momento. Intente mas tarde.",
    # Red
    "TIMEOUT": "El servicio no respondio a tiempo. Intente de nuevo.",
    "CONNECTION_ERROR": "Error de conexion. Verifique su conexion e intente nuevamente.",
    # Datos
    "EMPTY_DATA": "No se encontraron datos para los parametros consultados.",
    "PARSE_ERROR": "No se pudieron procesar los datos recibidos.",
    # Interno
    "INTERNAL_ERROR": "Error interno. El equipo tecnico ha sido notificado.",
    "PDF_GENERATION_ERROR": "Error al generar el documento PDF. Intente con otros parametros.",
    "S3_UPLOAD_ERROR": "Error al guardar el archivo. Intente nuevamente.",
}


def error_response(error_name: str, **context) -> dict:
    """Retorna un dict de error con mensaje amigable. El error real se loguea aparte."""
    msg = ERRORS.get(error_name, ERRORS["INTERNAL_ERROR"])
    if context:
        logger.error("Error [%s]: %s | context=%s", error_name, msg, context)
    else:
        logger.error("Error [%s]: %s", error_name, msg)
    return {"status": "error", "content": [{"text": msg}]}
