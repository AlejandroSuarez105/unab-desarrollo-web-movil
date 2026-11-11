/**
 * Datos fijos del sitio (informativos). El catalogo, los precios y los pedidos ya no viven aqui:
 * vienen del backend por /api/v1 (ver api.js).
 */

const SUCURSALES = [
  {
    id: 1,
    nombre: "La Fornace — Maipú Centro",
    direccion: "Av. Pajaritos 2340, Maipú, Santiago",
    horario: "Lun a Dom, 12:30 – 23:30",
    radioDelivery: "Despacho gratis dentro de 3 km",
    mapsQuery: "Av. Pajaritos, Maipú, Santiago",
  },
];

function formatCLP(valor) {
  return valor.toLocaleString("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 });
}
