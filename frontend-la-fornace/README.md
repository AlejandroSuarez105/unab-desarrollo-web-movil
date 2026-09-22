# La Fornace — Frontend (Primera entrega)

Frontend 100% navegable de Pizzeria La Fornace, sin backend. Todo el contenido
de productos, combos y sucursales vive en `js/data.js` como **datos simulados
(mock/dummy data)** — el backend real corresponde a la Unidad 2.

## Cómo verlo

No requiere instalación. Basta con abrir `index.html` en el navegador,
o servirlo con cualquier servidor estático:

```bash
# Python
python3 -m http.server 8080

# o con la extensión Live Server de VS Code
```

Luego entra a `http://localhost:8080`.

## Estructura

```
frontend-la-fornace/
  index.html          Inicio: hero carrusel, combos, destacados
  menu.html            Catálogo completo con filtro por categoría
  carrito.html          Resumen de pedido (localStorage, sin backend)
  sucursales.html        Ubicación, mapa embebido, horario
  contacto.html            Formulario de contacto (simulado)
  css/style.css               Identidad visual (paleta, tipografía, componentes)
  js/data.js                   Datos simulados: productos, combos, sucursales
  js/main.js                    Interacción: carrito, render, validaciones, modal
```

## Checklist de la entrega

- [x] Frontend 100% navegable de principio a fin (5 páginas enlazadas entre sí)
- [x] Sin backend — datos simulados en `js/data.js`
- [x] Diseño responsivo Mobile-First con Bootstrap 5 (sistema de grilla `row`/`col-*`)
- [x] Navbar persistente en las 5 páginas, con estado activo según la página actual
- [x] Footer persistente en las 5 páginas
- [x] Modal (Iniciar sesión) accesible desde el navbar y el footer en cualquier página
- [x] Carrusel de productos/promociones en el Home (Bootstrap Carousel)
- [x] Formulario de contacto con validación (`contacto.html`)
- [x] Carrito funcional con persistencia simulada vía `localStorage`

## Paleta de colores (definida por el equipo)

| Color     | Hex       | Uso                                              |
| --------- | --------- | ------------------------------------------------- |
| Negro     | `#121212` | Fondo general                                      |
| Rojo      | `#E64A19` | Acento principal — botones críticos, login, carrito |
| Amarillo  | `#FFB300` | Precios, ofertas, valoración                        |
| Verde     | `#388E3C` | Delivery gratis, confirmaciones                       |
| Blanco    | `#FFFFFF` | Contraste, texto, bordes                               |

## Notas técnicas

- Bootstrap 5.3 vía CDN (jsdelivr) para el sistema de grilla, navbar, carrusel, modal y validación de formularios.
- Sin frameworks de build: HTML + CSS + JS plano, fácil de revisar y de dividir entre el equipo.
- El carrito usa `localStorage` únicamente para simular persistencia entre páginas en esta entrega; en la Unidad 2 se reemplaza por las mutations reales de la API.
- Imágenes de productos vía Unsplash (solo para maquetar; se pueden reemplazar por fotografía propia).
