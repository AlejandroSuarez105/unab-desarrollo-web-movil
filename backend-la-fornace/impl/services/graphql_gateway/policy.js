// Politicas del Modulo 8 (8.8 y 8.9): operacion, campo, profundidad, costo y paginacion. Se evaluan antes de llamar a ningun sistema.
import { GraphQLError, Kind, getNamedType, isListType, isNonNullType, getArgumentValues } from 'graphql';

export const LIMITES = { camposPrimerNivel: 3, profundidad: Number(process.env.GQL_PROFUNDIDAD || 5), costo: 600, maxItems: 30, maxHistorial: 10, limitePedidosMin: 1, limitePedidosMax: 20 };
const LECTURA = ['cliente', 'administrador', 'cajero_virtual', 'encargado_despachos'];
const PERSONAL = ['administrador', 'cajero_virtual', 'encargado_despachos'];
export const OPERACIONES = { resumenPedido: LECTURA, miCuenta: ['cliente'] };
export const CAMPOS = { 'ResumenPedido.clienteNombre': PERSONAL };

export function err(code, message, status = 400) {
  return new GraphQLError(message, { extensions: { code, http: { status } } });
}

function esLista(tipo) { return isListType(isNonNullType(tipo) ? tipo.ofType : tipo); }

function multiplicador(padre, campo, argsPadre) {
  const clave = `${padre}.${campo}`;
  if (clave === 'ResumenPedido.items') return LIMITES.maxItems;
  if (clave === 'ResumenPedido.historialEstados') return LIMITES.maxHistorial;
  if (clave === 'MiCuenta.pedidos') return Math.min(argsPadre.limitePedidos ?? 5, LIMITES.limitePedidosMax);
  return 1;
}

/** Recorre la consulta y devuelve profundidad, costo y campos usados. Costo: escalar = 1; objeto = 1 + hijos; lista = tamano maximo x (1 + hijos). */
export function analizar(schema, documento, operacion, variables) {
  const frag = Object.fromEntries(documento.definitions.filter((d) => d.kind === Kind.FRAGMENT_DEFINITION).map((d) => [d.name.value, d]));
  const usados = new Set();
  let maxProf = 0;
  const tops = [];

  function sel(set, tipoPadre, nivel, argsPadre = {}) {
    let suma = 0;
    for (const s of set.selections) {
      if (s.kind === Kind.FIELD) {
        if (s.name.value === '__typename') continue;
        const def = tipoPadre.getFields()[s.name.value];
        if (!def) continue;
        usados.add(`${tipoPadre.name}.${s.name.value}`);
        maxProf = Math.max(maxProf, nivel);
        const args = getArgumentValues(def, s, variables);
        const nombrado = getNamedType(def.type);
        let costo = 1;
        if (s.selectionSet && nombrado.getFields) {
          const hijos = sel(s.selectionSet, nombrado, nivel + 1, args);
          costo = (esLista(def.type) ? multiplicador(tipoPadre.name, s.name.value, argsPadre) : 1) * (1 + hijos);
        }
        if (nivel === 1) tops.push({ nombre: s.name.value, alias: s.alias?.value, args });
        suma += costo;
      } else if (s.kind === Kind.INLINE_FRAGMENT) {
        suma += sel(s.selectionSet, s.typeCondition ? schema.getType(s.typeCondition.name.value) : tipoPadre, nivel, argsPadre);
      } else if (s.kind === Kind.FRAGMENT_SPREAD) {
        const f = frag[s.name.value];
        suma += sel(f.selectionSet, schema.getType(f.typeCondition.name.value), nivel, argsPadre);
      }
    }
    return suma;
  }
  const costo = sel(operacion.selectionSet, schema.getQueryType(), 1);
  return { profundidad: maxProf, costo: costo, usados, tops };
}

/** Lanza el error que corresponda, en el orden: operacion valida, primer nivel, profundidad, costo, argumentos, operacion autorizada, campos. */
export function evaluar(schema, documento, operacion, variables, roles) {
  if (operacion.operation !== 'query') throw err('CONSULTA_INVALIDA', 'Solo se permiten consultas.');
  const a = analizar(schema, documento, operacion, variables);
  if (a.tops.length > LIMITES.camposPrimerNivel) throw err('LIMITE_COSTO', 'La consulta tiene demasiados campos de primer nivel.');
  if (a.profundidad > LIMITES.profundidad) throw err('LIMITE_PROFUNDIDAD', 'La consulta es demasiado profunda.');
  if (a.costo > LIMITES.costo) throw err('LIMITE_COSTO', 'La consulta es demasiado costosa.');
  for (const t of a.tops) {
    if (t.nombre === 'miCuenta') {
      const n = t.args.limitePedidos;
      if (!Number.isInteger(n) || n < LIMITES.limitePedidosMin || n > LIMITES.limitePedidosMax) throw err('CONSULTA_INVALIDA', 'limitePedidos debe estar entre 1 y 20.');
    }
  }
  for (const t of a.tops) {
    const permitidos = OPERACIONES[t.nombre];
    if (permitidos && !roles.some((r) => permitidos.includes(r))) throw err('OPERACION_NO_AUTORIZADA', 'No tienes permiso para esta operación.', 403);
  }
  for (const campo of a.usados) {
    const permitidos = CAMPOS[campo];
    if (permitidos && !roles.some((r) => permitidos.includes(r))) {
      throw err('CAMPO_NO_AUTORIZADO', `No tienes permiso para consultar el campo ${campo.split('.')[1]}.`, 403);
    }
  }
  return a;
}
