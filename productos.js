const responseAPI = {
    "status": 200,
    "message": "Productos Obtenidos",
    "data": [
        {"id": "1", "nombre": "Pokebola", "desc": "Captura Pokemon salvajes de forma segura.", "precio": 200},
        {"id": "2", "nombre": "Superbola", "desc": "Mayor tasa de captura que la Pokebola estandar.", "precio": 600},
        {"id": "3", "nombre": "Pocion", "desc": "Restaura 20 PS de un Pokemon herido.", "precio": 300},
        {"id": "4", "nombre": "Antidoto", "desc": "Cura el estado envenenado de un Pokemon.", "precio": 100}
    ]
};

function cargarProductos() {
    let contenedor = document.getElementById("contenedorProductos");
    
    responseAPI.data.forEach((prod) => {
        let col = document.createElement("div");
        col.setAttribute("class", "col-md-3 mb-4");

        let card = document.createElement("div");
        card.setAttribute("class", "card h-100 text-center");

        let cardBody = document.createElement("div");
        cardBody.setAttribute("class", "card-body");

        let h5 = document.createElement("h5");
        h5.setAttribute("class", "card-title");
        h5.innerText = prod.nombre;

        let pDesc = document.createElement("p");
        pDesc.setAttribute("class", "card-text");
        pDesc.innerText = prod.desc;

        let pPrecio = document.createElement("p");
        pPrecio.setAttribute("class", "fw-bold");
        pPrecio.innerText = `$${prod.precio}`;

        cardBody.appendChild(h5);
        cardBody.appendChild(pDesc);
        cardBody.appendChild(pPrecio);
        card.appendChild(cardBody);
        col.appendChild(card);
        contenedor.appendChild(col);
    });
}
