from django.urls import path
from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('habitaciones/', views.lista_habitaciones, name='lista_habitaciones'),
    path('habitaciones/crear/', views.crear_habitacion, name='crear_habitacion'),
    path('habitaciones/cambiar-estado/<int:habitacion_id>/', views.cambiar_estado_habitacion, name='cambiar_estado_habitacion'),
    path('recepcion/', views.grid_recepcion, name='grid_recepcion'),
    path('turismo/', views.turismo_view, name='turismo'),
    path('turismo/reservar/', views.reservar_tour, name='reservar_tour'),
    
    # Módulo de Limpieza / Housekeeping
    path('limpieza/', views.panel_limpieza, name='panel_limpieza'),
    path('limpieza/cambiar/<int:habitacion_id>/', views.cambiar_limpieza_habitacion, name='cambiar_limpieza_habitacion'),

    # Autenticación y Registro
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('registro/', views.registro_view, name='registro'),
    path('perfil/', views.perfil_view, name='perfil'),

    # Portal de Cliente
    path('mis-reservas/', views.mis_reservas_view, name='mis_reservas'),

    # Administración de Usuarios y Roles
    path('usuarios/', views.gestion_usuarios_view, name='gestion_usuarios'),
    path('usuarios/cambiar-rol/<int:user_id>/', views.cambiar_rol_usuario_view, name='cambiar_rol_usuario'),

    # Gerencia & Reportes
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('reportes/', views.reportes_view, name='reportes'),
    path('reportes/exportar-csv/', views.exportar_reportes_csv, name='exportar_reportes_csv'),

    # Reservas, Facturación & Operaciones
    path('reservas/', views.lista_reservas, name='lista_reservas'),
    path('reservas/crear/', views.crear_reserva, name='crear_reserva'),
    path('reservas/cancelar/<int:reserva_id>/', views.cancelar_reserva, name='cancelar_reserva'),
    path('reservas/checkin/<int:reserva_id>/', views.realizar_checkin, name='realizar_checkin'),
    path('reservas/checkout/<int:reserva_id>/', views.realizar_checkout, name='realizar_checkout'),
    path('reservas/factura/imprimir/<int:reserva_id>/', views.descargar_factura_pdf, name='descargar_factura_pdf'),

    # Pagos & Servicios Adicionales
    path('servicios/', views.lista_servicios, name='lista_servicios'),
    path('servicios/crear/', views.crear_servicio, name='crear_servicio'),
    path('servicios/ordenar/<int:servicio_id>/', views.ordenar_servicio_huesped, name='ordenar_servicio_huesped'),
    path('servicios/procesar/<int:pedido_id>/', views.procesar_pedido_huesped, name='procesar_pedido_huesped'),
    path('reservas/pago/<int:reserva_id>/', views.registrar_pago, name='registrar_pago'),
    path('reservas/servicio/<int:reserva_id>/', views.cargar_servicio, name='cargar_servicio'),

    # Huéspedes
    path('huespedes/', views.lista_huespedes, name='lista_huespedes'),
    path('huespedes/crear/', views.crear_huesped, name='crear_huesped'),
    path('huespedes/editar/<int:huesped_id>/', views.editar_huesped, name='editar_huesped'),
]