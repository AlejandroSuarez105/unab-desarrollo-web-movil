// graphql-gateway: solo lectura. Agrega orders, inventory y clients (Modulo 8). Sin puerto publico: se llega por el API Gateway (R36).
import fs from 'node:fs';
import https from 'node:https';
import http from 'node:http';
import crypto from 'node:crypto';
import express from 'express';
import DataLoader from 'dataloader';
import { ApolloServer } from '@apollo/server';
import { expressMiddleware } from '@as-integrations/express4';
import { GraphQLError } from 'graphql';
import { makeExecutableSchema } from '@graphql-tools/schema';
import { typeDefs } from './schema.js';
import { evaluar, err } from './policy.js';
import { leer } from './clientes.js';
import { candidatos, iguales } from './vault.js';

const NOMBRE = 'graphql-gateway';
const logDir = process.env.LOG_DIR;
if (logDir) fs.mkdirSync(logDir, { recursive: true });
const logFile = logDir ? fs.createWriteStream(`${logDir}/${NOMBRE}.log`, { flags: 'a' }) : null;
function log(evento, campos = {}) {
  const l = JSON.stringify({ ts: new Date().toISOString().slice(0, 19), servicio: NOMBRE, evento, ...campos });
  console.log(l);
  if (logFile) logFile.write(l + '\n');
}

// ---------------- resolvers ----------------
const resolvers = {
  Query: {
    async resumenPedido(_, { id }, ctx) {
      const r = await leer('orders', `/orders/${encodeURIComponent(id)}`, ctx, log);
      if (r.status === 404) throw new GraphQLError('Pedido no encontrado.', { extensions: { code: 'NO_ENCONTRADO' } });   // idéntico para ajeno e inexistente
      if (r.status !== 200) throw new GraphQLError('No se pudo obtener el pedido.', { extensions: { code: 'SUBSISTEMA_NO_DISPONIBLE', sistema: 'orders' } });
      return r.json;
    },
    miCuenta: () => ({}),   // cada parte se resuelve por separado para que una falla no tumbe a la otra
  },
  ResumenPedido: {
    creadoEn: (p) => p.creadoEn ?? p.historialEstados?.[0]?.fecha,
    expiraEn: (p) => p.expiraEn ?? null,
    clienteNombre: (p) => p.clienteNombre ?? null,
  },
  ItemPedido: {
    async producto(item, _, ctx) {
      return ctx.loaders.producto.load(item.productoId);   // un lote por solicitud: una sola llamada a inventory
    },
  },
  MiCuenta: {
    async perfil(_, __, ctx) {
      const r = await leer('clients', '/clients/me', ctx, log);
      if (r.status !== 200) throw new GraphQLError('El perfil no está disponible.', { extensions: { code: 'SUBSISTEMA_NO_DISPONIBLE', sistema: 'clients' } });
      return r.json;
    },
    async pedidos(_, __, ctx) {
      const r = await leer('orders', `/orders?limit=${ctx.limitePedidos}`, ctx, log);
      if (r.status !== 200) throw new GraphQLError('Los pedidos no están disponibles.', { extensions: { code: 'SUBSISTEMA_NO_DISPONIBLE', sistema: 'orders' } });
      return r.json;
    },
  },
};

function crearLoaders(ctx) {
  return {
    producto: new DataLoader(async (ids) => {
      const unicos = [...new Set(ids)];
      const r = await leer('inventory', `/products?ids=${unicos.join(',')}&limit=100`, ctx, log);
      if (r.status !== 200) throw new GraphQLError('El catálogo no está disponible.', { extensions: { code: 'SUBSISTEMA_NO_DISPONIBLE', sistema: 'inventory' } });
      const porId = new Map(r.json.map((p) => [p.id, p]));
      return ids.map((id) => porId.get(id) ?? null);   // retirado o ausente: null sin error
    }, { cache: true }),   // cache solo de esta solicitud (el loader se crea por solicitud)
  };
}

// ---------------- Apollo ----------------
const CODIGOS_CONSULTA = new Set(['GRAPHQL_PARSE_FAILED', 'GRAPHQL_VALIDATION_FAILED', 'BAD_USER_INPUT', 'BAD_REQUEST', 'OPERATION_RESOLUTION_FAILURE', 'PERSISTED_QUERY_NOT_FOUND']);
const schema = makeExecutableSchema({ typeDefs, resolvers });

const politicas = {
  async requestDidStart() {
    return {
      async didResolveOperation(rc) {
        const a = evaluar(schema, rc.document, rc.operation, rc.request.variables ?? {}, rc.contextValue.roles);
        rc.contextValue.costo = a.costo;
        rc.contextValue.operaciones = a.tops.map((t) => t.nombre).join(',');
        const mc = a.tops.find((t) => t.nombre === 'miCuenta');
        rc.contextValue.limitePedidos = mc?.args.limitePedidos ?? 5;
      },
      async willSendResponse(rc) {
        const b = rc.response.body;
        if (b.kind === 'single' && b.singleResult.errors) {
          for (const e of b.singleResult.errors) e.extensions = { ...e.extensions, requestId: rc.contextValue.rid };
        }
      },
    };
  },
};

const server = new ApolloServer({
  schema,
  introspection: false,
  includeStacktraceInErrorResponses: false,
  allowBatchedHttpRequests: false,
  plugins: [politicas],
  formatError(formatted) {
    const ext = formatted.extensions ?? {};
    const deApollo = CODIGOS_CONSULTA.has(ext.code);
    let code = deApollo ? 'CONSULTA_INVALIDA' : ext.code;
    if (!code || code === 'INTERNAL_SERVER_ERROR') code = 'ERROR_INTERNO';
    // los mensajes de Apollo (sugerencias de campos, introspeccion) se reemplazan para no describir el schema
    const mensaje = code === 'ERROR_INTERNO' ? 'Error interno.' : deApollo ? 'La consulta no es válida para este servicio.' : formatted.message;
    return { message: mensaje, ...(formatted.path ? { path: formatted.path } : {}), extensions: { code } };
  },
});
await server.start();

// ---------------- Express ----------------
const app = express();
app.disable('x-powered-by');
app.get('/health', (_req, res) => res.json({ ok: true }));

app.use('/graphql', async (req, res, next) => {
  const rid = req.get('x-request-id') || 'req_' + crypto.randomBytes(6).toString('hex');
  req.rid = rid;
  res.set('X-Request-Id', rid);
  const t0 = Date.now();
  res.on('finish', () => log('acceso', { requestId: rid, verbo: req.method, ruta: '/graphql', estado: res.statusCode, ms: Date.now() - t0,
    cuentaId: req.cuenta ?? null, operaciones: req.ctx?.operaciones ?? null, costo: req.ctx?.costo ?? null }));
  const rechazo = (status, code, message) => res.status(status).json({ errors: [{ message, extensions: { code, requestId: rid } }] });
  try {
    const recibido = req.get('x-gateway-secret');
    const validos = await candidatos('services/gateway-to-graphql');
    if (!validos.some((v) => iguales(recibido, v))) return rechazo(401, 'CREDENCIAL_INVALIDA', 'Credencial inválida.');
  } catch { return rechazo(503, 'SECRETOS_NO_DISPONIBLES', 'Servicio no disponible.'); }
  if (!req.get('x-authenticated-user')) return rechazo(401, 'NO_AUTENTICADO', 'Debes iniciar sesión.');
  req.cuenta = req.get('x-authenticated-user');
  next();
});
app.use('/graphql', express.json({ limit: '16kb' }), (req, res, next) => {
  if (Array.isArray(req.body)) return res.status(400).json({ errors: [{ message: 'No se permiten lotes de operaciones.', extensions: { code: 'CONSULTA_INVALIDA', requestId: req.rid } }] });
  next();
});
app.use('/graphql', expressMiddleware(server, {
  context: async ({ req }) => {
    const ctx = {
      rid: req.rid, cuenta: req.get('x-authenticated-user'), email: req.get('x-authenticated-email') ?? '',
      roles: (req.get('x-authenticated-roles') ?? '').split(',').filter(Boolean), limitePedidos: 5,
    };
    ctx.loaders = crearLoaders(ctx);
    req.ctx = ctx;
    return ctx;
  },
}));
// errores de formato del cuerpo (JSON invalido o demasiado grande)
app.use((e, req, res, _next) => {
  const grande = e.type === 'entity.too.large';
  res.status(grande ? 413 : 400).json({ errors: [{ message: grande ? 'El cuerpo es demasiado grande.' : 'Cuerpo inválido.', extensions: { code: 'CONSULTA_INVALIDA', requestId: req.rid } }] });
});

const port = Number(process.env.PORT);
const host = process.env.HOST || '127.0.0.1';
const srv = process.env.TLS_CERT
  ? https.createServer({ cert: fs.readFileSync(process.env.TLS_CERT), key: fs.readFileSync(process.env.TLS_KEY) }, app)
  : http.createServer(app);
srv.listen(port, host, () => log('iniciado', { puerto: port }));
