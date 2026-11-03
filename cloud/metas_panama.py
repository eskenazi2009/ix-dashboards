# -*- coding: utf-8 -*-
"""
Acumulado del mes por tienda de Panama, para el tablero "Metas" (artifact de claude.ai).

    IX_CLAVE=... python3 cloud/metas_panama.py            -> JSON del mes en curso (hora Panama)
    IX_CLAVE=... python3 cloud/metas_panama.py 2026-10    -> JSON de ese mes

Lee ventas-panama.enc (misma fuente que la app Ventas) y suma la venta neta por tienda
desde el dia 1 hasta el ultimo dia con datos del mes. Imprime SOLO un JSON, por ejemplo:
  {"mes":"2026-10","hasta":"2026-10-05","dias":5,"dias_mes":31,
   "tiendas":{"NBP":22481.74,...},"total":91490.29,
   "detalle":{"NBP":{"venta":..,"uds":..,"tickets":..,"visitas":..,"vpt":..,"upt":..,"conv":..},...},
   "actualizado":"2026-10-06 23:50"}
"tiendas" (solo venta) lo usa el tablero de octubre; "detalle" (venta, UPT, VPT, conversion) el de noviembre en adelante.
La rutina de Claude pasa ese JSON tal cual a la base del artifact (ArtifactData).
"""
import calendar, datetime, hashlib, json, os, sys
from zoneinfo import ZoneInfo
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.dirname(HERE)
TZ = ZoneInfo("America/Panama")
TIENDAS = ["NBP", "RBP", "NBA", "RBA", "NBD", "NBM"]

cfg = json.load(open(os.path.join(SITE, "crypt.json"), encoding="utf-8"))
clave = os.environ.get("IX_CLAVE") or sys.exit("falta IX_CLAVE")
aes = AESGCM(hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(cfg["salt"]), cfg["iter"], 32))
b = open(os.path.join(SITE, "ventas-panama.enc"), "rb").read()
days = json.loads(aes.decrypt(b[:12], b[12:], None).decode("utf-8"))["days"]

hoy = datetime.datetime.now(TZ)
mes = sys.argv[1] if len(sys.argv) > 1 else hoy.strftime("%Y-%m")
tot = {k: 0.0 for k in TIENDAS}; fechas = []
det = {k: {"venta": 0.0, "uds": 0, "tickets": 0, "visitas": 0} for k in TIENDAS}
for d, v in days.items():
    if not d.startswith(mes): continue
    fechas.append(d)
    for k in TIENDAS:
        x = v.get(k)
        if x is None: continue
        if isinstance(x, list):
            tot[k] += x[0]; det[k]["venta"] += x[0]
            if len(x) > 1 and x[1] is not None: det[k]["uds"] += x[1]
            if len(x) > 2 and x[2] is not None: det[k]["tickets"] += x[2]
            if len(x) > 3 and x[3] is not None: det[k]["visitas"] += x[3]
        else:
            tot[k] += x; det[k]["venta"] += x
for k in TIENDAS:
    e = det[k]; e["venta"] = round(e["venta"], 2)
    # indicadores del mes: VPT (venta/ticket), UPT (unidades/ticket), conversion (tickets/visitas)
    e["vpt"] = round(e["venta"] / e["tickets"], 2) if e["tickets"] else None
    e["upt"] = round(e["uds"] / e["tickets"], 2) if e["tickets"] else None
    e["conv"] = round(e["tickets"] / e["visitas"], 4) if e["visitas"] else None
y, m = map(int, mes.split("-"))
out = {"mes": mes, "hasta": max(fechas) if fechas else None, "dias": len(fechas),
       "dias_mes": calendar.monthrange(y, m)[1],
       "tiendas": {k: round(v, 2) for k, v in tot.items()}, "total": round(sum(tot.values()), 2),
       "detalle": det,
       "actualizado": hoy.strftime("%Y-%m-%d %H:%M")}
print(json.dumps(out, ensure_ascii=False))
