const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const { ApolloServer, gql } = require('apollo-server-express');
const Usuario = require('./models/usuario');
const Cliente = require('./models/cliente');
const Producto = require('./models/producto');
const Pedido = require('./models/pedido');

mongoose.connect('mongodb://localhost:27017/pizzeria_la_fornace');

const typeDefs = gql`
  type Usuario {
    id: ID!
    nombre: String
    pass: String
  }
  input UsuarioInput {
    nombre: String
    pass: String
  }

  type Cliente {
    id: ID!
    run: String
    nombre: String
    direccion: String
    comuna: String
    correo: String
    telefono: String
  }
  input ClienteInput {
    run: String
    nombre: String
    direccion: String
    comuna: String
    correo: String
    telefono: String
  }

  type Producto {
    id: ID!
    nombre: String
    categoria: String
    precio: Float
    disponible: Boolean
  }
  input ProductoInput {
    nombre: String
    categoria: String
    precio: Float
    disponible: Boolean
  }

  type ItemPedido {
    producto: Producto
    cantidad: Int
    precioUnitario: Float
  }
  input ItemPedidoInput {
    productoId: ID!
    cantidad: Int!
  }

  type Pedido {
    id: ID!
    cliente: Cliente
    items: [ItemPedido]
    total: Float
    estado: String
    direccionDespacho: String
    motivoAnulacion: String
  }
  input PedidoInput {
    clienteId: ID!
    direccionDespacho: String
    items: [ItemPedidoInput]
  }

  type Alert {
    message: String
  }

  type Query {
    getUsuarios: [Usuario]
    getUsuariosById(id: ID!): Usuario

    getClientes: [Cliente]
    getClientesById(id: ID!): Cliente

    getProductos: [Producto]
    getProductosById(id: ID!): Producto

    getPedidos: [Pedido]
    getPedidosById(id: ID!): Pedido
  }

  type Mutation {
    addUsuario(input: UsuarioInput): Usuario
    updateUsuario(id: ID!, input: UsuarioInput): Usuario
    delUsuario(id: ID!): Alert

    addCliente(input: ClienteInput): Cliente
    updateCliente(id: ID!, input: ClienteInput): Cliente
    delCliente(id: ID!): Alert

    addProducto(input: ProductoInput): Producto
    updateProducto(id: ID!, input: ProductoInput): Producto
    delProducto(id: ID!): Alert

    addPedido(input: PedidoInput): Pedido
    confirmarPago(id: ID!): Pedido
    anularPedido(id: ID!, motivo: String!): Pedido
    delPedido(id: ID!): Alert
  }
`;

const resolvers = {
  Query: {
    async getUsuarios(obj){
      const usuarios = await Usuario.find();
      return usuarios;
    },
    async getUsuariosById(obj, {id}){
      const usuarioBus = await Usuario.findById(id);
      if (usuarioBus == null){
        return null;
      } else {
        return usuarioBus;
      }
    },

    async getClientes(obj){
      const clientes = await Cliente.find();
      return clientes;
    },
    async getClientesById(obj, {id}){
      const clienteBus = await Cliente.findById(id);
      if (clienteBus == null){
        return null;
      } else {
        return clienteBus;
      }
    },

    async getProductos(obj){
      const productos = await Producto.find();
      return productos;
    },
    async getProductosById(obj, {id}){
      const productoBus = await Producto.findById(id);
      if (productoBus == null){
        return null;
      } else {
        return productoBus;
      }
    },

    async getPedidos(obj){
      const pedidos = await Pedido.find().populate('cliente').populate('items.producto');
      return pedidos;
    },
    async getPedidosById(obj, {id}){
      const pedidoBus = await Pedido.findById(id).populate('cliente').populate('items.producto');
      if (pedidoBus == null){
        return null;
      } else {
        return pedidoBus;
      }
    }
  },
  Mutation: {
    async addUsuario(obj, { input }){
      const usuario = new Usuario(input);
      await usuario.save();
      return usuario;
    },
    async updateUsuario(obj, { id, input }){
      const usuario = await Usuario.findByIdAndUpdate(id, input);
      return usuario;
    },
    async delUsuario(obj, { id }){
      await Usuario.deleteOne({ _id: id });
      return { message: "usuario eliminado" };
    },

    async addCliente(obj, { input }){
      const cliente = new Cliente(input);
      await cliente.save();
      return cliente;
    },
    async updateCliente(obj, { id, input }){
      const cliente = await Cliente.findByIdAndUpdate(id, input);
      return cliente;
    },
    async delCliente(obj, { id }){
      await Cliente.deleteOne({ _id: id });
      return { message: "cliente eliminado" };
    },

    async addProducto(obj, { input }){
      const producto = new Producto(input);
      await producto.save();
      return producto;
    },
    async updateProducto(obj, { id, input }){
      const producto = await Producto.findByIdAndUpdate(id, input);
      return producto;
    },
    async delProducto(obj, { id }){
      await Producto.deleteOne({ _id: id });
      return { message: "producto eliminado" };
    },

    async addPedido(obj, { input }){
      let total = 0;
      const items = [];

      for (const item of input.items) {
        const producto = await Producto.findById(item.productoId);
        total += producto.precio * item.cantidad;
        items.push({
          producto: producto._id,
          cantidad: item.cantidad,
          precioUnitario: producto.precio
        });
      }

      const pedido = new Pedido({
        cliente: input.clienteId,
        items: items,
        total: total,
        estado: "pendiente_pago",
        direccionDespacho: input.direccionDespacho
      });
      await pedido.save();
      return pedido.populate('cliente').populate('items.producto');
    },
    async confirmarPago(obj, { id }){
      const pedido = await Pedido.findByIdAndUpdate(id, { estado: "pagado" });
      return pedido;
    },
    async anularPedido(obj, { id, motivo }){
      const pedido = await Pedido.findByIdAndUpdate(id, { estado: "anulado", motivoAnulacion: motivo });
      return pedido;
    },
    async delPedido(obj, { id }){
      await Pedido.deleteOne({ _id: id });
      return { message: "pedido eliminado" };
    }
  }
};

const corsOptions = {
  origin: 'http://localhost:8090',
  credentials: false
};

async function startServer() {
  const apolloServer = new ApolloServer({
    typeDefs,
    resolvers,
    cors: corsOptions
  });
  await apolloServer.start();
  apolloServer.applyMiddleware({ app });
}

const app = express();
app.use(cors());
startServer();
app.listen(8090, () => {
  console.log('graphql iniciado');
});
