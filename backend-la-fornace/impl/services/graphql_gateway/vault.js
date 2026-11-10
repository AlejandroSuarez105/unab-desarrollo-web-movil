// Cliente minimo de Vault (KV v2) con cache. Los secretos nunca se registran.
import http from 'node:http';
import fs from 'node:fs';
import crypto from 'node:crypto';

const cache = new Map();
const TTL = 300_000;

function get(url, token) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, { headers: { 'X-Vault-Token': token }, timeout: 3000 }, (res) => {
      let b = '';
      res.on('data', (c) => (b += c));
      res.on('end', () => (res.statusCode === 200 ? resolve(JSON.parse(b)) : reject(new Error('vault ' + res.statusCode))));
    });
    req.on('error', reject);
    req.on('timeout', () => req.destroy(new Error('vault timeout')));
  });
}

export async function secreto(ruta) {
  const hit = cache.get(ruta);
  if (hit && Date.now() - hit.t < TTL) return hit.v;
  try {
    const token = fs.readFileSync(process.env.VAULT_TOKEN_FILE, 'utf8').trim();
    const r = await get(`${process.env.VAULT_ADDR.replace(/\/$/, '')}/v1/secret/data/${ruta}`, token);
    cache.set(ruta, { t: Date.now(), v: r.data.data });
    return r.data.data;
  } catch (e) {
    if (hit) return hit.v;   // valor anterior si Vault no responde
    throw new Error('secreto no disponible');
  }
}

export async function candidatos(ruta) {
  const v = await secreto(ruta);
  return [v.actual, v.anterior].filter(Boolean);
}

export function iguales(a, b) {
  const x = Buffer.from(a || ''), y = Buffer.from(b || '');
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}
