<!DOCTYPE html>
<html lang="es">
<head>
    <title>Centro Pokemon - Servicios</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script>
</head>
<body>

    <!-- Navbar -->
    <nav class="navbar navbar-expand-sm bg-danger navbar-dark">
        <div class="container-fluid">
            <a class="navbar-brand fw-bold" href="index.php">PokeCentro</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="collapsibleNavbar">
                <ul class="navbar-nav">
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Entrenadores</a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="empresa.php">Quienes Somos</a></li>
                            <li><a class="dropdown-item" href="empresa.php#equipo">Nuestro Equipo</a></li>
                            <li><a class="dropdown-item" href="empresa.php#mision">Mision</a></li>
                        </ul>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="productos.php">Productos</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="servicios.php">Servicios</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="contacto.php">Contacto</a>
                    </li>
                </ul>
            </div>
            <button type="button" class="btn btn-outline-light" data-bs-toggle="modal" data-bs-target="#myModal">Acceder</button>
        </div>
    </nav>

    <!-- Container -->
    <div class="container-fluid bg-warning py-5">
        <div class="container">
            <h1 class="fw-bold">Nuestros Servicios</h1>
            <p class="lead">Cuidamos a tu equipo Pokemon en cada etapa de su entrenamiento.</p>
        </div>
    </div>

    <div class="container my-5">
        <div class="list-group">
            <div class="list-group-item">
                <h5>Curacion gratuita</h5>
                <p class="mb-0">Restauramos por completo la salud de tus Pokemon, sin costo alguno.</p>
            </div>
            <div class="list-group-item">
                <h5>Guarderia Pokemon</h5>
                <p class="mb-0">Dejamos a tus Pokemon en buenas manos mientras continuas tu viaje.</p>
            </div>
            <div class="list-group-item">
                <h5>Zona de entrenamiento</h5>
                <p class="mb-0">Combates de practica supervisados para fortalecer a tu equipo.</p>
            </div>
            <div class="list-group-item">
                <h5>Intercambio de Pokemon</h5>
                <p class="mb-0">Facilitamos el intercambio seguro entre entrenadores.</p>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <div class="container-fluid bg-dark py-3">
        <div class="row">
            <div class="col-4"></div>
            <div class="col-4 text-center" style="color:white"><strong>PokeCentro&#64;2026</strong></div>
            <div class="col-4"></div>
        </div>
    </div>

    <!-- Modal -->
    <div class="modal fade" id="myModal">
        <div class="modal-dialog">
            <div class="modal-content">
                <!-- Modal Header -->
                <div class="modal-header">
                    <h4 class="modal-title">Acceso de Entrenador</h4>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <!-- Modal body -->
                <div class="modal-body">
                    <form action="servicios.php" method="post">
                        <div class="mb-3 mt-3">
                            <label for="email" class="form-label">Email:</label>
                            <input type="email" class="form-control" id="email" placeholder="entrenador@pokecentro.com" name="email">
                        </div>
                        <div class="mb-3">
                            <label for="pwd" class="form-label">Contrasena:</label>
                            <input type="password" class="form-control" id="pwd" placeholder="Ingresa tu contrasena" name="pswd">
                        </div>
                        <div class="form-check mb-3">
                            <label class="form-check-label">
                                <input class="form-check-input" type="checkbox" name="remember"> Recordarme
                            </label>
                        </div>
                        <button type="submit" class="btn btn-danger">Entrar</button>
                    </form>
                </div>
                <!-- Modal footer -->
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cerrar</button>
                </div>
            </div>
        </div>
    </div>

</body>
</html>
