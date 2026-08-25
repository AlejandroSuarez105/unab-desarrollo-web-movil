const responseAPI = {
    "status": 200,
    "message": "Servicios Obtenidos",
    "data": [
        {"id": "1", "nombre": "Curacion gratuita", "desc": "Restauramos por completo la salud de tus Pokemon, sin costo alguno."},
        {"id": "2", "nombre": "Guarderia Pokemon", "desc": "Dejamos a tus Pokemon en buenas manos mientras continuas tu viaje."},
        {"id": "3", "nombre": "Zona de entrenamiento", "desc": "Combates de practica supervisados para fortalecer a tu equipo."},
        {"id": "4", "nombre": "Intercambio de Pokemon", "desc": "Facilitamos el intercambio seguro entre entrenadores."}
    ]
};

function cargarServicios() {
    let contenedor = document.getElementById("contenedorServicios");

    responseAPI.data.forEach((srv) => {
        let listItem = document.createElement("div");
        listItem.setAttribute("class", "list-group-item");

        let h5 = document.createElement("h5");
        h5.innerText = srv.nombre;

        let pDesc = document.createElement("p");
        pDesc.setAttribute("class", "mb-0");
        pDesc.innerText = srv.desc;

        listItem.appendChild(h5);
        listItem.appendChild(pDesc);
        contenedor.appendChild(listItem);
    });
}
