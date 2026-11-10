"""Registro de resultados reales de cada prueba (id, esperado, observado, estado). Se escribe en tests/resultados/<suite>.json."""
import json, time, pathlib
RES = pathlib.Path(__file__).resolve().parent / 'resultados'
RES.mkdir(exist_ok=True)

class Suite:
    def __init__(self, nombre):
        self.nombre, self.filas, self.t0 = nombre, [], time.time()

    def caso(self, id, descripcion, ok, observado):
        self.filas.append({'id': id, 'descripcion': descripcion, 'estado': 'OK' if ok else 'FALLA', 'observado': str(observado)[:600]})
        print(f"[{'OK   ' if ok else 'FALLA'}] {id}: {descripcion} -> {str(observado)[:200]}")
        return ok

    def cerrar(self):
        f = RES / f'{self.nombre}.json'
        json.dump({'suite': self.nombre, 'ejecutado': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'segundos': round(time.time() - self.t0, 1),
                   'total': len(self.filas), 'ok': sum(1 for x in self.filas if x['estado'] == 'OK'), 'casos': self.filas}, open(f, 'w'), ensure_ascii=False, indent=1)
        print(f"== {self.nombre}: {sum(1 for x in self.filas if x['estado']=='OK')}/{len(self.filas)} OK")
        return all(x['estado'] == 'OK' for x in self.filas)
