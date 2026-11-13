"""Estado en memoria y lógica de negocio de la tienda.

Todo vive en estructuras de Python dentro del proceso: al reiniciar la app
se recarga el catálogo desde data/catalogo.json y se pierden carritos,
usuarios registrados y órdenes.
"""

from __future__ import annotations

import copy
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

RUTA_CATALOGO = Path(__file__).parent / "data" / "catalogo.json"

TASA_IMPUESTO = 0.115          # IVU Puerto Rico 11.5 %
COSTO_ENVIO = 5.99
ENVIO_GRATIS_DESDE = 50.00
TARJETA_RECHAZO = "4000000000000002"   # tarjeta de prueba que siempre se rechaza

_lock = threading.Lock()

CATALOGO: dict[str, dict] = {}
CARRITOS: dict[str, dict[str, int]] = {}
USUARIOS: dict[str, dict] = {}
ORDENES: list[dict] = []


# ---------------------------------------------------------------- catálogo
def cargar_catalogo() -> None:
    with open(RUTA_CATALOGO, encoding="utf-8") as f:
        productos = json.load(f)
    CATALOGO.clear()
    for p in productos:
        CATALOGO[p["id"]] = copy.deepcopy(p)


def listar_productos(texto: str = "", categoria: str = "") -> list[dict]:
    texto = texto.strip().lower()
    resultado = []
    for p in CATALOGO.values():
        if categoria and p["categoria"] != categoria:
            continue
        if texto and texto not in p["nombre"].lower() and texto not in p["descripcion"].lower():
            continue
        resultado.append(p)
    return resultado


def categorias() -> list[str]:
    return sorted({p["categoria"] for p in CATALOGO.values()})


def reponer_stock(pid: str, cantidad: int) -> tuple[bool, str]:
    if pid not in CATALOGO:
        return False, "Producto no encontrado."
    if cantidad <= 0:
        return False, "La cantidad a reponer debe ser mayor que cero."
    with _lock:
        CATALOGO[pid]["stock"] += cantidad
    return True, f"Stock de «{CATALOGO[pid]['nombre']}» actualizado a {CATALOGO[pid]['stock']}."


# ---------------------------------------------------------------- carrito
def nuevo_carrito() -> str:
    cid = uuid.uuid4().hex
    CARRITOS[cid] = {}
    return cid


def obtener_carrito(cid: str | None) -> dict[str, int]:
    if cid is None or cid not in CARRITOS:
        return {}
    return CARRITOS[cid]


def hay_stock(pid: str, cantidad_total: int) -> bool:
    return pid in CATALOGO and cantidad_total <= CATALOGO[pid]["stock"]


def agregar_al_carrito(cid: str, pid: str, cantidad: int) -> tuple[bool, str]:
    if pid not in CATALOGO:
        return False, "Producto no encontrado."
    if cantidad <= 0:
        return False, "La cantidad debe ser al menos 1."
    carrito = CARRITOS.setdefault(cid, {})
    total = carrito.get(pid, 0) + cantidad
    if not hay_stock(pid, total):
        disp = CATALOGO[pid]["stock"] - carrito.get(pid, 0)
        return False, f"Stock insuficiente para «{CATALOGO[pid]['nombre']}» (disponibles: {max(disp, 0)})."
    carrito[pid] = total
    return True, f"Agregado: {cantidad} × {CATALOGO[pid]['nombre']}."


def actualizar_cantidad(cid: str, pid: str, cantidad: int) -> tuple[bool, str]:
    carrito = CARRITOS.get(cid, {})
    if pid not in carrito:
        return False, "El producto no está en el carrito."
    if cantidad <= 0:
        carrito.pop(pid)
        return True, "Producto eliminado del carrito."
    if not hay_stock(pid, cantidad):
        return False, f"Stock insuficiente: solo hay {CATALOGO[pid]['stock']} unidades."
    carrito[pid] = cantidad
    return True, "Cantidad actualizada."


def eliminar_del_carrito(cid: str, pid: str) -> None:
    CARRITOS.get(cid, {}).pop(pid, None)


def vaciar_carrito(cid: str) -> None:
    CARRITOS[cid] = {}


def lineas_carrito(carrito: dict[str, int]) -> list[dict]:
    lineas = []
    for pid, cant in carrito.items():
        p = CATALOGO[pid]
        lineas.append({"producto": p, "cantidad": cant, "total": round(p["precio"] * cant, 2)})
    return lineas


def calcular_totales(carrito: dict[str, int]) -> dict:
    subtotal = round(sum(CATALOGO[pid]["precio"] * c for pid, c in carrito.items()), 2)
    impuestos = round(subtotal * TASA_IMPUESTO, 2)
    envio = 0.0 if subtotal >= ENVIO_GRATIS_DESDE or subtotal == 0 else COSTO_ENVIO
    return {
        "subtotal": subtotal,
        "impuestos": impuestos,
        "envio": envio,
        "total": round(subtotal + impuestos + envio, 2),
        "falta_envio_gratis": round(max(ENVIO_GRATIS_DESDE - subtotal, 0), 2),
    }


def conciliar_stock(cid: str) -> list[str]:
    """Flujo secundario: ajusta el carrito si el stock cambió desde que se agregó.

    Devuelve la lista de avisos (vacía si no hubo conflicto)."""
    avisos = []
    carrito = CARRITOS.get(cid, {})
    for pid in list(carrito):
        disp = CATALOGO[pid]["stock"]
        if carrito[pid] > disp:
            nombre = CATALOGO[pid]["nombre"]
            if disp == 0:
                carrito.pop(pid)
                avisos.append(f"«{nombre}» se agotó y se quitó del carrito.")
            else:
                carrito[pid] = disp
                avisos.append(f"«{nombre}»: solo quedan {disp}, se ajustó la cantidad.")
    return avisos


# ---------------------------------------------------------------- usuarios
def registrar_usuario(usuario: str, nombre: str, clave: str, confirmar: str) -> tuple[bool, str]:
    usuario = usuario.strip().lower()
    if len(usuario) < 3 or not usuario.isalnum():
        return False, "El usuario debe tener al menos 3 caracteres alfanuméricos."
    if usuario in USUARIOS:
        return False, "Ese usuario ya existe."
    if len(clave) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."
    if clave != confirmar:
        return False, "Las contraseñas no coinciden."
    USUARIOS[usuario] = {
        "usuario": usuario,
        "nombre": nombre.strip() or usuario,
        "hash": generate_password_hash(clave),
        "admin": False,
    }
    return True, "Cuenta creada. ¡Bienvenido!"


def autenticar(usuario: str, clave: str) -> dict | None:
    u = USUARIOS.get(usuario.strip().lower())
    if u and check_password_hash(u["hash"], clave):
        return u
    return None


def _sembrar_usuarios() -> None:
    USUARIOS.clear()
    USUARIOS["demo"] = {"usuario": "demo", "nombre": "Usuario Demo",
                        "hash": generate_password_hash("demo123"), "admin": False}
    USUARIOS["admin"] = {"usuario": "admin", "nombre": "Administrador",
                         "hash": generate_password_hash("admin123"), "admin": True}


# ---------------------------------------------------------------- pago
def _luhn(numero: str) -> bool:
    total = 0
    for i, d in enumerate(reversed(numero)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def procesar_pago(titular: str, numero: str, vencimiento: str, cvv: str, monto: float) -> tuple[bool, str]:
    """Pasarela de pago SIMULADA. No guarda el número de tarjeta."""
    numero = numero.replace(" ", "").replace("-", "")
    if not titular.strip():
        return False, "Falta el nombre del titular."
    if not numero.isdigit() or not 13 <= len(numero) <= 19 or not _luhn(numero):
        return False, "Número de tarjeta inválido."
    try:
        mes, anio = vencimiento.split("/")
        mes, anio = int(mes), int(anio) + (2000 if len(anio.strip()) == 2 else 0)
        if not 1 <= mes <= 12:
            raise ValueError
    except ValueError:
        return False, "Fecha de vencimiento inválida (use MM/AA)."
    hoy = datetime.now()
    if (anio, mes) < (hoy.year, hoy.month):
        return False, "La tarjeta está vencida."
    if not cvv.isdigit() or len(cvv) not in (3, 4):
        return False, "CVV inválido."
    if numero == TARJETA_RECHAZO:
        return False, "El banco emisor rechazó la transacción (fondos insuficientes)."
    if monto <= 0:
        return False, "Monto inválido."
    return True, "Pago aprobado."


# ---------------------------------------------------------------- órdenes
def confirmar_compra(cid: str, usuario: str, ultimos4: str) -> dict:
    """Descuenta stock del catálogo y genera la orden + recibo."""
    with _lock:
        carrito = CARRITOS.get(cid, {})
        for pid, cant in carrito.items():
            if cant > CATALOGO[pid]["stock"]:
                raise ValueError(f"Stock insuficiente para «{CATALOGO[pid]['nombre']}».")
        lineas = lineas_carrito(carrito)
        totales = calcular_totales(carrito)
        for pid, cant in carrito.items():
            CATALOGO[pid]["stock"] -= cant
        orden = {
            "numero": f"ORD-{len(ORDENES) + 1:04d}",
            "usuario": usuario,
            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "lineas": [{"id": l["producto"]["id"], "nombre": l["producto"]["nombre"],
                        "precio": l["producto"]["precio"], "cantidad": l["cantidad"],
                        "total": l["total"]} for l in lineas],
            "tarjeta": f"•••• {ultimos4}",
            **totales,
        }
        ORDENES.append(orden)
        CARRITOS[cid] = {}
    return orden


def ordenes_de(usuario: str) -> list[dict]:
    return [o for o in reversed(ORDENES) if o["usuario"] == usuario]


def buscar_orden(numero: str) -> dict | None:
    return next((o for o in ORDENES if o["numero"] == numero), None)


def inicializar() -> None:
    cargar_catalogo()
    _sembrar_usuarios()
    CARRITOS.clear()
    ORDENES.clear()
