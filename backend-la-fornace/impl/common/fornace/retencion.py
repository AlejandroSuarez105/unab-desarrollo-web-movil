"""Plazos de retencion del Modulo 7 (7.9). Cada sistema purga sus propios datos con una tarea periodica.
RETENCION_SEGUNDOS define cada cuanto corre la tarea (por defecto, una vez por hora)."""
import os
from fornace.db import en_segundos

DIA = 86400
PLAZOS_DIAS = {
    'orden_despacho': 90,        # orden de despacho y su mensaje: desde la llegada
    'contacto': 365,             # mensaje de contacto
    'evento_pago': 365,          # aviso de pago y pago sin venta
    'movimiento_stock': 365,     # movimiento de stock
    'pedido_sin_pago': 365,      # pedido vencido o anulado sin pago: desde el cambio de estado
    'direccion_pedido': 365,     # calle, referencia y telefono del pedido: desde la entrega
    'cliente_baja': 730,         # cliente dado de baja: desde la baja
}
INTERVALO = int(os.environ.get('RETENCION_SEGUNDOS', '3600'))

def corte(clave):
    """Fecha (texto ISO UTC) anterior a la cual el dato ya cumplio su plazo."""
    return en_segundos(-PLAZOS_DIAS[clave] * DIA)
