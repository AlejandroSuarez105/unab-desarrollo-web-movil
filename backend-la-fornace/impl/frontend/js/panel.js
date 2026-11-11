/**
 * Panel interno (P13 a P18). Cada seccion se muestra solo a los roles que la usan; la autorizacion real la hace el backend en cada llamada.
 */
const SECCIONES = [
  { id: "productos", titulo: "Productos", roles: ["administrador", "dueno"], render: pProductos },
  { id: "pedidos", titulo: "Pedidos y ventas", roles: ["administrador", "cajero_virtual", "encargado_despachos"], render: pPedidos },
  { id: "despacho", titulo: "Despacho", roles: ["administrador", "encargado_despachos"], render: pDespacho },
  { id: "clientes", titulo: "Clientes", roles: ["administrador"], render: pClientes },
  { id: "usuarios", titulo: "Usuarios", roles: ["administrador"], render: pUsuarios },
  { id: "reporte", titulo: "Reporte de ventas", roles: ["administrador", "dueno"], render: pReporte },
];
const ESTADOS_P = { pendiente_pago: "Pendiente de pago", pagado: "Pagado", en_preparacion: "En preparación", en_despacho: "En despacho", entregado: "Entregado", anulado: "Anulado" };
const SIGUIENTE = { pagado: "en_preparacion", en_preparacion: "en_despacho", en_despacho: "entregado" };
const cont = () => document.getElementById("panel-contenido");

function falla(e) {
  const b = document.getElementById("panel-error");
  b.textContent = mensajeError(e);
  b.classList.remove("d-none");
}
function sinFalla() { document.getElementById("panel-error").classList.add("d-none"); }

function tabla(cols, filas) {
  if (!filas.length) return '<p class="texto-muted">Sin resultados.</p>';
  return `<div class="table-responsive"><table class="table table-dark table-sm align-middle"><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${filas.map((f) => `<tr>${f.map((x) => `<td>${x}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

/** Ventana con formulario. campos: [{n, etiqueta, tipo, opciones, valor}] */
function formulario(titulo, campos, alGuardar) {
  document.getElementById("mf-titulo").textContent = titulo;
  const f = document.getElementById("mf-form");
  f.innerHTML = campos.map((c) => `<div class="mb-2"><label class="form-label small">${esc(c.etiqueta)}</label>` + (c.opciones
    ? `<select name="${c.n}" class="form-select">${c.opciones.map((o) => `<option value="${esc(o)}" ${String(c.valor) === String(o) ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`
    : `<input name="${c.n}" type="${c.tipo || "text"}" class="form-control" value="${esc(c.valor ?? "")}" ${c.tipo === "checkbox" && c.valor ? "checked" : ""}>`) + "</div>").join("");
  const err = document.getElementById("mf-error"); err.classList.add("d-none");
  const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById("modalForm"));
  document.getElementById("mf-guardar").onclick = async () => {
    const v = {};
    campos.forEach((c) => { const el = f.elements[c.n]; v[c.n] = c.tipo === "checkbox" ? el.checked : c.tipo === "number" ? Number(el.value) : el.value.trim(); });
    try { await alGuardar(v); modal.hide(); } catch (e) { err.textContent = mensajeError(e); err.classList.remove("d-none"); }
  };
  modal.show();
}

/* ---------- P13 Productos (S07 S08 S09 S10 S11) ---------- */
async function pProductos() {
  const lista = await api("GET", "/admin/products?incluirRetirados=true&limit=100");
  cont().innerHTML = '<button class="btn btn-fornace btn-sm mb-3" id="nuevo-prod">Nuevo producto</button>' +
    tabla(["ID", "Nombre", "Categoría", "Precio", "Stock", "Disponible", "Retirado", ""], lista.map((p) => [
      esc(p.id), esc(p.nombre), esc(p.categoria), formatCLP(p.precio), p.stock, p.disponible ? "Sí" : "No", p.retirado ? "Sí" : "No",
      p.retirado ? "" : `<button class="btn btn-sm btn-fornace-outline" data-stock="${esc(p.id)}" data-v="${p.stock}">Stock</button>
        <button class="btn btn-sm btn-fornace-outline" data-edit="${esc(p.id)}">Editar</button>
        <button class="btn btn-sm btn-outline-danger" data-ret="${esc(p.id)}">Retirar</button>`]));
  const campos = (v = {}) => [
    { n: "nombre", etiqueta: "Nombre", valor: v.nombre }, { n: "categoria", etiqueta: "Categoría", opciones: ["clasica", "premium", "acompanamiento", "bebida", "combo"], valor: v.categoria },
    { n: "descripcion", etiqueta: "Descripción", valor: v.descripcion }, { n: "precio", etiqueta: "Precio (CLP)", tipo: "number", valor: v.precio },
    { n: "imagen", etiqueta: "URL de la imagen", valor: v.imagen }, { n: "destacado", etiqueta: "Destacado", tipo: "checkbox", valor: v.destacado }];
  document.getElementById("nuevo-prod").onclick = () => formulario("Nuevo producto", [...campos(), { n: "stock", etiqueta: "Stock inicial", tipo: "number", valor: 0 }],
    async (v) => { await api("POST", "/products", v); mostrarToast("Producto creado"); pProductos().catch(falla); });
  cont().querySelectorAll("[data-stock]").forEach((b) => b.onclick = () => formulario("Disponibilidad y stock " + b.dataset.stock,
    [{ n: "stock", etiqueta: "Stock", tipo: "number", valor: b.dataset.v }, { n: "disponible", etiqueta: "Disponible", tipo: "checkbox", valor: true }],
    async (v) => { await api("PUT", `/products/${b.dataset.stock}/stock`, v); mostrarToast("Stock actualizado"); pProductos().catch(falla); }));
  cont().querySelectorAll("[data-edit]").forEach((b) => b.onclick = async () => {
    const cat = await api("GET", "/products?limit=100", undefined, { anonimo: true });
    const p = cat.find((x) => x.id === b.dataset.edit) || {};
    formulario("Editar " + b.dataset.edit, campos(p), async (v) => { await api("PUT", `/products/${b.dataset.edit}`, v); mostrarToast("Producto guardado"); pProductos().catch(falla); });
  });
  cont().querySelectorAll("[data-ret]").forEach((b) => b.onclick = async () => {
    if (!confirm("¿Retirar el producto " + b.dataset.ret + "? El historial de pedidos se conserva.")) return;
    try { await api("DELETE", "/products/" + b.dataset.ret); pProductos().catch(falla); } catch (e) { falla(e); }
  });
}

/* ---------- P14 Pedidos y ventas (S16 S17 S22) ---------- */
async function pPedidos() {
  const rol = sesion().rol;
  const lista = await api("GET", "/admin/orders?limit=50");
  let html = tabla(["Pedido", "Estado", "Total", "Creado", "Cliente", "Entrega", ""], lista.map((p) => {
    const sig = SIGUIENTE[p.estado];
    const puede = rol === "administrador" || rol === "encargado_despachos";
    return [esc(p.id), esc(ESTADOS_P[p.estado] || p.estado), formatCLP(p.total), esc(p.creadoEn), esc(p.clienteNombre), esc(`${p.direccionEntrega.calle}, ${p.direccionEntrega.comuna}`),
      (puede && sig ? `<button class="btn btn-sm btn-fornace-outline" data-sig="${esc(p.id)}" data-e="${sig}">→ ${esc(ESTADOS_P[sig])}</button> ` : "") +
      (rol === "administrador" && ["pendiente_pago", "pagado", "en_preparacion"].includes(p.estado) ? `<button class="btn btn-sm btn-outline-danger" data-anu="${esc(p.id)}">Anular</button>` : "")];
  }));
  if (rol === "administrador" || rol === "cajero_virtual") {
    const ventas = await api("GET", "/admin/sales?limit=50");
    html += '<h2 class="h5 mt-4">Ventas de la caja virtual</h2>' + tabla(["Venta", "Pedido", "Boleta", "Total", "Fecha", "Correo enviado"],
      ventas.map((v) => [esc(v.ventaId), esc(v.pedidoId), esc(v.numeroBoleta), formatCLP(v.total), esc(v.fecha), v.correoEnviado ? "Sí" : "No"]));
  }
  cont().innerHTML = html;
  cont().querySelectorAll("[data-sig]").forEach((b) => b.onclick = async () => {
    try { await api("PATCH", `/admin/orders/${b.dataset.sig}/status`, { estado: b.dataset.e }); pPedidos().catch(falla); } catch (e) { falla(e); }
  });
  cont().querySelectorAll("[data-anu]").forEach((b) => b.onclick = () => formulario("Anular " + b.dataset.anu, [{ n: "motivo", etiqueta: "Motivo (5 a 200 caracteres)" }],
    async (v) => { await api("PATCH", `/admin/orders/${b.dataset.anu}/status`, { estado: "anulado", motivo: v.motivo }); pPedidos().catch(falla); }));
}

/* ---------- P15 Despacho (S18 S19) ---------- */
async function pDespacho() {
  const cola = await api("GET", "/admin/dispatch-orders?impresa=false&limit=50");
  cont().innerHTML = "<p class='texto-muted'>Órdenes pagadas, de la más antigua a la más reciente.</p>" + tabla(["Orden", "Pedido", "Pagado", "Cliente", "Teléfono", "Entrega", "Ítems", ""],
    cola.map((o) => [esc(o.numeroOrden), esc(o.pedidoId), esc(o.pagadoEn), esc(o.clienteNombre), esc(o.telefono), esc(`${o.direccionEntrega.calle}, ${o.direccionEntrega.comuna}`),
      o.items.map((i) => `${esc(i.nombre)} × ${i.cantidad}`).join("<br>"), `<button class="btn btn-sm btn-fornace" data-print="${esc(o.pedidoId)}">Imprimir</button>`]));
  cont().querySelectorAll("[data-print]").forEach((b) => b.onclick = async () => {
    try {
      // la orden es HTML: se pide con el token y se muestra en una ventana nueva para imprimir
      const r = await fetch(window.FORNACE.API + `/admin/dispatch-orders/${encodeURIComponent(b.dataset.print)}/print`, { headers: { Authorization: "Bearer " + sesion().token } });
      if (!r.ok) throw new ErrorApi(r.status, "ERROR", "No se pudo obtener la orden.");
      const url = URL.createObjectURL(new Blob([await r.text()], { type: "text/html" }));
      window.open(url, "_blank");
      pDespacho().catch(falla);
    } catch (e) { falla(e); }
  });
}

/* ---------- P16 Clientes (S26 S27 S28 S29) ---------- */
const CAMPOS_CLIENTE = (v = {}) => [
  { n: "nombreCompleto", etiqueta: "Nombre completo", valor: v.nombreCompleto }, { n: "telefono", etiqueta: "Teléfono", valor: v.telefono },
  { n: "fechaNacimiento", etiqueta: "Nacimiento", tipo: "date", valor: v.fechaNacimiento }, { n: "sexo", etiqueta: "Sexo", opciones: ["F", "M", "O"], valor: v.sexo },
  { n: "calle", etiqueta: "Calle y número", valor: v.direccion?.calle }, { n: "comuna", etiqueta: "Comuna", valor: v.direccion?.comuna || "Maipú" },
  { n: "provincia", etiqueta: "Provincia", valor: v.direccion?.provincia || "Santiago" }, { n: "region", etiqueta: "Región", valor: v.direccion?.region || "Metropolitana" }];
const cuerpoCliente = (v) => ({ nombreCompleto: v.nombreCompleto, telefono: v.telefono, fechaNacimiento: v.fechaNacimiento, sexo: v.sexo,
  direccion: { calle: v.calle, comuna: v.comuna, provincia: v.provincia, region: v.region } });

async function pClientes() {
  const lista = await api("GET", "/admin/clients?limit=100");
  cont().innerHTML = '<button class="btn btn-fornace btn-sm mb-3" id="nuevo-cli">Registrar cliente</button>' +
    tabla(["ID", "RUN", "Nombre", "Correo", "Teléfono", "Estado", ""], lista.map((c) => [esc(c.id), esc(c.run), esc(c.nombreCompleto), esc(c.correo), esc(c.telefono), esc(c.estado),
      `<button class="btn btn-sm btn-fornace-outline" data-edit="${esc(c.id)}">Editar</button> <button class="btn btn-sm btn-outline-danger" data-baja="${esc(c.id)}">Dar de baja</button>`]));
  document.getElementById("nuevo-cli").onclick = () => formulario("Registrar cliente", [{ n: "run", etiqueta: "RUN" }, { n: "correo", etiqueta: "Correo", tipo: "email" }, ...CAMPOS_CLIENTE()],
    async (v) => { await api("POST", "/admin/clients", { run: v.run, correo: v.correo, ...cuerpoCliente(v) }); mostrarToast("Cliente registrado. Recibirá un correo para definir su contraseña."); pClientes().catch(falla); });
  cont().querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => {
    const c = lista.find((x) => x.id === b.dataset.edit);
    formulario("Editar " + c.id, CAMPOS_CLIENTE(c), async (v) => { await api("PUT", "/admin/clients/" + c.id, cuerpoCliente(v)); pClientes().catch(falla); });
  });
  cont().querySelectorAll("[data-baja]").forEach((b) => b.onclick = async () => {
    if (!confirm("¿Dar de baja al cliente? Sus pedidos y ventas se conservan.")) return;
    try { await api("DELETE", "/admin/clients/" + b.dataset.baja); pClientes().catch(falla); } catch (e) { falla(e); }
  });
}

/* ---------- P17 Usuarios (S30 S31 S32 S33) ---------- */
const ROLES_P = ["administrador", "dueno", "cajero_virtual", "encargado_despachos"];
async function pUsuarios() {
  const lista = await api("GET", "/admin/users?limit=100");
  cont().innerHTML = '<button class="btn btn-fornace btn-sm mb-3" id="nuevo-usr">Nuevo usuario</button>' +
    tabla(["ID", "Nombre", "Correo", "Rol", "Estado", ""], lista.map((u) => [esc(u.id), esc(u.nombreCompleto), esc(u.correo), esc(u.rol), esc(u.estado),
      `<button class="btn btn-sm btn-fornace-outline" data-edit="${esc(u.id)}">Editar</button> <button class="btn btn-sm btn-outline-danger" data-baja="${esc(u.id)}">Dar de baja</button>`]));
  document.getElementById("nuevo-usr").onclick = () => formulario("Nuevo usuario", [{ n: "nombreCompleto", etiqueta: "Nombre completo" }, { n: "correo", etiqueta: "Correo", tipo: "email" }, { n: "rol", etiqueta: "Rol", opciones: ROLES_P }],
    async (v) => { await api("POST", "/admin/users", v); mostrarToast("Usuario creado. Recibirá un correo para definir su contraseña."); pUsuarios().catch(falla); });
  cont().querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => {
    const u = lista.find((x) => x.id === b.dataset.edit);
    formulario("Editar " + u.id, [{ n: "nombreCompleto", etiqueta: "Nombre completo", valor: u.nombreCompleto }, { n: "rol", etiqueta: "Rol", opciones: ROLES_P, valor: u.rol },
      { n: "activo", etiqueta: "Activo", tipo: "checkbox", valor: u.estado !== "inactivo" }], async (v) => { await api("PUT", "/admin/users/" + u.id, v); pUsuarios().catch(falla); });
  });
  cont().querySelectorAll("[data-baja]").forEach((b) => b.onclick = async () => {
    if (!confirm("¿Dar de baja al usuario? Sus sesiones se cierran.")) return;
    try { await api("DELETE", "/admin/users/" + b.dataset.baja); pUsuarios().catch(falla); } catch (e) { falla(e); }
  });
}

/* ---------- P18 Reporte de ventas (S34) ---------- */
async function pReporte() {
  const hoy = new Date().toISOString().slice(0, 10), mes = new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10);
  cont().innerHTML = `<form id="f-rep" class="row g-2 mb-3"><div class="col-auto"><input type="date" name="desde" class="form-control" value="${mes}" required></div>
    <div class="col-auto"><input type="date" name="hasta" class="form-control" value="${hoy}" required></div><div class="col-auto"><button class="btn btn-fornace">Generar reporte</button></div></form><div id="rep"></div>`;
  document.getElementById("f-rep").onsubmit = async (ev) => {
    ev.preventDefault(); sinFalla();
    const f = ev.target;
    try {
      const r = await api("GET", `/admin/reports/sales?desde=${f.desde.value}&hasta=${f.hasta.value}`);
      document.getElementById("rep").innerHTML = `<p><strong>Total recaudado:</strong> ${formatCLP(r.totalVentas)} · <strong>Ventas:</strong> ${r.cantidadVentas}</p>
        <p class="texto-muted small">El total no descuenta reembolsos pendientes.</p><h6>Por día</h6>${tabla(["Fecha", "Ventas", "Total"], r.porDia.map((d) => [esc(d.fecha), d.ventas, formatCLP(d.total)]))}
        <h6>Productos más vendidos</h6>${tabla(["Producto", "Unidades"], r.topProductos.map((p) => [esc(p.nombre), p.unidades]))}`;
    } catch (e) { falla(e); }
  };
}

async function abrirSeccion(s) {
  sinFalla();
  document.querySelectorAll("#panel-tabs .nav-link").forEach((a) => a.classList.toggle("active", a.dataset.id === s.id));
  cont().innerHTML = "Cargando…";
  try { await s.render(); } catch (e) { cont().innerHTML = ""; falla(e); }
}

function iniciarPanel() {
  const s = sesion();
  if (!s.token || s.rol === "cliente") { location.href = "index.html?login=1"; return; }
  document.getElementById("panel-quien").textContent = `${s.nombre} · ${s.rol}`;
  const mias = SECCIONES.filter((x) => x.roles.includes(s.rol));
  const tabs = document.getElementById("panel-tabs");
  tabs.innerHTML = mias.map((x) => `<li class="nav-item"><a href="#" class="nav-link icono-boton" data-id="${x.id}">${esc(x.titulo)}</a></li>`).join("");
  tabs.querySelectorAll("a").forEach((a) => a.onclick = (ev) => { ev.preventDefault(); abrirSeccion(mias.find((x) => x.id === a.dataset.id)); });
  abrirSeccion(mias[0]);
}
document.addEventListener("DOMContentLoaded", iniciarPanel);
