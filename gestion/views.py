import csv
import re
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from datetime import datetime, date
from .models import Habitacion, TipoHabitacion, Huesped, Reserva, Servicio, ServicioReserva, Pago, ReservaTour

# --- PROCESADOR DE CONTEXTO PARA NOTIFICACIONES EN NAVBAR ---
def notificaciones_context(request):
    if request.user.is_authenticated and request.user.is_staff:
        pedidos_pendientes_count = ServicioReserva.objects.filter(estado='PENDIENTE').count()
        habitaciones_sucias_count = Habitacion.objects.filter(estado_limpieza='SUCIA').count()
        return {
            'pedidos_pendientes_count': pedidos_pendientes_count,
            'habitaciones_sucias_count': habitaciones_sucias_count
        }
    return {
        'pedidos_pendientes_count': 0,
        'habitaciones_sucias_count': 0
    }

# --- VISTAS PÚBLICAS Y TURISMO ---
def inicio(request):
    total_habitaciones = Habitacion.objects.count()
    disponibles = Habitacion.objects.filter(estado='DISPONIBLE').count()
    ocupadas = Habitacion.objects.filter(estado='OCUPADA').count()
    reservas_activas = Reserva.objects.filter(estado='ACTIVA').count()

    context = {
        'total_habitaciones': total_habitaciones,
        'disponibles': disponibles,
        'ocupadas': ocupadas,
        'reservas_activas': reservas_activas,
    }
    return render(request, 'inicio.html', context)

def lista_habitaciones(request):
    habitaciones = Habitacion.objects.all().order_by('numero')
    return render(request, 'habitaciones/lista.html', {'habitaciones': habitaciones})

@login_required
def grid_recepcion(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso restringido únicamente a personal de recepción y administración.')
        return redirect('inicio')

    filtro_estado = request.GET.get('estado', '').strip()
    filtro_limpieza = request.GET.get('limpieza', '').strip()

    habitaciones_qs = Habitacion.objects.all().order_by('numero')

    if filtro_estado:
        habitaciones_qs = habitaciones_qs.filter(estado=filtro_estado)
    if filtro_limpieza:
        habitaciones_qs = habitaciones_qs.filter(estado_limpieza=filtro_limpieza)

    habitaciones_datos = []
    for hab in habitaciones_qs:
        reserva_activa = Reserva.objects.filter(habitacion=hab, estado='ACTIVA').order_by('-id').first()
        habitaciones_datos.append({
            'habitacion': hab,
            'reserva_activa': reserva_activa
        })

    pedidos_pendientes = ServicioReserva.objects.filter(estado='PENDIENTE').order_by('-fecha_solicitud')

    total_hab = Habitacion.objects.count()
    disp_count = Habitacion.objects.filter(estado='DISPONIBLE').count()
    ocup_count = Habitacion.objects.filter(estado='OCUPADA').count()
    maint_count = Habitacion.objects.filter(estado='MANTENIMIENTO').count()
    sucias_count = Habitacion.objects.filter(estado_limpieza='SUCIA').count()

    context = {
        'habitaciones_datos': habitaciones_datos,
        'filtro_estado': filtro_estado,
        'filtro_limpieza': filtro_limpieza,
        'total_hab': total_hab,
        'disp_count': disp_count,
        'ocup_count': ocup_count,
        'maint_count': maint_count,
        'sucias_count': sucias_count,
        'pedidos_pendientes': pedidos_pendientes,
    }
    return render(request, 'habitaciones/grid_recepcion.html', context)

# --- MÓDULO DE LIMPIEZA Y AMA DE LLAVES ---
@login_required
def panel_limpieza(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso restringido al personal del hotel.')
        return redirect('inicio')

    filtro = request.GET.get('filtro', '').strip()
    habitaciones = Habitacion.objects.all().order_by('numero')

    if filtro:
        habitaciones = habitaciones.filter(estado_limpieza=filtro)

    limpias = Habitacion.objects.filter(estado_limpieza='LIMPIA').count()
    sucias = Habitacion.objects.filter(estado_limpieza='SUCIA').count()
    en_limpieza = Habitacion.objects.filter(estado_limpieza='EN_LIMPIEZA').count()

    context = {
        'habitaciones': habitaciones,
        'filtro': filtro,
        'limpias': limpias,
        'sucias': sucias,
        'en_limpieza': en_limpieza,
    }
    return render(request, 'habitaciones/limpieza.html', context)

@login_required
def cambiar_limpieza_habitacion(request, habitacion_id):
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado.')
        return redirect('inicio')

    habitacion = get_object_or_404(Habitacion, id=habitacion_id)

    if request.method == 'POST':
        nuevo_estado = request.POST.get('nuevo_estado_limpieza')
        if nuevo_estado in ['LIMPIA', 'SUCIA', 'EN_LIMPIEZA']:
            habitacion.estado_limpieza = nuevo_estado
            habitacion.save()
            messages.success(request, f'Habitación {habitacion.numero} marcada como: {habitacion.get_estado_limpieza_display()}.')
        else:
            messages.error(request, 'Estado de limpieza no válido.')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    return redirect(next_url or 'panel_limpieza')

@login_required
def procesar_pedido_huesped(request, pedido_id):
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado.')
        return redirect('inicio')

    pedido = get_object_or_404(ServicioReserva, id=pedido_id)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'aprobar':
            pedido.estado = 'APROBADO'
            pedido.atendido = True
            pedido.save()
            messages.success(request, f'✅ Pedido de "{pedido.servicio.nombre}" APROBADO para la Habitación {pedido.reserva.habitacion.numero}.')
            
        elif accion == 'rechazar':
            motivo = request.POST.get('motivo_rechazo', 'No disponible en el momento').strip()
            pedido.estado = 'RECHAZADO'
            pedido.atendido = True
            pedido.motivo_rechazo = motivo
            pedido.save()
            messages.warning(request, f'❌ Pedido de "{pedido.servicio.nombre}" RECHAZADO (Hab. {pedido.reserva.habitacion.numero}): {motivo}.')

    return redirect('grid_recepcion')

@login_required
def cambiar_estado_habitacion(request, habitacion_id):
    if not request.user.is_staff:
        messages.error(request, 'Acceso restringido únicamente a administración y recepción.')
        return redirect('inicio')

    habitacion = get_object_or_404(Habitacion, id=habitacion_id)
    nuevo_estado = request.POST.get('nuevo_estado')

    if nuevo_estado in ['DISPONIBLE', 'MANTENIMIENTO']:
        if habitacion.estado == 'OCUPADA' and nuevo_estado == 'MANTENIMIENTO':
            messages.error(request, f'No se puede colocar la Habitación {habitacion.numero} en mantenimiento porque se encuentra ocupada.')
        else:
            habitacion.estado = nuevo_estado
            habitacion.save()
            messages.success(request, f'Habitación {habitacion.numero} actualizada exitosamente a estado: {nuevo_estado}.')
    else:
        messages.error(request, 'Estado seleccionado no válido.')

    return redirect('grid_recepcion')

@login_required
def crear_habitacion(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso restringido únicamente a administradores.')
        return redirect('lista_habitaciones')

    tipos = TipoHabitacion.objects.all()

    if request.method == 'POST':
        numero = request.POST.get('numero')
        tipo_id = request.POST.get('tipo')
        capacidad = request.POST.get('capacidad')
        precio = request.POST.get('precio')
        piso = request.POST.get('piso', '1')
        imagen = request.FILES.get('imagen')

        if Habitacion.objects.filter(numero=numero).exists():
            messages.error(request, f'Ya existe una habitación con el número {numero}.')
            return redirect('crear_habitacion')

        tipo = get_object_or_404(TipoHabitacion, id=tipo_id)

        Habitacion.objects.create(
            numero=numero,
            tipo=tipo,
            capacidad=capacidad,
            precio=precio,
            piso=piso,
            estado='DISPONIBLE',
            estado_limpieza='LIMPIA',
            imagen=imagen
        )

        messages.success(request, f'Habitación {numero} creada exitosamente con su fotografía.')
        return redirect('lista_habitaciones')

    return render(request, 'habitaciones/crear.html', {'tipos': tipos})

# --- MÓDULO DE TURISMO Y EXPERIENCIAS (IMÁGENES LOCALES OFFLINE) ---
def turismo_view(request):
    sitios_turisticos = [
        {
            'id': 1,
            'nombre': 'Camellón y Muelle de Riohacha',
            'municipio': 'Riohacha',
            'descripcion': 'Icónico paseo marítimo junto al mar Caribe. Ideal para adquirir mochilas Wayúu directamente de las artesanas y disfrutar de atardeceres inolvidables.',
            'imagen': '/static/img/camellon.jpg',
            'distancia': 'A 5 minutos del hotel',
            'categoria': 'Cultura & Mar',
            'precio': 35000
        },
        {
            'id': 2,
            'nombre': 'Playas de Mayapo',
            'municipio': 'Manaure',
            'descripcion': 'Playas de arenas blancas y viento idóneo para Kitesurf y Windsurf. Excelente oferta gastronómica marina frente al mar.',
            'imagen': '/static/img/mayapo.jpg',
            'distancia': 'A 30 minutos de Riohacha',
            'categoria': 'Aventura & Playa',
            'precio': 90000
        },
        {
            'id': 3,
            'nombre': 'Cabo de la Vela & Pilón de Azúcar',
            'municipio': 'Uribia',
            'descripcion': 'Encuentro mágico entre el desierto y el Océano Atlántico. Atardeceres místicos desde el Faro y la ensenada de Kamaishi.',
            'imagen': '/static/img/cabo_vela.jpg',
            'distancia': 'Excursión desde Riohacha',
            'categoria': 'Desierto & Misticismo',
            'precio': 220000
        },
        {
            'id': 4,
            'nombre': 'Salinas Marítimas de Manaure',
            'municipio': 'Manaure',
            'descripcion': 'El depósito de sal marina más grande de Colombia con impactantes montañas blancas sobre el horizonte costero.',
            'imagen': '/static/img/salinas.jpg',
            'distancia': 'A 1 hora de Riohacha',
            'categoria': 'Patrimonio & Paisaje',
            'precio': 75000
        },
        {
            'id': 5,
            'nombre': 'Santuario de Flamencos Rosados',
            'municipio': 'Camarones',
            'descripcion': 'Reserva biológica natural. Paseos en cayuco tradicional para el avistamiento de bandadas de flamencos en su hábitat.',
            'imagen': '/static/img/flamencos.jpg',
            'distancia': 'A 20 minutos de Riohacha',
            'categoria': 'Ecoturismo',
            'precio': 110000
        },
        {
            'id': 6,
            'nombre': 'Palomino & Sierra Nevada',
            'municipio': 'Dibulla',
            'descripcion': 'Lugar donde los ríos de la Sierra Nevada se unen con el mar Caribe. Práctica de tubing, caminatas y selva tropical.',
            'imagen': '/static/img/palomino.jpg',
            'distancia': 'A 1 hora y 15 min de Riohacha',
            'categoria': 'Naturaleza & Selva',
            'precio': 130000
        }
    ]

    reservas_activas_usuario = []
    if request.user.is_authenticated:
        if not request.user.is_staff:
            huesped = Huesped.objects.filter(correo__iexact=request.user.email).first()
            if not huesped:
                huesped = Huesped.objects.filter(
                    Q(nombres__icontains=request.user.first_name) | 
                    Q(correo__icontains=request.user.username)
                ).first()
            if huesped:
                reservas_activas_usuario = Reserva.objects.filter(huesped=huesped, estado='ACTIVA')
        else:
            reservas_activas_usuario = Reserva.objects.filter(estado='ACTIVA')

    return render(request, 'turismo.html', {
        'sitios': sitios_turisticos,
        'reservas_activas_usuario': reservas_activas_usuario
    })

@login_required
def reservar_tour(request):
    if request.method == 'POST':
        reserva_id = request.POST.get('reserva_id')
        nombre_tour = request.POST.get('nombre_tour')
        precio_persona = float(request.POST.get('precio_persona', 0))
        personas = int(request.POST.get('personas', 1))
        fecha_tour_str = request.POST.get('fecha_tour')

        if not reserva_id or not nombre_tour or not fecha_tour_str:
            messages.error(request, 'Por favor completa los campos requeridos para reservar el tour.')
            return redirect('turismo')

        reserva = get_object_or_404(Reserva, id=reserva_id)
        fecha_tour = datetime.strptime(fecha_tour_str, '%Y-%m-%d').date()

        ReservaTour.objects.create(
            reserva=reserva,
            nombre_tour=nombre_tour,
            personas=personas,
            precio_persona=precio_persona,
            fecha_tour=fecha_tour
        )

        messages.success(request, f'¡Tour "{nombre_tour}" para {personas} persona(s) reservado exitosamente! El valor total de ${personas * precio_persona:,.2f} se cargó a la habitación.')
        return redirect('mis_reservas' if not request.user.is_staff else 'lista_reservas')

    return redirect('turismo')

# --- CÁLCULO DE DETALLE DE RESERVA CON TOURS INCLUIDOS ---
def calcular_detalle_reserva(reserva):
    dias = (reserva.fecha_salida - reserva.fecha_entrada).days
    dias = max(dias, 1)
    
    costo_alojamiento = dias * reserva.habitacion.precio
    
    # Servicios APROBADOS
    servicios_asociados = ServicioReserva.objects.filter(reserva=reserva, estado='APROBADO')
    costo_servicios = sum(item.servicio.precio * item.cantidad for item in servicios_asociados)
    
    # Tours reservados
    tours_asociados = ReservaTour.objects.filter(reserva=reserva)
    costo_tours = sum(tour.total_tour for tour in tours_asociados)

    total_general = costo_alojamiento + costo_servicios + costo_tours
    
    pagos_realizados = Pago.objects.filter(reserva=reserva)
    total_pagado = sum(pago.valor_pagado for pago in pagos_realizados)
    
    saldo_pendiente = total_general - total_pagado

    return {
        'dias': dias,
        'costo_alojamiento': costo_alojamiento,
        'servicios_asociados': servicios_asociados,
        'costo_servicios': costo_servicios,
        'tours_asociados': tours_asociados,
        'costo_tours': costo_tours,
        'total_general': total_general,
        'pagos_realizados': pagos_realizados,
        'total_pagado': total_pagado,
        'saldo_pendiente': saldo_pendiente,
    }

@login_required
def lista_servicios(request):
    query = request.GET.get('q', '').strip()
    categoria_filtro = request.GET.get('categoria', '').strip()

    servicios = Servicio.objects.all().order_by('nombre')

    if categoria_filtro:
        servicios = servicios.filter(categoria=categoria_filtro)

    if query:
        servicios = servicios.filter(
            Q(nombre__icontains=query) | Q(descripcion__icontains=query)
        )

    categorias = Servicio.CATEGORIAS

    reservas_activas_usuario = []
    if not request.user.is_staff:
        huesped = Huesped.objects.filter(correo__iexact=request.user.email).first()
        if not huesped:
            huesped = Huesped.objects.filter(
                Q(nombres__icontains=request.user.first_name) | 
                Q(correo__icontains=request.user.username)
            ).first()
        if huesped:
            reservas_activas_usuario = Reserva.objects.filter(huesped=huesped, estado='ACTIVA')

    context = {
        'servicios': servicios,
        'query': query,
        'categoria_filtro': categoria_filtro,
        'categorias': categorias,
        'reservas_activas_usuario': reservas_activas_usuario,
    }
    return render(request, 'servicios/lista.html', context)

@login_required
def ordenar_servicio_huesped(request, servicio_id):
    servicio = get_object_or_404(Servicio, id=servicio_id)

    if request.method == 'POST':
        reserva_id = request.POST.get('reserva_id')
        cantidad = int(request.POST.get('cantidad', 1))

        if not reserva_id:
            messages.error(request, 'Debes seleccionar una habitación / reserva válida.')
            return redirect('lista_servicios')

        reserva = get_object_or_404(Reserva, id=reserva_id)

        if not request.user.is_staff and reserva.huesped.correo.lower() != request.user.email.lower():
            messages.error(request, 'No tienes permisos sobre la reserva seleccionada.')
            return redirect('lista_servicios')

        ServicioReserva.objects.create(
            reserva=reserva,
            servicio=servicio,
            cantidad=cantidad,
            estado='PENDIENTE',
            atendido=False
        )

        messages.success(request, f'¡Solicitud de "{servicio.nombre}" (x{cantidad}) enviada a recepción para aprobación!')
        return redirect('mis_reservas' if not request.user.is_staff else 'lista_reservas')

    return redirect('lista_servicios')

@login_required
def crear_servicio(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso restringido únicamente a administración.')
        return redirect('lista_servicios')

    categorias = Servicio.CATEGORIAS

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        categoria = request.POST.get('categoria', 'RESTAURANTE')
        precio_str = request.POST.get('precio', '0')
        descripcion = request.POST.get('descripcion', '').strip()
        imagen = request.FILES.get('imagen')

        if not nombre or not precio_str:
            messages.error(request, 'Por favor completa todos los campos obligatorios.')
            return redirect('crear_servicio')

        try:
            precio = float(precio_str)
            if precio <= 0:
                messages.error(request, 'El precio debe ser un valor mayor a cero.')
                return redirect('crear_servicio')
        except ValueError:
            messages.error(request, 'Ingresa una tarifa numérica válida.')
            return redirect('crear_servicio')

        Servicio.objects.create(
            nombre=nombre,
            categoria=categoria,
            precio=precio,
            descripcion=descripcion,
            imagen=imagen
        )

        messages.success(request, f'Servicio "{nombre}" agregado exitosamente con su fotografía.')
        return redirect('lista_servicios')

    return render(request, 'servicios/crear.html', {'categorias': categorias})

# --- GESTIÓN DE ROLES DE USUARIOS ---
def obtener_rol_usuario(user):
    """
    Determina el rol principal de un usuario en el sistema.
    Por defecto, cualquier cuenta registrada siempre figura como 'Huésped'.
    """
    if user.is_superuser:
        return 'Administrador'
    elif user.groups.filter(name='Ama de Llaves').exists():
        return 'Ama de Llaves'
    elif user.is_staff or user.groups.filter(name='Recepcionista').exists():
        return 'Recepcionista'
    return 'Huésped'

def asignar_rol_usuario(user, nuevo_rol):
    """
    Asigna un rol al usuario ajustando permisos y grupos de Django.
    Roles disponibles:
    - 'Huésped': Rol por defecto. Acceso a portal de cliente y reservas.
    - 'Recepcionista': Personal de recepción. Acceso al panel de habitaciones, check-in/out y pedidos.
    - 'Ama de Llaves': Personal de aseo y desinfección de habitaciones.
    - 'Administrador': Control total gerencial del hotel y administración de roles.
    """
    grupo_recepcion, _ = Group.objects.get_or_create(name='Recepcionista')
    grupo_limpieza, _ = Group.objects.get_or_create(name='Ama de Llaves')
    grupo_admin, _ = Group.objects.get_or_create(name='Administrador')
    grupo_huesped, _ = Group.objects.get_or_create(name='Huésped')

    user.groups.clear()

    if nuevo_rol == 'Administrador':
        user.is_staff = True
        user.is_superuser = True
        user.groups.add(grupo_admin)
    elif nuevo_rol == 'Recepcionista':
        user.is_staff = True
        user.is_superuser = False
        user.groups.add(grupo_recepcion)
    elif nuevo_rol == 'Ama de Llaves':
        user.is_staff = True
        user.is_superuser = False
        user.groups.add(grupo_limpieza)
    else:  # Huésped (Por defecto)
        user.is_staff = False
        user.is_superuser = False
        user.groups.add(grupo_huesped)

    user.save()

# --- REGISTRO Y PORTAL DE CLIENTE ---
def registro_view(request):
    if request.user.is_authenticated:
        return redirect('inicio')

    if request.method == 'POST':
        usuario = (request.POST.get('username') or '').strip().lower()
        correo = (request.POST.get('email') or '').strip().lower()
        clave = request.POST.get('password') or ''
        nombres = (request.POST.get('nombres') or '').strip()
        apellidos = (request.POST.get('apellidos') or '').strip()
        tipo_doc = (request.POST.get('tipo_documento') or 'CC').strip().upper()
        num_doc = (request.POST.get('numero_documento') or '').strip()
        telefono = (request.POST.get('telefono') or '').strip()
        nacionalidad = (request.POST.get('nacionalidad') or 'Colombiana').strip()

        # Validación Nombres: Solo letras y espacios
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]{2,50}$', nombres):
            messages.error(request, 'El campo Nombres solo permite letras y espacios (entre 2 y 50 caracteres).')
            return render(request, 'registro.html', {'form_data': request.POST})

        # Validación Apellidos: Solo letras y espacios
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]{2,50}$', apellidos):
            messages.error(request, 'El campo Apellidos solo permite letras y espacios (entre 2 y 50 caracteres).')
            return render(request, 'registro.html', {'form_data': request.POST})

        # Validación Tipo de Documento
        if tipo_doc not in ['CC', 'CE', 'PASAPORTE', 'TI']:
            messages.error(request, 'Tipo de documento no válido.')
            return render(request, 'registro.html', {'form_data': request.POST})

        # Validación Número de Documento según Tipo
        if tipo_doc in ['CC', 'TI']:
            if not re.match(r'^\d{6,10}$', num_doc):
                messages.error(request, f'Para {tipo_doc}, el número de documento debe contener entre 6 y 10 dígitos numéricos.')
                return render(request, 'registro.html', {'form_data': request.POST})
        else:
            if not re.match(r'^[a-zA-Z0-9]{5,15}$', num_doc):
                messages.error(request, f'Para {tipo_doc}, el número de documento debe contener entre 5 y 15 caracteres alfanuméricos.')
                return render(request, 'registro.html', {'form_data': request.POST})

        # Validación Teléfono: 10 dígitos numéricos
        if not re.match(r'^\d{10}$', telefono):
            messages.error(request, 'El teléfono de contacto debe contener exactamente 10 dígitos numéricos.')
            return render(request, 'registro.html', {'form_data': request.POST})

        # Validación Correo Electrónico
        try:
            validate_email(correo)
        except ValidationError:
            messages.error(request, 'Por favor ingresa un correo electrónico válido.')
            return render(request, 'registro.html', {'form_data': request.POST})

        # Validación Nombre de Usuario: 4 a 20 caracteres alfanuméricos, . o _ (sin espacios)
        if not re.match(r'^[a-zA-Z0-9._]{4,20}$', usuario):
            messages.error(request, 'El nombre de usuario debe contener entre 4 y 20 caracteres (solo letras, números, puntos o guiones bajos, sin espacios).')
            return render(request, 'registro.html', {'form_data': request.POST})

        # Validación Contraseña: Mínimo 6 caracteres
        if len(clave) < 6:
            messages.error(request, 'La contraseña debe contener al menos 6 caracteres.')
            return render(request, 'registro.html', {'form_data': request.POST})

        if User.objects.filter(username__iexact=usuario).exists():
            messages.error(request, 'El nombre de usuario ya está registrado.')
            return render(request, 'registro.html', {'form_data': request.POST})

        if Huesped.objects.filter(numero_documento=num_doc).exists():
            messages.error(request, 'Ya existe un huésped registrado con este número de documento.')
            return render(request, 'registro.html', {'form_data': request.POST})

        if User.objects.filter(email__iexact=correo).exists():
            messages.error(request, 'Ya existe una cuenta de usuario con este correo electrónico.')
            return render(request, 'registro.html', {'form_data': request.POST})

        user = User.objects.create_user(
            username=usuario, 
            email=correo, 
            password=clave, 
            first_name=nombres, 
            last_name=apellidos,
            is_staff=False,
            is_superuser=False
        )
        # Asignar explícitamente el rol Huésped por defecto
        asignar_rol_usuario(user, 'Huésped')

        Huesped.objects.create(
            tipo_documento=tipo_doc,
            numero_documento=num_doc,
            nombres=nombres,
            apellidos=apellidos,
            telefono=telefono,
            correo=correo,
            nacionalidad=nacionalidad
        )

        login(request, user)
        messages.success(request, f'¡Cuenta creada exitosamente! Bienvenido, {nombres}.')
        return redirect('inicio')

    return render(request, 'registro.html')

@login_required
def perfil_view(request):
    user = request.user
    huesped = Huesped.objects.filter(correo__iexact=user.email).first()
    if not huesped:
        huesped = Huesped.objects.filter(
            Q(nombres__icontains=user.first_name) | 
            Q(correo__icontains=user.username)
        ).first()

    total_reservas = Reserva.objects.filter(huesped=huesped).count() if huesped else 0

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'actualizar_datos':
            nombres = (request.POST.get('nombres') or '').strip()
            apellidos = (request.POST.get('apellidos') or '').strip()
            telefono = (request.POST.get('telefono') or '').strip()
            correo = (request.POST.get('correo') or '').strip().lower()
            nacionalidad = (request.POST.get('nacionalidad') or 'Colombiana').strip()

            # Validación Nombres
            if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]{2,50}$', nombres):
                messages.error(request, 'El campo Nombres solo permite letras y espacios (entre 2 y 50 caracteres).')
                return redirect('perfil')

            # Validación Apellidos
            if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]{2,50}$', apellidos):
                messages.error(request, 'El campo Apellidos solo permite letras y espacios (entre 2 y 50 caracteres).')
                return redirect('perfil')

            # Validación Teléfono
            if not re.match(r'^\d{10}$', telefono):
                messages.error(request, 'El teléfono de contacto debe contener exactamente 10 dígitos numéricos.')
                return redirect('perfil')

            # Validación Correo
            try:
                validate_email(correo)
            except ValidationError:
                messages.error(request, 'Por favor ingresa un correo electrónico válido.')
                return redirect('perfil')

            # Verificar que el correo no esté ocupado por otra cuenta de usuario
            if User.objects.filter(email__iexact=correo).exclude(id=user.id).exists():
                messages.error(request, 'Ese correo electrónico ya se encuentra registrado por otro usuario.')
                return redirect('perfil')

            # Actualizar User
            user.first_name = nombres
            user.last_name = apellidos
            user.email = correo
            user.save()

            # Actualizar o vincular Huesped
            if huesped:
                huesped.nombres = nombres
                huesped.apellidos = apellidos
                huesped.telefono = telefono
                huesped.correo = correo
                huesped.nacionalidad = nacionalidad
                huesped.save()
            else:
                num_doc = (request.POST.get('numero_documento') or str(user.id)).strip()
                tipo_doc = (request.POST.get('tipo_documento') or 'CC').strip().upper()
                huesped = Huesped.objects.create(
                    tipo_documento=tipo_doc,
                    numero_documento=num_doc,
                    nombres=nombres,
                    apellidos=apellidos,
                    telefono=telefono,
                    correo=correo,
                    nacionalidad=nacionalidad
                )

            messages.success(request, '¡Tus datos personales han sido actualizados correctamente!')
            return redirect('perfil')

        elif action == 'cambiar_password':
            password_actual = request.POST.get('password_actual') or ''
            password_nueva = request.POST.get('password_nueva') or ''
            password_confirmar = request.POST.get('password_confirmar') or ''

            if not user.check_password(password_actual):
                messages.error(request, 'La contraseña actual ingresada es incorrecta.')
                return redirect('perfil')

            if len(password_nueva) < 6:
                messages.error(request, 'La nueva contraseña debe contener al menos 6 caracteres.')
                return redirect('perfil')

            if password_nueva != password_confirmar:
                messages.error(request, 'La nueva contraseña y su confirmación no coinciden.')
                return redirect('perfil')

            user.set_password(password_nueva)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, '¡Tu contraseña ha sido actualizada con éxito!')
            return redirect('perfil')

    context = {
        'user': user,
        'huesped': huesped,
        'total_reservas': total_reservas,
    }
    return render(request, 'perfil.html', context)

@login_required
def gestion_usuarios_view(request):
    """
    Panel administrativo para consultar usuarios registrados y gestionar sus roles.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Acceso restringido únicamente a personal administrativo.')
        return redirect('inicio')

    query = request.GET.get('q', '').strip()
    filtro_rol = request.GET.get('rol', '').strip()

    usuarios_qs = User.objects.all().order_by('-date_joined')

    if query:
        usuarios_qs = usuarios_qs.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    lista_usuarios = []
    conteo_huespedes = 0
    conteo_recepcion = 0
    conteo_limpieza = 0
    conteo_admin = 0

    for u in usuarios_qs:
        rol = obtener_rol_usuario(u)
        u.rol_actual = rol

        # Buscar huesped asociado para mostrar documento y teléfono si existen
        u.huesped_asociado = Huesped.objects.filter(correo__iexact=u.email).first()

        if rol == 'Administrador':
            conteo_admin += 1
        elif rol == 'Recepcionista':
            conteo_recepcion += 1
        elif rol == 'Ama de Llaves':
            conteo_limpieza += 1
        else:
            conteo_huespedes += 1

        if not filtro_rol or filtro_rol.lower() == rol.lower():
            lista_usuarios.append(u)

    total_usuarios = User.objects.count()

    context = {
        'usuarios': lista_usuarios,
        'query': query,
        'filtro_rol': filtro_rol,
        'total_usuarios': total_usuarios,
        'conteo_huespedes': conteo_huespedes,
        'conteo_recepcion': conteo_recepcion,
        'conteo_limpieza': conteo_limpieza,
        'conteo_admin': conteo_admin,
        'roles_disponibles': ['Huésped', 'Recepcionista', 'Ama de Llaves', 'Administrador'],
    }
    return render(request, 'usuarios/gestion_usuarios.html', context)

@login_required
def cambiar_rol_usuario_view(request, user_id):
    """
    Procesa la actualización de rol asignado a un usuario por parte del administrador.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'No tienes permisos para modificar roles de usuarios.')
        return redirect('inicio')

    usuario_objetivo = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        nuevo_rol = request.POST.get('nuevo_rol', '').strip()

        # Protección: evitar que el último administrador se quite sus privilegios
        if usuario_objetivo == request.user and nuevo_rol != 'Administrador' and User.objects.filter(is_superuser=True).count() <= 1:
            messages.error(request, 'No puedes quitarte el rol de Administrador porque eres el único administrador en el sistema.')
            return redirect('gestion_usuarios')

        roles_validos = ['Huésped', 'Recepcionista', 'Ama de Llaves', 'Administrador']
        if nuevo_rol not in roles_validos:
            messages.error(request, 'El rol seleccionado no es válido.')
            return redirect('gestion_usuarios')

        rol_anterior = obtener_rol_usuario(usuario_objetivo)
        asignar_rol_usuario(usuario_objetivo, nuevo_rol)

        messages.success(
            request, 
            f'El rol de @{usuario_objetivo.username} ha sido actualizado de "{rol_anterior}" a "{nuevo_rol}" correctamente.'
        )

    return redirect('gestion_usuarios')

@login_required
def mis_reservas_view(request):
    huesped = Huesped.objects.filter(correo__iexact=request.user.email).first()
    
    if not huesped:
        huesped = Huesped.objects.filter(
            Q(nombres__icontains=request.user.first_name) | 
            Q(correo__icontains=request.user.username)
        ).first()

    reservas_con_detalle = []
    hoy = date.today()

    if huesped:
        reservas = Reserva.objects.filter(huesped=huesped).order_by('-id')
        for r in reservas:
            detalle = calcular_detalle_reserva(r)
            r.detalle = detalle
            pedidos_solicitados = ServicioReserva.objects.filter(reserva=r).order_by('-fecha_solicitud')
            dias_restantes = (r.fecha_salida - hoy).days

            reservas_con_detalle.append({
                'reserva': r,
                'detalle': detalle,
                'pedidos_solicitados': pedidos_solicitados,
                'dias_restantes': dias_restantes
            })

    return render(request, 'reservas/mis_reservas.html', {
        'reservas': [item['reserva'] for item in reservas_con_detalle],
        'reservas_detalle': reservas_con_detalle,
        'huesped': huesped,
        'hoy': hoy
    })

@login_required
def descargar_factura_pdf(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    
    if not request.user.is_staff and reserva.huesped.correo.lower() != request.user.email.lower():
        messages.error(request, 'No tienes permisos para consultar esta factura.')
        return redirect('mis_reservas')

    detalle = calcular_detalle_reserva(reserva)
    hoy = date.today()

    context = {
        'reserva': reserva,
        'detalle': detalle,
        'hoy': hoy,
        'modo_impresion': True
    }
    return render(request, 'reservas/factura.html', context)

@login_required
def cancelar_reserva(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    
    if reserva.check_in:
        messages.error(request, 'No se puede cancelar una reserva que ya cuenta con Check-In.')
        return redirect('mis_reservas')

    reserva.estado = 'CANCELADA'
    reserva.habitacion.estado = 'DISPONIBLE'
    reserva.habitacion.save()
    reserva.save()

    messages.success(request, f'La reserva #{reserva.id} ha sido cancelada correctamente.')
    if request.user.is_staff:
        return redirect('lista_reservas')
    return redirect('mis_reservas')

# --- DASHBOARD Y REPORTES ---
@login_required
def dashboard_view(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso restringido únicamente a Gerencia y Administración.')
        return redirect('inicio')

    hoy = date.today()
    total_habitaciones = Habitacion.objects.count()
    disponibles = Habitacion.objects.filter(estado='DISPONIBLE').count()
    ocupadas = Habitacion.objects.filter(estado='OCUPADA').count()
    mantenimiento = Habitacion.objects.filter(estado='MANTENIMIENTO').count()
    
    porcentaje_ocupacion = round((ocupadas / total_habitaciones * 100), 1) if total_habitaciones > 0 else 0
    
    reservas_activas = Reserva.objects.filter(estado='ACTIVA').count()
    reservas_hoy = Reserva.objects.filter(fecha_entrada=hoy).count()
    total_huespedes = Huesped.objects.count()
    
    total_ingresos = Pago.objects.aggregate(total=Sum('valor_pagado'))['total'] or 0

    grafico_habitaciones = [disponibles, ocupadas, mantenimiento]

    context = {
        'total_habitaciones': total_habitaciones,
        'disponibles': disponibles,
        'ocupadas': ocupadas,
        'mantenimiento': mantenimiento,
        'porcentaje_ocupacion': porcentaje_ocupacion,
        'reservas_activas': reservas_activas,
        'reservas_hoy': reservas_hoy,
        'total_huespedes': total_huespedes,
        'total_ingresos': total_ingresos,
        'grafico_habitaciones': grafico_habitaciones,
    }
    return render(request, 'dashboard.html', context)

@login_required
def reportes_view(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso restringido únicamente a Administración y Gerencia.')
        return redirect('inicio')

    fecha_inicio = request.GET.get('fecha_inicio', '').strip()
    fecha_fin = request.GET.get('fecha_fin', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()
    buscar_q = request.GET.get('q', '').strip()

    reservas = Reserva.objects.all().order_by('-fecha_entrada')

    if fecha_inicio:
        reservas = reservas.filter(fecha_entrada__gte=fecha_inicio)
    if fecha_fin:
        reservas = reservas.filter(fecha_entrada__lte=fecha_fin)
    if estado_filtro:
        reservas = reservas.filter(estado=estado_filtro)
    if buscar_q:
        reservas = reservas.filter(
            Q(huesped__nombres__icontains=buscar_q) |
            Q(huesped__apellidos__icontains=buscar_q) |
            Q(huesped__numero_documento__icontains=buscar_q) |
            Q(habitacion__numero__icontains=buscar_q)
        )

    reporte_datos = []
    recaudado_total = 0
    saldos_pendientes_total = 0

    for r in reservas:
        det = calcular_detalle_reserva(r)
        r.detalle = det
        reporte_datos.append({
            'reserva': r,
            'detalle': det
        })
        recaudado_total += det['total_pagado']
        saldos_pendientes_total += max(det['saldo_pendiente'], 0)

    context = {
        'reporte_datos': reporte_datos,
        'recaudado_total': recaudado_total,
        'saldos_pendientes_total': saldos_pendientes_total,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'estado_filtro': estado_filtro,
        'buscar_q': buscar_q,
    }
    return render(request, 'reportes.html', context)

@login_required
def exportar_reportes_csv(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso restringido únicamente a Administración y Gerencia.')
        return redirect('inicio')

    fecha_inicio = request.GET.get('fecha_inicio', '').strip()
    fecha_fin = request.GET.get('fecha_fin', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()
    buscar_q = request.GET.get('q', '').strip()

    reservas = Reserva.objects.all().order_by('-fecha_entrada')

    if fecha_inicio:
        reservas = reservas.filter(fecha_entrada__gte=fecha_inicio)
    if fecha_fin:
        reservas = reservas.filter(fecha_entrada__lte=fecha_fin)
    if estado_filtro:
        reservas = reservas.filter(estado=estado_filtro)
    if buscar_q:
        reservas = reservas.filter(
            Q(huesped__nombres__icontains=buscar_q) |
            Q(huesped__apellidos__icontains=buscar_q) |
            Q(huesped__numero_documento__icontains=buscar_q) |
            Q(habitacion__numero__icontains=buscar_q)
        )

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="reporte_financiero_hotel_wajira.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'ID Reserva', 
        'Huésped', 
        'Documento', 
        'Habitación', 
        'Fecha Entrada', 
        'Fecha Salida', 
        'Total Estancia ($)', 
        'Total Pagado ($)', 
        'Saldo Pendiente ($)', 
        'Estado'
    ])

    for r in reservas:
        det = calcular_detalle_reserva(r)
        saldo = max(det['saldo_pendiente'], 0)
        writer.writerow([
            f"#{r.id}",
            f"{r.huesped.nombres} {r.huesped.apellidos}",
            r.huesped.numero_documento,
            f"Hab. {r.habitacion.numero}",
            r.fecha_entrada.strftime('%Y-%m-%d'),
            r.fecha_salida.strftime('%Y-%m-%d'),
            f"{det['total_general']:.2f}",
            f"{det['total_pagado']:.2f}",
            f"{saldo:.2f}",
            r.estado
        ])

    return response

# --- VISTAS OPERATIVAS ---
@login_required
def crear_reserva(request):
    habitaciones = Habitacion.objects.all()
    huespedes = Huesped.objects.all().order_by('-id')

    if request.method == 'POST':
        if not request.user.is_staff:
            huesped = Huesped.objects.filter(correo__iexact=request.user.email).first()
            if not huesped:
                huesped = Huesped.objects.create(
                    tipo_documento='CC',
                    numero_documento='1000' + str(request.user.id),
                    nombres=request.user.first_name or request.user.username,
                    apellidos=request.user.last_name or 'Cliente',
                    telefono='3000000000',
                    correo=request.user.email or f"{request.user.username}@mail.com",
                    nacionalidad='Colombiana'
                )
        else:
            huesped_id = request.POST.get('huesped')
            if huesped_id:
                huesped = get_object_or_404(Huesped, id=huesped_id)
            else:
                huesped = Huesped.objects.first()
                if not huesped:
                    messages.error(request, 'No hay huéspedes registrados en el sistema.')
                    return redirect('crear_huesped')

        habitacion_id = request.POST.get('habitacion')
        fecha_entrada_str = request.POST.get('fecha_entrada')
        fecha_salida_str = request.POST.get('fecha_salida')
        num_huespedes = int(request.POST.get('num_huespedes', 1))

        fecha_entrada = datetime.strptime(fecha_entrada_str, '%Y-%m-%d').date()
        fecha_salida = datetime.strptime(fecha_salida_str, '%Y-%m-%d').date()
        hoy = date.today()

        if fecha_entrada < hoy:
            messages.error(request, 'Error: No se pueden realizar reservas para fechas pasadas.')
            return redirect('crear_reserva')

        if fecha_salida <= fecha_entrada:
            messages.error(request, 'Error (RN03): La fecha de salida debe ser posterior a la fecha de entrada.')
            return redirect('crear_reserva')

        habitacion = get_object_or_404(Habitacion, id=habitacion_id)

        if num_huespedes > habitacion.capacidad:
            messages.error(request, f'Error (RN02): La habitación {habitacion.numero} solo tiene capacidad para {habitacion.capacidad} personas.')
            return redirect('crear_reserva')

        reservas_solapadas = Reserva.objects.filter(
            habitacion=habitacion,
            estado='ACTIVA'
        ).filter(
            Q(fecha_entrada__lt=fecha_salida) & Q(fecha_salida__gt=fecha_entrada)
        )

        if reservas_solapadas.exists():
            messages.error(request, 'Error (RN01): La habitación ya cuenta con una reserva activa en el rango de fechas seleccionado.')
            return redirect('crear_reserva')

        # Cálculo de estancia y validación del anticipo requerido
        noches = (fecha_salida - fecha_entrada).days
        total_alojamiento = float(habitacion.precio) * noches

        try:
            valor_anticipo = float(request.POST.get('valor_anticipo', 0))
        except (ValueError, TypeError):
            valor_anticipo = 0.0

        metodo_pago = (request.POST.get('metodo_pago') or 'TRANSFERENCIA').strip().upper()
        if metodo_pago not in ['TRANSFERENCIA', 'TARJETA', 'EFECTIVO']:
            metodo_pago = 'TRANSFERENCIA'

        anticipo_minimo = round(total_alojamiento * 0.20, 2)

        if valor_anticipo <= 0:
            messages.error(request, f'Se requiere registrar un anticipo mínimo de ${anticipo_minimo:,.0f} (20% de la estancia) para garantizar la reserva de la habitación.')
            return redirect('crear_reserva')

        if valor_anticipo < anticipo_minimo:
            messages.error(request, f'El anticipo ingresado (${valor_anticipo:,.0f}) es inferior al mínimo de garantía requerido (${anticipo_minimo:,.0f}).')
            return redirect('crear_reserva')

        if valor_anticipo > total_alojamiento:
            messages.error(request, f'El anticipo (${valor_anticipo:,.0f}) no puede ser mayor al valor total del alojamiento (${total_alojamiento:,.0f}).')
            return redirect('crear_reserva')

        # Crear la reserva activa
        nueva_reserva = Reserva.objects.create(
            huesped=huesped,
            habitacion=habitacion,
            fecha_entrada=fecha_entrada,
            fecha_salida=fecha_salida,
            estado='ACTIVA'
        )

        # Registrar automáticamente el comprobante de pago del anticipo
        Pago.objects.create(
            reserva=nueva_reserva,
            valor_pagado=valor_anticipo,
            metodo_pago=metodo_pago
        )

        saldo_pendiente = total_alojamiento - valor_anticipo

        messages.success(
            request, 
            f'¡Reserva #{nueva_reserva.id} creada con éxito! Se ha registrado el anticipo de ${valor_anticipo:,.0f} ({metodo_pago}). Saldo pendiente a pagar en el hotel: ${saldo_pendiente:,.0f}.'
        )
        return redirect('lista_reservas' if request.user.is_staff else 'mis_reservas')

    # Parámetros GET opcionales para prellenado
    habitacion_id_previa = request.GET.get('habitacion', '')
    fecha_entrada_previa = request.GET.get('fecha_entrada', '')
    fecha_salida_previa = request.GET.get('fecha_salida', '')
    num_huespedes_previo = request.GET.get('num_huespedes', '1')

    return render(request, 'reservas/crear.html', {
        'habitaciones': habitaciones,
        'huespedes': huespedes,
        'habitacion_id_previa': habitacion_id_previa,
        'fecha_entrada_previa': fecha_entrada_previa,
        'fecha_salida_previa': fecha_salida_previa,
        'num_huespedes_previo': num_huespedes_previo,
    })

@login_required
def lista_reservas(request):
    if not request.user.is_staff:
        return redirect('mis_reservas')

    reservas_qs = Reserva.objects.all().order_by('-id')
    reservas_con_detalle = []
    
    for r in reservas_qs:
        detalle = calcular_detalle_reserva(r)
        r.detalle = detalle
        reservas_con_detalle.append({
            'reserva': r,
            'detalle': detalle
        })

    return render(request, 'reservas/lista.html', {
        'reservas': reservas_qs,
        'reservas_detalle': reservas_con_detalle
    })

@login_required
def realizar_checkin(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    if reserva.estado == 'CANCELADA':
        messages.error(request, 'Error (RN05): No se puede realizar Check-In sobre una reserva cancelada.')
        return redirect('lista_reservas')

    reserva.check_in = True
    reserva.habitacion.estado = 'OCUPADA'
    reserva.habitacion.save()
    reserva.save()
    messages.success(request, f'Check-In realizado para la Habitación {reserva.habitacion.numero}.')
    return redirect('lista_reservas')

@login_required
def realizar_checkout(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    if not reserva.check_in:
        messages.error(request, 'Error (RN06): No se puede realizar Check-Out de una reserva que no tenga Check-In.')
        return redirect('lista_reservas')

    detalle = calcular_detalle_reserva(reserva)

    if request.method == 'POST':
        reserva.check_out = True
        reserva.estado = 'FINALIZADA'
        reserva.habitacion.estado = 'DISPONIBLE'
        reserva.habitacion.estado_limpieza = 'SUCIA'
        reserva.habitacion.save()
        reserva.save()
        messages.success(request, f'Check-Out completado. Habitación {reserva.habitacion.numero} marcada para LIMPIEZA.')
        return redirect('lista_reservas')

    return render(request, 'reservas/factura.html', {'reserva': reserva, 'detalle': detalle})

@login_required
def registrar_pago(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    detalle = calcular_detalle_reserva(reserva)

    if request.method == 'POST':
        valor_pagado = float(request.POST.get('valor_pagado', 0))
        metodo_pago = request.POST.get('metodo_pago')

        if valor_pagado <= 0:
            messages.error(request, 'El monto a pagar debe ser mayor a cero.')
            return redirect('registrar_pago', reserva_id=reserva.id)

        Pago.objects.create(
            reserva=reserva,
            valor_pagado=valor_pagado,
            metodo_pago=metodo_pago
        )
        messages.success(request, f'Pago de ${valor_pagado:,.2f} registrado correctamente.')
        return redirect('lista_reservas' if request.user.is_staff else 'mis_reservas')

    return render(request, 'reservas/pago.html', {'reserva': reserva, 'detalle': detalle})

@login_required
def cargar_servicio(request, reserva_id):
    reserva = get_object_or_404(Reserva, id=reserva_id)
    servicios = Servicio.objects.all()

    if request.method == 'POST':
        servicio_id = request.POST.get('servicio')
        cantidad = int(request.POST.get('cantidad', 1))

        servicio = get_object_or_404(Servicio, id=servicio_id)

        ServicioReserva.objects.create(
            reserva=reserva,
            servicio=servicio,
            cantidad=cantidad,
            estado='APROBADO',
            atendido=True
        )
        messages.success(request, f'Servicio "{servicio.nombre}" x{cantidad} cargado a la reserva #{reserva.id}.')
        return redirect('lista_reservas')

    return render(request, 'reservas/servicio.html', {'reserva': reserva, 'servicios': servicios})

@login_required
def lista_huespedes(request):
    if not request.user.is_staff:
        return redirect('inicio')

    query = request.GET.get('q', '')
    if query:
        huespedes = Huesped.objects.filter(
            Q(numero_documento__icontains=query) |
            Q(nombres__icontains=query) |
            Q(apellidos__icontains=query)
        )
    else:
        huespedes = Huesped.objects.all().order_by('-id')
    return render(request, 'huespedes/lista.html', {'huespedes': huespedes, 'query': query})

@login_required
def crear_huesped(request):
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        tipo_documento = (request.POST.get('tipo_documento') or 'CC').strip().upper()
        numero_documento = (request.POST.get('numero_documento') or '').strip()
        nombres = (request.POST.get('nombres') or '').strip()
        apellidos = (request.POST.get('apellidos') or '').strip()
        telefono = (request.POST.get('telefono') or '').strip()
        correo = (request.POST.get('correo') or '').strip().lower()
        nacionalidad = (request.POST.get('nacionalidad') or 'Colombiana').strip()

        # Validación Nombres
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]{2,50}$', nombres):
            messages.error(request, 'El campo Nombres solo permite letras y espacios (entre 2 y 50 caracteres).')
            return render(request, 'huespedes/crear.html', {'next_url': next_url, 'form_data': request.POST})

        # Validación Apellidos
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]{2,50}$', apellidos):
            messages.error(request, 'El campo Apellidos solo permite letras y espacios (entre 2 y 50 caracteres).')
            return render(request, 'huespedes/crear.html', {'next_url': next_url, 'form_data': request.POST})

        # Validación Tipo Doc
        if tipo_documento not in ['CC', 'CE', 'PASAPORTE', 'TI']:
            messages.error(request, 'Tipo de documento no válido.')
            return render(request, 'huespedes/crear.html', {'next_url': next_url, 'form_data': request.POST})

        # Validación Número Documento
        if tipo_documento in ['CC', 'TI']:
            if not re.match(r'^\d{6,10}$', numero_documento):
                messages.error(request, f'Para {tipo_documento}, el número de documento debe contener entre 6 y 10 dígitos numéricos.')
                return render(request, 'huespedes/crear.html', {'next_url': next_url, 'form_data': request.POST})
        else:
            if not re.match(r'^[a-zA-Z0-9]{5,15}$', numero_documento):
                messages.error(request, f'Para {tipo_documento}, el número de documento debe contener entre 5 y 15 caracteres alfanuméricos.')
                return render(request, 'huespedes/crear.html', {'next_url': next_url, 'form_data': request.POST})

        # Validación Teléfono
        if not re.match(r'^\d{10}$', telefono):
            messages.error(request, 'El teléfono de contacto debe contener exactamente 10 dígitos numéricos.')
            return render(request, 'huespedes/crear.html', {'next_url': next_url, 'form_data': request.POST})

        # Validación Correo
        try:
            validate_email(correo)
        except ValidationError:
            messages.error(request, 'Por favor ingresa un correo electrónico válido.')
            return render(request, 'huespedes/crear.html', {'next_url': next_url, 'form_data': request.POST})

        if Huesped.objects.filter(numero_documento=numero_documento).exists():
            messages.error(request, 'Ya existe un huésped registrado con este número de documento.')
            return render(request, 'huespedes/crear.html', {'next_url': next_url, 'form_data': request.POST})

        Huesped.objects.create(
            tipo_documento=tipo_documento,
            numero_documento=numero_documento,
            nombres=nombres,
            apellidos=apellidos,
            telefono=telefono,
            correo=correo,
            nacionalidad=nacionalidad
        )
        messages.success(request, f'Huésped {nombres} {apellidos} registrado correctamente.')
        
        if next_url:
            return redirect(next_url)
        return redirect('lista_huespedes')

    return render(request, 'huespedes/crear.html', {'next_url': next_url})

@login_required
def editar_huesped(request, huesped_id):
    if not request.user.is_staff:
        messages.error(request, 'Acceso restringido únicamente a personal de administración y recepción.')
        return redirect('inicio')

    huesped = get_object_or_404(Huesped, id=huesped_id)

    if request.method == 'POST':
        tipo_documento = (request.POST.get('tipo_documento') or 'CC').strip().upper()
        numero_documento = (request.POST.get('numero_documento') or '').strip()
        nombres = (request.POST.get('nombres') or '').strip()
        apellidos = (request.POST.get('apellidos') or '').strip()
        telefono = (request.POST.get('telefono') or '').strip()
        correo = (request.POST.get('correo') or '').strip().lower()
        nacionalidad = (request.POST.get('nacionalidad') or 'Colombiana').strip()

        # Validación Nombres
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]{2,50}$', nombres):
            messages.error(request, 'El campo Nombres solo permite letras y espacios (entre 2 y 50 caracteres).')
            return render(request, 'huespedes/editar.html', {'huesped': huesped})

        # Validación Apellidos
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]{2,50}$', apellidos):
            messages.error(request, 'El campo Apellidos solo permite letras y espacios (entre 2 y 50 caracteres).')
            return render(request, 'huespedes/editar.html', {'huesped': huesped})

        # Validación Tipo Doc
        if tipo_documento not in ['CC', 'CE', 'PASAPORTE', 'TI']:
            messages.error(request, 'Tipo de documento no válido.')
            return render(request, 'huespedes/editar.html', {'huesped': huesped})

        # Validación Número Documento
        if tipo_documento in ['CC', 'TI']:
            if not re.match(r'^\d{6,10}$', numero_documento):
                messages.error(request, f'Para {tipo_documento}, el número de documento debe contener entre 6 y 10 dígitos numéricos.')
                return render(request, 'huespedes/editar.html', {'huesped': huesped})
        else:
            if not re.match(r'^[a-zA-Z0-9]{5,15}$', numero_documento):
                messages.error(request, f'Para {tipo_documento}, el número de documento debe contener entre 5 y 15 caracteres alfanuméricos.')
                return render(request, 'huespedes/editar.html', {'huesped': huesped})

        # Validación Teléfono
        if not re.match(r'^\d{10}$', telefono):
            messages.error(request, 'El teléfono de contacto debe contener exactamente 10 dígitos numéricos.')
            return render(request, 'huespedes/editar.html', {'huesped': huesped})

        # Validación Correo
        try:
            validate_email(correo)
        except ValidationError:
            messages.error(request, 'Por favor ingresa un correo electrónico válido.')
            return render(request, 'huespedes/editar.html', {'huesped': huesped})

        if Huesped.objects.filter(numero_documento=numero_documento).exclude(id=huesped_id).exists():
            messages.error(request, f'Ya existe otro huésped registrado con el número de documento {numero_documento}.')
            return render(request, 'huespedes/editar.html', {'huesped': huesped})

        huesped.tipo_documento = tipo_documento
        huesped.numero_documento = numero_documento
        huesped.nombres = nombres
        huesped.apellidos = apellidos
        huesped.telefono = telefono
        huesped.correo = correo
        huesped.nacionalidad = nacionalidad
        huesped.save()

        messages.success(request, f'Información de {nombres} {apellidos} actualizada con éxito.')
        return redirect('lista_huespedes')

    return render(request, 'huespedes/editar.html', {'huesped': huesped})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('inicio')

    if request.method == 'POST':
        usuario = request.POST.get('username')
        clave = request.POST.get('password')
        user = authenticate(request, username=usuario, password=clave)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido, {user.first_name or user.username}!')
            return redirect('inicio')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    messages.info(request, 'Has cerrado la sesión de trabajo.')
    return redirect('inicio')