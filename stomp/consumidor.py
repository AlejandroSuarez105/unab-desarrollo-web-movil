import argparse
import json
import time
import xml.etree.ElementTree as ET
import stomp

DESTINATION_QUEUE = "/queue/cola_pedidos"

def interpretar_mensaje(body: str, headers: dict) -> tuple[str, dict | str]:
    formato = headers.get("X-formato") or headers.get("x-formato")
    mime_type = headers.get("content-type", "").lower()

    if not formato:
        if "application/json" in mime_type:
            formato = "json"
        elif "application/xml" in mime_type or "text/xml" in mime_type:
            formato = "xml"
        else:
            formato = "texto"

    formato = formato.lower()

    if formato == "texto":
        return "texto", body

    elif formato == "fijo":
        if len(body) != 36:
            raise ValueError(f"Longitud de mensaje de ancho fijo incorrecta: {len(body)} (esperado 36)")
        
        id_val = body[0:6].strip()
        cliente_val = body[6:26].strip()
        monto_val = body[26:36].strip()

        # Validación del formato decimal (esperado 00123.45)
        if body[33] != ".":
            raise ValueError("Formato de monto fijo no contiene punto decimal en la posición esperada")

        return "fijo", {
            "id": id_val,
            "cliente": cliente_val,
            "monto": float(monto_val)
        }

    elif formato == "xml":
        root = ET.fromstring(body)
        if root.tag != "pedido":
            raise ValueError(f"El nodo raíz debe ser 'pedido', encontrado: '{root.tag}'")
        
        id_val = root.findtext("id")
        cliente_val = root.findtext("cliente")
        monto_val = root.findtext("monto")

        return "xml", {
            "id": id_val,
            "cliente": cliente_val,
            "monto": float(monto_val) if monto_val else 0.0
        }

    elif formato == "json":
        data = json.loads(body)
        return "json", data

    else:
        raise ValueError(f"Formato desconocido: {formato}")


class Escuchador(stomp.ConnectionListener):
    def __init__(self, connection):
        self.connection = connection

    def on_error(self, frame):
        print(f"[-] Error recibido del Broker: {frame.body}")

    def on_disconnected(self):
        print("[!] Conexión Stomp cerrada.")

    def on_message(self, frame):
        ack_id = frame.headers.get("ack")
        headers = frame.headers
        body = frame.body

        try:
            formato, contenido = interpretar_mensaje(body, headers)
            print(f"\n[+] Recibido [Formato: {formato}]:")
            if isinstance(contenido, str):
                print(f"    {contenido}")
            else:
                print(json.dumps(contenido, indent=2, ensure_ascii=False))

            # Confirmación de procesamiento exitoso (Ack)
            if ack_id:
                self.connection.ack(ack_id)

        except Exception as e:
            print(f"[-] Mensaje inválido descartado: {e}")
            # Se descarta el mensaje para evitar bloqueos en la cola
            if ack_id:
                self.connection.ack(ack_id)


def main():
    parser = argparse.ArgumentParser(description="Consumidor Stomp para cola de pedidos")
    parser.add_argument("--host", default="127.0.0.1", help="Host del broker Stomp")
    parser.add_argument("--port", type=int, default=61613, help="Puerto Stomp (ej. 61613)")
    parser.add_argument("--usuario", default="demo", help="Usuario de autenticación")
    parser.add_argument("--clave", default="demo123", help="Contraseña de autenticación")

    args = parser.parse_args()

    conn = stomp.Connection([(args.host, args.port)])
    listener = Escuchador(conn)
    conn.set_listener("lector_pedidos", listener)

    try:
        conn.connect(username=args.usuario, passcode=args.clave, wait=True)
        conn.subscribe(destination=DESTINATION_QUEUE, id=1, ack="client-individual", headers={"prefetch-count": 1})
        print(f"[*] Escuchando en {DESTINATION_QUEUE}... Presiona Ctrl+C para salir.")

        while conn.is_connected():
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[!] Deteniendo consumidor...")
    except Exception as e:
        print(f"[-] Error en el consumidor: {e}")
    finally:
        if conn.is_connected():
            conn.disconnect()

if __name__ == "__main__":
    main()
