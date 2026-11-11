"""Topologia: quien puede llamar a quien (M3 3.8 y M4 4.10) y nombres simbolicos de secretos (M6 6.9)."""
SISTEMAS = ['auth', 'clients', 'inventory', 'orders', 'payments', 'dispatch', 'notifications']

# (llamador, llamado) -> referencia del secreto en Vault (ruta bajo secret/data/services/)
PARES = {
    ('api-gateway', 'auth-service'): 'gateway-introspect',
    ('clients-service', 'auth-service'): 'clients-to-auth',
    ('auth-service', 'notifications-service'): 'auth-to-notifications',
    ('orders-service', 'clients-service'): 'orders-to-clients',
    ('orders-service', 'inventory-service'): 'orders-to-inventory',
    ('payments-service', 'orders-service'): 'payments-to-orders',
    ('payments-service', 'notifications-service'): 'payments-to-notifications',
    ('graphql-gateway', 'orders-service'): 'graphql-to-orders',
    ('graphql-gateway', 'inventory-service'): 'graphql-to-inventory',
    ('graphql-gateway', 'clients-service'): 'graphql-to-clients',
}

ROLES_TODOS = ['administrador', 'cajero_virtual', 'cliente', 'dueno', 'encargado_despachos']
PERSONAL = ['administrador', 'cajero_virtual', 'encargado_despachos']

def ref_gateway(destino):
    return f'services/gateway-to-{destino}'

def ref_par(llamador, llamado):
    return f'services/{PARES[(llamador, llamado)]}'

# componentes y lo que lee cada uno de Vault (M6 6.9). Se usa al inicializar las politicas.
def lecturas():
    r = {}
    comps = ['api-gateway', 'graphql-gateway'] + [f'{s}-service' for s in SISTEMAS]
    for c in comps:
        r[c] = set()
    for d in SISTEMAS + ['graphql']:
        r['api-gateway'].add(f'services/gateway-to-{d}')
        r['graphql-gateway' if d == 'graphql' else f'{d}-service'].add(f'services/gateway-to-{d}')
    for (a, b), ref in PARES.items():
        r[a].add(f'services/{ref}')
        r[b].add(f'services/{ref}')
    r['payments-service'] |= {'payments/webhook', 'payments/provider'}
    r['notifications-service'] |= {'notifications/mail'}
    r['pasarela-prueba'] = {'payments/provider', 'payments/webhook'}
    r['correo-prueba'] = {'notifications/mail'}
    r['orders-service'] |= {'orders/activemq'}
    r['dispatch-service'] |= {'dispatch/activemq'}
    for s in SISTEMAS:
        r[f'{s}-service'].add(f'{s}/db')
    return {k: sorted(v) for k, v in r.items()}
