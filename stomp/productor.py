import argparse
import decimal
from decimal import Decimal, InvalidOperation
import json
import xml.etree.ElementTree as ET
import stomp

DESTINATION_QUEUE = "/queue/cola_pedidos"

def construir_mensaje(formato: str, pedido: dict, mensaje_texto: str) -> tuple[str, str]:
    if formato == "texto":
        return mensaje_texto, "text/plain; charset=UTF-8"

    elif formato == "fijo":
        # Contrato de 36 caracteres: ID (6 chars), Cliente (20 chars), Monto (10 chars)
        id_str = str(pedido["id"]).zfill(6)[:6]
        cliente_str = str(pedido["cliente"]).ljust(20)[:20]
        monto_str = f"{pedido['monto']:010.2f}"
        
        cuerpo = f"{id_str}{cliente_str}{monto_str}"
        if len(cuerpo) != 36:
            raise ValueError(f"El mensaje de ancho fijo debe tener exactamente 36 caracteres, actual: {len(cuerpo)}")
        return cuerpo, "text/plain; charset=UTF-8"

    elif formato == "xml":
        root = ET.Element("pedido")
        id_elem = ET.SubElement(root, "id")
        id_elem.text = str(pedido["id"])
        
        cli_elem = ET.SubElement(root, "cliente")
        cli_elem.text = str(pedido["cliente"])
        
        monto_elem = ET.SubElement(root, "monto")
        monto_elem.text = f"{pedido['monto']:.2f}"
        
        cuerpo = ET.tostring(root, encoding="utf-8").decode("utf-8")
        return cuerpo, "application/xml"

    elif formato == "json":
        cuerpo = json.dumps(pedido, ensure_ascii=False)
        return cuerpo, "application/json"

    else:
        raise ValueError(f"Formato no soportado: {formato}")


def main():
    parser = argparse.ArgumentParser(description="Productor Stomp para cola de pedidos")
    
    parser.add_argument("--formato", choices=["texto", "fijo", "xml", "json"], required=True, help="Formato del mensaje")
    parser.add_argument("--mensaje", default="Hola desde el productor stomp", help="Mensaje para formato texto libre")
    parser.add_argument("--id", default="123", help="ID del pedido")
    parser.add_argument("--cliente", default="Edward Norton", help="Nombre del cliente")
    parser.add_argument("--monto", default="123.45", help="Monto del pedido")
    
    parser.add_argument("--host", default="127.0.0.1", help="Host del broker Stomp")
    parser.add_argument("--port", type=int, default=61613, help="Puerto Stomp (ej. 61613 para ActiveMQ)")
    parser.add_argument("--usuario", default="demo", help="Usuario de autenticación")
    parser.add_argument("--clave", default="demo123", help="Contraseña de autenticación")

    args = parser.parse_args()

    # Validar monto decimal
    try:
        monto_dec = Decimal(args.monto)
        if not monto_dec.is_finite() or monto_dec < 0:
            raise ValueError("El monto debe ser un número finito positivo")
    except (InvalidOperation, ValueError) as e:
        parser.error(f"Monto no válido: {args.monto} ({e})")

    pedido = {
        "id": args.id,
        "cliente": args.cliente,
        "monto": monto_dec
    }

    try:
        cuerpo, mime_type = construir_mensaje(args.formato, pedido, args.mensaje)
    except Exception as e:
        parser.error(f"Error al construir mensaje: {e}")

    # Conexión al Broker ActiveMQ mediante Stomp
    conn = stomp.Connection([(args.host, args.port)])
    try:
        conn.connect(username=args.usuario, passcode=args.clave, wait=True)
        
        headers = {
            "content-type": mime_type,
            "X-formato": args.formato,
            "persistent": "true"
        }

        conn.send(destination=DESTINATION_QUEUE, body=cuerpo, headers=headers)
        print(f"[+] Mensaje enviado a {DESTINATION_QUEUE} | Formato: {args.formato} | Cuerpo: {cuerpo}")
    except Exception as e:
        print(f"[-] Error al enviar mensaje al broker: {e}")
    finally:
        if conn.is_connected():
            conn.disconnect()

if __name__ == "__main__":
    main()
