# -*- coding: utf-8 -*-
"""
Corre EN LA NUBE (GitHub Actions, .github/workflows/panama.yml) dos veces al dia:
sincroniza las ventas de las 6 tiendas de Panama desde FollowUP y actualiza los
archivos cifrados del sitio, sin depender de ninguna PC.

Entradas (variables de entorno, secrets del repo):
  IX_CLAVE   clave del sitio (misma que escribe el usuario en la app)
  FUP_USER / FUP_PASS   cuenta de FollowUP (sportsfactory.fupbi.com)
  INCLUIR_HOY=1         guarda tambien el dia en curso (corrida de las 9 pm, provisional)

Archivos del repo que toca (todos cifrados AES-256-GCM, misma llave que los dashboards):
  ventas-panama.enc   historial de Panama {"stores":..., "days":{fecha:{tienda:[neto, uds]}}}
  ventas-macro.enc    datos de la app: se reemplazan solo las tiendas de Panama (country
                      "Panamá"); las de IX (GT/SV/RD) quedan como las dejo la PC.
Nada se escribe en claro. HOY se calcula en hora de Panama.
"""
import datetime, hashlib, json, os, re, secrets, sys
from zoneinfo import ZoneInfo
import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
BASE = "https://sportsfactory.fupbi.com"
STORES = {6: "NBA", 4: "NBD", 3: "NBM", 1: "NBP", 5: "RBA", 2: "RBP"}   # id FollowUP -> llave app
META = {"NBA": ("New Balance", "Albrook"), "NBD": ("New Balance", "Dorado Mall"),
        "NBM": ("New Balance", "Metro Mall"), "NBP": ("New Balance", "Multiplaza"),
        "RBA": ("Running Balboa", "Albrook"), "RBP": ("Running Balboa", "Multiplaza")}
AMOUNT, QTY = 11, 10          # columnas de /api/v1/daily_event_sale_facts.json
FUP_DESDE = datetime.date(2026, 9, 25)   # antes: historico de Jorge Peraza, no se toca
TZ = ZoneInfo("America/Panama")

# ------------------------------------------------------------------ cifrado
cfg = json.load(open(os.path.join(SITE, "crypt.json"), encoding="utf-8"))
clave = os.environ.get("IX_CLAVE") or sys.exit("falta IX_CLAVE")
aes = AESGCM(hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(cfg["salt"]), cfg["iter"], 32))
def dec(path): b = open(path, "rb").read(); return json.loads(aes.decrypt(b[:12], b[12:], None).decode("utf-8"))
def enc(path, obj):
    iv = secrets.token_bytes(12)
    open(path, "wb").write(iv + aes.encrypt(iv, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), None))

# ------------------------------------------------------------------ FollowUP
def fetch_followup(user, pw):
    s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0 (VentasIX)"
    r = s.get(BASE + "/users/sign_in", timeout=60)
    tok = re.search(r'name="authenticity_token" value="([^"]+)"', r.text)
    if not tok: raise SystemExit("FollowUP: no encontre el formulario de login")
    r = s.post(BASE + "/users/sign_in", timeout=60, data={"authenticity_token": tok.group(1),
               "user[login]": user, "user[password]": pw, "commit": "Ingresar"})
    if "sign_in" in r.url: raise SystemExit("FollowUP: login rechazado (clave vencida o cambiada?)")
    rows = s.get(BASE + "/api/v1/daily_event_sale_facts.json", timeout=120,
                 headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}).json()
    if not isinstance(rows, list) or not rows or len(rows[0]) < 12: raise SystemExit("FollowUP: respuesta inesperada")
    return rows

def main():
    incluir_hoy = os.environ.get("INCLUIR_HOY") == "1"
    hoy = datetime.datetime.now(TZ).date()
    hasta = hoy if incluir_hoy else hoy - datetime.timedelta(days=1)
    rows = fetch_followup(os.environ["FUP_USER"], os.environ["FUP_PASS"])
    por_dia = {}
    for r in rows:
        d = datetime.datetime.fromtimestamp(r[1], datetime.timezone.utc).date(); k = STORES.get(r[2])
        if not k or d < FUP_DESDE or d > hasta: continue
        por_dia.setdefault(d, {})[k] = [round(float(r[AMOUNT] or 0), 2), int(r[QTY] or 0)]

    # ---- historial cifrado de Panama
    pan_path = os.path.join(SITE, "ventas-panama.enc")
    pan = dec(pan_path)
    nuevos = cambiados = 0
    for d in sorted(por_dia):
        fila = {k: por_dia[d].get(k, [0.0, 0]) for k in STORES.values()}
        key = d.isoformat()
        if key not in pan["days"]: nuevos += 1
        elif pan["days"][key] != fila: cambiados += 1
        pan["days"][key] = fila
    if hasta < hoy and hoy.isoformat() in pan["days"]:
        del pan["days"][hoy.isoformat()]; print("quitado el dia en curso (provisional)")
    pan["days"] = dict(sorted(pan["days"].items()))
    enc(pan_path, pan)

    # ---- datos de la app: reemplazar solo las tiendas de Panama
    macro_path = os.path.join(SITE, "ventas-macro.enc")
    macro = dec(macro_path)
    macro["stores"] = [s for s in macro["stores"] if s.get("country") != "Panamá"]
    for sid, (brand, name) in META.items():
        days = {}
        for d, v in pan["days"].items():
            x = v.get(sid)
            if x is None: continue
            days[d] = [round(x[0], 2), x[1]] if isinstance(x, list) else [round(x, 2), None]
        if not days: continue
        ds = sorted(days)
        macro["stores"].append(dict(id=sid, brand=brand, country="Panamá", name=name, cov=[ds[0], ds[-1]], days=days))
    macro["gen"] = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    enc(macro_path, macro)

    ult = max(por_dia) if por_dia else None
    print("FollowUP: %d dias (%s a %s) | nuevos %d | cambiados %d | ultimo %s%s"
          % (len(por_dia), FUP_DESDE, hasta, nuevos, cambiados, ult, " (provisional)" if incluir_hoy else ""))
    if ult: print("  %s total 6 tiendas $%s" % (ult, format(sum(v[0] for v in pan["days"][ult.isoformat()].values()), ",.2f")))
    if ult and ult < hasta: print("  AVISO: FollowUP aun no tiene datos de %s" % hasta)

if __name__ == "__main__":
    main()
