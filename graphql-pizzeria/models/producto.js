const mongoose = require('mongoose');

// Esquema de base de datos para la colección de MongoDB
const productoSchema = new mongoose.Schema({
  nombre: String,
  categoria: String,
  precio: Number,
  disponible: Boolean
});

module.exports = mongoose.model('producto', productoSchema);
