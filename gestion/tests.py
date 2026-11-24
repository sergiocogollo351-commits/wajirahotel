from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from gestion.models import Huesped

class RegistroValidacionTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.registro_url = reverse('registro')

    def test_registro_exitoso(self):
        datos = {
            'nombres': 'María Camila',
            'apellidos': 'Gómez Pérez',
            'tipo_documento': 'CC',
            'numero_documento': '1082000123',
            'telefono': '3001234567',
            'nacionalidad': 'Colombiana',
            'email': 'maria.gomez@ejemplo.com',
            'username': 'mariagomez',
            'password': 'passwordSegura123'
        }
        response = self.client.post(self.registro_url, datos, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username='mariagomez').exists())
        self.assertTrue(Huesped.objects.filter(numero_documento='1082000123').exists())

    def test_registro_rechaza_numeros_en_nombres(self):
        datos = {
            'nombres': 'Carlos123',
            'apellidos': 'Gómez',
            'tipo_documento': 'CC',
            'numero_documento': '1082000124',
            'telefono': '3001234567',
            'nacionalidad': 'Colombiana',
            'email': 'carlos@ejemplo.com',
            'username': 'carlosg',
            'password': 'password123'
        }
        response = self.client.post(self.registro_url, datos)
        self.assertFalse(User.objects.filter(username='carlosg').exists())

    def test_registro_rechaza_numeros_en_apellidos(self):
        datos = {
            'nombres': 'Carlos',
            'apellidos': 'Gómez99',
            'tipo_documento': 'CC',
            'numero_documento': '1082000125',
            'telefono': '3001234567',
            'nacionalidad': 'Colombiana',
            'email': 'carlos2@ejemplo.com',
            'username': 'carlosg2',
            'password': 'password123'
        }
        response = self.client.post(self.registro_url, datos)
        self.assertFalse(User.objects.filter(username='carlosg2').exists())

    def test_registro_rechaza_documento_cc_con_letras(self):
        datos = {
            'nombres': 'Carlos',
            'apellidos': 'Gómez',
            'tipo_documento': 'CC',
            'numero_documento': '1082ABC123',
            'telefono': '3001234567',
            'nacionalidad': 'Colombiana',
            'email': 'carlos3@ejemplo.com',
            'username': 'carlosg3',
            'password': 'password123'
        }
        response = self.client.post(self.registro_url, datos)
        self.assertFalse(User.objects.filter(username='carlosg3').exists())

    def test_registro_rechaza_telefono_invalido(self):
        datos = {
            'nombres': 'Carlos',
            'apellidos': 'Gómez',
            'tipo_documento': 'CC',
            'numero_documento': '1082000126',
            'telefono': '300ABC4567',
            'nacionalidad': 'Colombiana',
            'email': 'carlos4@ejemplo.com',
            'username': 'carlosg4',
            'password': 'password123'
        }
        response = self.client.post(self.registro_url, datos)
        self.assertFalse(User.objects.filter(username='carlosg4').exists())

    def test_registro_rechaza_correo_invalido(self):
        datos = {
            'nombres': 'Carlos',
            'apellidos': 'Gómez',
            'tipo_documento': 'CC',
            'numero_documento': '1082000127',
            'telefono': '3001234567',
            'nacionalidad': 'Colombiana',
            'email': 'correo_no_valido',
            'username': 'carlosg5',
            'password': 'password123'
        }
        response = self.client.post(self.registro_url, datos)
        self.assertFalse(User.objects.filter(username='carlosg5').exists())

    def test_registro_rechaza_usuario_con_espacios(self):
        datos = {
            'nombres': 'Carlos',
            'apellidos': 'Gómez',
            'tipo_documento': 'CC',
            'numero_documento': '1082000128',
            'telefono': '3001234567',
            'nacionalidad': 'Colombiana',
            'email': 'carlos6@ejemplo.com',
            'username': 'carlos gomez',
            'password': 'password123'
        }
        response = self.client.post(self.registro_url, datos)
        self.assertFalse(User.objects.filter(email='carlos6@ejemplo.com').exists())

    def test_registro_rechaza_contrasena_corta(self):
        datos = {
            'nombres': 'Carlos',
            'apellidos': 'Gómez',
            'tipo_documento': 'CC',
            'numero_documento': '1082000129',
            'telefono': '3001234567',
            'nacionalidad': 'Colombiana',
            'email': 'carlos7@ejemplo.com',
            'username': 'carlosg7',
            'password': '123'
        }
        response = self.client.post(self.registro_url, datos)
        self.assertFalse(User.objects.filter(username='carlosg7').exists())

class PerfilUrlTestCase(TestCase):
    def test_url_perfil_requiere_login(self):
        client = Client()
        url = reverse('perfil')
        response = client.get(url)
        # Debe redirigir al login si no está autenticado
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
