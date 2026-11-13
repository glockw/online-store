"""Tienda en línea — implementación del diagrama de flujo de compra.

Ejecutar:  .venv/bin/python app.py   →  http://127.0.0.1:5000
"""

from __future__ import annotations

import os
import secrets
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_file, session, url_for)

import store

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)   # en memoria: las sesiones se invalidan al reiniciar
store.inicializar()

RUTA_PDF = Path(__file__).parent / "docs" / "flujos.pdf"


# ---------------------------------------------------------------- utilidades
def carrito_id() -> str:
    cid = session.get("cid")
    if cid not in store.CARRITOS:
        cid = store.nuevo_carrito()
        session["cid"] = cid
    return cid


def usuario_actual() -> dict | None:
    return store.USUARIOS.get(session.get("usuario", ""))


def requiere_login(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not usuario_actual():
            flash("Inicia sesión para continuar.", "aviso")
            return redirect(url_for("login", next=request.path))
        return vista(*args, **kwargs)
    return envoltura


def destino_seguro(destino: str | None) -> str:
    if destino and destino.startswith("/") and not destino.startswith("//"):
        return destino
    return url_for("catalogo")


def entero(valor, defecto=0) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return defecto


@app.context_processor
def contexto_global():
    carrito = store.obtener_carrito(session.get("cid"))
    return {"usuario": usuario_actual(), "items_carrito": sum(carrito.values())}


@app.template_filter("dinero")
def dinero(valor: float) -> str:
    return f"${valor:,.2f}"


# ---------------------------------------------------------------- catálogo
@app.get("/")
def catalogo():
    texto = request.args.get("q", "")
    categoria = request.args.get("cat", "")
    return render_template("catalogo.html",
                           productos=store.listar_productos(texto, categoria),
                           categorias=store.categorias(), q=texto, cat=categoria,
                           en_carrito=store.obtener_carrito(session.get("cid")))


# ---------------------------------------------------------------- carrito
@app.post("/carrito/agregar")
def agregar():
    pid = request.form.get("pid", "")
    cantidad = entero(request.form.get("cantidad"), 1)
    ok, mensaje = store.agregar_al_carrito(carrito_id(), pid, cantidad)
    if not ok:                                   # ¿Hay stock? → No
        flash(mensaje, "error")
        return redirect(request.referrer or url_for("catalogo"))
    return redirect(url_for("agregado", pid=pid, cantidad=cantidad))


@app.get("/carrito/agregado")
def agregado():                                  # ¿Seguir comprando?
    producto = store.CATALOGO.get(request.args.get("pid", ""))
    if not producto:
        return redirect(url_for("catalogo"))
    return render_template("agregado.html", producto=producto,
                           cantidad=entero(request.args.get("cantidad"), 1))


@app.get("/carrito")
def ver_carrito():
    carrito = store.obtener_carrito(session.get("cid"))
    return render_template("carrito.html", lineas=store.lineas_carrito(carrito),
                           totales=store.calcular_totales(carrito))


@app.post("/carrito/actualizar")
def actualizar():
    ok, mensaje = store.actualizar_cantidad(carrito_id(), request.form.get("pid", ""),
                                            entero(request.form.get("cantidad"), 1))
    flash(mensaje, "ok" if ok else "error")
    return redirect(url_for("ver_carrito"))


@app.post("/carrito/eliminar")
def eliminar():
    store.eliminar_del_carrito(carrito_id(), request.form.get("pid", ""))
    flash("Producto eliminado del carrito.", "ok")
    return redirect(url_for("ver_carrito"))


@app.post("/carrito/vaciar")
def vaciar():
    store.vaciar_carrito(carrito_id())
    flash("Carrito vaciado.", "ok")
    return redirect(url_for("ver_carrito"))


# ---------------------------------------------------------------- checkout y pago
@app.get("/checkout")
def checkout():
    cid = carrito_id()
    carrito = store.obtener_carrito(cid)
    if not carrito:                              # ¿Carrito vacío? → Sí → Fin
        return render_template("carrito_vacio.html")
    avisos = store.conciliar_stock(cid)          # flujo secundario: conflicto de stock
    if avisos:
        for a in avisos:
            flash(a, "aviso")
        return redirect(url_for("ver_carrito"))
    totales = store.calcular_totales(carrito)    # Calcular subtotal, impuestos y envío
    if not usuario_actual():                     # ¿Usuario autenticado? → No → Iniciar sesión
        flash("Inicia sesión para completar tu compra.", "aviso")
        return redirect(url_for("login", next=url_for("checkout")))
    return render_template("checkout.html", lineas=store.lineas_carrito(carrito), totales=totales)


@app.post("/pago")
@requiere_login
def pagar():
    cid = carrito_id()
    carrito = store.obtener_carrito(cid)
    if not carrito:
        return render_template("carrito_vacio.html")
    avisos = store.conciliar_stock(cid)
    if avisos:
        for a in avisos:
            flash(a, "aviso")
        return redirect(url_for("ver_carrito"))
    totales = store.calcular_totales(carrito)
    f = request.form
    numero = f.get("numero", "").replace(" ", "")
    aprobado, mensaje = store.procesar_pago(f.get("titular", ""), numero,     # Procesar pago
                                            f.get("vencimiento", ""), f.get("cvv", ""),
                                            totales["total"])
    if not aprobado:                             # ¿Pago aprobado? → No → error → Fin
        return render_template("pago_error.html", mensaje=mensaje, totales=totales), 402
    try:                                         # Descontar stock + generar orden y recibo
        orden = store.confirmar_compra(cid, usuario_actual()["usuario"], numero[-4:])
    except ValueError as e:
        store.conciliar_stock(cid)
        flash(f"{e} El pago fue revertido; revisa tu carrito.", "error")
        return redirect(url_for("ver_carrito"))
    flash("¡Pago aprobado! Tu orden fue generada.", "ok")
    return redirect(url_for("recibo", numero=orden["numero"]))


@app.get("/recibo/<numero>")
@requiere_login
def recibo(numero):
    orden = store.buscar_orden(numero)
    u = usuario_actual()
    if not orden or (orden["usuario"] != u["usuario"] and not u["admin"]):
        abort(404)
    return render_template("recibo.html", orden=orden)


@app.get("/ordenes")
@requiere_login
def ordenes():
    return render_template("ordenes.html", ordenes=store.ordenes_de(usuario_actual()["usuario"]))


# ---------------------------------------------------------------- usuarios
@app.route("/login", methods=["GET", "POST"])
def login():
    destino = destino_seguro(request.values.get("next"))
    if request.method == "POST":
        u = store.autenticar(request.form.get("usuario", ""), request.form.get("clave", ""))
        if u:
            session["usuario"] = u["usuario"]
            flash(f"Hola, {u['nombre']}.", "ok")
            return redirect(destino)
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html", next=destino)


@app.route("/registro", methods=["GET", "POST"])
def registro():
    destino = destino_seguro(request.values.get("next"))
    if request.method == "POST":
        f = request.form
        ok, mensaje = store.registrar_usuario(f.get("usuario", ""), f.get("nombre", ""),
                                              f.get("clave", ""), f.get("confirmar", ""))
        flash(mensaje, "ok" if ok else "error")
        if ok:
            session["usuario"] = f.get("usuario", "").strip().lower()
            return redirect(destino)
    return render_template("registro.html", next=destino)


@app.post("/logout")
def logout():
    session.pop("usuario", None)
    flash("Sesión cerrada.", "ok")
    return redirect(url_for("catalogo"))


# ---------------------------------------------------------------- admin
@app.route("/admin", methods=["GET", "POST"])
@requiere_login
def admin():
    if not usuario_actual()["admin"]:
        abort(403)
    if request.method == "POST":
        ok, mensaje = store.reponer_stock(request.form.get("pid", ""),
                                          entero(request.form.get("cantidad")))
        flash(mensaje, "ok" if ok else "error")
        return redirect(url_for("admin"))
    return render_template("admin.html", productos=list(store.CATALOGO.values()),
                           ordenes=list(reversed(store.ORDENES)))


# ---------------------------------------------------------------- PDF de flujos
@app.get("/flujos.pdf")
def flujos_pdf():
    if not RUTA_PDF.exists():
        from generar_flujos_pdf import generar
        generar(RUTA_PDF)
    return send_file(RUTA_PDF, mimetype="application/pdf")


@app.errorhandler(403)
@app.errorhandler(404)
def error_http(e):
    return render_template("error.html", codigo=e.code, mensaje=e.description), e.code


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
