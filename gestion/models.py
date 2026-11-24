from django.db import models

class Rol(models.Model):
    nombre = models.CharField(max_length=50)
    
    def __str__(self):
        return self.nombre

class Alojamiento(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    direccion = models.CharField(max_length=200)
    municipio = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField()
    fotografia = models.ImageField(upload_to='alojamientos/', null=True, blank=True)
    servicios_disponibles = models.TextField()

    def __str__(self):
        return self.nombre

class TipoHabitacion(models.Model):
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField()

    def __str__(self):
        return self.nombre

class Habitacion(models.Model):
    ESTADOS = (
        ('DISPONIBLE', 'Disponible'),
        ('OCUPADA', 'Ocupada'),
        ('MANTENIMIENTO', 'Mantenimiento'),
    )

    ESTADOS_LIMPIEZA = (
        ('LIMPIA', 'Limpia / Lista'),
        ('SUCIA', 'Sucia / Por Limpiar'),
        ('EN_LIMPIEZA', 'En Limpieza'),
    )

    numero = models.CharField(max_length=10, unique=True)
    tipo = models.ForeignKey(TipoHabitacion, on_delete=models.CASCADE)
    capacidad = models.IntegerField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    piso = models.CharField(max_length=10)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='DISPONIBLE')
    estado_limpieza = models.CharField(max_length=20, choices=ESTADOS_LIMPIEZA, default='LIMPIA')
    imagen = models.ImageField(upload_to='habitaciones/', null=True, blank=True)

    def __str__(self):
        return f"Habitacion {self.numero} - {self.tipo.nombre}"

class Huesped(models.Model):
    tipo_documento = models.CharField(max_length=20)
    numero_documento = models.CharField(max_length=50, unique=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField()
    nacionalidad = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

class Reserva(models.Model):
    ESTADOS_RESERVA = (
        ('ACTIVA', 'Activa'),
        ('CANCELADA', 'Cancelada'),
        ('FINALIZADA', 'Finalizada'),
    )
    huesped = models.ForeignKey(Huesped, on_delete=models.CASCADE)
    habitacion = models.ForeignKey(Habitacion, on_delete=models.CASCADE)
    fecha_entrada = models.DateField()
    fecha_salida = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS_RESERVA, default='ACTIVA')
    check_in = models.BooleanField(default=False)
    check_out = models.BooleanField(default=False)

    def __str__(self):
        return f"Reserva #{self.id} - {self.huesped}"

class Servicio(models.Model):
    CATEGORIAS = (
        ('RESTAURANTE', 'Restaurante & Bar'),
        ('MINIBAR', 'Minibar & Snacks'),
        ('TOURS', 'Tours & Excursiones'),
        ('LAVANDERIA', 'Lavandería'),
        ('SPA', 'Spa & Bienestar'),
        ('OTRO', 'Otros Servicios'),
    )
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    categoria = models.CharField(max_length=30, choices=CATEGORIAS, default='RESTAURANTE')
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    imagen = models.ImageField(upload_to='servicios/', null=True, blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_categoria_display()})"

class ServicioReserva(models.Model):
    ESTADOS_PEDIDO = (
        ('PENDIENTE', 'Pendiente'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
    )
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE)
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    atendido = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, choices=ESTADOS_PEDIDO, default='PENDIENTE')
    motivo_rechazo = models.CharField(max_length=255, blank=True, null=True)

class Pago(models.Model):
    METODOS = (
        ('EFECTIVO', 'Efectivo'),
        ('TARJETA', 'Tarjeta'),
        ('TRANSFERENCIA', 'Transferencia'),
    )
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE)
    valor_pagado = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=20, choices=METODOS)

class ReservaTour(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE)
    nombre_tour = models.CharField(max_length=150)
    personas = models.IntegerField(default=1)
    precio_persona = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_tour = models.DateField()
    fecha_solicitud = models.DateTimeField(auto_now_add=True)

    @property
    def total_tour(self):
        return self.personas * self.precio_persona

    def __str__(self):
        return f"Tour {self.nombre_tour} - Reserva #{self.reserva.id}"