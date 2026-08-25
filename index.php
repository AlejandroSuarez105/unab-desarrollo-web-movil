<!DOCTYPE html>
<html lang="es">
<head>
    <title>Centro Pokemon - Inicio</title>
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
    
    <!-- Carrusel -->
    <div id="carruselPokemon" class="carousel slide" data-bs-ride="carousel">
        <div class="carousel-indicators">
            <button type="button" data-bs-target="#carruselPokemon" data-bs-slide-to="0" class="active" aria-current="true"></button>
            <button type="button" data-bs-target="#carruselPokemon" data-bs-slide-to="1"></button>
            <button type="button" data-bs-target="#carruselPokemon" data-bs-slide-to="2"></button>
        </div>
        <div class="carousel-inner">
            <div class="carousel-item active">
                <div class="bg-danger text-white text-center py-5">
                    <h2>Bienvenido a PokeCentro</h2>
                    <p>El mejor lugar para cuidar a tus Pokemon</p>
                </div>
            </div>
            <div class="carousel-item">
                <div class="bg-primary text-white text-center py-5">
                    <h2>Curacion gratuita 24/7</h2>
                    <p>La Enfermera Joy siempre esta lista para ayudarte</p>
                </div>
            </div>
            <div class="carousel-item">
                <div class="bg-warning text-dark text-center py-5">
                    <h2>Tienda especializada</h2>
                    <p>Encuentra pokebolas, pociones y mas</p>
                </div>
            </div>
        </div>
        <button class="carousel-control-prev" type="button" data-bs-target="#carruselPokemon" data-bs-slide="prev">
            <span class="carousel-control-prev-icon"></span>
        </button>
        <button class="carousel-control-next" type="button" data-bs-target="#carruselPokemon" data-bs-slide="next">
            <span class="carousel-control-next-icon"></span>
        </button>
    </div>

    <!-- Container -->
    <div class="container-fluid bg-warning py-5">
        <div class="container text-center">
            <h1 class="display-5 fw-bold">Bienvenido al Centro Pokemon</h1>
            <p class="lead">Aqui tus Pokemon descansan, se curan y se preparan para su proxima aventura.</p>
            <a href="productos.php" class="btn btn-danger btn-lg me-2">Ver Productos</a>
            <a href="servicios.php" class="btn btn-outline-dark btn-lg">Ver Servicios</a>
        </div>
    </div>

    <div class="container my-5">
        <div class="row text-center">
            <div class="col-md-4 mb-4">
                <h4>Curacion gratuita</h4>
                <p>La enfermera Joy atiende a tu equipo Pokemon las 24 horas.</p>
            </div>
            <div class="col-md-4 mb-4">
                <h4>Tienda especializada</h4>
                <p>Pokebolas, pociones y objetos para tu viaje.</p>
            </div>
            <div class="col-md-4 mb-4">
                <h4>Zona de entrenamiento</h4>
                <p>Combates amistosos para fortalecer a tus Pokemon.</p>
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
                    <form action="index.php" method="post">
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
