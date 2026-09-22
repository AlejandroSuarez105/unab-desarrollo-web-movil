/**
 * Datos simulados (dummy data) — Pizzeria La Fornace
 * No hay backend en esta entrega: todo el contenido de productos,
 * combos y sucursales vive en este archivo como mock data.
 */

const PRODUCTOS = [
  {
    id: 1,
    nombre: "Napolitana",
    categoria: "clasica",
    precio: 8990,
    descripcion: "Salsa de tomate, mozzarella, jamón, orégano fresco.",
    imagen: "https://images.unsplash.com/photo-1595854341625-f33ee10dbf94?w=600&q=80",
    destacado: true,
  },
  {
    id: 2,
    nombre: "Margarita",
    categoria: "clasica",
    precio: 7990,
    descripcion: "Tomate San Marzano, mozzarella fior di latte, albahaca.",
    imagen: "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=600&q=80",
    destacado: true,
  },
  {
    id: 3,
    nombre: "Cuatro Quesos",
    categoria: "premium",
    precio: 10990,
    descripcion: "Mozzarella, gorgonzola, parmesano, provolone ahumado.",
    imagen: "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600&q=80",
    destacado: true,
  },
  {
    id: 4,
    nombre: "Prosciutto e Funghi",
    categoria: "premium",
    precio: 11990,
    descripcion: "Jamón crudo, champiñones laminados, rúcula, parmesano.",
    imagen: "https://images.unsplash.com/photo-1541745537411-b8046dc6d66c?w=600&q=80",
    destacado: false,
  },
  {
    id: 5,
    nombre: "Diávola",
    categoria: "premium",
    precio: 10490,
    descripcion: "Salame picante, mozzarella, chili flakes, aceite de oliva.",
    imagen: "https://images.unsplash.com/photo-1628840042765-356cda07504e?w=600&q=80",
    destacado: false,
  },
  {
    id: 6,
    nombre: "Vegetariana",
    categoria: "clasica",
    precio: 9490,
    descripcion: "Pimentón, zapallo italiano, cebolla morada, aceitunas.",
    imagen: "https://images.unsplash.com/photo-1511689660979-10d2b1aada49?w=600&q=80",
    destacado: false,
  },
  {
    id: 7,
    nombre: "Bebida 500ml",
    categoria: "bebida",
    precio: 1990,
    descripcion: "Línea de bebidas frías, a elección.",
    imagen: "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=600&q=80",
    destacado: false,
  },
  {
    id: 8,
    nombre: "Pan de Ajo",
    categoria: "acompanamiento",
    precio: 3490,
    descripcion: "Masa madre horneada a la piedra, mantequilla de ajo y perejil.",
    imagen: "https://images.unsplash.com/photo-1619535860434-ba1d8fa44669?w=600&q=80",
    destacado: false,
  },
];

const COMBOS = [
  {
    id: "c1",
    nombre: "Combo Solo",
    descripcion: "1 pizza clásica + bebida 500ml",
    precio: 10490,
  },
  {
    id: "c2",
    nombre: "Combo Dúo",
    descripcion: "2 pizzas clásicas + pan de ajo",
    precio: 18990,
  },
  {
    id: "c3",
    nombre: "Combo Familiar",
    descripcion: "2 pizzas premium + pan de ajo + 2 bebidas",
    precio: 28990,
  },
  {
    id: "c4",
    nombre: "Combo Noche Fornace",
    descripcion: "3 pizzas a elección + 2 acompañamientos",
    precio: 34990,
  },
];

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
