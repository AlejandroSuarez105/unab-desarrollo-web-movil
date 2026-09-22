/**
 * Pizzeria La Fornace — logica de interfaz (frontend puro, sin backend)
 * El carrito se guarda en localStorage para simular persistencia entre paginas.
 */

const CARRITO_KEY = "fornace_carrito";

/* ---------------- Carrito (mock, sin backend) ---------------- */
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

/* ---------------- Toast simulado ---------------- */
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

/* ---------------- Render: grilla de productos ---------------- */
function renderProductos(contenedorId, categoriaFiltro = "todas", lista = PRODUCTOS) {
  const contenedor = document.getElementById(contenedorId);
  if (!contenedor) return;

  const productos = categoriaFiltro === "todas" ? lista : lista.filter((p) => p.categoria === categoriaFiltro);

  contenedor.innerHTML = productos
    .map(
      (p) => `
    <div class="col-12 col-sm-6 col-lg-4 col-xl-3">
      <div class="card-producto">
        <img src="${p.imagen}" alt="Pizza ${p.nombre}" loading="lazy">
        <div class="cuerpo">
          <span class="categoria-tag">${etiquetaCategoria(p.categoria)}</span>
          <h3 class="h5 mb-0">${p.nombre}</h3>
          <p class="texto-muted small mb-1">${p.descripcion}</p>
          <div class="d-flex align-items-center justify-content-between mt-auto">
            <span class="precio">${formatCLP(p.precio)}</span>
            <button class="btn btn-fornace btn-sm" onclick="agregarAlCarrito(${p.id})">Agregar</button>
          </div>
        </div>
      </div>
    </div>`
    )
    .join("");
}

function etiquetaCategoria(cat) {
  const mapa = {
    clasica: "Clásica",
    premium: "Premium",
    bebida: "Bebida",
    acompanamiento: "Acompañamiento",
  };
  return mapa[cat] || cat;
}

/* ---------------- Render: combos ---------------- */
function renderCombos(contenedorId) {
  const contenedor = document.getElementById(contenedorId);
  if (!contenedor) return;

  contenedor.innerHTML = COMBOS.map(
    (c) => `
    <div class="col-12 col-sm-6 col-lg-3">
      <div class="card-combo">
        <h3>${c.nombre}</h3>
        <p class="texto-muted small mb-0">${c.descripcion}</p>
        <div class="precio">${formatCLP(c.precio)}</div>
        <button class="btn btn-fornace w-100" onclick="agregarComboAlCarrito('${c.id}')">Pedir combo</button>
      </div>
    </div>`
  ).join("");
}

function agregarComboAlCarrito(comboId) {
  agregarAlCarrito("combo-" + comboId, 1);
}

/* ---------------- Render: carrito ---------------- */
function buscarProductoPorId(id) {
  if (typeof id === "string" && id.startsWith("combo-")) {
    const combo = COMBOS.find((c) => c.id === id.replace("combo-", ""));
    return combo ? { id, nombre: combo.nombre, precio: combo.precio, imagen: null, esCombo: true } : null;
  }
  const producto = PRODUCTOS.find((p) => p.id === id);
  return producto ? { ...producto } : null;
}

function renderCarrito() {
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

  let subtotal = 0;

  contenedor.innerHTML = carrito
    .map((item) => {
      const producto = buscarProductoPorId(item.id);
      if (!producto) return "";
      const totalLinea = producto.precio * item.cantidad;
      subtotal += totalLinea;
      return `
      <div class="item-carrito mb-3">
        ${producto.imagen ? `<img src="${producto.imagen}" alt="${producto.nombre}">` : `<div class="d-flex align-items-center justify-content-center" style="width:72px;height:72px;background:var(--negro-suave);border-radius:8px;">🍕</div>`}
        <div class="flex-grow-1">
          <h4 class="h6 mb-1">${producto.nombre}</h4>
          <span class="texto-muted small">${formatCLP(producto.precio)} c/u</span>
        </div>
        <div class="control-cantidad d-flex align-items-center gap-2">
          <button onclick="actualizarCantidad('${item.id}', -1)">−</button>
          <span>${item.cantidad}</span>
          <button onclick="actualizarCantidad('${item.id}', 1)">+</button>
        </div>
        <div class="text-end" style="min-width:90px;">
          <div class="precio">${formatCLP(totalLinea)}</div>
          <button class="btn btn-link btn-sm text-danger p-0" onclick="eliminarDelCarrito('${item.id}')">Quitar</button>
        </div>
      </div>`;
    })
    .join("");

  const despachoGratis = subtotal >= 15000;
  const despacho = despachoGratis ? 0 : 1500;
  const total = subtotal + despacho;

  const elSubtotal = document.getElementById("carrito-subtotal");
  const elDespacho = document.getElementById("carrito-despacho");
  const elTotal = document.getElementById("carrito-total");
  if (elSubtotal) elSubtotal.textContent = formatCLP(subtotal);
  if (elDespacho) elDespacho.textContent = despachoGratis ? "Gratis" : formatCLP(despacho);
  if (elTotal) elTotal.textContent = formatCLP(total);
}

function confirmarPedidoSimulado(event) {
  event.preventDefault();
  guardarCarrito([]);
  const modalEl = document.getElementById("modalConfirmacion");
  if (modalEl) {
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  }
  renderCarrito();
}

/* ---------------- Login (modal, simulado) ---------------- */
function manejarLoginSimulado(event) {
  event.preventDefault();
  const form = event.target;
  if (!form.checkValidity()) {
    form.classList.add("was-validated");
    return;
  }
  const modalEl = document.getElementById("modalLogin");
  const modal = bootstrap.Modal.getInstance(modalEl);
  if (modal) modal.hide();
  mostrarToast("Sesión iniciada (simulada) — sin backend en esta entrega");
  form.reset();
  form.classList.remove("was-validated");
}

/* ---------------- Formulario de contacto (simulado) ---------------- */
function manejarContactoSimulado(event) {
  event.preventDefault();
  const form = event.target;
  if (!form.checkValidity()) {
    form.classList.add("was-validated");
    return;
  }
  form.classList.add("d-none");
  const confirmacion = document.getElementById("contacto-confirmacion");
  if (confirmacion) confirmacion.classList.remove("d-none");
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
});
