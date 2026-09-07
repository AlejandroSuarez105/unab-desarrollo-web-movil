const mongoose = require('mongoose');

// Esquema de base de datos para la colección de MongoDB
const itemSchema = new mongoose.Schema({
  producto: { type: mongoose.Schema.Types.ObjectId, ref: 'producto' },
  cantidad: Number,
  precioUnitario: Number
});

const pedidoSchema = new mongoose.Schema({
  cliente: { type: mongoose.Schema.Types.ObjectId, ref: 'cliente' },
  items: [itemSchema],
  total: Number,
  estado: String,
  direccionDespacho: String,
  motivoAnulacion: String
});

module.exports = mongoose.model('pedido', pedidoSchema);
