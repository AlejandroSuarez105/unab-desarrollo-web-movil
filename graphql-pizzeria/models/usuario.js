const mongoose = require('mongoose');

// Esquema de base de datos para la colección de MongoDB
const usuarioSchema = new mongoose.Schema({
  nombre: String,
  pass: String
});

module.exports = mongoose.model('usuario', usuarioSchema);
