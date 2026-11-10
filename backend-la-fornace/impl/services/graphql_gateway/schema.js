// Schema de solo lectura (Modulo 8, 8.6). No hay mutaciones ni suscripciones.
export const typeDefs = `#graphql
type Query {
  "Detalle de un pedido con los datos vigentes de sus productos (orders + inventory)."
  resumenPedido(id: ID!): ResumenPedido
  "Perfil y últimos pedidos de la cuenta autenticada (clients + orders)."
  miCuenta(limitePedidos: Int = 5): MiCuenta
}

enum EstadoPedido { pendiente_pago pagado en_preparacion en_despacho entregado anulado }

type ResumenPedido {
  id: ID!
  estado: EstadoPedido!
  estadoPago: String!
  total: Int!
  creadoEn: String!
  expiraEn: String
  boletaDisponible: Boolean!
  direccionEntrega: DireccionEntrega
  historialEstados: [CambioEstado!]!
  items: [ItemPedido!]!
  clienteNombre: String
}

type ItemPedido {
  productoId: ID!
  nombre: String!
  cantidad: Int!
  precioUnitario: Int!
  producto: ProductoPublico
}

type ProductoPublico {
  id: ID!
  nombre: String!
  categoria: String!
  descripcion: String!
  precio: Int!
  imagen: String
  disponible: Boolean!
}

type CambioEstado { estado: EstadoPedido! fecha: String! }
type DireccionEntrega { calle: String! comuna: String! referencia: String }
type MiCuenta { perfil: PerfilCliente pedidos: [PedidoResumen!] }
type PerfilCliente { nombreCompleto: String! correo: String! telefono: String! direccion: Domicilio! }
type Domicilio { calle: String! comuna: String! provincia: String! region: String! }
type PedidoResumen { id: ID! estado: EstadoPedido! total: Int! creadoEn: String! }
`;
