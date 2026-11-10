// Llamadas de solo lectura a orders, inventory y clients con el par de credenciales de cada sistema (GET unicamente).
import https from 'node:https';
import fs from 'node:fs';
import { GraphQLError } from 'graphql';
import { secreto } from './vault.js';

const ca = fs.readFileSync(process.env.CA_FILE);
const agente = new https.Agent({ ca, keepAlive: true });
const PLAZO_MS = 5000;

function pedir(url, headers) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers, agent: agente, timeout: PLAZO_MS }, (res) => {
      const trozos = [];
      res.on('data', (c) => trozos.push(c));
      res.on('end', () => {
        let json = null;
        try { json = JSON.parse(Buffer.concat(trozos).toString('utf8')); } catch { /* cuerpo no JSON */ }
        resolve({ status: res.statusCode, json });
      });
    });
    req.on('timeout', () => req.destroy(Object.assign(new Error('plazo'), { plazo: true })));
    req.on('error', reject);
  });
}

/** sistema: 'orders' | 'inventory' | 'clients'. Devuelve {status, json}. Lanza GraphQLError si no hay respuesta o hay 5xx. */
export async function leer(sistema, ruta, ctx, log) {
  const t0 = Date.now();
  const par = await secreto(`services/graphql-to-${sistema}`);
  const headers = {
    'X-Service-Id': 'graphql-gateway', 'X-Service-Secret': par.actual, 'X-Request-Id': ctx.rid,
    'X-Authenticated-User': ctx.cuenta, 'X-Authenticated-Email': ctx.email, 'X-Authenticated-Roles': ctx.roles.join(','),
  };
  const base = process.env[`URL_${sistema.toUpperCase()}`].replace(/\/$/, '');
  let r;
  try {
    r = await pedir(base + ruta, headers);
  } catch (e) {
    log('llamada', { requestId: ctx.rid, sistema, ruta: ruta.split('?')[0], estado: e.plazo ? 'plazo' : 'sin_respuesta', ms: Date.now() - t0 });
    throw new GraphQLError(sistema === 'inventory' ? 'El catálogo no está disponible.' : 'Un servicio no está disponible.', {
      extensions: { code: e.plazo ? 'PLAZO_EXCEDIDO' : 'SUBSISTEMA_NO_DISPONIBLE', sistema },
    });
  }
  log('llamada', { requestId: ctx.rid, sistema, ruta: ruta.split('?')[0], estado: r.status, ms: Date.now() - t0 });
  if (r.status >= 500) {
    throw new GraphQLError('Un servicio no está disponible.', { extensions: { code: 'SUBSISTEMA_NO_DISPONIBLE', sistema } });
  }
  return r;
}
