/**
 * Pizzeria La Fornace — logica de interfaz conectada al backend (/api/v1).
 * El carrito (solo id y cantidad) se guarda en localStorage; el resto viene de los servicios.
 */

const CARRITO_KEY = "fornace_carrito";

/* ---------------- Carrito (almacenamiento local) ---------------- */
function leerCarrito() {
  try {
    const raw = localStorage.getItem(CARRITO_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function guardarCarrito(carrito) {
  localStorage.setItem(CARRITO_KEY, JSON.stringify(carrito));
  actualizarBadgeCarrito();
}

function agregarAlCarrito(productoId, cantidad = 1) {
  const carrito = leerCarrito();
  const existente = carrito.find((i) => i.id === productoId);
  if (existente) {
    existente.cantidad += cantidad;
  } else {
    carrito.push({ id: productoId, cantidad });
  }
  guardarCarrito(carrito);
  mostrarToast("Se agregó a tu pedido");
}

function actualizarCantidad(productoId, delta) {
  const carrito = leerCarrito();
  const item = carrito.find((i) => i.id === productoId);
  if (!item) return;
  item.cantidad += delta;
  const nuevoCarrito = item.cantidad <= 0 ? carrito.filter((i) => i.id !== productoId) : carrito;
  guardarCarrito(nuevoCarrito);
  renderCarrito();
}

function eliminarDelCarrito(productoId) {
  const carrito = leerCarrito().filter((i) => i.id !== productoId);
  guardarCarrito(carrito);
  renderCarrito();
}

function totalItemsCarrito() {
  return leerCarrito().reduce((acc, i) => acc + i.cantidad, 0);
}

function actualizarBadgeCarrito() {
  document.querySelectorAll("[data-badge-carrito]").forEach((el) => {
    const total = totalItemsCarrito();
    el.textContent = total;
    el.style.display = total > 0 ? "inline-block" : "none";
  });
}

/* ---------------- Aviso en pantalla ---------------- */
function mostrarToast(mensaje) {
  const contenedor = document.getElementById("toast-contenedor");
  if (!contenedor) return;

  const toastEl = document.createElement("div");
  toastEl.className = "toast toast-fornace align-items-center border-0";
  toastEl.setAttribute("role", "alert");
  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${mensaje}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  contenedor.appendChild(toastEl);

  const toast = new bootstrap.Toast(toastEl, { delay: 2500 });
  toast.show();
  toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}

/* ---------------- Catalogo (S06) ---------------- */
let CATALOGO = null;
async function cargarCatalogo() {
  if (CATALOGO) return CATALOGO;
  try {
    CATALOGO = await api("GET", "/products?limit=100", undefined, { anonimo: true });
  } catch (e) {
    CATALOGO = [];
    mostrarToast(mensajeError(e));
  }
  return CATALOGO;
}

function etiquetaCategoria(cat) {
  const mapa = { clasica: "Clásica", premium: "Premium", bebida: "Bebida", acompanamiento: "Acompañamiento", combo: "Combo" };
  return mapa[cat] || cat;
}

async function renderProductos(contenedorId, categoriaFiltro = "todas", filtro = null) {
  const contenedor = document.getElementById(contenedorId);
  if (!contenedor) return;
  let lista = (await cargarCatalogo()).filter((p) => p.categoria !== "combo");
  if (categoriaFiltro !== "todas") lista = (await cargarCatalogo()).filter((p) => p.categoria === categoriaFiltro);
  if (filtro) lista = lista.filter(filtro);
  if (lista.length === 0) { contenedor.innerHTML = '<p class="texto-muted">No hay productos disponibles por ahora.</p>'; return; }
  contenedor.innerHTML = lista.map((p) => `
    <div class="col-12 col-sm-6 col-lg-4 col-xl-3">
      <div class="card-producto">
        <img src="${esc(p.imagen)}" alt="${esc(p.nombre)}" loading="lazy">
        <div class="cuerpo">
          <span class="categoria-tag">${etiquetaCategoria(p.categoria)}</span>
          <h3 class="h5 mb-0">${esc(p.nombre)}</h3>
          <p class="texto-muted small mb-1">${esc(p.descripcion)}</p>
          <div class="d-flex align-items-center justify-content-between mt-auto">
            <span class="precio">${formatCLP(p.precio)}</span>
            ${p.disponible ? `<button class="btn btn-fornace btn-sm" onclick="agregarAlCarrito('${esc(p.id)}')">Agregar</button>`
                           : '<span class="badge bg-secondary">Agotado</span>'}
          </div>
        </div>
      </div>
    </div>`).join("");
}

async function renderCombos(contenedorId) {
  const contenedor = document.getElementById(contenedorId);
  if (!contenedor) return;
  const combos = (await cargarCatalogo()).filter((p) => p.categoria === "combo");
  contenedor.innerHTML = combos.map((c) => `
    <div class="col-12 col-sm-6 col-lg-3">
      <div class="card-combo">
        <h3>${esc(c.nombre)}</h3>
        <p class="texto-muted small mb-0">${esc(c.descripcion)}</p>
        <div class="precio">${formatCLP(c.precio)}</div>
        ${c.disponible ? `<button class="btn btn-fornace w-100" onclick="agregarAlCarrito('${esc(c.id)}')">Pedir combo</button>`
                       : '<button class="btn btn-secondary w-100" disabled>Agotado</button>'}
      </div>
    </div>`).join("");
}

/* ---------------- Carrito (pantalla P03) ----------------
   El carrito guarda solo id y cantidad. Los precios se muestran desde el catalogo, pero el total real lo calcula el servidor al crear el pedido (S12). */
let PERFIL = null;

async function renderCarrito() {
  const contenedor = document.getElementById("lista-carrito");
  const vacio = document.getElementById("carrito-vacio");
  const resumen = document.getElementById("resumen-carrito");
  if (!contenedor) return;
  const carrito = leerCarrito();
  if (carrito.length === 0) {
    contenedor.innerHTML = "";
    if (vacio) vacio.classList.remove("d-none");
    if (resumen) resumen.classList.add("d-none");
    return;
  }
  if (vacio) vacio.classList.add("d-none");
  if (resumen) resumen.classList.remove("d-none");
  const cat = await cargarCatalogo();
  let subtotal = 0;
  contenedor.innerHTML = carrito.map((item) => {
    const p = cat.find((x) => x.id === item.id);
    if (!p) return "";
    const totalLinea = p.precio * item.cantidad;
    subtotal += totalLinea;
    return `
      <div class="item-carrito mb-3">
        <img src="${esc(p.imagen)}" alt="${esc(p.nombre)}">
        <div class="flex-grow-1">
          <h4 class="h6 mb-1">${esc(p.nombre)}</h4>
          <span class="texto-muted small">${formatCLP(p.precio)} c/u</span>
        </div>
        <div class="control-cantidad d-flex align-items-center gap-2">
          <button onclick="actualizarCantidad('${esc(item.id)}', -1)">−</button>
          <span>${item.cantidad}</span>
          <button onclick="actualizarCantidad('${esc(item.id)}', 1)">+</button>
        </div>
        <div class="text-end" style="min-width:90px;">
          <div class="precio">${formatCLP(totalLinea)}</div>
          <button class="btn btn-link btn-sm text-danger p-0" onclick="eliminarDelCarrito('${esc(item.id)}')">Quitar</button>
        </div>
      </div>`;
  }).join("");
  document.getElementById("carrito-subtotal").textContent = formatCLP(subtotal);
  document.getElementById("carrito-total").textContent = formatCLP(subtotal);
  await precargarDireccion();
}

async function precargarDireccion() {
  const s = sesion();
  const aviso = document.getElementById("aviso-sesion");
  const form = document.getElementById("form-entrega");
  if (!form) return;
  if (!s.token || s.rol !== "cliente") {
    aviso.classList.remove("d-none");
    form.classList.add("d-none");
    return;
  }
  aviso.classList.add("d-none");
  form.classList.remove("d-none");
  if (!PERFIL) {
    try { PERFIL = await api("GET", "/clients/me"); } catch (e) { PERFIL = null; }
  }
  if (PERFIL && !form.calle.value) {
    form.calle.value = PERFIL.direccion.calle;
    form.comuna.value = PERFIL.direccion.comuna;
  }
}

/** Confirma el pedido (S12) y abre la plataforma de pago (S20). La Idempotency-Key evita pedidos duplicados por doble clic. */
async function confirmarPedido(event) {
  event.preventDefault();
  const form = document.getElementById("form-entrega");
  const aviso = document.getElementById("aviso-error");
  aviso.classList.add("d-none");
  if (!form.checkValidity()) { form.classList.add("was-validated"); return; }
  const boton = document.getElementById("btn-confirmar");
  boton.disabled = true;
  try {
    let clave = sessionStorage.getItem("fornace_idem");
    if (!clave) { clave = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2)).replaceAll("-", ""); sessionStorage.setItem("fornace_idem", clave); }
    const items = leerCarrito().map((i) => ({ productoId: i.id, cantidad: i.cantidad }));
    const pedido = await api("POST", "/orders", {
      items,
      direccionEntrega: { calle: form.calle.value.trim(), comuna: form.comuna.value.trim(), referencia: form.referencia.value.trim() },
    }, { headers: { "Idempotency-Key": clave } });
    const pago = await api("POST", `/orders/${encodeURIComponent(pedido.id)}/payments`, { medio: form.medio.value });
    sessionStorage.removeItem("fornace_idem");
    guardarCarrito([]);
    location.href = pago.urlPago;      // plataforma de pago (externa); al terminar vuelve a pago-retorno.html
  } catch (e) {
    aviso.textContent = mensajeError(e);
    aviso.classList.remove("d-none");
    if (e.codigo === "SIN_STOCK" || e.codigo === "PRODUCTO_NO_DISPONIBLE" || e.codigo === "FUERA_DE_COBERTURA") sessionStorage.removeItem("fornace_idem");
  } finally {
    boton.disabled = false;
  }
}

/* ---------------- Formulario de contacto (S35) ---------------- */
async function enviarContacto(event) {
  event.preventDefault();
  const form = event.target;
  if (!form.checkValidity()) { form.classList.add("was-validated"); return; }
  const aviso = document.getElementById("contacto-error");
  aviso.classList.add("d-none");
  try {
    await api("POST", "/contact-messages", {
      nombre: form.nombre.value.trim(), correo: form.correo.value.trim(), telefono: form.telefono.value.trim(),
      motivo: form.motivo.value, mensaje: form.mensaje.value.trim(),
    }, { anonimo: true });
    form.classList.add("d-none");
    document.getElementById("contacto-confirmacion").classList.remove("d-none");
  } catch (e) {
    aviso.textContent = mensajeError(e);
    aviso.classList.remove("d-none");
  }
}

/* ---------------- Filtros de categoria (menu.html) ---------------- */
function inicializarFiltros() {
  const botones = document.querySelectorAll("[data-filtro-categoria]");
  botones.forEach((btn) => {
    btn.addEventListener("click", () => {
      botones.forEach((b) => b.classList.remove("activo"));
      btn.classList.add("activo");
      renderProductos("grilla-productos", btn.dataset.filtroCategoria);
    });
  });
}

/* ---------------- Marcar link activo del navbar ---------------- */
function marcarNavActivo() {
  const actual = window.location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".navbar-fornace .nav-link").forEach((link) => {
    const href = link.getAttribute("href");
    if (href === actual) link.classList.add("active");
  });
}

document.addEventListener("DOMContentLoaded", () => {
  actualizarBadgeCarrito();
  marcarNavActivo();
  actualizarZonaSesion();
  if (new URLSearchParams(location.search).get("login") === "1" && !sesion().token) {
    const m = document.getElementById("modalLogin");
    if (m) new bootstrap.Modal(m).show();
  }
});
