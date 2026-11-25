// SPDX-License-Identifier: GPL-3.0-or-later
// Carte de commande du portail — firmware ESP32-S3 (Arduino-ESP32 3.x + HomeSpan 2.x)
// Compilation : voir LISEZMOI.md
#include "HomeSpan.h"
#include "gate.h"

Gate gate;

// ---------------------------------------------------------------- HomeKit : « porte de garage »
struct GateService : Service::GarageDoorOpener {
  Characteristic::CurrentDoorState current{4};
  Characteristic::TargetDoorState target{1};
  Characteristic::ObstructionDetected obstruction{false};

  static int hkState(St s, int tgt) {   // 0 ouvert, 1 fermé, 2 ouverture, 3 fermeture, 4 arrêté
    switch (s) {
      case St::OPEN: return 0;
      case St::CLOSED: return 1;
      case St::OPENING: return 2;
      case St::CLOSING: return 3;
      default: return 4;
    }
  }
  uint32_t cmdAt = 0;
  boolean update() override {
    if (!target.updated()) return true;
    St s = gate.state;
    // défaut, apprentissage ou essai sur banc : la commande serait ignorée, Maison doit afficher un échec
    if (s == St::FAULT || s == St::LEARN || s == St::BENCH) return false;
    gate.cmd = target.getNewVal() == 0 ? Cmd::OPEN : Cmd::CLOSE;
    cmdAt = millis();
    return true;
  }
  void loop() override {
    St s = gate.state;
    int cur = hkState(s, target.getVal());
    if (cur != current.getVal()) {
      current.setVal(cur);
      // un mouvement lancé par un bouton ou la radio doit aussi se voir dans la cible
      if ((cur == 0 || cur == 2) && target.getVal() != 0) target.setVal(0);
      if ((cur == 1 || cur == 3) && target.getVal() != 1) target.setVal(1);
    }
    // commande refusée par le portail (photocellule occupée, par exemple) : la cible revient à l'état réel
    if ((cur == 0 || cur == 1) && target.getVal() != cur && millis() - cmdAt > 1500) target.setVal(cur);
    if (gate.obstruction != obstruction.getVal()) obstruction.setVal(gate.obstruction);
  }
};

// Capteur de contact servant d'alerte : « ouvert » dans Maison = alerte active (Maison sait envoyer une notification).
struct AlertSensor : Service::ContactSensor {
  Characteristic::ContactSensorState st{0};
  bool (*active)();
  AlertSensor(const char *name, bool (*f)()) : active(f) { new Characteristic::ConfiguredName(name); }
  void loop() override {
    int v = active() ? 1 : 0;
    if (v != st.getVal()) st.setVal(v);
  }
};

static bool alertFault() { return gate.state == St::FAULT; }
static bool alertOpen() {            // portail appris et pas fermé depuis trop longtemps
  static uint32_t since = 0;
  if (gate.state == St::CLOSED || !gate.P.learned) { since = 0; return false; }
  if (!since) since = millis() | 1;
  return gate.P.openAlertMin && millis() - since > gate.P.openAlertMin * 60000UL;
}

// ---------------------------------------------------------------- console série (commandes « @x »)
static const char *args(const char *buf) {   // saute « @x » et les espaces
  if (*buf == '@') buf++;
  if (*buf) buf++;
  while (*buf == ' ') buf++;
  return buf;
}

// modifie un réglage par son nom ; faux si le nom est inconnu. Utilisé par la console et par la page web.
static bool setParam(const String &n, float v) {
  Params &P = gate.P;
  if (n == "inv1") P.inv[0] = v; else if (n == "inv2") P.inv[1] = v;
  else if (n == "cruise") P.cruisePct = constrain((int)v, 20, 100);
  else if (n == "slow") P.slowPct = constrain((int)v, 10, 100);
  else if (n == "ramp") P.rampMs = constrain((int)v, 100, 5000);
  else if (n == "zone") P.slowZonePct = constrain((int)v, 0, 50);
  else if (n == "seuil1") P.iStall[0] = constrain(v, 0.5f, 9.0f);
  else if (n == "seuil2") P.iStall[1] = constrain(v, 0.5f, 9.0f);
  else if (n == "seuilL1") P.iSlow[0] = v <= 0 ? 0 : constrain(v, 0.5f, 9.0f);
  else if (n == "seuilL2") P.iSlow[1] = v <= 0 ? 0 : constrain(v, 0.5f, 9.0f);
  else if (n == "arret") P.stopRampMs = constrain((int)v, 0, 1000);
  else if (n == "fotoOn") P.fotoOn = v; else if (n == "fotoNC") P.fotoNC = v;
  else if (n == "stopOn") P.stopOn = v; else if (n == "stopNC") P.stopNC = v;
  else if (n == "clignote") P.lampBlink = v;
  else if (n == "preavis") P.preflashMs = constrain((int)v, 0, 5000);
  else if (n == "autoferme") P.autoCloseS = constrain((int)v, 0, 600);
  else if (n == "alerteouv") P.openAlertMin = constrain((int)v, 0, 240);
  else return false;
  P.save();
  return true;
}

static void cmdParam(const char *buf) {
  char name[16] = ""; float v = 0;
  Params &P = gate.P;
  if (sscanf(args(buf), "%15s %f", name, &v) == 2 && !setParam(String(name), v)) {
    Serial.println("parametre inconnu");
    return;
  }
  Serial.printf("inv1=%d inv2=%d cruise=%d slow=%d ramp=%d zone=%d seuil1=%.1f seuil2=%.1f seuilL1=%.1f seuilL2=%.1f arret=%d\n"
                "fotoOn=%d fotoNC=%d stopOn=%d stopNC=%d clignote=%d preavis=%d autoferme=%d alerteouv=%d\n",
                P.inv[0], P.inv[1], P.cruisePct, P.slowPct, P.rampMs, P.slowZonePct, P.iStall[0], P.iStall[1], P.iSlow[0], P.iSlow[1], P.stopRampMs,
                P.fotoOn, P.fotoNC, P.stopOn, P.stopNC, P.lampBlink, P.preflashMs, P.autoCloseS, P.openAlertMin);
}

// Sauvegarde / restauration : tous les réglages, courses apprises comprises, en JSON plat (nombres uniquement).
static const char *const BACKUP_KEYS[] = {"inv1", "inv2", "cruise", "slow", "ramp", "zone", "seuil1", "seuil2", "fotoOn", "fotoNC",
                                          "stopOn", "stopNC", "clignote", "preavis", "autoferme", "alerteouv", "seuilL1", "seuilL2", "arret"};
static String backupJson() {
  Params &P = gate.P;
  float v[] = {(float)P.inv[0], (float)P.inv[1], (float)P.cruisePct, (float)P.slowPct, (float)P.rampMs, (float)P.slowZonePct, P.iStall[0], P.iStall[1],
               (float)P.fotoOn, (float)P.fotoNC, (float)P.stopOn, (float)P.stopNC, (float)P.lampBlink, (float)P.preflashMs, (float)P.autoCloseS, (float)P.openAlertMin,
               P.iSlow[0], P.iSlow[1], (float)P.stopRampMs};
  String j = "{\"portail\":1";
  for (unsigned i = 0; i < sizeof(v) / sizeof(v[0]); i++) { j += ",\""; j += BACKUP_KEYS[i]; j += "\":"; j += String(v[i], strncmp(BACKUP_KEYS[i], "seuil", 5) ? 0 : 1); }
  j += ",\"appris\":" + String((int)P.learned);
  j += ",\"t1f\":" + String(P.travelMs[0][0]) + ",\"t1o\":" + String(P.travelMs[0][1]) + ",\"t2f\":" + String(P.travelMs[1][0]) + ",\"t2o\":" + String(P.travelMs[1][1]) + "}";
  return j;
}
static bool jsonNum(const String &s, const char *key, float &out) {   // cherche "clé": nombre
  String k = String("\"") + key + "\"";
  int i = s.indexOf(k);
  if (i < 0) return false;
  i = s.indexOf(':', i + k.length());
  if (i < 0) return false;
  const char *p = s.c_str() + i + 1; char *end;
  out = strtof(p, &end);
  return end != p;
}
// renvoie le nombre de réglages repris, -1 si le fichier n'est pas une sauvegarde, -2 si le portail n'est pas au repos
static int backupRestore(const String &s) {
  float v;
  if (!jsonNum(s, "portail", v) || v != 1) return -1;
  St st = gate.state;
  if (st != St::STOPPED && st != St::CLOSED && st != St::OPEN && st != St::FAULT) return -2;
  int n = 0;
  for (const char *k : BACKUP_KEYS) if (jsonNum(s, k, v) && setParam(String(k), v)) n++;
  Params &P = gate.P;
  const char *tk[4] = {"t1f", "t1o", "t2f", "t2o"};
  for (int i = 0; i < 4; i++) if (jsonNum(s, tk[i], v) && v >= 0 && v <= 600000) { P.travelMs[i / 2][i % 2] = (uint32_t)v; n++; }
  if (jsonNum(s, "appris", v)) { P.learned = v != 0 && P.travelMs[0][0] && P.travelMs[0][1] && P.travelMs[1][0] && P.travelMs[1][1]; n++; }
  P.save();
  return n;
}

static int wifiConnects = 0;   // connexions au réseau depuis le démarrage
#include "web.h"   // page web de réglage (port 8080) ; a besoin de gate et de setParam

static void cmdBench(const char *buf) {
  int m = 0, pct = 0, ms = 1000;
  if (sscanf(args(buf), "%d %d %d", &m, &pct, &ms) < 2 || m < 1 || m > 2) {
    Serial.println("usage : @m <moteur 1|2> <rapport -100..100 %> [duree ms, 5000 max]");
    return;
  }
  gate.benchMotor = m; gate.benchPct = pct; gate.benchMs = ms;
  gate.benchRaw = false;
  gate.cmd = Cmd::BENCH;
}

void setup() {
  gate.begin();                    // en premier : met les sorties moteur en état sûr
  Serial.begin(115200);
  journalBegin();                  // note le démarrage et sa cause
  homeSpan.setStatusPin(PIN_LED);
  homeSpan.setControlPin(PIN_BOOT);
  homeSpan.setConnectionCallback([](int n) {                  // appelé à chaque (re)connexion au réseau
    webBegin();
    wifiConnects = n;
    configTzTime("CET-1CEST,M3.5.0,M10.5.0/3", "pool.ntp.org");   // heure de Paris, pour dater le journal
    if (n > 1) { char m[60]; snprintf(m, sizeof(m), "Wi-Fi retabli (connexion no %d depuis le demarrage)", n); evPush(EV_WIFI, m); }
  });
  homeSpan.setHostNameSuffix("");  // nom sur le réseau : portail.local (au lieu de portail-<identifiant>)
  homeSpan.enableOTA();            // mot de passe par défaut « homespan-ota », à changer par la commande O
  homeSpan.begin(Category::GarageDoorOpeners, "Portail", "portail", "Portail-v0.4");

  new SpanAccessory();
  new Service::AccessoryInformation();
  new Characteristic::Identify();
  new Characteristic::Name("Portail");
  new GateService();
  new AlertSensor("Défaut portail", alertFault);
  new AlertSensor("Portail resté ouvert", alertOpen);

  new SpanUserCommand('e', "- etat du portail, courants, entrees", [](const char *) { gate.printStatus(); });
  new SpanUserCommand('o', "- ouvrir", [](const char *) { gate.cmd = Cmd::OPEN; });
  new SpanUserCommand('f', "- fermer", [](const char *) { gate.cmd = Cmd::CLOSE; });
  new SpanUserCommand('x', "- arreter", [](const char *) { gate.cmd = Cmd::STOP; });
  new SpanUserCommand('s', "- pas a pas (comme le bouton ou la telecommande)", [](const char *) { gate.cmd = Cmd::STEP; });
  new SpanUserCommand('k', "- acquitter un defaut (ne lance aucun mouvement)", [](const char *) { gate.cmd = Cmd::ACK; });
  new SpanUserCommand('a', "- apprentissage des courses (3 mouvements lents, puis 2 a vitesse normale)", [](const char *) { gate.cmd = Cmd::LEARN; });
  new SpanUserCommand('p', "<nom> <valeur> - lire ou modifier un reglage", cmdParam);
  new SpanUserCommand('m', "<1|2> <%> [ms] - essai sur banc d'un moteur seul", cmdBench);
}

void loop() {
  homeSpan.poll();
  webPoll();
  journalPoll();
}
