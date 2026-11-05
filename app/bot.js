// Asistente de ventas: entiende preguntas en español por patrones y calcula la respuesta
// sobre los datos que la app ya descifró (variable global DATA). Todo corre en el teléfono,
// sin internet ni servicios externos. Nunca inventa números: si no entiende, lo dice.
(function(){
"use strict";
var $=function(id){return document.getElementById(id);};
var MESES=["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
var MABR=["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
var DIAS=["dom","lun","mar","mié","jue","vie","sáb"];
var MESRX="(enero|ene|febrero|feb|marzo|mar|abril|abr|mayo|may|junio|jun|julio|jul|agosto|ago|septiembre|setiembre|sept|sep|octubre|oct|noviembre|nov|diciembre|dic)";

// ------------------------------------------------------------- utilidades
function norm(s){return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/[¿?¡!.,;:()]/g," ").replace(/\s+/g," ").trim();}
function esc(s){return s.replace(/[&<>]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
function pad(n){return String(n).padStart(2,"0");}
function iso(d){return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());}
function fromIso(s){var p=s.split("-");return new Date(+p[0],+p[1]-1,+p[2]);}
function addDays(d,n){var x=new Date(d);x.setDate(x.getDate()+n);return x;}
function dim(y,m){return new Date(y,m,0).getDate();}   // m 1-12
function usd(n){return "$"+Math.round(n).toLocaleString("en-US");}
function usd2(n){return "$"+n.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});}
function num(n){return Math.round(n).toLocaleString("en-US");}
function dif(a,b){ if(!b) return ""; var p=(a-b)/b*100; return '<span class="'+(p>=0?"up":"dn")+'">'+(p>=0?"+":"")+p.toFixed(1)+"%</span>"; }
function mesIdx(w){ var i=MESES.indexOf(w); if(i<0) i=MABR.indexOf(w.slice(0,3)); if(w==="setiembre"||w==="sept") i=8; return i; }
function fdia(s){ var d=fromIso(s); return DIAS[d.getDay()]+" "+d.getDate()+" "+MABR[d.getMonth()]; }
function hoy(){ var d=new Date(); d.setHours(0,0,0,0); return d; }

// ------------------------------------------------------------- tiendas
function tiendas(){
  var m={}; DATA.stores.forEach(function(s){ m[s.id]={id:s.id, s:s, nombre:(s.brand==="New Balance"?"NB ":"RB ")+(s.name||s.country), nb:s.brand==="New Balance", pty:s.country==="Panamá"}; });
  return m;
}
// [regex, ids(fn), etiqueta]. Las más específicas primero; lo que casa se borra de la pregunta.
function reglasTienda(T){
  var ids=Object.keys(T), has=function(id){return ids.indexOf(id)>=0;};
  var R=[
    [/\b(nb|new balance) (multiplaza|mp)\b/, ["NBP"], null],
    [/\b(rb|running( balboa)?) (multiplaza|mp)\b/, ["RBP"], null],
    [/\b(nb|new balance) albrook\b/, ["NBA"], null],
    [/\b(rb|running( balboa)?) albrook\b/, ["RBA"], null],
    [/\b((nb|new balance) )?(dorado mall|dorado)\b/, ["NBD"], null],
    [/\b((nb|new balance) )?(metro mall|metromall|metro)\b/, ["NBM"], null],
    [/\b(multiplaza|mp)\b/, ["NBP","RBP"], "Multiplaza"],
    [/\balbrook\b/, ["NBA","RBA"], "Albrook"],
    [/\b(rb |running( balboa)? )?(guatemala|guate|gt)\b/, ["GT"], null],
    [/\b(nb |new balance )?(el salvador|salvador|sv)\b/, ["SV"], null],
    [/\b(nb |new balance )?(republica dominicana|dominicana|santo domingo|rd)\b/, ["RD"], null],
    [/\b(panama|pty|las de panama)\b/, ids.filter(function(i){return T[i].pty;}), "Panamá"],
    [/\b(ix|centroamerica|las de ix)\b/, ids.filter(function(i){return !T[i].pty;}), "IX"],
    [/\b(new balance|nb)\b/, ids.filter(function(i){return T[i].nb;}), "New Balance"],
    [/\b(running balboa|running|rb)\b/, ids.filter(function(i){return !T[i].nb;}), "Running Balboa"],
    [/\b(todas( las tiendas)?|todo|general|las 9|las nueve)\b/, ids, "Todas"]
  ];
  return R.map(function(r){ var f=r[1].filter(has); return {rx:r[0], ids:f, label:r[2]}; }).filter(function(r){return r.ids.length;});
}
function parseTiendas(q, T){
  var grupos=[], R=reglasTienda(T);
  R.forEach(function(r){
    var m;
    while((m=q.match(r.rx))){
      q=q.replace(r.rx," ");
      var label=r.label||(r.ids.length===1?T[r.ids[0]].nombre:r.ids.map(function(i){return T[i].nombre;}).join(" + "));
      if(!grupos.some(function(g){return g.ids.join()===r.ids.join();})) grupos.push({ids:r.ids, label:label});
    }
  });
  return {q:q, grupos:grupos};
}

// ------------------------------------------------------------- períodos
// -> {q, periodos:[{from,to,kind,label}]} (máximo dos, en el orden en que aparecen)
function parsePeriodos(q){
  var H=hoy(), found=[];
  function add(idx, from, to, kind, label){ found.push({i:idx, from:iso(from), to:iso(to), kind:kind, label:label}); }
  function anioMes(mi, y){ // año para un mes nombrado sin año: el más reciente que no sea futuro
    if(y) return y; var Y=H.getFullYear(); return mi>H.getMonth()?Y-1:Y;
  }
  var rules=[
    // "del 1 al 15 de octubre" / "del 1 al 15"
    [new RegExp("\\bdel (\\d{1,2}) al (\\d{1,2})( de "+MESRX+"( de (\\d{4}))?)?\\b"), function(m,i){
      var mi=m[4]?mesIdx(m[4]):H.getMonth(), y=m[4]?anioMes(mi,m[6]&&+m[6]):H.getFullYear();
      add(i,new Date(y,mi,+m[1]),new Date(y,mi,+m[2]),"rango",null); }],
    // "4 de noviembre (de 2026)"
    [new RegExp("\\b(\\d{1,2}) de "+MESRX+"( de (\\d{4}))?\\b"), function(m,i){
      var mi=mesIdx(m[2]), y=anioMes(mi,m[4]&&+m[4]), d=new Date(y,mi,+m[1]); add(i,d,d,"dia",null); }],
    // "4/11" o "04/11/2026"
    [/\b(\d{1,2})\/(\d{1,2})(\/(\d{2,4}))?\b/, function(m,i){
      var y=m[4]?(+m[4]<100?2000+ +m[4]:+m[4]):anioMes(+m[2]-1,null), d=new Date(y,+m[2]-1,+m[1]); add(i,d,d,"dia",null); }],
    // mes nombrado: "octubre", "oct 2026", "octubre de 2025"
    [new RegExp("\\b"+MESRX+"( de)?( (\\d{4}))?\\b"), function(m,i){
      var mi=mesIdx(m[1]), y=anioMes(mi,m[4]&&+m[4]); add(i,new Date(y,mi,1),new Date(y,mi,dim(y,mi+1)),"mes",null); }],
    [/\b(hoy)\b/, function(m,i){ add(i,H,H,"dia",null); }],
    [/\b(ayer)\b/, function(m,i){ var d=addDays(H,-1); add(i,d,d,"dia",null); }],
    [/\b(antier|anteayer|antes de ayer)\b/, function(m,i){ var d=addDays(H,-2); add(i,d,d,"dia",null); }],
    [/\b(ultimo dia|ultimo dia con datos)\b/, function(m,i){ var d=fromIso(ultimoDia()); add(i,d,d,"dia",null); }],
    [/\b(semana pasada|semana anterior)\b/, function(m,i){ var l=lunes(H); add(i,addDays(l,-7),addDays(l,-1),"rango",null); }],
    [/\b(esta semana|la semana|semana actual|semana en curso|semana)\b/, function(m,i){ add(i,lunes(H),H,"rango",null); }],
    [/\b(mes pasado|mes anterior)\b/, function(m,i){ var y=H.getFullYear(), mi=H.getMonth()-1; if(mi<0){mi=11;y--;} add(i,new Date(y,mi,1),new Date(y,mi,dim(y,mi+1)),"mes",null); }],
    [/\b(este mes|el mes|mes actual|mes en curso|del mes|en el mes|a la fecha|mtd|mes)\b/, function(m,i){ add(i,new Date(H.getFullYear(),H.getMonth(),1),H,"mes",null); }],
    [/\b(ano pasado|ano anterior)\b/, function(m,i){ var y=H.getFullYear()-1; add(i,new Date(y,0,1),new Date(y,11,31),"anio",null); }],
    [/\b(este ano|el ano|ano|ytd|en lo que va del ano)\b/, function(m,i){ add(i,new Date(H.getFullYear(),0,1),H,"anio",null); }],
    [/\b(20\d\d)\b/, function(m,i){ var y=+m[1]; add(i,new Date(y,0,1),new Date(y,11,31),"anio",null); }]
  ];
  rules.forEach(function(r){
    var m;
    while((m=q.match(r[0]))){ r[1](m, m.index); q=q.slice(0,m.index)+" "+q.slice(m.index+m[0].length); }
  });
  found.sort(function(a,b){return a.i-b.i;});
  return {q:q, periodos:found.slice(0,2)};
}
function lunes(d){ var x=new Date(d); var w=(x.getDay()+6)%7; x.setDate(x.getDate()-w); return x; }
function ultimoDia(){ var u=null; DATA.stores.forEach(function(s){ if(!u||s.cov[1]>u) u=s.cov[1]; }); return u; }

// ------------------------------------------------------------- agregación
function agg(ids, from, to){
  var T=tiendas(), r={net:0,u:0,t:0,tn:0,tu:0,hasU:false,hasT:false,min:null,max:null,by:{},byDay:{}};
  ids.forEach(function(id){
    var s=T[id]&&T[id].s; if(!s) return;
    var b=r.by[id]={net:0,u:0,t:0,tn:0,tu:0,hasT:false,ndays:0};
    Object.keys(s.days).forEach(function(d){
      if(d<from||d>to) return; var v=s.days[d];
      b.net+=v[0]; r.net+=v[0]; b.ndays++;
      if(v[1]!=null){ r.u+=v[1]; b.u+=v[1]; r.hasU=true; }
      if(v[2]!=null){ r.t+=v[2]; b.t+=v[2]; r.hasT=b.hasT=true; r.tn+=v[0]; b.tn+=v[0]; r.tu+=(v[1]||0); b.tu+=(v[1]||0); }
      var dd=r.byDay[d]||(r.byDay[d]={net:0,u:0,t:0,tn:0,tu:0}); dd.net+=v[0]; dd.u+=(v[1]||0);
      if(v[2]!=null){ dd.t+=v[2]; dd.tn+=v[0]; dd.tu+=(v[1]||0); }
      if(!r.min||d<r.min) r.min=d; if(!r.max||d>r.max) r.max=d;
    });
  });
  r.ndays=Object.keys(r.byDay).length;
  return r;
}
var METR={net:"Venta",t:"Tickets",u:"Unidades",vpt:"VPT",upt:"UPT"};
function mval(a,m){ if(m==="t") return a.t; if(m==="u") return a.u; if(m==="vpt") return a.t?a.tn/a.t:null; if(m==="upt") return a.t?a.tu/a.t:null; return a.net; }
function mfmt(v,m){ if(v==null) return "–"; if(m==="t"||m==="u") return num(v); if(m==="vpt") return usd2(v); if(m==="upt") return v.toFixed(2); return usd(v); }
function resumen(a){ // "$X · N tickets · VPT $Y · UPT Z"
  var s=usd(a.net);
  if(a.hasT&&a.t) s+=" · "+num(a.t)+" tickets · VPT "+usd2(a.tn/a.t)+" · UPT "+(a.tu/a.t).toFixed(2);
  else if(a.hasU&&a.u) s+=" · "+num(a.u)+" uds";
  return s;
}
function etiqueta(p, a){ // etiqueta del período según los días con datos
  if(!a.ndays) return p.label||rangoTxt(p.from,p.to);
  if(a.min===a.max) return fdia(a.min);
  var f=fromIso(a.min), t=fromIso(a.max);
  if(p.kind==="mes"&&a.min.slice(8)==="01"&&a.max===p.to) return MESES[f.getMonth()]+" "+f.getFullYear();
  if(p.kind==="anio"&&a.max===p.to) return "año "+f.getFullYear();
  return rangoTxt(a.min,a.max);
}
function rangoTxt(a,b){
  var f=fromIso(a), t=fromIso(b);
  if(a===b) return fdia(a);
  if(f.getMonth()===t.getMonth()&&f.getFullYear()===t.getFullYear()) return f.getDate()+" al "+t.getDate()+" "+MABR[f.getMonth()];
  return f.getDate()+" "+MABR[f.getMonth()]+" al "+t.getDate()+" "+MABR[t.getMonth()];
}

// ------------------------------------------------------------- intérprete
function responder(texto){
  if(!window.DATA) return "Todavía no hay datos cargados.";
  var T=tiendas(), q=norm(texto);
  if(/^(hola|buenas|buenos dias|buenas tardes|hey|que tal)\b/.test(q)) return "Hola. Pregúntame por ventas, tickets, VPT o UPT de cualquier tienda, por día o por mes."+ejemplos();
  if(/\b(ayuda|que puedes|que sabes|como funciona|opciones)\b/.test(q)) return ayuda();

  var metrica = /\b(vpt|valor por ticket|ticket promedio|venta por ticket)\b/.test(q)?"vpt"
    : /\b(upt|unidades por ticket|articulos por ticket|piezas por ticket|pares por ticket)\b/.test(q)?"upt"
    : /\b(tickets?|transacciones|clientes|facturas)\b/.test(q)?"t"
    : /\b(unidades|uds|piezas|pares|articulos)\b/.test(q)?"u":"net";
  var comparar=/\b(vs|versus|contra|compar\w*)\b/.test(q);
  var mejorDia=q.match(/\b(mejor|peor|mas alto|mas bajo|mayor|menor|mas fuerte|mas flojo) dia\b|\bdia (mas|menos) (alto|bajo|fuerte|flojo|vendido)\b|\bdia (mas|mejor|peor) vendido\b/);
  var desglose=/\b(dia por dia|diario|por dia|desglose|detalle|detallado|cada dia|por dias|los dias)\b/.test(q) && !/\bpromedio\b/.test(q);
  var promedio=/\bpromedio\b/.test(q);
  var peor=/\b(peor|menos|mas bajo|menor|mas flojo)\b/.test(q);
  var ranking=/\b(quien|cual|cuales|que tienda|ranking|mejor tienda|peor tienda|por tienda|mas vendio|menos vendio|mejor|peor|top)\b/.test(q) && !mejorDia;

  var pt=parseTiendas(q,T); q=pt.q;
  var pp=parsePeriodos(q); q=pp.q;
  var grupos=pt.grupos.length?pt.grupos:[{ids:Object.keys(T), label:"Todas las tiendas"}];
  var H=hoy();
  var per=pp.periodos.length?pp.periodos:[{from:iso(new Date(H.getFullYear(),H.getMonth(),1)), to:iso(H), kind:"mes"}];

  // nada reconocible en la pregunta -> no inventar
  var resto=q.replace(/\b(cuanto|cuanta|cuantos|cuantas|vendio|vendimos|vendieron|venta|ventas|de|del|la|las|el|los|en|y|me|dime|dame|muestra|muestrame|ver|quiero|tiene|tienen|tuvo|fue|es|son|que|como|va|van|vamos|con|total|totales|dato|datos|resultado|resultados|cifra|cifras|a|al|por|para|su|sus|tienda|tiendas|mes|dia|dias|numero|numeros)\b/g," ").replace(/\s+/g," ").trim();
  var algo=pt.grupos.length||pp.periodos.length||metrica!=="net"||comparar||mejorDia||desglose||promedio||ranking;
  if(!algo||(resto.length>3&&!pt.grupos.length&&!pp.periodos.length)) return noEntendi();

  // --- comparación de dos períodos
  if(comparar&&per.length===2){
    return grupos.map(function(g){
      var a=agg(g.ids,per[0].from,per[0].to), b=agg(g.ids,per[1].from,per[1].to);
      var va=mval(a,metrica), vb=mval(b,metrica);
      var h="<b>"+g.label+"</b> · "+METR[metrica]+"<br>"+etiqueta(per[0],a)+": <b>"+mfmt(va,metrica)+"</b><br>"+etiqueta(per[1],b)+": <b>"+mfmt(vb,metrica)+"</b>";
      if(va!=null&&vb!=null) h+="<br>Diferencia: "+dif(va,vb);
      if(!a.ndays||!b.ndays) h+="<br><small>Uno de los dos períodos no tiene datos.</small>";
      return h;
    }).join("<hr>");
  }
  // --- comparación de dos tiendas o grupos
  if(comparar&&grupos.length>=2){
    var p0=per[0], filas=grupos.map(function(g){ var a=agg(g.ids,p0.from,p0.to); return {g:g,a:a,v:mval(a,metrica)}; });
    var h="<b>"+METR[metrica]+"</b> · "+etiqueta(p0,filas[0].a)+"<br>"+filas.map(function(f){return f.g.label+": <b>"+mfmt(f.v,metrica)+"</b>";}).join("<br>");
    if(filas.length===2&&filas[0].v!=null&&filas[1].v!=null) h+="<br>"+filas[0].g.label+" vs "+filas[1].g.label+": "+dif(filas[0].v,filas[1].v);
    return h;
  }
  var g=grupos[0], p=per[0], a=agg(g.ids,p.from,p.to);
  if(!a.ndays){
    var u=ultimoDia();
    var msg="Sin datos de <b>"+g.label+"</b> para "+(p.label||rangoTxt(p.from,p.to))+".";
    if(p.to>=u) msg+="<br>Los datos se cargan en la noche; el último día con datos es "+fdia(u)+".";
    return msg;
  }
  // --- mejor / peor día
  if(mejorDia){
    var malo=/peor|bajo|menor|flojo|menos/.test(mejorDia[0]);
    var ds=Object.keys(a.byDay).map(function(d){return {d:d,v:mval(a.byDay[d],metrica)};}).filter(function(x){return x.v!=null;});
    ds.sort(function(x,y){return malo?x.v-y.v:y.v-x.v;});
    var top=ds.slice(0,3);
    return "<b>"+(malo?"Peor":"Mejor")+" día de "+g.label+"</b> · "+etiqueta(p,a)+" · "+METR[metrica]+"<br>"+
      top.map(function(x,i){return (i+1)+". "+fdia(x.d)+": <b>"+mfmt(x.v,metrica)+"</b>";}).join("<br>")+
      (g.ids.length>1?"<br><small>Suma de "+g.ids.length+" tiendas.</small>":"");
  }
  // --- ranking por tienda
  if(ranking&&g.ids.length>1){
    var filas2=g.ids.map(function(id){ var b=a.by[id]; return {id:id, n:T[id].nombre, v:b&&b.ndays?mval(b,metrica):null, b:b}; });
    filas2.sort(function(x,y){ if(x.v==null) return 1; if(y.v==null) return -1; return peor?x.v-y.v:y.v-x.v; });
    return "<b>"+METR[metrica]+" por tienda</b> · "+g.label+" · "+etiqueta(p,a)+"<br>"+
      filas2.map(function(f,i){return (i+1)+". "+f.n+": <b>"+mfmt(f.v,metrica)+"</b>"+(metrica!=="net"&&f.v!=null?" <small>("+usd(f.b.net)+")</small>":"");}).join("<br>");
  }
  // --- día por día
  if(desglose){
    var dias=Object.keys(a.byDay).sort().reverse(), nota="";
    if(dias.length>45){ nota="<small>Muestro los últimos 45 días.</small><br>"; dias=dias.slice(0,45); }
    var conT=a.hasT, t='<table><tr><th>Día</th><th>Venta</th>'+(conT?'<th>Tkts</th><th>VPT</th>':'')+'</tr>';
    dias.forEach(function(d){ var x=a.byDay[d]; t+='<tr><td>'+fdia(d)+'</td><td>'+usd(x.net)+'</td>'+(conT?'<td>'+num(x.t)+'</td><td>'+(x.t?usd2(x.tn/x.t):"–")+'</td>':'')+'</tr>'; });
    t+='<tr class="tot"><td>Total</td><td>'+usd(a.net)+'</td>'+(conT?'<td>'+num(a.t)+'</td><td>'+(a.t?usd2(a.tn/a.t):"–")+'</td>':'')+'</tr></table>';
    return "<b>"+g.label+"</b> · "+etiqueta(p,a)+"<br>"+nota+t;
  }
  // --- promedio diario
  if(promedio){
    return "<b>Promedio diario de "+g.label+"</b> · "+etiqueta(p,a)+"<br><b>"+mfmt(mval(a,metrica)/(metrica==="vpt"||metrica==="upt"?1:a.ndays),metrica)+"</b>"+(metrica==="vpt"||metrica==="upt"?"":" por día")+" <small>("+a.ndays+" días con venta)</small>";
  }
  // --- total
  var h2="<b>"+g.label+"</b> · "+etiqueta(p,a)+"<br>";
  if(metrica!=="net") h2+=METR[metrica]+": <b>"+mfmt(mval(a,metrica),metrica)+"</b><br><small>"+resumen(a)+"</small>";
  else h2+="<b>"+usd(a.net)+"</b>"+(a.hasT&&a.t?"<br><small>"+num(a.t)+" tickets · VPT "+usd2(a.tn/a.t)+" · UPT "+(a.tu/a.t).toFixed(2)+"</small>":(a.hasU&&a.u?"<br><small>"+num(a.u)+" uds</small>":""));
  if(g.ids.length>1){
    var fl=g.ids.map(function(id){var b=a.by[id];return {n:T[id].nombre,v:b&&b.ndays?mval(b,metrica):null};}).sort(function(x,y){return (y.v||0)-(x.v||0);});
    h2+="<br>"+fl.map(function(f){return f.n+": "+mfmt(f.v,metrica);}).join("<br>");
  }
  if(p.kind==="mes"&&a.ndays>1&&metrica==="net"){ h2+="<br><small>Promedio "+usd(a.net/a.ndays)+" por día ("+a.ndays+" días).</small>"; }
  return h2;
}
var EJ=["Ventas de ayer","Panamá del mes","Mejor día del mes","Quién tiene mejor VPT esta semana","Octubre vs septiembre","Guatemala día por día"];
function ejemplos(){ return '<div class="bsug">'+EJ.map(function(e){return '<button type="button">'+e+'</button>';}).join("")+'</div>'; }
function ayuda(){ return "Puedo decirte <b>ventas, tickets, VPT o UPT</b> por tienda o grupo (Panamá, IX, NB, RB), por día, semana, mes o rango, y además: comparar dos meses o dos tiendas, ranking por tienda, mejor o peor día, promedio diario y día por día."+ejemplos(); }
function noEntendi(){ return "No entendí. Puedo decirte ventas, tickets, VPT o UPT por tienda, por día, por mes y comparar meses o tiendas. Por ejemplo:"+ejemplos(); }

// ------------------------------------------------------------- interfaz
var panel=$("bot"), msgs=$("bmsgs"), form=$("bform"), inp=$("binp");
function abrir(){ panel.classList.add("on"); document.body.classList.add("botopen"); $("bdatos").textContent=window.DATA?"Datos al "+fdia(ultimoDia()):""; if(!msgs.children.length) burbuja("bot","Hola. ¿Qué quieres saber de las ventas?"+ejemplos()); setTimeout(function(){inp.focus();},50); }
function cerrar(){ panel.classList.remove("on"); document.body.classList.remove("botopen"); }
function burbuja(quien, html){
  var d=document.createElement("div"); d.className="bm "+quien; d.innerHTML=html; msgs.appendChild(d); msgs.scrollTop=msgs.scrollHeight;
  d.querySelectorAll(".bsug button").forEach(function(b){ b.onclick=function(){ preguntar(b.textContent); }; });
}
function preguntar(t){
  t=(t||"").trim(); if(!t) return;
  burbuja("yo", esc(t)); inp.value="";
  var r; try{ r=responder(t); }catch(e){ r="Algo falló al calcular eso. Prueba con otra pregunta."; }
  setTimeout(function(){ burbuja("bot", r); }, 120);
}
$("botfab").onclick=abrir; $("bclose").onclick=cerrar;
form.onsubmit=function(e){ e.preventDefault(); preguntar(inp.value); };
window.VentasBot={responder:responder, abrir:abrir};
})();
