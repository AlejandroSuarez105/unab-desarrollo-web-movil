<!DOCTYPE html>
<html lang="es">
<head>
    <title>Centro Pokemon - Contacto</title>
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
            <h1 class="fw-bold">Contactanos</h1>
            <p class="lead">Escribenos si tienes dudas o necesitas ayuda con tu equipo Pokemon.</p>
        </div>
    </div>

    <div class="container my-5">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <form action="#" method="post">
                    <div class="mb-3">
                        <label for="nombre" class="form-label">Nombre de entrenador:</label>
                        <input type="text" class="form-control" id="nombre" placeholder="Ash Ketchum" name="nombre">
                    </div>
                    <div class="mb-3">
                        <label for="email" class="form-label">Email:</label>
                        <input type="email" class="form-control" id="email" placeholder="entrenador@pokecentro.com" name="email">
                    </div>
                    <div class="mb-3">
                        <label for="mensaje" class="form-label">Mensaje:</label>
                        <textarea class="form-control" id="mensaje" rows="4" name="mensaje" placeholder="Cuentanos que necesitas"></textarea>
                    </div>
                    <button type="submit" class="btn btn-danger">Enviar mensaje</button>
                </form>
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
                    <form action="contacto.php" method="post">
                        <div class="mb-3 mt-3">
                            <label for="loginEmail" class="form-label">Email:</label>
                            <input type="email" class="form-control" id="loginEmail" placeholder="entrenador@pokecentro.com" name="email">
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
