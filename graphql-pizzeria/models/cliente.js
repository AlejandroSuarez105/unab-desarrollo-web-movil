const mongoose = require('mongoose');

// Esquema de base de datos para la colección de MongoDB
const clienteSchema = new mongoose.Schema({
  run: String,
  nombre: String,
  direccion: String,
  comuna: String,
  correo: String,
  telefono: String
});

module.exports = mongoose.model('cliente', clienteSchema);
