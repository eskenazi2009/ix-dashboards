# -*- coding: utf-8 -*-
"""
Arma el sitio de los 3 dashboards de IX en pestanas, CIFRADOS con clave.

Por que cifrado y no un "if (clave == ...)" en JavaScript: el repo es publico y
GitHub Pages sirve archivos estaticos, asi que un candado de JS se salta viendo
el codigo fuente o entrando directo al .html del dashboard. Aqui los dashboards
se suben como .enc (AES-256-GCM); sin la clave son bytes inservibles. El
navegador deriva la llave con PBKDF2 y descifra en memoria.

    python publish.py            # regenera el sitio cifrado
    python publish.py --push     # ademas commit + push

OJO: en la carpeta del repo NUNCA debe quedar el .html en claro. Los .html
plano viven solo en sus carpetas de trabajo, fuera del repo, y .gitignore los
bloquea por si acaso.
"""
import datetime, json, os, re, secrets, shutil, subprocess, sys
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = os.path.dirname(os.path.abspath(__file__))
IX = os.path.dirname(HERE)

# La clave NUNCA va escrita aqui: este archivo se sube a un repo PUBLICO.
# Sale de la variable de entorno IX_CLAVE o de clave.txt (ignorado por git).
CLAVE = os.environ.get("IX_CLAVE") or (
    open(os.path.join(HERE, "clave.txt"), encoding="utf-8").read().strip()
    if os.path.exists(os.path.join(HERE, "clave.txt")) else "")
if not CLAVE:
    sys.exit("Falta la clave: pone IX_CLAVE en el entorno o crea clave.txt en esta carpeta.")
ITER = 310_000          # PBKDF2-SHA256

# (id, etiqueta, sublabel, archivo .enc, origen, etiqueta corta para la linea de fechas)
TABS = [
    ("ventas-rb", "Ventas", "Running Balboa GT", "ventas-rb-gt.enc",
     os.path.join(IX, "RB GT", "Ventas", "dashboard-ventas-RB-GT.html"), "Ventas RB GT"),
    ("inv-rb", "Inventario", "Running Balboa GT", "inventario-rb-gt.enc",
     os.path.join(IX, "RB GT", "Inventarios", "dashboard-inventario-RB-GT.html"), "Stock RB GT"),
    # Las dos tiendas NB van SEPARADAS: son paises distintos y no se pueden
    # hacer traspasos entre ellas, mezclarlas solo confunde.
    ("ventas-nb-sv", "Ventas", "New Balance El Salvador", "ventas-nb-sv.enc",
     os.path.join(IX, "NB Inv", "ventas", "dashboard-ventas-NB-SV.html"), "Ventas NB SV"),
    ("ventas-nb-rd", "Ventas", "New Balance Dominicana", "ventas-nb-rd.enc",
     os.path.join(IX, "NB Inv", "ventas", "dashboard-ventas-NB-RD.html"), "Ventas NB RD"),
    ("inv-nb", "Inventario", "New Balance · Bambú / Santiago", "inventario-nb.enc",
     os.path.join(IX, "NB Inv", "dashboard-inventario-NB.html"), "Inventario NB"),
]

# ------------------------------------------------- fecha de datos de cada uno
def fecha_datos(tab_id, html, src):
    """Hasta que fecha llegan los DATOS del dashboard (no cuando se corrio el
    script). Cada dashboard la escribe en un sitio distinto; si algun dia cambia
    el texto, se cae a la fecha de modificacion del archivo."""
    if tab_id.startswith("ventas-"):
        m = re.search(r'DMAX\s*=\s*"(\d{4})-(\d{2})-(\d{2})"', html)      # ultima venta
        if m: return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    if tab_id == "inv-rb":
        m = re.search(r"Foto de inventario al (\d{2}/\d{2}/\d{4})", html)  # fecha del corte
        if m: return m.group(1)
    if tab_id == "inv-nb":
        m = re.search(r"Datos:\s*(\d{2}/\d{2}/\d{4})", html)
        if m: return m.group(1)
    print(f"    AVISO: no encontre la fecha de datos en {os.path.basename(src)}, uso la del archivo")
    return datetime.date.fromtimestamp(os.path.getmtime(src)).strftime("%d/%m/%Y")

# ------------------------------------------------------------------- cifrado
# El salt se REUTILIZA entre publicaciones. Si se genera uno nuevo cada vez, la
# llave cambia y cualquier .enc que el navegador o el CDN tengan cacheado deja
# de descifrar (AES-GCM falla con mensaje vacio). Con el salt fijo, un .enc
# viejo en cache a lo sumo esta desactualizado, pero abre.
_cj = os.path.join(HERE, "crypt.json")
if os.path.exists(_cj):
    salt = bytes.fromhex(json.load(open(_cj, encoding="utf-8"))["salt"])
    print("  salt reutilizado de crypt.json")
else:
    salt = secrets.token_bytes(16)
    print("  salt nuevo (primera publicacion)")
key = hashlib.pbkdf2_hmac("sha256", CLAVE.encode(), salt, ITER, 32)
aes = AESGCM(key)

def cifrar(data: bytes) -> bytes:
    iv = secrets.token_bytes(12)
    return iv + aes.encrypt(iv, data, None)

fechas, faltan, total, vers = [], [], 0, {}
for tid, lbl, sub, dest, src, corto in TABS:
    if not os.path.exists(src):
        faltan.append(src); continue
    html = open(src, encoding="utf-8").read()
    f = fecha_datos(tid, html, src)
    fechas.append((corto, f))
    blob = cifrar(html.encode("utf-8"))
    open(os.path.join(HERE, dest), "wb").write(blob)
    # version por contenido: cuelga de la URL para que una publicacion nueva
    # nunca se sirva contra un .enc viejo en cache
    vers[tid] = hashlib.sha256(blob).hexdigest()[:10]
    total += len(blob)
    print(f"  {dest:<24} {len(blob)/1048576:>5.1f} MB cifrado   datos al {f}   <- {os.path.relpath(src, IX)}")
if faltan:
    print("\nFALTAN (no se cifraron):")
    for f in faltan: print("   ", f)

# ------------------------------------------ app movil: totales por dia cifrados
# build-ventas-macro.py (en IX) resume los mismos Ventas_*.xlsx en un JSON de
# unos KB; la app en app/ lo baja, lo descifra con la misma clave y muestra
# los totales por mes y por dia de las 3 tiendas.
# Panama: el historial vive CIFRADO en el repo (ventas-panama.enc) y lo actualiza
# GitHub Actions dos veces al dia desde FollowUP (cloud/sync_panama.py), sin
# depender de esta PC. Aqui solo se trae lo ultimo del repo, se descifra a
# IXentas-panama.json (fuera del repo) y build-ventas-macro.py lo usa.
if os.path.isdir(os.path.join(HERE, ".git")):
    r = subprocess.run(["git", "pull", "--rebase", "--autostash", "-q"], cwd=HERE, capture_output=True, text=True)
    print("  git pull:", "ok" if r.returncode == 0 else "FALLO " + (r.stderr or r.stdout).strip()[-300:])
_pan_enc = os.path.join(HERE, "ventas-panama.enc")
_pan_js = os.path.join(IX, "ventas-panama.json")
if os.path.exists(_pan_enc):
    _b = open(_pan_enc, "rb").read()
    open(_pan_js, "w", encoding="utf-8").write(aes.decrypt(_b[:12], _b[12:], None).decode("utf-8"))
    print("  ventas-panama.json       tomado del repo (cifrado)")
elif os.path.exists(_pan_js):
    open(_pan_enc, "wb").write(cifrar(open(_pan_js, "rb").read()))
    print("  ventas-panama.enc        creado desde el json local (primera vez)")

_macro_py = os.path.join(IX, "build-ventas-macro.py")
_macro_js = os.path.join(IX, "ventas-macro.json")
if os.path.exists(_macro_py):
    r = subprocess.run([sys.executable, _macro_py], capture_output=True, text=True)
    if r.returncode != 0:
        print("  AVISO build-ventas-macro.py fallo: " + (r.stderr or r.stdout)[-800:])
# IX (GT/SV/RD): el historial tambien vive cifrado en el repo (ventas-ix.enc) y lo
# alimenta la rutina de Claude en la nube (cloud/sync_ix.py) cada manana (8 am). Aqui se
# MEZCLA: los dias que esta PC tiene en sus Excel mandan; los que no, se toman de
# la nube. Y se re-escribe ventas-ix.enc con la union, para que la nube tampoco
# pierda lo que bajo la PC.
_ix_enc = os.path.join(HERE, "ventas-ix.enc")
if os.path.exists(_macro_js):
    macro = json.load(open(_macro_js, encoding="utf-8"))
    ix = {"days": {}, "cov": {}}
    if os.path.exists(_ix_enc):
        _b = open(_ix_enc, "rb").read()
        ix = json.loads(aes.decrypt(_b[:12], _b[12:], None).decode("utf-8"))
    for st in macro["stores"]:
        cid = st["id"]
        if cid not in ("GT", "SV", "RD"): continue
        nube = {d: v[cid] for d, v in ix["days"].items() if cid in v}
        union = dict(nube); union.update(st["days"])          # PC manda donde hay ambos
        st["days"] = dict(sorted(union.items()))
        c = ix["cov"].get(cid)
        st["cov"] = [min(st["cov"][0], c[0]), max(st["cov"][1], c[1])] if c else st["cov"]
        for d, v in st["days"].items(): ix["days"].setdefault(d, {})[cid] = v
        ix["cov"][cid] = list(st["cov"])
        print(f"  IX {cid}: {len(st['days'])} dias (PC + nube), cobertura {st['cov'][0]} a {st['cov'][1]}")
    ix["days"] = dict(sorted(ix["days"].items()))
    open(_ix_enc, "wb").write(cifrar(json.dumps(ix, ensure_ascii=False, separators=(",", ":")).encode("utf-8")))
    json.dump(macro, open(_macro_js, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    blob = cifrar(open(_macro_js, "rb").read())
    open(os.path.join(HERE, "ventas-macro.enc"), "wb").write(blob)
    print(f"  {'ventas-macro.enc':<24} {len(blob)/1024:>5.1f} KB cifrado   (app movil)")
else:
    print("  AVISO: no hay ventas-macro.json, la app movil no se actualiza")

# sonda: permite validar la clave sin bajar 4 MB primero
open(os.path.join(HERE, "crypt.json"), "w", encoding="utf-8").write(json.dumps({
    "salt": salt.hex(), "iter": ITER,
    "check": cifrar(b"ix-dashboards-ok").hex(),
}, separators=(",", ":")))

# --------------------------------------------------------------------- index
btns = "\n".join(
    '    <button class="tab" data-tab="%s" role="tab" aria-selected="false">'
    '<span class="t-lbl">%s</span><span class="t-sub">%s</span></button>' % (tid, lbl, sub)
    for tid, lbl, sub, _d, _s, _c in TABS)
frames = "\n".join(
    '    <iframe id="f%s" data-enc="%s?v=%s" title="%s — %s"></iframe>'
    % (tid, dest, vers.get(tid, "0"), lbl, sub)
    for tid, lbl, sub, dest, _s, _c in TABS)
linea = " &nbsp;·&nbsp; ".join('<b>%s</b> %s' % (c, f) for c, f in fechas)

HTML = open(os.path.join(HERE, "_index_tpl.html"), encoding="utf-8").read()

# barrer cualquier dashboard en claro que haya quedado de una version anterior
# (index.html y la plantilla se quedan, obviamente)
for _f in os.listdir(HERE):
    if _f.endswith(".html") and _f not in ("index.html", "_index_tpl.html"):
        os.remove(os.path.join(HERE, _f)); print(f"  borrado plano: {_f}")

HTML = (HTML.replace("__TABS__", btns).replace("__FRAMES__", frames)
            .replace("__FECHAS__", linea).replace("__FIRST__", TABS[0][0])
            .replace("__IDS__", json.dumps([t[0] for t in TABS]))
            .replace("__HOY__", datetime.date.today().strftime("%d/%m/%Y")))
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(HTML)

print(f"\n  index.html               {os.path.getsize(os.path.join(HERE,'index.html'))/1024:>5.1f} KB")
print(f"  total cifrado            {total/1048576:>5.1f} MB")
print("  fechas de datos:        ", " | ".join(f"{c} {f}" for c, f in fechas))

# ---------------------------------------------------------------------- push
if "--push" in sys.argv:
    if not os.path.isdir(os.path.join(HERE, ".git")):
        sys.exit("\nNo hay repo git en esta carpeta.")
    subprocess.run(["git", "add", "-A"], cwd=HERE, check=True)
    r = subprocess.run(["git", "commit", "-m",
                        "Actualiza dashboards " + datetime.date.today().strftime("%Y-%m-%d")], cwd=HERE)
    if r.returncode == 0:
        subprocess.run(["git", "push"], cwd=HERE, check=True)
        print("\nPush listo.")
    else:
        print("\nNada que commitear.")
