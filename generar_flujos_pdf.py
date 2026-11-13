"""Genera docs/flujos.pdf con el flujo principal y los flujos secundarios.

Uso:  .venv/bin/python generar_flujos_pdf.py

Los diagramas se dibujan con reportlab (sin Graphviz). Cada diagrama se
describe como datos: nodos en una cuadrícula (columna, fila) y aristas
ortogonales entre lados de los nodos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen.canvas import Canvas

ANCHO, ALTO = A4
MARGEN = 40
FUENTE = "Helvetica"
FUENTE_B = "Helvetica-Bold"

COLOR = {
    "T": (colors.HexColor("#2f6f5e"), colors.white),        # inicio / fin
    "P": (colors.HexColor("#eef4f1"), colors.HexColor("#1f2a27")),  # proceso
    "D": (colors.HexColor("#fdf1dc"), colors.HexColor("#1f2a27")),  # decisión
    "M": (colors.HexColor("#fbe9e7"), colors.HexColor("#1f2a27")),  # mensaje / salida
    "S": (colors.HexColor("#e6eef8"), colors.HexColor("#1f2a27")),  # subproceso (otro flujo)
}
BORDE = colors.HexColor("#4b5753")
LINEA = colors.HexColor("#3b4642")
VERDE = colors.HexColor("#2f6f5e")
ROJO = colors.HexColor("#b3372f")


# ------------------------------------------------------------------ modelo
@dataclass
class Nodo:
    id: str
    tipo: str            # T, P, D, M, S
    texto: str
    col: float
    fila: float
    # calculados
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0

    def lado(self, s: str) -> tuple[float, float]:
        return {"t": (self.x, self.y + self.h / 2), "b": (self.x, self.y - self.h / 2),
                "l": (self.x - self.w / 2, self.y), "r": (self.x + self.w / 2, self.y)}[s]


@dataclass
class Arista:
    origen: str
    destino: str
    sale: str = "b"
    entra: str = "t"
    etiqueta: str = ""
    via: list = field(default_factory=list)   # [("x", col) | ("y", fila)]


@dataclass
class Diagrama:
    titulo: str
    descripcion: str
    nodos: list[Nodo]
    aristas: list[Arista]
    rutas: str = ""
    columnas: tuple = (0.27, 0.62, 0.89)      # posición x de cada columna (fracción del ancho)


def N(id, tipo, texto, col, fila):
    return Nodo(id, tipo, texto, col, fila)


def A(o, d, sale="b", entra="t", etiqueta="", via=None):
    return Arista(o, d, sale, entra, etiqueta, via or [])


# ------------------------------------------------------------------ dibujo
class Lienzo:
    def __init__(self, c: Canvas, diag: Diagrama, y_sup: float, y_inf: float):
        self.c, self.d = c, diag
        filas = max(n.fila for n in diag.nodos) + 1
        self.paso = min(64, (y_sup - y_inf) / filas)
        self.y0 = y_sup - self.paso / 2
        self.escala = min(1.0, self.paso / 52)

    def col_x(self, col: float) -> float:
        cols = self.d.columnas
        i = int(col)
        frac = col - i
        if i >= len(cols) - 1:
            base = cols[-1]
        else:
            base = cols[i] + (cols[i + 1] - cols[i]) * frac
        return MARGEN + base * (ANCHO - 2 * MARGEN)

    def fila_y(self, fila: float) -> float:
        return self.y0 - fila * self.paso

    # --- nodos
    def medir(self, n: Nodo):
        n.x, n.y = self.col_x(n.col), self.fila_y(n.fila)
        tam = 8.6
        if n.tipo == "T":
            n.w = max(70, self.c.stringWidth(n.texto, FUENTE_B, tam) + 28)
            n.h = 22 * self.escala + 2
        elif n.tipo == "D":
            n.w = 160
            lineas = simpleSplit(n.texto, FUENTE_B, tam, n.w * 0.58)
            n.h = max(36 * self.escala + 4, 14 + 11 * len(lineas))
        else:
            n.w = 140
            lineas = simpleSplit(n.texto, FUENTE, tam, n.w - 18)
            n.h = max(24 * self.escala + 4, 10 + 11 * len(lineas))

    def nodo(self, n: Nodo):
        c = self.c
        fondo, tinta = COLOR[n.tipo]
        c.setStrokeColor(BORDE)
        c.setLineWidth(0.9)
        c.setFillColor(fondo)
        x, y, w, h = n.x, n.y, n.w, n.h
        if n.tipo == "T":
            c.setStrokeColor(fondo)
            c.roundRect(x - w / 2, y - h / 2, w, h, h / 2, stroke=1, fill=1)
        elif n.tipo == "D":
            p = c.beginPath()
            p.moveTo(x, y + h / 2); p.lineTo(x + w / 2, y); p.lineTo(x, y - h / 2); p.lineTo(x - w / 2, y)
            p.close()
            c.drawPath(p, stroke=1, fill=1)
        elif n.tipo == "M":
            k = 9
            p = c.beginPath()
            p.moveTo(x - w / 2 + k, y + h / 2); p.lineTo(x + w / 2, y + h / 2)
            p.lineTo(x + w / 2 - k, y - h / 2); p.lineTo(x - w / 2, y - h / 2)
            p.close()
            c.drawPath(p, stroke=1, fill=1)
        elif n.tipo == "S":
            c.rect(x - w / 2, y - h / 2, w, h, stroke=1, fill=1)
            c.line(x - w / 2 + 7, y - h / 2, x - w / 2 + 7, y + h / 2)
            c.line(x + w / 2 - 7, y - h / 2, x + w / 2 - 7, y + h / 2)
        else:
            c.roundRect(x - w / 2, y - h / 2, w, h, 4, stroke=1, fill=1)

        fuente = FUENTE_B if n.tipo in ("T", "D") else FUENTE
        tam = 8.6
        ancho_txt = n.w * 0.58 if n.tipo == "D" else n.w - 18
        lineas = simpleSplit(n.texto, fuente, tam, ancho_txt)
        c.setFillColor(tinta)
        c.setFont(fuente, tam)
        alto = 11 * len(lineas)
        for i, l in enumerate(lineas):
            c.drawCentredString(x, y + alto / 2 - 8.5 - 11 * i, l)

    # --- aristas
    def ruta(self, a: Arista, o: Nodo, d: Nodo) -> list[tuple[float, float]]:
        s, e = o.lado(a.sale), d.lado(a.entra)
        pts = [s]
        if a.via:
            p = s
            for eje, v in a.via:
                if eje == "x":
                    p = (self.col_x(v), p[1])
                elif eje == "X":                     # x absoluta (carriles laterales)
                    p = (v, p[1])
                else:
                    p = (p[0], self.fila_y(v))
                pts.append(p)
        else:
            vs, ve = a.sale in "tb", a.entra in "tb"
            if vs and ve and s[0] != e[0]:
                my = (s[1] + e[1]) / 2
                pts += [(s[0], my), (e[0], my)]
            elif not vs and not ve and s[1] != e[1]:
                mx = (s[0] + e[0]) / 2
                pts += [(mx, s[1]), (mx, e[1])]
            elif not vs and ve:
                pts.append((e[0], s[1]))
            elif vs and not ve:
                pts.append((s[0], e[1]))
        ult = pts[-1]
        if ult[0] != e[0] and ult[1] != e[1]:
            pts.append((e[0], ult[1]) if a.entra in "tb" else (ult[0], e[1]))
        pts.append(e)
        limpios = [pts[0]]
        for p in pts[1:]:
            if abs(p[0] - limpios[-1][0]) > 0.1 or abs(p[1] - limpios[-1][1]) > 0.1:
                limpios.append(p)
        return limpios

    def arista(self, a: Arista, nodos: dict[str, Nodo]):
        c = self.c
        pts = self.ruta(a, nodos[a.origen], nodos[a.destino])
        color = VERDE if a.etiqueta == "Sí" else ROJO if a.etiqueta == "No" else LINEA
        c.setStrokeColor(color)
        c.setLineWidth(1.1)
        p = c.beginPath()
        p.moveTo(*pts[0])
        for q in pts[1:]:
            p.lineTo(*q)
        c.drawPath(p, stroke=1, fill=0)
        # punta de flecha
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        dx, dy = x2 - x1, y2 - y1
        largo = max((dx * dx + dy * dy) ** 0.5, 0.01)
        ux, uy = dx / largo, dy / largo
        t, ancho = 7, 3.4
        f = c.beginPath()
        f.moveTo(x2, y2)
        f.lineTo(x2 - ux * t - uy * ancho, y2 - uy * t + ux * ancho)
        f.lineTo(x2 - ux * t + uy * ancho, y2 - uy * t - ux * ancho)
        f.close()
        c.setFillColor(color)
        c.drawPath(f, stroke=0, fill=1)
        # etiqueta
        if a.etiqueta:
            (sx, sy), (nx, ny) = pts[0], pts[1]
            c.setFont(FUENTE_B, 8)
            if abs(ny - sy) < 0.1:      # sale horizontal
                dirx = 1 if nx > sx else -1
                tx = sx + dirx * 6
                if dirx > 0:
                    c.drawString(tx, sy + 3, a.etiqueta)
                else:
                    c.drawRightString(tx, sy + 3, a.etiqueta)
            else:
                ty = sy + (-11 if ny < sy else 4)
                c.drawString(sx + 4, ty, a.etiqueta)

    def dibujar(self):
        nodos = {n.id: n for n in self.d.nodos}
        for n in self.d.nodos:
            self.medir(n)
        for a in self.d.aristas:
            self.arista(a, nodos)
        for n in self.d.nodos:
            self.nodo(n)


# ------------------------------------------------------------------ diagramas
def flujo_principal() -> Diagrama:
    nodos = [
        N("ini", "T", "Inicio", 0, 0),
        N("cat", "P", "Mostrar catálogo de productos", 0, 1),
        N("sel", "P", "Seleccionar producto y cantidad", 0, 2),
        N("stk", "D", "¿Hay stock disponible?", 0, 3),
        N("mstk", "M", 'Mostrar: "Stock insuficiente"', 1, 3),
        N("add", "P", "Agregar producto al carrito", 0, 4),
        N("seg", "D", "¿Seguir comprando?", 0, 5),
        N("vac", "D", "¿Carrito vacío?", 0, 6),
        N("mvac", "M", 'Mostrar: "Carrito vacío"', 1, 6),
        N("fin1", "T", "Fin", 2, 6),
        N("calc", "P", "Calcular subtotal, impuestos (IVU 11.5%) y envío", 0, 7),
        N("aut", "D", "¿Usuario autenticado?", 0, 8),
        N("log", "S", "Iniciar sesión (flujo 4)", 1, 8),
        N("pag", "P", "Procesar pago", 0, 9),
        N("apr", "D", "¿Pago aprobado?", 0, 10),
        N("err", "M", "Mostrar error de pago", 1, 10),
        N("fin2", "T", "Fin", 2, 10),
        N("des", "P", "Descontar stock del catálogo", 0, 11),
        N("ord", "P", "Generar orden de compra y recibo", 0, 12),
        N("fin", "T", "Fin", 0, 13),
    ]
    aristas = [
        A("ini", "cat"), A("cat", "sel"), A("sel", "stk"),
        A("stk", "mstk", "r", "l", "No"),
        A("mstk", "cat", "t", "r"),
        A("stk", "add", etiqueta="Sí"), A("add", "seg"),
        A("seg", "cat", "r", "r", "Sí", via=[("x", 1.75), ("y", 1)]),
        A("seg", "vac", etiqueta="No"),
        A("vac", "mvac", "r", "l", "Sí"), A("mvac", "fin1", "r", "l"),
        A("vac", "calc", etiqueta="No"), A("calc", "aut"),
        A("aut", "log", "r", "l", "No"),
        A("log", "pag", "b", "r"),
        A("aut", "pag", etiqueta="Sí"), A("pag", "apr"),
        A("apr", "err", "r", "l", "No"), A("err", "fin2", "r", "l"),
        A("apr", "des", etiqueta="Sí"), A("des", "ord"), A("ord", "fin"),
    ]
    return Diagrama(
        "Flujo principal: proceso de compra",
        "Implementa el diagrama original. El catálogo se carga desde data/catalogo.json a memoria al "
        "arrancar. La validación de stock considera lo que ya está en el carrito. Tras \"No seguir "
        "comprando\" se pasa al checkout; si no hay sesión se redirige al inicio de sesión y luego se "
        "regresa al pago. Solo después de un pago aprobado se descuenta el stock y se genera la orden.",
        nodos, aristas,
        "GET /  ·  POST /carrito/agregar  ·  GET /carrito/agregado  ·  GET /checkout  ·  POST /pago  ·  GET /recibo/<n>",
    )


def flujo_arranque() -> Diagrama:
    nodos = [
        N("ini", "T", "Inicio (python app.py)", 0, 0),
        N("leer", "P", "Leer data/catalogo.json", 0, 1),
        N("ok", "D", "¿Archivo existe y es JSON válido?", 0, 2),
        N("err", "M", "Mostrar excepción; la app no inicia", 1, 2),
        N("fin1", "T", "Fin", 2, 2),
        N("mem", "P", "Copiar productos al diccionario CATALOGO en memoria", 0, 3),
        N("usr", "P", "Crear usuarios de prueba (demo, admin) con contraseña cifrada", 0, 4),
        N("vac", "P", "Inicializar carritos y órdenes vacíos", 0, 5),
        N("srv", "P", "Iniciar servidor web Flask (puerto 5000)", 0, 6),
        N("fin", "T", "Fin", 0, 7),
    ]
    aristas = [
        A("ini", "leer"), A("leer", "ok"),
        A("ok", "err", "r", "l", "No"), A("err", "fin1", "r", "l"),
        A("ok", "mem", etiqueta="Sí"), A("mem", "usr"), A("usr", "vac"), A("vac", "srv"), A("srv", "fin"),
    ]
    return Diagrama(
        "Flujo 1: Arranque y carga del catálogo en memoria",
        "El archivo JSON solo se lee al iniciar; todo cambio posterior (stock, carritos, usuarios, "
        "órdenes) vive en memoria y se pierde al reiniciar el servidor.",
        nodos, aristas, "store.inicializar()  ·  store.cargar_catalogo()")


def flujo_busqueda() -> Diagrama:
    nodos = [
        N("ini", "T", "Inicio", 0, 0),
        N("abr", "P", "Abrir catálogo", 0, 1),
        N("ing", "P", "Ingresar texto de búsqueda y/o elegir categoría", 0, 2),
        N("hay", "D", "¿Hay filtros aplicados?", 0, 3),
        N("todos", "P", "Mostrar todos los productos", 1, 3),
        N("filt", "P", "Filtrar por categoría y por texto en nombre o descripción", 0, 4),
        N("res", "D", "¿Hay resultados?", 0, 5),
        N("nada", "M", 'Mostrar: "No se encontraron productos"', 1, 5),
        N("most", "P", "Mostrar productos filtrados", 0, 6),
        N("limp", "D", "¿Limpiar filtros?", 0, 7),
        N("fin", "T", "Fin (continúa flujo principal)", 0, 8),
    ]
    aristas = [
        A("ini", "abr"), A("abr", "ing"), A("ing", "hay"),
        A("hay", "todos", "r", "l", "No"),
        A("todos", "fin", "b", "r", via=[("y", 8)]),
        A("hay", "filt", etiqueta="Sí"), A("filt", "res"),
        A("res", "nada", "r", "l", "No"), A("nada", "limp", "b", "r", via=[("y", 7)]),
        A("res", "most", etiqueta="Sí"), A("most", "limp"),
        A("limp", "abr", "l", "l", "Sí", via=[("X", 100), ("y", 1)]),
        A("limp", "fin", etiqueta="No"),
    ]
    d = Diagrama(
        "Flujo 2: Búsqueda y filtro por categoría",
        "La búsqueda no distingue mayúsculas y revisa nombre y descripción. La categoría se elige en "
        "una lista generada a partir del catálogo en memoria. \"Limpiar\" vuelve a mostrar el catálogo completo.",
        nodos, aristas, "GET /?q=<texto>&cat=<categoría>")
    d.columnas = (0.36, 0.78, 0.95)
    return d


def flujo_carrito() -> Diagrama:
    nodos = [
        N("ini", "T", "Inicio", 0, 0),
        N("ver", "P", "Ver carrito", 0, 1),
        N("vac", "D", "¿Carrito vacío?", 0, 2),
        N("mvac", "M", 'Mostrar: "Tu carrito está vacío"', 1, 2),
        N("fin1", "T", "Fin", 2, 2),
        N("lis", "P", "Mostrar productos, subtotal, IVU y envío", 0, 3),
        N("acc", "D", "¿Modificar cantidad?", 0, 4),
        N("cant", "P", "Ingresar nueva cantidad", 1, 5),
        N("cero", "D", "¿Cantidad = 0?", 1, 6),
        N("eli", "P", "Eliminar producto del carrito", 2, 6),
        N("stk", "D", "¿Hay stock suficiente?", 1, 7),
        N("mstk", "M", 'Mostrar: "Stock insuficiente"', 2, 7),
        N("upd", "P", "Actualizar cantidad", 1, 8),
        N("pagar", "D", "¿Ir a pagar?", 0, 9),
        N("chk", "S", "Checkout (flujo principal)", 0, 10),
        N("seguir", "S", "Seguir comprando (catálogo)", 1, 10),
        N("fin", "T", "Fin", 0, 11),
    ]
    carril = ANCHO - 22
    aristas = [
        A("ini", "ver"), A("ver", "vac"),
        A("vac", "mvac", "r", "l", "Sí"), A("mvac", "fin1", "r", "l"),
        A("vac", "lis", etiqueta="No"), A("lis", "acc"),
        A("acc", "cant", "r", "t", "Sí"), A("cant", "cero"),
        A("cero", "eli", "r", "l", "Sí"),
        A("eli", "lis", "t", "r", via=[("y", 3)]),
        A("cero", "stk", etiqueta="No"),
        A("stk", "mstk", "r", "l", "No"),
        A("mstk", "lis", "r", "r", via=[("X", carril), ("y", 3)]),
        A("stk", "upd", etiqueta="Sí"),
        A("upd", "lis", "r", "r", via=[("X", carril), ("y", 3)]),
        A("acc", "pagar", etiqueta="No"),
        A("pagar", "chk", etiqueta="Sí"),
        A("pagar", "seguir", "r", "t", "No"),
        A("chk", "fin"), A("seguir", "fin", "b", "r", via=[("y", 11)]),
    ]
    d = Diagrama(
        "Flujo 3: Gestión del carrito",
        "Desde la página del carrito se puede cambiar la cantidad (0 elimina el producto), quitar un "
        "producto con el botón X o vaciar todo el carrito. Cada cambio de cantidad vuelve a validar "
        "contra el stock en memoria. Todas las acciones regresan a la vista del carrito.",
        nodos, aristas,
        "GET /carrito  ·  POST /carrito/actualizar  ·  POST /carrito/eliminar  ·  POST /carrito/vaciar")
    d.columnas = (0.15, 0.5, 0.86)
    return d


def flujo_sesion() -> Diagrama:
    nodos = [
        N("ini", "T", "Inicio", 0, 0),
        N("form", "P", "Mostrar formulario de inicio de sesión", 0, 1),
        N("ing", "P", "Ingresar usuario y contraseña", 0, 2),
        N("val", "D", "¿Credenciales válidas?", 0, 3),
        N("merr", "M", 'Mostrar: "Usuario o contraseña incorrectos"', 1, 3),
        N("ses", "P", "Guardar usuario en la sesión (el carrito se conserva)", 0, 4),
        N("next", "D", "¿Venía del checkout?", 0, 5),
        N("chk", "S", "Regresar al checkout (flujo principal)", 1, 5),
        N("cat", "P", "Ir al catálogo", 0, 6),
        N("fin", "T", "Fin", 0, 7),
        N("ini2", "T", "Inicio", 0, 8.6),
        N("salir", "P", 'Pulsar "Salir"', 0, 9.6),
        N("borrar", "P", "Quitar usuario de la sesión", 0, 10.6),
        N("cat2", "P", "Mostrar catálogo", 0, 11.6),
        N("fin2", "T", "Fin", 0, 12.6),
    ]
    aristas = [
        A("ini", "form"), A("form", "ing"), A("ing", "val"),
        A("val", "merr", "r", "l", "No"),
        A("merr", "form", "t", "r"),
        A("val", "ses", etiqueta="Sí"), A("ses", "next"),
        A("next", "chk", "r", "l", "Sí"),
        A("chk", "fin", "b", "r", via=[("y", 7)]),
        A("next", "cat", etiqueta="No"), A("cat", "fin"),
        A("ini2", "salir"), A("salir", "borrar"), A("borrar", "cat2"), A("cat2", "fin2"),
    ]
    return Diagrama(
        "Flujo 4: Inicio y cierre de sesión",
        "Arriba: inicio de sesión. Si el usuario llegó desde el checkout (parámetro next), al autenticarse "
        "regresa directamente al pago. Abajo: cierre de sesión. Usuarios de prueba: demo/demo123 y admin/admin123.",
        nodos, aristas, "GET|POST /login?next=/checkout  ·  POST /logout")


def flujo_registro() -> Diagrama:
    nodos = [
        N("ini", "T", "Inicio", 0, 0),
        N("form", "P", "Mostrar formulario de registro", 0, 1),
        N("ing", "P", "Ingresar usuario, nombre, contraseña y confirmación", 0, 2),
        N("u", "D", "¿Usuario de 3+ caracteres alfanuméricos?", 0, 3),
        N("ex", "D", "¿El usuario ya existe?", 0, 4),
        N("c", "D", "¿Contraseña de 6+ caracteres?", 0, 5),
        N("cf", "D", "¿Las contraseñas coinciden?", 0, 6),
        N("merr", "M", "Mostrar mensaje de error de validación", 1, 4.5),
        N("guar", "P", "Guardar usuario en memoria con contraseña cifrada", 0, 7),
        N("ses", "P", "Iniciar sesión automáticamente", 0, 8),
        N("red", "P", "Redirigir al destino (checkout o catálogo)", 0, 9),
        N("fin", "T", "Fin", 0, 10),
    ]
    aristas = [
        A("ini", "form"), A("form", "ing"), A("ing", "u"),
        A("u", "merr", "r", "t", "No"),
        A("ex", "merr", "r", "l", "Sí", via=[("x", 0.62)]),
        A("c", "merr", "r", "l", "No", via=[("x", 0.62)]),
        A("cf", "merr", "r", "b", "No"),
        A("merr", "form", "r", "r", via=[("x", 1.8), ("y", 1)]),
        A("u", "ex", etiqueta="Sí"), A("ex", "c", etiqueta="No"),
        A("c", "cf", etiqueta="Sí"), A("cf", "guar", etiqueta="Sí"),
        A("guar", "ses"), A("ses", "red"), A("red", "fin"),
    ]
    return Diagrama(
        "Flujo 5: Registro de usuario",
        "Flujo secundario que se puede iniciar desde el inicio de sesión. Las contraseñas se guardan "
        "cifradas (werkzeug) en el diccionario USUARIOS en memoria.",
        nodos, aristas, "GET|POST /registro")


def flujo_validacion_pago() -> Diagrama:
    nodos = [
        N("ini", "T", "Inicio (Procesar pago)", 0, 0),
        N("ing", "P", "Recibir titular, número, vencimiento y CVV", 0, 1),
        N("t", "D", "¿Titular presente?", 0, 2),
        N("n", "D", "¿Número válido (13-19 dígitos, Luhn)?", 0, 3),
        N("v", "D", "¿Vencimiento MM/AA no vencido?", 0, 4),
        N("cvv", "D", "¿CVV de 3 o 4 dígitos?", 0, 5),
        N("bco", "D", "¿Banco emisor aprueba?", 0, 6),
        N("rech", "M", "Pago rechazado: mostrar motivo (carrito se conserva)", 1, 4),
        N("fin1", "T", "Fin", 1, 5.3),
        N("ok", "P", "Pago aprobado (se guardan solo los últimos 4 dígitos)", 0, 7),
        N("fin", "T", "Fin (Descontar stock)", 0, 8),
    ]
    via = [("x", 0.62)]
    aristas = [
        A("ini", "ing"), A("ing", "t"),
        A("t", "rech", "r", "t", "No"),
        A("n", "rech", "r", "t", "No", via=[("x", 0.55)]),
        A("v", "rech", "r", "l", "No"),
        A("cvv", "rech", "r", "l", "No", via=via),
        A("bco", "rech", "r", "l", "No", via=via),
        A("rech", "fin1"),
        A("t", "n", etiqueta="Sí"), A("n", "v", etiqueta="Sí"), A("v", "cvv", etiqueta="Sí"),
        A("cvv", "bco", etiqueta="Sí"), A("bco", "ok", etiqueta="Sí"), A("ok", "fin"),
    ]
    d = Diagrama(
        "Flujo 6: Validación del pago (pasarela simulada)",
        "Detalle del paso \"Procesar pago\". Tarjetas de prueba: 4242 4242 4242 4242 se aprueba; "
        "4000 0000 0000 0002 la rechaza el banco simulado (fondos insuficientes).",
        nodos, aristas, "store.procesar_pago()  ·  POST /pago")
    d.columnas = (0.3, 0.8, 0.95)
    return d


def flujo_conflicto() -> Diagrama:
    nodos = [
        N("ini", "T", "Inicio (checkout o confirmar pago)", 0, 0),
        N("rev", "P", "Tomar siguiente producto del carrito", 0, 1),
        N("may", "D", "¿Cantidad > stock actual?", 0, 2),
        N("cero", "D", "¿Stock actual = 0?", 1, 3),
        N("aj", "P", "Ajustar cantidad al stock disponible", 2, 3),
        N("quit", "P", "Quitar producto del carrito", 1, 4),
        N("mas", "D", "¿Quedan productos por revisar?", 0, 5),
        N("hub", "D", "¿Hubo ajustes?", 0, 6),
        N("av", "M", "Mostrar avisos y volver al carrito", 2, 6),
        N("fin1", "T", "Fin", 2, 7),
        N("pag", "S", "Procesar pago (flujo principal)", 0, 7),
        N("lock", "P", "Al descontar: verificación final con bloqueo (lock)", 0, 8),
        N("fin", "T", "Fin", 0, 9),
    ]
    aristas = [
        A("ini", "rev"), A("rev", "may"),
        A("may", "cero", "r", "t", "Sí"),
        A("cero", "quit", etiqueta="Sí"),
        A("cero", "aj", "r", "l", "No"),
        A("quit", "mas", "b", "r", via=[("y", 5)]),
        A("aj", "mas", "b", "r", via=[("y", 5)]),
        A("may", "mas", etiqueta="No"),
        A("mas", "rev", "l", "l", "Sí", via=[("X", 26), ("y", 1)]),
        A("mas", "hub", etiqueta="No"),
        A("hub", "av", "r", "l", "Sí"), A("av", "fin1"),
        A("hub", "pag", etiqueta="No"), A("pag", "lock"), A("lock", "fin"),
    ]
    d = Diagrama(
        "Flujo 7: Conflicto de stock al pagar",
        "Otro cliente pudo comprar o el administrador pudo cambiar el inventario después de que el "
        "producto se agregó al carrito. Antes de cobrar se concilia el carrito con el stock actual; al "
        "descontar, una verificación protegida con un lock evita vender más de lo disponible.",
        nodos, aristas, "store.conciliar_stock()  ·  store.confirmar_compra()")
    d.columnas = (0.18, 0.5, 0.86)
    return d


def flujo_ordenes() -> Diagrama:
    nodos = [
        N("ini", "T", "Inicio", 0, 0),
        N("abr", "P", 'Abrir "Mis órdenes"', 0, 1),
        N("aut", "D", "¿Usuario autenticado?", 0, 2),
        N("log", "S", "Iniciar sesión (flujo 4)", 1, 2),
        N("bus", "P", "Buscar órdenes del usuario en memoria", 0, 3),
        N("tiene", "D", "¿Tiene órdenes?", 0, 4),
        N("nada", "M", 'Mostrar: "Aún no tienes órdenes"', 1, 4),
        N("fin1", "T", "Fin", 2, 4),
        N("lis", "P", "Mostrar lista (número, fecha, artículos, total)", 0, 5),
        N("sel", "P", "Seleccionar una orden", 0, 6),
        N("due", "D", "¿La orden es del usuario (o es admin)?", 0, 7),
        N("e404", "M", "Mostrar error 404", 1, 7),
        N("fin2", "T", "Fin", 2, 7),
        N("rec", "P", "Mostrar recibo imprimible", 0, 8),
        N("fin", "T", "Fin", 0, 9),
    ]
    aristas = [
        A("ini", "abr"), A("abr", "aut"),
        A("aut", "log", "r", "l", "No"), A("log", "abr", "t", "r"),
        A("aut", "bus", etiqueta="Sí"), A("bus", "tiene"),
        A("tiene", "nada", "r", "l", "No"), A("nada", "fin1", "r", "l"),
        A("tiene", "lis", etiqueta="Sí"), A("lis", "sel"), A("sel", "due"),
        A("due", "e404", "r", "l", "No"), A("e404", "fin2", "r", "l"),
        A("due", "rec", etiqueta="Sí"), A("rec", "fin"),
    ]
    return Diagrama(
        "Flujo 8: Historial de órdenes y recibo",
        "Cada usuario solo puede ver sus propias órdenes; el administrador puede ver cualquiera desde el panel.",
        nodos, aristas, "GET /ordenes  ·  GET /recibo/<número>")


def flujo_admin() -> Diagrama:
    nodos = [
        N("ini", "T", "Inicio", 0, 0),
        N("abr", "P", "Abrir panel de administración", 0, 1),
        N("aut", "D", "¿Usuario autenticado?", 0, 2),
        N("log", "S", "Iniciar sesión (flujo 4)", 1, 2),
        N("adm", "D", "¿Es administrador?", 0, 3),
        N("e403", "M", "Mostrar error 403", 1, 3),
        N("fin1", "T", "Fin", 2, 3),
        N("inv", "P", "Mostrar inventario y órdenes recientes", 0, 4),
        N("ing", "P", "Elegir producto e ingresar cantidad a reponer", 0, 5),
        N("pos", "D", "¿Cantidad > 0?", 0, 6),
        N("merr", "M", "Mostrar error de cantidad", 1, 6),
        N("sum", "P", "Sumar cantidad al stock en memoria", 0, 7),
        N("ok", "M", "Mostrar stock actualizado", 0, 8),
        N("fin", "T", "Fin", 0, 9),
    ]
    aristas = [
        A("ini", "abr"), A("abr", "aut"),
        A("aut", "log", "r", "l", "No"), A("log", "abr", "t", "r"),
        A("aut", "adm", etiqueta="Sí"),
        A("adm", "e403", "r", "l", "No"), A("e403", "fin1", "r", "l"),
        A("adm", "inv", etiqueta="Sí"), A("inv", "ing"), A("ing", "pos"),
        A("pos", "merr", "r", "l", "No"),
        A("merr", "inv", "t", "r", via=[("y", 4)]),
        A("pos", "sum", etiqueta="Sí"), A("sum", "ok"), A("ok", "fin"),
    ]
    return Diagrama(
        "Flujo 9: Reposición de stock (administrador)",
        "Permite reabastecer productos agotados. El cambio solo afecta al catálogo en memoria "
        "(el archivo JSON no se modifica). Usuario: admin / admin123.",
        nodos, aristas, "GET|POST /admin")


DIAGRAMAS = [flujo_principal, flujo_arranque, flujo_busqueda, flujo_carrito, flujo_sesion,
             flujo_registro, flujo_validacion_pago, flujo_conflicto, flujo_ordenes, flujo_admin]


# ------------------------------------------------------------------ páginas
def pie(c: Canvas, pagina: int):
    c.setFont(FUENTE, 8)
    c.setFillColor(colors.HexColor("#6b7671"))
    c.drawString(MARGEN, 22, "InLine Orders · Diagramas de flujo")
    c.drawRightString(ANCHO - MARGEN, 22, f"Página {pagina}")


def portada(c: Canvas, diagramas: list[Diagrama]):
    c.setFillColor(VERDE)
    c.rect(0, ALTO - 170, ANCHO, 170, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(FUENTE_B, 26)
    c.drawString(MARGEN, ALTO - 90, "InLine Orders")
    c.setFont(FUENTE, 14)
    c.drawString(MARGEN, ALTO - 115, "Diagramas de flujo del sistema de compras")
    c.setFont(FUENTE, 10)
    c.drawString(MARGEN, ALTO - 140, f"Generado el {date.today().strftime('%d/%m/%Y')}")

    c.setFillColor(colors.HexColor("#1f2a27"))
    c.setFont(FUENTE_B, 14)
    y = ALTO - 215
    c.drawString(MARGEN, y, "Contenido")
    c.setFont(FUENTE, 11)
    for i, d in enumerate(diagramas, start=2):
        y -= 22
        c.drawString(MARGEN + 10, y, d.titulo)
        c.drawRightString(ANCHO - MARGEN, y, str(i))
        c.setStrokeColor(colors.HexColor("#d7ddd9"))
        c.setDash(1, 2)
        ancho_txt = c.stringWidth(d.titulo, FUENTE, 11)
        c.line(MARGEN + 16 + ancho_txt, y + 3, ANCHO - MARGEN - 14, y + 3)
        c.setDash()

    # leyenda
    y -= 50
    c.setFont(FUENTE_B, 14)
    c.drawString(MARGEN, y, "Leyenda")
    muestras = [("T", "Inicio", "Inicio / Fin"), ("P", "Proceso", "Acción del sistema o del usuario"),
                ("D", "¿Decisión?", "Pregunta con salidas Sí (verde) / No (rojo)"),
                ("M", "Mensaje", "Mensaje o resultado mostrado al usuario"),
                ("S", "Subproceso", "Paso detallado en otro flujo")]
    lz = Lienzo(c, Diagrama("", "", [N("x", "T", "", 0, 0)], []), y, y - 60)
    for tipo, texto, desc in muestras:
        y -= 48
        n = N("m", tipo, texto, 0, 0)
        lz.medir(n)
        n.x, n.y = MARGEN + 95, y
        lz.nodo(n)
        c.setFillColor(colors.HexColor("#1f2a27"))
        c.setFont(FUENTE, 10)
        c.drawString(MARGEN + 200, y - 3, desc)

    c.setFont(FUENTE, 9)
    c.setFillColor(colors.HexColor("#6b7671"))
    texto = ("Aplicación web en Python (Flask). Catálogo en data/catalogo.json cargado a memoria; "
             "carritos, usuarios y órdenes se mantienen en memoria del proceso.")
    yy = 70
    for l in simpleSplit(texto, FUENTE, 9, ANCHO - 2 * MARGEN):
        c.drawString(MARGEN, yy, l)
        yy -= 12
    pie(c, 1)


def pagina_diagrama(c: Canvas, d: Diagrama, num: int):
    c.setFillColor(VERDE)
    c.rect(0, ALTO - 8, ANCHO, 8, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#1f2a27"))
    c.setFont(FUENTE_B, 15)
    c.drawString(MARGEN, ALTO - 42, d.titulo)
    c.setFont(FUENTE, 9)
    c.setFillColor(colors.HexColor("#4b5753"))
    y = ALTO - 60
    for l in simpleSplit(d.descripcion, FUENTE, 9, ANCHO - 2 * MARGEN):
        c.drawString(MARGEN, y, l)
        y -= 11.5
    y_rutas = 40
    if d.rutas:
        c.setFont("Courier", 7.5)
        c.setFillColor(colors.HexColor("#6b7671"))
        lineas = simpleSplit("Implementación: " + d.rutas, "Courier", 7.5, ANCHO - 2 * MARGEN)
        for i, l in enumerate(reversed(lineas)):
            c.drawString(MARGEN, y_rutas + 10 * i, l)
        y_rutas += 10 * (len(lineas) - 1)
    Lienzo(c, d, y - 10, y_rutas + 14).dibujar()
    pie(c, num)


def generar(ruta: Path | str = Path(__file__).parent / "docs" / "flujos.pdf") -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    diagramas = [f() for f in DIAGRAMAS]
    c = Canvas(str(ruta), pagesize=A4)
    c.setTitle("InLine Orders - Diagramas de flujo")
    c.setAuthor("InLine Orders")
    portada(c, diagramas)
    c.showPage()
    for i, d in enumerate(diagramas, start=2):
        pagina_diagrama(c, d, i)
        c.showPage()
    c.save()
    return ruta


if __name__ == "__main__":
    print(f"PDF generado en {generar()}")
