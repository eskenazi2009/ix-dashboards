# -*- coding: utf-8 -*-
"""
GitHub Actions: abre cada sobre de inbox/*.enc (enlaces .xlsx que dejo la rutina
de Claude), baja los exports, actualiza ventas-ix.enc y ventas-macro.enc y borra
el sobre. Requiere INBOX_PRIV (llave privada del buzon) e IX_CLAVE (clave del sitio).
"""
import glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import inbox, sync_ix

# rango que Actions le pidio al portal (inbox/pedido.json); manda sobre el que traiga el sobre
_ped = os.path.join(SITE, "inbox", "pedido.json")
PEDIDO = None
if os.path.exists(_ped):
    import json; _j = json.load(open(_ped)); PEDIDO = (_j["desde"], _j["hasta"]); print("rango pedido:", PEDIDO)
sobres = sorted(glob.glob(os.path.join(SITE, "inbox", "*.enc")))
if not sobres:
    print("inbox vacio"); sys.exit(0)
for p in sobres:
    try:
        d = inbox.abrir(p)
    except Exception as e:
        print("no pude abrir", os.path.basename(p), ":", e); continue
    print("sobre", os.path.basename(p), "|", len(d["urls"]), "enlaces | rango", d.get("rango"))
    ok = True
    try:
        sync_ix.cargar(d["urls"], PEDIDO or (tuple(d["rango"]) if d.get("rango") else None))
    except Exception as e:
        ok = False; print("  ERROR cargando:", e)
    if ok: os.remove(p); print("  sobre procesado y borrado")
