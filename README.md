# InLine Orders — Tienda en línea (Flask)

Aplicación web en Python que implementa el diagrama de flujo de compra:
catálogo → validación de stock → carrito → totales → autenticación → pago → descuento de stock → orden y recibo.

- Catálogo en `data/catalogo.json`, cargado **en memoria** al arrancar (el archivo no se modifica).
- Carritos, usuarios y órdenes viven en memoria: se pierden al reiniciar.
- Diagramas de todos los flujos en `docs/flujos.pdf` (también en `/flujos.pdf` dentro de la app).

## Ejecutar

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python generar_flujos_pdf.py   # (re)genera docs/flujos.pdf
.venv/bin/python app.py                  # http://127.0.0.1:5000
```

## Datos de prueba

| Qué | Valor |
|---|---|
| Usuario | `demo` / `demo123` |
| Administrador | `admin` / `admin123` |
| Tarjeta aprobada | `4242 4242 4242 4242`, fecha futura, CVV `123` |
| Tarjeta rechazada | `4000 0000 0000 0002` |

Impuesto: IVU 11.5 %. Envío $5.99, gratis desde $50.

## Flujos

| # | Flujo | Rutas |
|---|---|---|
| — | Principal: proceso de compra | `/`, `/carrito/agregar`, `/carrito/agregado`, `/checkout`, `/pago`, `/recibo/<n>` |
| 1 | Arranque y carga del catálogo | `store.inicializar()` |
| 2 | Búsqueda y filtro por categoría | `/?q=&cat=` |
| 3 | Gestión del carrito | `/carrito`, `/carrito/actualizar`, `/carrito/eliminar`, `/carrito/vaciar` |
| 4 | Inicio y cierre de sesión | `/login`, `/logout` |
| 5 | Registro de usuario | `/registro` |
| 6 | Validación del pago (simulada) | `store.procesar_pago()` |
| 7 | Conflicto de stock al pagar | `store.conciliar_stock()`, `store.confirmar_compra()` |
| 8 | Historial de órdenes y recibo | `/ordenes`, `/recibo/<n>` |
| 9 | Reposición de stock (admin) | `/admin` |
