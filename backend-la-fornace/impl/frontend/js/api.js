/**
 * Acceso al backend. El navegador solo habla con el API Gateway (/api/v1).
 * - El token de sesion vive en sessionStorage (se borra al cerrar la pestana). No se guardan claves ni secretos.
 * - El navegador nunca envia precios, totales, estados ni roles como dato confiable: los decide el servidor.
 */
const SES = { token: "fornace_token", rol: "fornace_rol", nombre: "fornace_nombre" };

function esc(valor) {
  const d = document.createElement("div");
  d.textContent = valor == null ? "" : String(valor);
  return d.innerHTML;
}

function sesion() {
  return { token: sessionStorage.getItem(SES.token), rol: sessionStorage.getItem(SES.rol), nombre: sessionStorage.getItem(SES.nombre) };
}

function guardarSesion(r) {
  sessionStorage.setItem(SES.token, r.access_token);
  sessionStorage.setItem(SES.rol, r.rol);
  sessionStorage.setItem(SES.nombre, r.nombre || "");
}

function borrarSesion() {
  Object.values(SES).forEach((k) => sessionStorage.removeItem(k));
}

class ErrorApi extends Error {
  constructor(status, codigo, mensaje, requestId) {
    super(mensaje);
    this.status = status;
    this.codigo = codigo;
    this.requestId = requestId;
  }
}

/** Llama a un servicio REST. Devuelve el JSON (o null si 204). Lanza ErrorApi con el formato de error del backend. */
async function api(metodo, ruta, cuerpo, extra = {}) {
  const headers = { Accept: "application/json", ...(extra.headers || {}) };
  const s = sesion();
  if (s.token && !extra.anonimo) headers.Authorization = "Bearer " + s.token;
  if (cuerpo !== undefined) headers["Content-Type"] = "application/json";
  let r;
  try {
    r = await fetch(window.FORNACE.API + ruta, { method: metodo, headers, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) });
  } catch (e) {
    throw new ErrorApi(0, "SIN_CONEXION", "No pudimos conectarnos con el servidor. Revisa tu conexión e intenta de nuevo.");
  }
  if (r.status === 401 && s.token && !extra.anonimo && ruta !== "/auth/login") {
    borrarSesion();
    actualizarZonaSesion();
  }
  if (r.status === 204) return null;
  const tipo = r.headers.get("content-type") || "";
  const datos = tipo.includes("json") ? await r.json() : await r.text();
  if (!r.ok) {
    const e = (datos && datos.error) || {};
    throw new ErrorApi(r.status, e.codigo || "ERROR", e.mensaje || "Ocurrió un error. Intenta de nuevo.", e.requestId);
  }
  return datos;
}

/** Consulta GraphQL (solo lectura). Devuelve {data, errors}. */
async function gql(query, variables = {}) {
  const s = sesion();
  let r;
  try {
    r = await fetch(window.FORNACE.API + "/graphql", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + s.token },
      body: JSON.stringify({ query, variables }),
    });
  } catch (e) {
    throw new ErrorApi(0, "SIN_CONEXION", "No pudimos conectarnos con el servidor.");
  }
  if (r.status === 401) { borrarSesion(); actualizarZonaSesion(); throw new ErrorApi(401, "TOKEN_INVALIDO", "Tu sesión venció."); }
  const datos = await r.json();
  if (!r.ok && !datos.errors && datos.error) throw new ErrorApi(r.status, datos.error.codigo, datos.error.mensaje, datos.error.requestId);
  return datos;
}

function mensajeError(e) {
  const base = e instanceof ErrorApi ? e.message : "Ocurrió un error inesperado.";
  return e.requestId ? `${base} (código de soporte: ${e.requestId})` : base;
}

function exigirSesion(roles) {
  const s = sesion();
  if (!s.token) { location.href = "index.html?login=1"; return false; }
  if (roles && !roles.includes(s.rol)) { location.href = "index.html"; return false; }
  return true;
}

/* ---------------- Sesion en la barra de navegacion ---------------- */
async function iniciarSesion(event) {
  event.preventDefault();
  const form = event.target;
  if (!form.checkValidity()) { form.classList.add("was-validated"); return; }
  const aviso = form.querySelector("[data-error]");
  if (aviso) aviso.classList.add("d-none");
  try {
    const r = await api("POST", "/auth/login", { correo: form.correo.value.trim(), password: form.password.value }, { anonimo: true });
    guardarSesion(r);
    form.reset();
    const modal = bootstrap.Modal.getInstance(document.getElementById("modalLogin"));
    if (modal) modal.hide();
    actualizarZonaSesion();
    mostrarToast("Sesión iniciada");
    if (typeof alIniciarSesion === "function") alIniciarSesion();
  } catch (e) {
    if (aviso) { aviso.textContent = mensajeError(e); aviso.classList.remove("d-none"); }
  }
}

async function cerrarSesion() {
  try { await api("POST", "/auth/logout"); } catch (e) { /* si el token ya no sirve, igual se limpia */ }
  borrarSesion();
  location.href = "index.html";
}

function actualizarZonaSesion() {
  const s = sesion();
  const boton = document.querySelector('button.icono-boton[data-bs-target="#modalLogin"]');
  let zona = document.getElementById("zona-sesion");
  if (!zona && boton) {
    zona = document.createElement("div");
    zona.id = "zona-sesion";
    zona.className = "dropdown";
    boton.parentNode.insertBefore(zona, boton);
  }
  if (!zona) return;
  if (boton) boton.style.display = s.token ? "none" : "";
  if (!s.token) { zona.innerHTML = ""; return; }
  const personal = s.rol !== "cliente";
  zona.innerHTML = `
    <button class="icono-boton dropdown-toggle" data-bs-toggle="dropdown">${esc(s.nombre || "Mi cuenta")}</button>
    <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end">
      ${personal ? '<li><a class="dropdown-item" href="panel.html">Panel interno</a></li>' :
        '<li><a class="dropdown-item" href="mis-pedidos.html">Mis pedidos</a></li><li><a class="dropdown-item" href="mi-cuenta.html">Mi cuenta</a></li>'}
      <li><hr class="dropdown-divider"></li>
      <li><button class="dropdown-item" onclick="cerrarSesion()">Cerrar sesión</button></li>
    </ul>`;
}
