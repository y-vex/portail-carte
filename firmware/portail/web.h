// SPDX-License-Identifier: GPL-3.0-or-later
// Page web de réglage et de suivi, sur le port 8080 (le port 80 est pris par HomeKit).
// Adresse : http://<adresse de la carte>:8080/ — accessible à tout appareil du réseau local, sans mot de passe.
#pragma once
#include <WebServer.h>

static WebServer webSrv(8080);
static bool webUp = false;

static const char WEB_PAGE[] PROGMEM = R"HTML(<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Portail</title><style>
:root{--bg:#f4f5f7;--card:#fff;--fg:#1c1f24;--mu:#667;--ac:#1565c0;--bad:#c62828;--ok:#2e7d32;--bd:#d9dce1}
@media(prefers-color-scheme:dark){:root{--bg:#15171a;--card:#1f2226;--fg:#e8eaed;--mu:#9aa;--ac:#64b5f6;--bad:#ef5350;--ok:#81c784;--bd:#33373d}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:16px/1.4 system-ui,sans-serif}
main{max-width:640px;margin:auto}h1{font-size:22px;margin:0 0 12px}h2{font-size:16px;margin:0 0 10px}
section{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px;margin-bottom:14px}
#etat{font-size:26px;font-weight:600}.bad{color:var(--bad)}.ok{color:var(--ok)}.mu{color:var(--mu);font-size:14px}
table{width:100%;border-collapse:collapse}td{padding:4px 0}td+td{text-align:right;font-variant-numeric:tabular-nums}
.btns{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
button{font:inherit;padding:12px 6px;border-radius:8px;border:1px solid var(--bd);background:var(--card);color:var(--fg)}
button.p{background:var(--ac);color:#fff;border-color:var(--ac)}button.s{background:var(--bad);color:#fff;border-color:var(--bad)}
.row{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:6px 0;border-top:1px solid var(--bd)}
.row:first-of-type{border-top:0}.row span{flex:1}.row small{display:block;color:var(--mu)}
input[type=number]{width:84px;font:inherit;padding:6px;border:1px solid var(--bd);border-radius:6px;background:var(--bg);color:var(--fg);text-align:right}
input[type=checkbox]{width:22px;height:22px}</style></head><body><main>
<h1>Portail</h1>
<section><div id="etat">…</div><div id="def" class="bad"></div>
<div class="btns" id="ackb" style="display:none;margin:8px 0"><button data-c="k">Acquitter le défaut</button></div>
<div id="lien" class="mu"></div><div id="fw" class="mu"></div></section>
<section><h2>Commandes</h2><div class="btns">
<button class="p" data-c="o">Ouvrir</button><button class="s" data-c="x">Arrêt</button><button class="p" data-c="f">Fermer</button>
<button data-c="s">Pas à pas</button><button data-c="a">Apprentissage</button></div></section>
<section><h2>Essai sur banc</h2><div class="mu">Un seul moteur, sans position ni détection de butée. Le STOP actif bloque l’essai.</div>
<label class="row"><span>Moteur</span><input type="number" id="b_m" min="1" max="2" value="1"></label>
<label class="row"><span>Rapport <small>-100 à 100 %, négatif = autre sens</small></span><input type="number" id="b_p" min="-100" max="100" value="30"></label>
<label class="row"><span>Durée <small>100 à 5000 ms</small></span><input type="number" id="b_t" min="100" max="5000" step="100" value="1000"></label>
<div class="btns"><button id="b_go">Lancer</button></div></section>
<section><h2>Mesures</h2><table id="mes"></table></section>
<section><h2>Journal</h2><div id="jinfo" class="mu"></div><table id="jour"></table>
<div class="btns" style="margin-top:8px"><button id="j_eff">Effacer le journal</button></div></section>
<section><h2>Réglages</h2><div id="reg"></div>
<div class="btns" style="margin-top:10px"><button id="r_sav">Sauvegarder…</button><button id="r_res">Restaurer…</button></div>
<input type="file" id="r_file" accept=".json,application/json" style="display:none">
<div class="mu" style="margin-top:6px">La sauvegarde contient tous les réglages et les courses apprises.</div></section>
</main><script>
const R=[['cruise','Vitesse de croisière','%',20,100,1],['slow','Vitesse lente','%',10,100,1],['ramp','Durée de la rampe','ms',100,5000,50],
['zone','Part de la course au ralenti','%',0,50,1],['seuil1','Seuil de blocage, vantail 1','A',0.5,9,0.1],['seuil2','Seuil de blocage, vantail 2','A',0.5,9,0.1],
['seuilL1','Seuil en approche lente, vantail 1 (0 = seuil normal)','A',0,9,0.1],['seuilL2','Seuil en approche lente, vantail 2 (0 = seuil normal)','A',0,9,0.1],
['arret','Décélération à l\'arrêt commandé (0 = arrêt net)','ms',0,1000,50],
['preavis','Préavis du feu avant mouvement','ms',0,5000,100],['autoferme','Fermeture automatique (0 = non)','s',0,600,1],['alerteouv','Alerte HomeKit « resté ouvert » (0 = non)','min',0,240,1],
['inv1','Inverser le sens du vantail 1'],['inv2','Inverser le sens du vantail 2'],['fotoOn','Photocellule utilisée'],['fotoNC','Photocellule normalement fermée'],
['stopOn','Entrée STOP utilisée'],['stopNC','STOP normalement fermé'],['clignote','La carte fait clignoter le feu']];
const E={ARRETE:'Arrêté',FERME:'Fermé',OUVERTURE:'Ouverture…',OUVERT:'Ouvert',FERMETURE:'Fermeture…',PAUSE:'Pause',RECUL:'Recul',DEFAUT:'Défaut',
APPRENTISSAGE:'Apprentissage…',BANC:'Essai sur banc'};
const $=i=>document.getElementById(i);let prets=false;
function post(u){return fetch(u,{method:'POST'}).then(r=>{if(!r.ok)throw 0;maj()}).catch(()=>{$('lien').textContent='Commande refusée ou carte injoignable'})}
function reglages(p){$('reg').innerHTML=R.map(r=>'<label class="row"><span>'+r[1]+(r[2]?' <small>'+r[3]+' à '+r[4]+' '+r[2]+'</small>':'')+'</span>'+
(r[2]?'<input type="number" id="p_'+r[0]+'" min="'+r[3]+'" max="'+r[4]+'" step="'+r[5]+'">':'<input type="checkbox" id="p_'+r[0]+'">')+'</label>').join('');
R.forEach(r=>{const e=$('p_'+r[0]);e.onchange=()=>post('/api/param?n='+r[0]+'&v='+(r[2]?e.value:+e.checked)).then(()=>{prets=false})});prets=false}
function remplir(p){R.forEach(r=>{const e=$('p_'+r[0]);if(document.activeElement===e)return;if(r[2])e.value=p[r[0]];else e.checked=!!p[r[0]]})}
function v(x,d,u){return x==null?'inconnue':x.toFixed(d)+(u||'')}
function maj(){fetch('/api/etat').then(r=>r.json()).then(j=>{
$('etat').textContent=E[j.etat]||j.etat;$('etat').className=j.etat=='DEFAUT'?'bad':'';$('ackb').style.display=j.etat=='DEFAUT'?'':'none';
if(j.fw){const d=new Date(j.fw);$('fw').textContent='Firmware compilé le '+(isNaN(d)?j.fw:d.toLocaleString('fr-FR',{dateStyle:'short',timeStyle:'medium'}))}$('def').textContent=j.defaut?'Défaut : '+j.defaut:'';
$('lien').textContent='Wi-Fi '+j.rssi+' dBm · '+(j.appris?'courses apprises':'apprentissage non fait')+(j.obstacle?' · obstacle détecté':'');
const d=i=>j.drv[i]<0||j.drv[i]==255?'pas de réponse':j.drv[i]==0?'bon':(j.drv[i]&6)?'défaut 0x'+j.drv[i].toString(16):(j.drv[i]&64)?'présent, pas encore réglé (0x'+j.drv[i].toString(16)+')':'signalement 0x'+j.drv[i].toString(16);
$('mes').innerHTML=[['Tension du bus',v(j.bus,1,' V')],['Température de l’ESP32',v(j.temp,1,' °C')],['Vantail 1 : position',j.pos[0]==null?'inconnue':Math.round(j.pos[0]*100)+' %'],
['Vantail 1 : courant',v(j.amps[0],2,' A')],['Vantail 1 : driver',d(0)],['Vantail 2 : position',j.pos[1]==null?'inconnue':Math.round(j.pos[1]*100)+' %'],
['Vantail 2 : courant',v(j.amps[1],2,' A')],['Vantail 2 : driver',d(1)],
['Pointe en approche lente (dernier mouvement)',v(j.picLent[0],2,' A')+' / '+v(j.picLent[1],2,' A')],
['Entrées actives',['pp','foto','radio','stop'].filter(k=>j.ent[k]).map(k=>k.toUpperCase()).join(', ')||'aucune'],
['Courses apprises (ferm. / ouv.)',j.course.map(c=>c[0]+' / '+c[1]+' ms').join(' · ')]].map(r=>'<tr><td>'+r[0]+'</td><td>'+r[1]+'</td></tr>').join('');
if(!$('p_cruise'))reglages(j.p);if(!prets){remplir(j.p);prets=true}
}).catch(()=>{$('lien').textContent='Carte injoignable'})}
document.querySelectorAll('button[data-c]').forEach(b=>b.onclick=()=>{
if(b.dataset.c=='a'&&!confirm('Lancer l’apprentissage ? Le portail va faire trois mouvements lents complets, puis une ouverture et une fermeture à vitesse normale.'))return;post('/api/cmd?c='+b.dataset.c)});
$('b_go').onclick=()=>post('/api/cmd?c=m&m='+$('b_m').value+'&pct='+$('b_p').value+'&ms='+$('b_t').value);
function duree(s){return s<120?s+' s':s<7200?Math.round(s/60)+' min':s<172800?Math.round(s/3600)+' h':Math.round(s/86400)+' j'}
function jour(){fetch('/api/journal').then(r=>r.json()).then(j=>{
$('jinfo').textContent='Démarrage n° '+j.boots+' · en marche depuis '+duree(j.up)+' · connexions Wi-Fi depuis le démarrage : '+j.wifi;
$('jour').innerHTML=j.ev.map(e=>{const q=e.t?new Date(e.t*1000).toLocaleString('fr-FR',{dateStyle:'short',timeStyle:'medium'}):'heure inconnue';
const det=e.k==2||e.k==3?'<br><small class="mu">'+e.i[0].toFixed(2)+' / '+e.i[1].toFixed(2)+' A · '+e.v.toFixed(1)+' V · drivers 0x'+e.d[0].toString(16)+' / 0x'+e.d[1].toString(16)+'</small>':'';
return '<tr><td style="text-align:left'+(e.k==2?';color:var(--bad)':'')+'">'+e.m+det+'</td><td class="mu" style="white-space:nowrap;vertical-align:top">'+q+'<br>dém. '+e.b+' + '+duree(e.up)+'</td></tr>'}).join('')||'<tr><td>aucun événement</td></tr>';
}).catch(()=>{})}
$('j_eff').onclick=()=>{if(confirm('Effacer tous les événements du journal ?'))fetch('/api/journal/efface',{method:'POST'}).then(jour)};
$('r_sav').onclick=()=>{location.href='/api/reglages'};
$('r_res').onclick=()=>$('r_file').click();
$('r_file').onchange=e=>{const f=e.target.files[0];e.target.value='';if(!f||!confirm('Remplacer tous les réglages de la carte par ceux du fichier « '+f.name+' » ?'))return;
f.text().then(t=>fetch('/api/reglages',{method:'POST',headers:{'Content-Type':'text/plain'},body:t})).then(r=>r.text()).then(t=>{alert(t);prets=false;maj()}).catch(()=>alert('Échec de l’envoi'))};
maj();setInterval(maj,1000);jour();setInterval(jour,5000);
</script></body></html>)HTML";

static String jnum(float v, int dec) { return isnan(v) ? String("null") : String(v, dec); }

static void webEtat() {
  Params &P = gate.P;
  String j;
  j.reserve(700);
  j += "{\"fw\":\"" __DATE__ " " __TIME__ "\",\"etat\":\""; j += stName(gate.state);
  j += "\",\"defaut\":\""; j += gate.fault;
  j += "\",\"bus\":" + jnum(gate.vbus, 1);
  j += ",\"obstacle\":" + String((int)gate.obstruction) + ",\"appris\":" + String((int)P.learned);
  j += ",\"rssi\":" + String(WiFi.RSSI());
  j += ",\"pente\":" + String((int)drv::srCode);
  j += ",\"temp\":" + jnum(temperatureRead(), 1);   // capteur interne de l'ESP32 : température de la puce, pas de la carte
  j += ",\"pos\":[" + jnum(gate.L[0].pos, 3) + "," + jnum(gate.L[1].pos, 3) + "]";
  j += ",\"amps\":[" + jnum(gate.L[0].amps, 2) + "," + jnum(gate.L[1].amps, 2) + "]";
  j += ",\"picLent\":[" + jnum(gate.L[0].slowPeak, 2) + "," + jnum(gate.L[1].slowPeak, 2) + "]";   // dernier mouvement
  j += ",\"drv\":[" + String(gate.drvFault(0)) + "," + String(gate.drvFault(1)) + "]";
  j += ",\"course\":[[" + String(P.travelMs[0][0]) + "," + String(P.travelMs[0][1]) + "],[" + String(P.travelMs[1][0]) + "," + String(P.travelMs[1][1]) + "]]";
  j += ",\"ent\":{\"pp\":" + String((int)gate.inPP) + ",\"foto\":" + String((int)gate.inFoto) + ",\"radio\":" + String((int)gate.inRadio) + ",\"stop\":" + String((int)gate.inStop) + "}";
  j += ",\"p\":{\"inv1\":" + String((int)P.inv[0]) + ",\"inv2\":" + String((int)P.inv[1]) + ",\"cruise\":" + String(P.cruisePct) + ",\"slow\":" + String(P.slowPct);
  j += ",\"ramp\":" + String(P.rampMs) + ",\"zone\":" + String(P.slowZonePct) + ",\"seuil1\":" + String(P.iStall[0], 1) + ",\"seuil2\":" + String(P.iStall[1], 1);
  j += ",\"seuilL1\":" + String(P.iSlow[0], 1) + ",\"seuilL2\":" + String(P.iSlow[1], 1) + ",\"arret\":" + String(P.stopRampMs);
  j += ",\"fotoOn\":" + String((int)P.fotoOn) + ",\"fotoNC\":" + String((int)P.fotoNC) + ",\"stopOn\":" + String((int)P.stopOn) + ",\"stopNC\":" + String((int)P.stopNC);
  j += ",\"clignote\":" + String((int)P.lampBlink) + ",\"preavis\":" + String(P.preflashMs) + ",\"autoferme\":" + String(P.autoCloseS) + ",\"alerteouv\":" + String(P.openAlertMin) + "}}";
  webSrv.sendHeader("Cache-Control", "no-store");
  webSrv.send(200, "application/json", j);
}

static void webJournal() {   // du plus récent au plus ancien
  using namespace journal;
  String j;
  j.reserve(3600);
  j += "{\"boots\":" + String(boots) + ",\"up\":" + String(millis() / 1000) + ",\"wifi\":" + String(wifiConnects) + ",\"ev\":[";
  bool first = true;
  for (int n = 1; n <= JOURNAL_N; n++) {
    const JEntry &e = ent[(head + JOURNAL_N - n) % JOURNAL_N];
    if (!e.kind) continue;
    if (!first) j += ",";
    first = false;
    j += "{\"t\":" + String(e.t) + ",\"up\":" + String(e.up) + ",\"b\":" + String(e.boot) + ",\"k\":" + String(e.kind);
    j += ",\"i\":[" + String(e.cA[0] / 100.0f, 2) + "," + String(e.cA[1] / 100.0f, 2) + "],\"v\":" + String(e.dV / 10.0f, 1);
    j += ",\"d\":[" + String(e.drv[0]) + "," + String(e.drv[1]) + "],\"m\":\""; j += e.msg; j += "\"}";
  }
  j += "]}";
  webSrv.sendHeader("Cache-Control", "no-store");
  webSrv.send(200, "application/json", j);
}

static void webCmd() {
  String c = webSrv.arg("c");
  if (c == "m") {   // essai sur banc d'un moteur seul, comme la commande « @m » de la console
    int m = webSrv.arg("m").toInt();
    if (m < 1 || m > 2 || !webSrv.hasArg("pct")) { webSrv.send(400, "text/plain", "moteur 1 ou 2, pct -100..100"); return; }
    gate.benchMotor = m; gate.benchPct = webSrv.arg("pct").toInt(); gate.benchMs = webSrv.hasArg("ms") ? webSrv.arg("ms").toInt() : 1000;
    gate.benchRaw = webSrv.arg("brut") == "1";
    gate.cmd = Cmd::BENCH;
    webSrv.send(200, "text/plain", "ok");
    return;
  }
  Cmd k = c == "o" ? Cmd::OPEN : c == "f" ? Cmd::CLOSE : c == "x" ? Cmd::STOP : c == "s" ? Cmd::STEP : c == "a" ? Cmd::LEARN : c == "k" ? Cmd::ACK : Cmd::NONE;
  if (k == Cmd::NONE) { webSrv.send(400, "text/plain", "commande inconnue"); return; }
  gate.cmd = k;
  webSrv.send(200, "text/plain", "ok");
}

static void webParam() {
  if (webSrv.arg("n") == "pente" && webSrv.hasArg("v")) {   // pente de commutation des drivers, 0 (douce) à 7 (raide) ; non enregistrée
    drv::srCode = constrain(webSrv.arg("v").toInt(), 0, 7);
    webSrv.send(200, "text/plain", "ok");
    return;
  }
  if (!webSrv.hasArg("n") || !webSrv.hasArg("v") || !setParam(webSrv.arg("n"), webSrv.arg("v").toFloat())) {
    webSrv.send(400, "text/plain", "parametre inconnu");
    return;
  }
  webSrv.send(200, "text/plain", "ok");
}

inline void webBegin() {   // appelé par HomeSpan à chaque (re)connexion au réseau
  if (webUp) return;
  webSrv.on("/", HTTP_GET, []() { webSrv.send_P(200, "text/html; charset=utf-8", WEB_PAGE); });
  webSrv.on("/api/etat", HTTP_GET, webEtat);
  webSrv.on("/api/journal", HTTP_GET, webJournal);
  webSrv.on("/api/journal/efface", HTTP_POST, []() { journal::clear(); webSrv.send(200, "text/plain", "ok"); });
  webSrv.on("/api/reglages", HTTP_GET, []() {
    webSrv.sendHeader("Content-Disposition", "attachment; filename=\"portail-reglages.json\"");
    webSrv.send(200, "application/json", backupJson());
  });
  webSrv.on("/api/reglages", HTTP_POST, []() {
    int n = backupRestore(webSrv.arg("plain"));
    if (n == -1) webSrv.send(400, "text/plain; charset=utf-8", "Ce fichier n'est pas une sauvegarde du portail.");
    else if (n == -2) webSrv.send(409, "text/plain; charset=utf-8", "Portail en mouvement : restauration refusée.");
    else webSrv.send(200, "text/plain; charset=utf-8", String(n) + " réglages restaurés.");
  });
  webSrv.on("/api/cmd", HTTP_POST, webCmd);      // les actions passent par POST : un simple lien ne peut pas ouvrir le portail
  webSrv.on("/api/param", HTTP_POST, webParam);
  webSrv.begin();
  webUp = true;
}

inline void webPoll() { if (webUp) webSrv.handleClient(); }
