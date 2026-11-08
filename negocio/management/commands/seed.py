import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from core.models import Organizacion, Perfil, Ajuste
from negocio.models import (
    Tienda, Familia, Proveedor, Cliente, Articulo, Variante, Stock,
    Venta, LineaVenta, Compra, LineaCompra, Gasto, Empleado, Nomina,
    mover_stock,
)

ORG_SLUG = "bosselli"
TIENDAS = [
    ("Nervión", "NER", "Avda. San Francisco Javier 7, Sevilla", "954 64 00 00"),
    ("Porvenir", "POR", "Avda. Ramón Carande 14, Sevilla", "954 64 00 01"),
]
FAMILIAS = [
    ("Camisas de vestir", 1),
    ("Camisas sport", 2),
    ("Corbatas", 3),
    ("Sastrería", 4),
    ("Cazadoras", 5),
    ("Jerseys y cárdigans", 6),
    ("Complementos", 7),
    ("Pañuelos", 8),
]
PROVEEDORES = [
    ("Tejidos del Sur S.L.", "B12345678", "954 11 22 33", "pedidos@tejidosdelsur.es"),
    ("Confecciones Andaluzas S.A.", "A87654321", "954 22 33 44", "info@confeccionesandaluzas.es"),
    ("Sederías Italianas", "NIF-IT-123", "954 33 44 55", "orders@sederiasitalianas.it"),
    ("Cinturones y Complementos", "B11223344", "954 44 55 66", "ventas@cinturones.es"),
    ("Lino Premium S.L.", "B99887766", "954 55 66 77", "info@linopremium.es"),
]
CLIENTES = [
    ("Antonio", "García López", "12345678A", "antoniogarcia@gmail.com", "611 111 111", "Sevilla"),
    ("Manuel", "Fernández Ruiz", "23456789B", "manuelfr@gmail.com", "622 222 222", "Sevilla"),
    ("José", "Martín Sánchez", "34567890C", "josemartin@gmail.com", "633 333 333", "Dos Hermanas"),
    ("Francisco", "López Gómez", "45678901D", "franciscolg@gmail.com", "644 444 444", "Sevilla"),
    ("David", "Hernández Pérez", "56789012E", "davidhp@gmail.com", "655 555 555", "Sevilla"),
    ("Javier", "González Torres", "67890123F", "javiergt@gmail.com", "666 666 666", "Maírena del Aljarafe"),
    ("Carlos", "Ramírez Díaz", "78901234G", "carlosrd@gmail.com", "677 777 777", "Sevilla"),
    ("Miguel", "Álvarez Moreno", "89012345H", "miguelam@gmail.com", "688 888 888", "Sevilla"),
    ("Luis", "Romero Jiménez", "90123456J", "luisrj@gmail.com", "699 999 999", "Sevilla"),
    ("Pedro", "Vargas Navarro", "01234567K", "pedrovnavarro@gmail.com", "600 000 000", "Sevilla"),
]
ARTICULOS = [
    ("CAM-001", "Camisa vestir blanca algodón egipcio", "Camisas de vestir", "Bosselli", 28.00, 69.00, "S,M,L,XL,XXL", "Blanco"),
    ("CAM-002", "Camisa vestir celeste", "Camisas de vestir", "Bosselli", 26.00, 65.00, "S,M,L,XL", "Celeste"),
    ("CAM-003", "Camisa vestir marino", "Camisas de vestir", "Bosselli", 26.00, 65.00, "S,M,L,XL,XXL", "Marino"),
    ("CAM-004", "Camisa vestir rayas", "Camisas de vestir", "Bosselli", 27.00, 67.00, "M,L,XL", "Azul/Blanco"),
    ("CAM-005", "Camisa lino premium blanca", "Camisas de vestir", "Bosselli", 32.00, 79.00, "S,M,L,XL", "Blanco"),
    ("CAM-006", "Camisa lino premium celeste", "Camisas de vestir", "Bosselli", 32.00, 79.00, "S,M,L,XL", "Celeste"),
    ("CAM-007", "Camisa lino premium marino", "Camisas de vestir", "Bosselli", 32.00, 79.00, "M,L,XL", "Marino"),
    ("CAM-101", "Camisa sport burdeos", "Camisas sport", "Bosselli", 24.00, 59.00, "S,M,L,XL", "Burdeos"),
    ("CAM-102", "Camisa sport verde", "Camisas sport", "Bosselli", 24.00, 59.00, "S,M,L,XL", "Verde"),
    ("CAM-103", "Camisa sport blanca", "Camisas sport", "Bosselli", 22.00, 55.00, "S,M,L,XL,XXL", "Blanco"),
    ("COR-001", "Corbata de seda azul", "Corbatas", "Bosselli", 18.00, 45.00, "Única", "Azul"),
    ("COR-002", "Corbata de seda burdeos", "Corbatas", "Bosselli", 18.00, 45.00, "Única", "Burdeos"),
    ("COR-003", "Corbata de seda verde", "Corbatas", "Bosselli", 18.00, 45.00, "Única", "Verde"),
    ("COR-004", "Corbata de seda gris", "Corbatas", "Bosselli", 18.00, 45.00, "Única", "Gris"),
    ("COR-005", "Corbata paisley", "Corbatas", "Bosselli", 22.00, 55.00, "Única", "Multicolor"),
    ("TRA-001", "Traje azul marino 2 piezas", "Sastrería", "Bosselli", 120.00, 299.00, "46,48,50,52,54", "Azul marino"),
    ("TRA-002", "Traje gris marengo", "Sastrería", "Bosselli", 120.00, 299.00, "46,48,50,52", "Gris"),
    ("TRA-003", "Chaqué negro clásico", "Sastrería", "Bosselli", 150.00, 399.00, "46,48,50,52,54", "Negro"),
    ("TRA-004", "Americana Príncipe de Gales", "Sastrería", "Bosselli", 95.00, 239.00, "46,48,50,52", "Gris"),
    ("CAZ-001", "Cazadora Manchester marfil", "Cazadoras", "Bosselli", 60.00, 149.00, "M,L,XL", "Marfil"),
    ("CAZ-002", "Cazadora Manchester verde", "Cazadoras", "Bosselli", 60.00, 149.00, "M,L,XL", "Verde"),
    ("CAZ-003", "Cazadora Windsor camel", "Cazadoras", "Bosselli", 65.00, 159.00, "M,L,XL,XXL", "Camel"),
    ("JER-001", "Jersey media cremallera marfil", "Jerseys y cárdigans", "Bosselli", 38.00, 89.00, "S,M,L,XL", "Marfil"),
    ("JER-002", "Jersey media cremallera verde", "Jerseys y cárdigans", "Bosselli", 38.00, 89.00, "S,M,L,XL", "Verde"),
    ("JER-003", "Jersey media cremallera azul", "Jerseys y cárdigans", "Bosselli", 38.00, 89.00, "M,L,XL", "Azul"),
    ("JER-004", "Jersey media cremallera burdeos", "Jerseys y cárdigans", "Bosselli", 38.00, 89.00, "M,L,XL", "Burdeos"),
    ("CAR-001", "Cárdigan cremallera verde", "Jerseys y cárdigans", "Bosselli", 42.00, 99.00, "M,L,XL", "Verde"),
    ("CAR-002", "Cárdigan azul marino", "Jerseys y cárdigans", "Bosselli", 55.00, 139.00, "M,L,XL", "Azul marino"),
    ("POL-001", "Chaleco polar sin mangas ceniza", "Jerseys y cárdigans", "Bosselli", 22.00, 55.00, "M,L,XL", "Ceniza"),
    ("POL-002", "Chaleco polar sin mangas marrón", "Jerseys y cárdigans", "Bosselli", 22.00, 55.00, "M,L,XL", "Marrón"),
    ("POL-003", "Chaleco polar sin mangas verde", "Jerseys y cárdigans", "Bosselli", 22.00, 55.00, "M,L,XL", "Verde"),
    ("REB-001", "Rebeca punto azul", "Jerseys y cárdigans", "Bosselli", 48.00, 119.00, "S,M,L", "Azul"),
    ("REB-002", "Rebeca punto burdeos", "Jerseys y cárdigans", "Bosselli", 48.00, 119.00, "S,M,L", "Burdeos"),
    ("PAN-001", "Pañuelo San Lorenzo", "Pañuelos", "Bosselli", 8.00, 25.00, "Única", "Multicolor"),
    ("PAN-002", "Pañuelo Macarena", "Pañuelos", "Bosselli", 8.00, 25.00, "Única", "Multicolor"),
    ("PAN-003", "Pañuelo Catedral de Sevilla", "Pañuelos", "Bosselli", 8.00, 25.00, "Única", "Multicolor"),
    ("PAN-004", "Pañuelo Taurino", "Pañuelos", "Bosselli", 8.00, 25.00, "Única", "Multicolor"),
    ("PAN-005", "Pañuelo Plaza de España", "Pañuelos", "Bosselli", 8.00, 25.00, "Única", "Multicolor"),
    ("GEM-001", "Gemelos nazareno personalizados", "Complementos", "Bosselli", 12.00, 35.00, "Única", "Oro"),
    ("CIN-001", "Cinturón trenzado marrón", "Complementos", "Bosselli", 15.00, 39.00, "90,95,100,105", "Marrón"),
    ("CIN-002", "Cinturón trenzado negro", "Complementos", "Bosselli", 15.00, 39.00, "90,95,100,105", "Negro"),
]
EMPLEADOS = [
    ("Jaime", "Bosselli", "12345678Z", "12/1234567890", "jaime@bosselli.es", "600 111 222", "Gerente", 0, 36000.00),
    ("María", "López", "23456789Y", "12/2345678901", "maria@bosselli.es", "600 222 333", "Vendedora", 0, 21000.00),
    ("Antonio", "Ruiz", "34567890X", "12/3456789012", "antonio@bosselli.es", "600 333 444", "Vendedor", 1, 20000.00),
    ("Carmen", "Gómez", "45678901W", "12/4567890123", "carmen@bosselli.es", "600 444 555", "Administrativa", 0, 22000.00),
]
GASTOS_FIJOS = [
    ("Alquiler tienda Nervión", "alquiler", 1800.00, 0),
    ("Alquiler tienda Porvenir", "alquiler", 1500.00, 1),
    ("Electricidad Nervión", "suministros", 220.00, 0),
    ("Electricidad Porvenir", "suministros", 180.00, 1),
    ("Seguro multirriesgo", "seguros", 180.00, None),
    ("Asesoría gestoría", "servicios", 150.00, None),
    ("Publicidad Instagram", "publicidad", 200.00, None),
    ("Limpieza", "mantenimiento", 120.00, None),
]


class Command(BaseCommand):
    help = "Puebla la base de datos con datos demo de Bosselli."

    def handle(self, *args, **options):
        org, _ = Organizacion.objects.get_or_create(
            slug=ORG_SLUG,
            defaults=dict(
                nombre="Bosselli",
                cif="B41123456",
                direccion="Avda. San Francisco Javier 7, Sevilla",
                telefono="954 64 00 00",
                email="infobosselli@gmail.com",
                web="https://www.bosselli.es",
                color="#0f172a",
            ),
        )

        ajuste = Ajuste.obtener()
        ajuste.nombre_app = "Bosselli Gestión"
        ajuste.lema = "Sastrería y moda clásica desde 1973"
        ajuste.email_gestoria = "gestoria@ejemplo.es"
        ajuste.email_avisos = "infobosselli@gmail.com"
        ajuste.save()

        if not User.objects.filter(username="jaime").exists():
            jaime = User.objects.create_user("jaime", "jaime@bosselli.es", "bosselli2024")
            jaime.first_name = "Jaime"
            jaime.last_name = "Bosselli"
            jaime.save()
            Perfil.objects.create(user=jaime, organizacion=org, rol="admin", telefono="600 111 222")
        if not User.objects.filter(username="vendedor").exists():
            vend = User.objects.create_user("vendedor", "vendedor@bosselli.es", "bosselli2024")
            vend.first_name = "María"
            vend.last_name = "López"
            vend.save()
            Perfil.objects.create(user=vend, organizacion=org, rol="vendedor")

        tiendas = []
        for nombre, codigo, direccion, telefono in TIENDAS:
            t, _ = Tienda.all_objects.get_or_create(
                organizacion=org, codigo=codigo,
                defaults=dict(nombre=nombre, direccion=direccion, telefono=telefono, activa=True),
            )
            tiendas.append(t)

        familias = {}
        for nombre, orden in FAMILIAS:
            f, _ = Familia.all_objects.get_or_create(
                organizacion=org, nombre=nombre, defaults=dict(orden=orden, activa=True)
            )
            familias[nombre] = f

        proveedores = []
        for nombre, cif, tel, email in PROVEEDORES:
            p, _ = Proveedor.all_objects.get_or_create(
                organizacion=org, nombre=nombre,
                defaults=dict(cif=cif, telefono=tel, email=email, activo=True),
            )
            proveedores.append(p)

        clientes = []
        for nombre, apellidos, nif, email, tel, ciudad in CLIENTES:
            c, _ = Cliente.all_objects.get_or_create(
                organizacion=org, nombre=nombre, apellidos=apellidos,
                defaults=dict(nif=nif, email=email, telefono=tel, ciudad=ciudad, tipo="particular", activo=True),
            )
            clientes.append(c)

        articulos = []
        for ref, nombre, fam, marca, coste, pvp, tallas, color in ARTICULOS:
            art, _ = Articulo.all_objects.get_or_create(
                organizacion=org, referencia=ref,
                defaults=dict(
                    nombre=nombre, familia=familias[fam], marca=marca,
                    coste=coste, pvp=pvp, iva_pct=21, stock_minimo=2, activo=True,
                    proveedor=random.choice(proveedores),
                ),
            )
            articulos.append(art)
            tallas_list = [t.strip() for t in tallas.split(",")]
            for talla in tallas_list:
                v, _ = Variante.all_objects.get_or_create(
                    organizacion=org, articulo=art, talla=talla, color=color,
                    defaults=dict(activa=True),
                )
                for tienda in tiendas:
                    if not Stock.all_objects.filter(organizacion=org, variante=v, tienda=tienda).exists():
                        cantidad = random.choice([0, 0, 1, 2, 3, 4, 5, 6, 8, 10])
                        Stock.all_objects.create(organizacion=org, variante=v, tienda=tienda, cantidad=cantidad)

        empleados = []
        for nombre, apellidos, nif, nss, email, tel, puesto, tienda_idx, salario in EMPLEADOS:
            e, _ = Empleado.all_objects.get_or_create(
                organizacion=org, nombre=nombre, apellidos=apellidos,
                defaults=dict(
                    nif=nif, nss=nss, email=email, telefono=tel, puesto=puesto,
                    tienda=tiendas[tienda_idx] if tienda_idx < len(tiendas) else None,
                    fecha_alta=date(2022, 1, 1), salario_bruto_anual=salario, activo=True,
                ),
            )
            empleados.append(e)

        hoy = date.today()
        for mes_atras in range(6):
            mes = hoy.replace(day=1) - timedelta(days=mes_atras * 28)
            mes = mes.replace(day=1)
            for desc, cat, importe, tienda_idx in GASTOS_FIJOS:
                Gasto.all_objects.create(
                    organizacion=org, fecha=mes.replace(day=random.randint(1, 25)),
                    categoria=cat, descripcion=desc, base=importe, iva_pct=21,
                    total=round(importe * 1.21, 2),
                    tienda=tiendas[tienda_idx] if tienda_idx is not None and tienda_idx < len(tiendas) else None,
                    recurrente=True, forma_pago="transferencia",
                )

        for _ in range(18):
            Gasto.all_objects.create(
                organizacion=org, fecha=hoy - timedelta(days=random.randint(0, 170)),
                categoria=random.choice(["compras", "servicios", "transporte", "publicidad", "mantenimiento", "otros"]),
                descripcion=random.choice([
                    "Compra de etiquetas y bolsas", "Reparación de máquina de coser",
                    "Envío de pedidos online", "Cartelería tienda", "Limpieza de escaparate",
                    "Material de oficina", "Reforma de probador", "Servicio de tintorería",
                ]),
                base=round(random.uniform(30, 400), 2), iva_pct=random.choice([21, 10, 4]),
                proveedor=random.choice(proveedores),
                tienda=random.choice(tiendas),
                forma_pago=random.choice(["tarjeta", "transferencia", "efectivo"]),
            )

        variantes = list(Variante.all_objects.filter(organizacion=org))
        for i in range(12):
            prov = random.choice(proveedores)
            tienda_destino = random.choice(tiendas)
            fecha = hoy - timedelta(days=random.randint(5, 170))
            compra = Compra.all_objects.create(
                organizacion=org, fecha=fecha, proveedor=prov,
                base=0, iva_pct=21, total=0, estado=random.choice(["pagada", "pagada", "pendiente"]),
                recibida=True, forma_pago="transferencia",
                notas="Entrada de mercancía de temporada",
            )
            base_total = 0
            for _ in range(random.randint(2, 5)):
                v = random.choice(variantes)
                cant = random.randint(3, 15)
                coste = v.articulo.coste
                LineaCompra.all_objects.create(
                    organizacion=org, compra=compra, articulo=v.articulo, variante=v,
                    descripcion=f"{v.articulo.nombre} {v.talla} {v.color}",
                    cantidad=cant, coste_unitario=coste, iva_pct=21,
                )
                base_total += cant * float(coste)
                mover_stock(v, tienda_destino, cant, "entrada", motivo=f"Compra {compra.numero}",
                            referencia=compra.numero, usuario=None, organizacion=org)
            compra.base = round(base_total, 2)
            compra.total = round(base_total * 1.21, 2)
            compra.save(update_fields=["base", "total"])

        formas = ["efectivo", "tarjeta", "tarjeta", "tarjeta", "bizum", "transferencia"]
        tipos = ["ticket", "ticket", "ticket", "factura", "resumen"]
        origenes = ["tienda", "tienda", "tienda", "online", "otro"]
        for i in range(60):
            tienda = random.choice(tiendas)
            cliente = random.choice(clientes + [None, None])
            fecha = hoy - timedelta(days=random.randint(0, 170))
            venta = Venta.all_objects.create(
                organizacion=org, fecha=fecha, tienda=tienda, cliente=cliente,
                tipo=random.choice(tipos), origen=random.choice(origenes),
                base=0, iva_pct=21, total=0,
                forma_pago=random.choice(formas),
                estado=random.choice(["cobrada", "cobrada", "cobrada", "emitida"]),
                notas="",
            )
            base_total = 0
            n_lineas = random.randint(1, 4)
            for _ in range(n_lineas):
                v = random.choice(variantes)
                cant = random.randint(1, 3)
                precio = v.articulo.pvp
                desc = random.choice([0, 0, 0, 5, 10])
                total_linea = cant * float(precio) * (1 - desc / 100)
                LineaVenta.all_objects.create(
                    organizacion=org, venta=venta, articulo=v.articulo, variante=v,
                    descripcion=f"{v.articulo.nombre} {v.talla} {v.color}",
                    cantidad=cant, precio_unitario=precio, descuento_pct=desc, iva_pct=21,
                )
                base_total += total_linea / 1.21
                stock = Stock.all_objects.filter(organizacion=org, variante=v, tienda=tienda).first()
                if stock and stock.cantidad >= cant and random.random() < 0.85:
                    mover_stock(v, tienda, -cant, "salida", motivo=f"Venta {venta.numero}",
                                referencia=venta.numero, usuario=None, organizacion=org)
            venta.base = round(base_total, 2)
            venta.total = round(base_total * 1.21, 2)
            venta.save(update_fields=["base", "total", "numero"])

        for emp in empleados:
            salario_mensual = float(emp.salario_bruto_anual) / 12
            for mes_atras in range(6):
                mes = (hoy.replace(day=1) - timedelta(days=mes_atras * 28)).replace(day=1)
                irpf_pct = random.choice([12.0, 15.0, 18.0, 20.0])
                ss_emp = round(salario_mensual * 0.0635, 2)
                ss_emp2 = round(salario_mensual * 0.30, 2)
                irpf = round(salario_mensual * irpf_pct / 100, 2)
                neto = round(salario_mensual - irpf - ss_emp, 2)
                Nomina.all_objects.get_or_create(
                    organizacion=org, empleado=emp, periodo=mes,
                    defaults=dict(
                        salario_base=round(salario_mensual, 2), complementos=0,
                        prorrateo_pagas=0, bruto=round(salario_mensual, 2),
                        irpf_pct=irpf_pct, irpf=irpf, ss_empleado=ss_emp,
                        ss_empresa=ss_emp2, otras_deducciones=0, neto=neto,
                        estado="pagada" if mes_atras > 0 else "borrador",
                    ),
                )

        for art in articulos[:6]:
            art.stock_minimo = 8
            art.save(update_fields=["stock_minimo"])

        self.stdout.write(self.style.SUCCESS("Datos demo de Bosselli creados correctamente."))
        self.stdout.write("  Superusuario: daw2 / bosselli2024")
        self.stdout.write("  Usuario Jaime: jaime / bosselli2024")
        self.stdout.write("  Usuario vendedor: vendedor / bosselli2024")
