"""Datos de ejemplo (ficticios). Crea catalogo, personal y dos clientes. Las contrasenas se generan al azar
y se guardan en $RUN_DIR/credenciales-demo.json (600, fuera del repositorio). Es idempotente."""
import os, sys, json, secrets, pathlib, time
import bcrypt, pymongo

RUN = pathlib.Path(os.environ.get('RUN_DIR', pathlib.Path(__file__).resolve().parents[1] / '.run'))
cli = pymongo.MongoClient(os.environ.get('MONGO_URL', 'mongodb://127.0.0.1:27017'))
ahora = lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
F = RUN / 'credenciales-demo.json'
cred = json.load(open(F)) if F.exists() else {}

def pw(clave):
    if clave not in cred:
        cred[clave] = secrets.token_urlsafe(12) + 'aA1'
    return bcrypt.hashpw(cred[clave].encode(), bcrypt.gensalt(rounds=12)).decode()

def contador(db, nombre, valor):
    db.contadores.update_one({'_id': nombre}, {'$max': {'n': valor}}, upsert=True)

PERSONAL = [('usr_0001', 'Ana Morales', 'admin@ejemplo.cl', 'administrador'), ('usr_0002', 'Diego Fuentes', 'dueno@ejemplo.cl', 'dueno'),
            ('usr_0003', 'Luis Mena', 'cajero@ejemplo.cl', 'cajero_virtual'), ('usr_0004', 'Marta Ibarra', 'despachos@ejemplo.cl', 'encargado_despachos')]
CLIENTES = [('cta_0001', 'cli_0001', 'Camila Rojas Pérez', 'camila@ejemplo.cl', '12.345.678-5', '+56911112222', '1995-04-20', 'F', 'Av. Ejemplo 1234'),
            ('cta_0002', 'cli_0002', 'Pedro Soto Díaz', 'pedro@ejemplo.cl', '11.111.111-1', '+56955556666', '1988-09-02', 'M', 'Pasaje Ficticio 78')]
DIR = lambda calle: {'calle': calle, 'comuna': 'Maipú', 'provincia': 'Santiago', 'region': 'Metropolitana'}
IMG = 'https://images.unsplash.com/'
PRODUCTOS = [
 ('Napolitana', 'clasica', 'Salsa de tomate, mozzarella, jamón, orégano fresco.', 8990, 'photo-1595854341625-f33ee10dbf94', True, 40),
 ('Margarita', 'clasica', 'Tomate San Marzano, mozzarella fior di latte, albahaca.', 7990, 'photo-1574071318508-1cdbab80d002', True, 40),
 ('Cuatro Quesos', 'premium', 'Mozzarella, gorgonzola, parmesano, provolone ahumado.', 10990, 'photo-1513104890138-7c749659a591', True, 30),
 ('Prosciutto e Funghi', 'premium', 'Jamón crudo, champiñones laminados, rúcula, parmesano.', 11990, 'photo-1541745537411-b8046dc6d66c', False, 30),
 ('Diávola', 'premium', 'Salame picante, mozzarella, chili flakes, aceite de oliva.', 10490, 'photo-1628840042765-356cda07504e', False, 30),
 ('Vegetariana', 'clasica', 'Pimentón, zapallo italiano, cebolla morada, aceitunas.', 9490, 'photo-1511689660979-10d2b1aada49', False, 30),
 ('Bebida 500ml', 'bebida', 'Línea de bebidas frías, a elección.', 1990, 'photo-1622483767028-3f66f32aef97', False, 200),
 ('Pan de Ajo', 'acompanamiento', 'Masa madre horneada a la piedra, mantequilla de ajo y perejil.', 3490, 'photo-1619535860434-ba1d8fa44669', False, 60),
 ('Combo Solo', 'combo', '1 pizza clásica + bebida 500ml', 10490, 'photo-1513104890138-7c749659a591', True, 50),
 ('Combo Dúo', 'combo', '2 pizzas clásicas + pan de ajo', 18990, 'photo-1513104890138-7c749659a591', True, 50),
 ('Combo Familiar', 'combo', '2 pizzas premium + pan de ajo + 2 bebidas', 28990, 'photo-1513104890138-7c749659a591', False, 50),
 ('Combo Noche Fornace', 'combo', '3 pizzas a elección + 2 acompañamientos', 34990, 'photo-1513104890138-7c749659a591', False, 50),
]

def main():
    a, c, i = cli['auth_db'], cli['clients_db'], cli['inventory_db']
    for cid, nombre, correo, rol in PERSONAL:
        if not a.cuentas.find_one({'id': cid}):
            a.cuentas.insert_one({'id': cid, 'correo': correo, 'rol': rol, 'nombre': nombre, 'estado': 'activo', 'hash': pw(correo), 'creadoEn': ahora()})
    contador(a, 'usr', len(PERSONAL))
    for cid, kid, nombre, correo, run, fono, nac, sexo, calle in CLIENTES:
        if not a.cuentas.find_one({'id': cid}):
            a.cuentas.insert_one({'id': cid, 'correo': correo, 'rol': 'cliente', 'nombre': nombre, 'estado': 'activo', 'hash': pw(correo), 'creadoEn': ahora()})
        if not c.clientes.find_one({'id': kid}):
            c.clientes.insert_one({'id': kid, 'cuentaId': cid, 'run': run, 'nombreCompleto': nombre, 'telefono': fono, 'fechaNacimiento': nac,
                                   'sexo': sexo, 'direccion': DIR(calle), 'baja': False, 'creadoEn': ahora()})
    contador(a, 'cta', len(CLIENTES)); contador(c, 'cli', len(CLIENTES))
    for n, (nombre, cat, desc, precio, img, dest, stock) in enumerate(PRODUCTOS, 1):
        pid = f'prod_{n:03d}'
        if not i.productos.find_one({'id': pid}):
            i.productos.insert_one({'id': pid, 'nombre': nombre, 'categoria': cat, 'descripcion': desc, 'precio': precio, 'imagen': IMG + img + '?w=600&q=80',
                                    'destacado': dest, 'stock': stock, 'disponible': True, 'retirado': False, 'creadoEn': ahora()})
    contador(i, 'prod', len(PRODUCTOS))
    json.dump(cred, open(F, 'w'), indent=1); os.chmod(F, 0o600)
    print(json.dumps({'personal': len(PERSONAL), 'clientes': len(CLIENTES), 'productos': len(PRODUCTOS)}))

main()
