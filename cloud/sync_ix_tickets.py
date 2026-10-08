# -*- coding: utf-8 -*-
"""
Tickets de las 3 tiendas IX (RB Guatemala, NB El Salvador, NB Dominicana) desde
FollowUP (ixcomercio.fupbi.com), para calcular VPT y UPT igual que en Panama.
Corre EN LA NUBE (GitHub Actions, .github/workflows/ix.yml) despues de procesar el
inbox del portal TotalCommerce. Tambien sirve a mano.

Entradas (variables de entorno, secrets del repo):
  IX_CLAVE                 clave del sitio (misma que escribe el usuario en la app)
  FUPIX_USER / FUPIX_PASS  cuenta de FollowUP de IX (ixcomercio.fupbi.com)
  FUPIX_STORES             opcional, mapeo manual "id:GT,id:SV,id:RD" si los nombres
                           de las tiendas en FollowUP no dicen el pais

La venta neta y las unidades siguen saliendo del portal TotalCommerce (sync_ix.py);
de FollowUP solo se toma la CANTIDAD DE TICKETS por dia y tienda. Se guarda en
ventas-ix.enc bajo "tickets" {fecha: {GT: n, SV: n, RD: n}}, separado de "days",
para que la mezcla PC+nube de publish.py no lo pise. Luego se re-arman las tiendas
IX de ventas-macro.enc como [neto, uds, tickets].
"""
import datetime, os, re, sys
from zoneinfo import ZoneInfo
import requests

HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import sync_ix

BASE = "https://ixcomercio.fupbi.com"
# palabras en el nombre de la tienda (FollowUP) -> cuenta de la app
PALABRAS = {"GT": ("guatemala", "running"), "SV": ("salvador",), "RD": ("domini",)}
TICKETS, QTY, AMOUNT = 9, 10, 11      # columnas de /api/v1/daily_event_sale_facts.json
FUP_DESDE = datetime.date(2026, 1, 1)
TZ = ZoneInfo("America/Panama")

def login(user, pw):
    s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0 (VentasIX)"
    r = s.get(BASE + "/users/sign_in", timeout=60)
    tok = re.search(r'name="authenticity_token" value="([^"]+)"', r.text)
    if not tok: raise SystemExit("FollowUP IX: no encontre el formulario de login")
    r = s.post(BASE + "/users/sign_in", timeout=60, data={"authenticity_token": tok.group(1),
               "user[login]": user, "user[password]": pw, "commit": "Ingresar"})
    if "sign_in" in r.url: raise SystemExit("FollowUP IX: login rechazado (clave vencida o cambiada?)")
    return s

def api(s, path):
    return s.get(BASE + path, timeout=120, headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}).json()

def mapear_tiendas(s):
    """id de tienda en FollowUP -> GT/SV/RD. Manual (FUPIX_STORES) o por el nombre."""
    manual = os.environ.get("FUPIX_STORES", "").strip()
    if manual:
        return {int(a): b.strip().upper() for a, b in (p.split(":") for p in manual.split(","))}
    j = api(s, "/api/v1/stores")
    stores = j.get("stores", j) if isinstance(j, dict) else j
    m = {}
    for st in stores:
        nombre = str(st.get("name") or st.get("short_name") or "").lower()
        cid = next((c for c, pal in PALABRAS.items() if any(p in nombre for p in pal)), None)
        print("  tienda FollowUP %s %r -> %s" % (st.get("id"), st.get("name"), cid or "SIN MAPEO"))
        if cid: m[int(st["id"])] = cid
    if not m: raise SystemExit("FollowUP IX: ninguna tienda reconocida; usar FUPIX_STORES=id:GT,id:SV,id:RD")
    return m

def main():
    user, pw = os.environ.get("FUPIX_USER"), os.environ.get("FUPIX_PASS")
    if not user or not pw: print("sin FUPIX_USER/FUPIX_PASS: no se bajan tickets de IX"); return
    hoy = datetime.datetime.now(TZ).date(); hasta = hoy - datetime.timedelta(days=1)
    s = login(user, pw)
    tiendas = mapear_tiendas(s)
    rows = api(s, "/api/v1/daily_event_sale_facts.json")
    if not isinstance(rows, list) or not rows or len(rows[0]) < 12: raise SystemExit("FollowUP IX: respuesta inesperada")
    tk, venta = {}, {}
    for r in rows:
        d = datetime.datetime.fromtimestamp(r[1], datetime.timezone.utc).date(); cid = tiendas.get(r[2])
        if not cid or d < FUP_DESDE or d > hasta: continue
        k = d.isoformat()
        tk.setdefault(k, {}); tk[k][cid] = tk[k].get(cid, 0) + int(r[TICKETS] or 0)
        venta.setdefault(k, {}); venta[k][cid] = venta[k].get(cid, 0.0) + float(r[AMOUNT] or 0)
    if not tk: raise SystemExit("FollowUP IX: sin filas de venta en el rango")

    aes = sync_ix._aes(); ix_path = os.path.join(SITE, "ventas-ix.enc")
    ix = sync_ix.dec(aes, ix_path)
    prev = ix.get("tickets", {}); nuevos = cambiados = 0
    for k, v in tk.items():
        fila = dict(prev.get(k, {})); fila.update(v)
        if k not in prev: nuevos += 1
        elif prev[k] != fila: cambiados += 1
        prev[k] = fila
    ix["tickets"] = dict(sorted(prev.items()))
    sync_ix.enc(aes, ix_path, ix)
    sync_ix.publicar_macro(aes, ix)

    ult = max(tk)
    print("FollowUP IX: %d dias (%s a %s) | nuevos %d | cambiados %d | ultimo %s" % (len(tk), min(tk), hasta, nuevos, cambiados, ult))
    port = ix["days"].get(ult, {})
    for cid in ("GT", "SV", "RD"):
        n = tk[ult].get(cid); neto = (port.get(cid) or [None])[0]
        print("  %s %s: %s tickets | FollowUP $%s | portal $%s" % (ult, cid, n, format(venta[ult].get(cid, 0), ",.2f"),
              format(neto, ",.2f") if neto is not None else "-"))
    if ult < hasta.isoformat(): print("  AVISO: FollowUP aun no tiene datos de %s" % hasta)

if __name__ == "__main__":
    main()
