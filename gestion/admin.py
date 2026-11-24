from django.contrib import admin
from .models import Rol, Alojamiento, TipoHabitacion, Habitacion, Huesped, Reserva, Servicio, ServicioReserva, Pago

@admin.register(TipoHabitacion)
class TipoHabitacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'descripcion')

@admin.register(Habitacion)
class HabitacionAdmin(admin.ModelAdmin):
    list_display = ('numero', 'tipo', 'capacidad', 'precio', 'piso', 'estado')
    list_filter = ('estado', 'tipo', 'piso')
    search_fields = ('numero',)

@admin.register(Huesped)
class HuespedAdmin(admin.ModelAdmin):
    list_display = ('numero_documento', 'nombres', 'apellidos', 'telefono', 'correo', 'nacionalidad')
    search_fields = ('numero_documento', 'nombres', 'apellidos')

@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ('id', 'huesped', 'habitacion', 'fecha_entrada', 'fecha_salida', 'estado', 'check_in', 'check_out')
    list_filter = ('estado', 'check_in', 'check_out')

admin.site.register(Rol)
admin.site.register(Alojamiento)
admin.site.register(Servicio)
admin.site.register(ServicioReserva)
admin.site.register(Pago)