# Dashboards IX

Tres dashboards de inventario y ventas en un solo sitio con pestañas, **cifrados**.

👉 https://eskenazi2009.github.io/ix-dashboards/ — pide clave al entrar.

| Pestaña | Qué muestra |
|---|---|
| **Ventas · Running Balboa GT** | Ventas por marca, categoría, canal (Físico/Ecom) y modelo. Detalle Marca › Modelo › Referencia › Talla, con filtro de rango de fechas. |
| **Inventario · Running Balboa GT** | Inventario cruzado contra ventas: cobertura, sobrestock, sin venta y agotados. Detalle con tallas y descarga a Excel. |
| **Inventario · New Balance** | Inventario de Bambú Salvador / Santiago RD. |

La cabecera muestra hasta qué fecha llegan los datos de cada uno, por separado.

## App móvil (Android)

👉 https://eskenazi2009.github.io/ix-dashboards/app/ — misma clave.

Muestra **solo el total de ventas** (neto USD) de las 3 tiendas por mes, y al tocar un mes,
por día. Es una PWA: en Chrome de Android, menú ⋮ → **"Agregar a pantalla de inicio"** /
**"Instalar app"** y queda como una app más, con ícono. Guarda la clave y la última copia
de los datos en el teléfono, así abre al instante y también sin señal.

Los datos salen de `ventas-macro.enc` (≈18 KB): `publish.py` corre `../build-ventas-macro.py`,
que resume los mismos `Ventas_*.xlsx` de los dashboards en totales por día y tienda, y lo cifra
con la misma clave. Se actualiza solo cada vez que corre `descargar-inventarios-ix.ps1`.

## Sobre el cifrado

Este repo es público, así que los dashboards **no** se suben en claro: van como `.enc`
(**AES-256-GCM**). La llave se deriva de la clave con **PBKDF2-SHA256, 310.000 iteraciones**,
usando el salt de `crypt.json`. El navegador descifra en memoria con WebCrypto y monta el
resultado en un iframe; sin la clave los `.enc` son bytes inservibles.

Un candado hecho con `if (clave === "...")` en JavaScript no habría servido de nada: se ve en
el código fuente y además cualquiera podría entrar directo al `.html` del dashboard.

**La clave no está en este repo** y no debe estarlo. `publish.py` la toma de la variable de
entorno `IX_CLAVE` o de `clave.txt`, que está en `.gitignore`.

### Lo que esto sí y no protege

- ✅ Nadie ve los datos entrando al sitio o clonando el repo sin la clave.
- ⚠️ La clave es corta. Quien se baje los `.enc` puede intentar romperla por fuerza bruta
  offline. Las 310.000 iteraciones lo encarecen, pero no lo hacen imposible.
- ⚠️ Quien tenga la clave puede pasarla a quien quiera. No hay usuarios ni permisos.

## Cómo se actualiza

Reconstruí el dashboard que haya cambiado en su carpeta de trabajo y después:

```bash
python publish.py --push
```

`publish.py` cifra los tres HTML, lee de cada uno hasta qué fecha llegan sus datos,
regenera `index.html` y hace commit + push. Sin `--push` solo actualiza local.

## Estructura

```
index.html              puerta + pestañas (generado)
_index_tpl.html         plantilla de index.html
*.enc                   dashboards cifrados (+ ventas-macro.enc, datos de la app)
app/                    app móvil (PWA): index.html, manifest, sw.js, íconos
crypt.json              salt, iteraciones y sonda para validar la clave
publish.py              cifra, calcula fechas y regenera el index
clave.txt               la clave (NO se versiona)
```
