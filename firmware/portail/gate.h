// SPDX-License-Identifier: GPL-3.0-or-later
// Commande du portail : deux vantaux, sans capteur de position.
// Position estimée par le temps (pondéré par le rapport cyclique), recalée à chaque butée ;
// butée et obstacle détectés par le courant moteur (IPROPI du DRV8245).
#pragma once
#include <atomic>
#include <esp_task_wdt.h>
#include "config.h"
#include "params.h"
#include "drv8245.h"
#include "journal.h"

enum class St : uint8_t { STOPPED, CLOSED, OPENING, OPEN, CLOSING, PAUSE, BACKOFF, FAULT, LEARN, BENCH };
enum class Cmd : uint8_t { NONE, OPEN, CLOSE, STOP, STEP, LEARN, BENCH, ACK };
enum class Res : uint8_t { RUN, END, OBSTACLE, OVERRUN };

inline const char *stName(St s) {
  static const char *n[] = {"ARRETE", "FERME", "OUVERTURE", "OUVERT", "FERMETURE", "PAUSE", "RECUL", "DEFAUT", "APPRENTISSAGE", "BANC"};
  return n[(int)s];
}

struct Leaf {
  float pos = NAN;        // 0 = fermé, 1 = ouvert, NAN = inconnue
  int8_t dir = 0;         // +1 ouvre, -1 ferme, 0 arrêté
  float duty = 0;         // 0..1
  float eq = 0;           // durée du mouvement ramenée à la vitesse de croisière (ms)
  float amps = 0;         // courant filtré
  uint32_t overMs = 0;    // temps passé au-dessus du seuil
  bool fullRun = false;   // parti d'une butée connue : la durée mesurée sert à recaler la course
  Res res = Res::END;
  float sumI = 0; uint32_t nI = 0;
  // approche lente d'une butée (position connue, vitesse lente établie)
  uint32_t slowMs = 0;    // temps passé dans cette phase
  float slowPeak = 0;     // plus fort courant vu dans cette phase, hors les 300 dernières ms (montée en butée exclue)
  float pkBlk = 0; uint8_t pkN = 0; float pkPend[6] = {0, 0, 0, 0, 0, 0};   // blocs de 50 ms en attente de validation
};

class Gate {
 public:
  Params P;
  Leaf L[2];
  volatile St state = St::STOPPED;
  volatile bool obstruction = false;
  volatile float vbus = 0;
  const char *volatile fault = "";
  std::atomic<Cmd> cmd{Cmd::NONE};
  volatile int benchMotor = 0, benchPct = 0, benchMs = 0;
  volatile bool benchRaw = false;
  volatile bool inPP = false, inFoto = false, inRadio = false, inStop = false;   // états logiques (vrai = actif)

  void begin() {
    // état sûr d'abord : PWM à 0. Tant qu'un driver n'a pas été configuré par SPI, ses sorties restent en haute
    // impédance (broche DRVOFF non câblée, tirée au niveau haut dans le composant).
    drv::begin();
    // Si l'ESP32 redémarre seul, les drivers restés sous tension gardent leurs registres, dont « sorties autorisées ».
    // On les remet donc explicitement en haute impédance (S_DRVOFF = 1) avant toute autre chose.
    for (int i = 0; i < 2; i++) { drv::clearFaults(i); drv::setInputs(i, false, true); }
    for (int i = 0; i < 2; i++) {
      ledcAttach(PIN_EN[i], PWM_HZ, PWM_BITS); ledcWrite(PIN_EN[i], 0);
      analogSetPinAttenuation(PIN_ISENSE[i], ADC_11db);
    }
    analogSetPinAttenuation(PIN_VSENSE, ADC_11db);
    for (int p : {PIN_PP, PIN_FOTO, PIN_RADIO, PIN_STOP, PIN_BTN_LEARN}) pinMode(p, INPUT);   // tirages sur la carte
    pinMode(PIN_LAMP, OUTPUT); digitalWrite(PIN_LAMP, LOW);
    pinMode(PIN_AUX, OUTPUT); digitalWrite(PIN_AUX, LOW);
    P.load();
    uint8_t rest = loadRest();
    if (rest == 1) { L[0].pos = L[1].pos = 0; state = St::CLOSED; }
    else if (rest == 2) { L[0].pos = L[1].pos = 1; state = St::OPEN; openSince = millis(); }
    evQ = xQueueCreate(8, sizeof(Ev));
    xTaskCreatePinnedToCore([](void *g) { ((Gate *)g)->task(); }, "portail", 6144, this, 10, nullptr, 1);
  }

  void printStatus() {
    Serial.printf("etat=%s  bus=%.1f V  obstacle=%d  defaut=\"%s\"  appris=%d\n", stName(state), vbus, obstruction, fault, P.learned);
    for (int i = 0; i < 2; i++)
      Serial.printf("  vantail %d : position=%.2f  courant=%.2f A  seuil=%.1f A  course fermeture=%lu ms ouverture=%lu ms  etat driver=0x%02X\n",
                    i + 1, L[i].pos, L[i].amps, P.iStall[i], (unsigned long)P.travelMs[i][0], (unsigned long)P.travelMs[i][1], drvState[i] & 0xFF);
    Serial.printf("  entrees actives : PP=%d FOTO=%d RADIO=%d STOP=%d\n", inPP, inFoto, inRadio, inStop);
    Serial.printf("  temperature de l'ESP32 : %.1f C\n", temperatureRead());
  }
  int drvFault(int i) const { return drvState[i]; }   // dernier état lu du driver (-1 ou 0xFF = pas de réponse)

 private:
  bool awake = false, dirty = false, reversal = false;
  int8_t moveDir = 0, lastDir = 0, nextDir = 0;
  bool moveSlow = false;
  bool halting = false;                // arrêt commandé en cours : décélération avant l'arrêt
  uint16_t haltMs = 0;                // durée de cette décélération (croisière -> 0)
  int8_t haltNext = 0;                 // ensuite : 0 = rester arrêté, +1 / -1 = repartir dans ce sens
  uint32_t moveStart = 0, idleSince = 0, pauseUntil = 0, backoffUntil = 0, openSince = 0, benchUntil = 0;
  uint8_t learnStep = 0, obstCount = 0;
  int benchI = 0, benchDir = 1; float benchTarget = 0;
  float learnI[2] = {0, 0};
  bool learnCal = false;               // apprentissage : courses de calage à vitesse normale en cours
  float learnPeak[2] = {0, 0};         // plus fort courant vu en marche pendant ces courses (hors butée)
  int8_t phNow[2] = {-1, -1};          // dernier sens écrit dans chaque driver (-1 = inconnu)
  uint32_t drvPollAt = 0;
  volatile int drvState[2] = {-1, -1}; // dernier FAULT_SUMMARY lu (-1 = pas de réponse)

  // ------------------------------------------------------------ drivers
  // lit l'état des deux drivers. Faux si l'un ne répond pas, a redémarré (réglages perdus) ou s'est verrouillé
  // sur une surintensité ou une surchauffe. Une sur- ou sous-tension passagère est seulement acquittée.
  bool driversOk() {
    bool ok = true;
    for (int i = 0; i < 2; i++) {
      int f = drv::faults(i);
      drvState[i] = f;
      if (f < 0 || (f & (drv::F_POR | drv::F_OCP | drv::F_TSD))) ok = false;
      else if (f & (drv::F_VMOV | drv::F_VMUV | drv::F_SPI_ERR)) drv::clearFaults(i);
    }
    return ok;
  }
  // (re)configure les deux drivers ; leurs sorties restent en haute impédance jusqu'à enableOutputs()
  bool wake() {
    awake = false;
    for (int i = 0; i < 2; i++) {
      phNow[i] = -1;
      if (!drv::configure(i) && !drv::configure(i)) { drvState[i] = drv::faults(i); return false; }
    }
    awake = driversOk();
    return awake;
  }
  void enableOutputs() {
    for (int i = 0; i < 2; i++) { if (phNow[i] < 0) phNow[i] = 0; drv::setInputs(i, phNow[i], false); }
  }
  void sleepDrivers() {   // pas de vraie veille (nSLEEP est relié au 3,3 V) : sorties en haute impédance
    for (int i = 0; i < 2; i++) { ledcWrite(PIN_EN[i], 0); drv::setInputs(i, phNow[i] > 0, true); }
    awake = false;
  }
  void drive(int i, int dir, float duty) {
    // Sens : bit S_PH_IN2 du driver. Sur la carte v0.4 les sorties OUT1 et OUT2 sont croisées par rapport à la v0.3,
    // d'où le test inversé : un même réglage « inv » donne le même sens de rotation qu'avant.
    if (dir) {
      int8_t ph = ((dir > 0) != P.inv[i]) ? 1 : 0;
      if (ph != phNow[i]) { phNow[i] = ph; drv::setInputs(i, ph, false); }
    }
    // à 100 % la sortie reste fixe à l'état haut (valeur 2^bits) : aucune commutation, donc aucune perte de commutation
    uint32_t full = 1u << PWM_BITS;
    ledcWrite(PIN_EN[i], duty >= 0.999f ? full : (uint32_t)(constrain(duty, 0.0f, 1.0f) * (full - 1)));
  }
  void stopAll() {
    for (int i = 0; i < 2; i++) { L[i].dir = 0; L[i].duty = 0; ledcWrite(PIN_EN[i], 0); }
    if (moveDir) lastDir = moveDir;
    moveDir = 0; halting = false;
    idleSince = millis();
  }
  void fail(const char *msg) {
    stopAll(); sleepDrivers();
    learnCal = false;
    fault = msg; state = St::FAULT;
    evPush(EV_FAULT, msg, L[0].amps, L[1].amps, vbus, drvState[0], drvState[1]);
    Serial.printf("DEFAUT : %s\n", msg);
  }
  void setState(St s) {
    if (s != state) Serial.printf("etat : %s -> %s\n", stName(state), stName(s));
    if (s != St::LEARN) learnCal = false;   // apprentissage terminé ou interrompu
    state = s;
  }

  // ------------------------------------------------------------ mouvement
  bool startMove(int dir, bool slow) {
    if (vbus < VBUS_MIN_V || vbus > VBUS_MAX_V) { fail("tension du bus hors plage (24 V absent ?)"); return false; }
    if (!wake()) { fail("un driver ne repond pas ou refuse ses reglages (liaison SPI)"); return false; }
    saveRest(0);                               // pendant un mouvement, la position de repos n'est plus connue
    enableOutputs();
    moveDir = dir; moveSlow = slow; moveStart = millis();
    for (int i = 0; i < 2; i++) {
      Leaf &l = L[i];
      float end = dir > 0 ? 1 : 0;
      l.duty = 0; l.eq = 0; l.overMs = 0; l.sumI = 0; l.nI = 0;
      l.slowMs = 0; l.slowPeak = 0; l.pkBlk = 0; l.pkN = 0; for (float &p : l.pkPend) p = 0;
      if (!isnan(l.pos) && l.pos == end) { l.dir = 0; l.res = Res::END; continue; }   // déjà en butée
      l.fullRun = !isnan(l.pos) && l.pos == 1 - end;
      l.dir = dir; l.res = Res::RUN;
      drive(i, dir, 0);
    }
    return true;
  }

  // fait avancer les deux vantaux d'un pas ; renvoie RUN tant qu'un vantail bouge, sinon le pire résultat
  Res tickMove() {
    uint32_t t = millis() - moveStart;
    if (t < P.preflashMs) return Res::RUN;
    t -= P.preflashMs;
    float cruise = P.cruisePct / 100.0f, slowDuty = min(P.slowPct, P.cruisePct) / 100.0f;
    bool anyRun = false;
    Res worst = Res::END;
    for (int i = 0; i < 2; i++) {
      Leaf &l = L[i];
      if (l.dir == 0) { if (l.res > worst) worst = l.res; continue; }
      int open = l.dir > 0;
      float travel = P.travelMs[i][open];
      bool known = (P.learned || learnCal) && !moveSlow && !isnan(l.pos) && travel > 0;
      float remaining = l.dir > 0 ? 1 - l.pos : l.pos;
      bool slow = !known || remaining < P.slowZonePct / 100.0f;
      float target = halting ? 0 : slow ? slowDuty : cruise;
      float step = cruise * TICK_MS / max<float>(halting ? haltMs : P.rampMs, 50);
      l.duty += constrain(target - l.duty, -step, step);
      if (halting && l.duty <= 0) {   // fin de la décélération : ce vantail est arrêté, sa position estimée est gardée
        l.dir = 0; l.duty = 0; ledcWrite(PIN_EN[i], 0);
        l.res = Res::END;
        continue;
      }
      drive(i, l.dir, l.duty);
      float de = l.duty / cruise * TICK_MS;
      l.eq += de;
      if (!isnan(l.pos) && travel > 0) l.pos += l.dir * de / travel;
      if (t > 1000) { l.sumI += l.amps; l.nI++; }
      if (learnCal && t > STALL_BLANK_MS && remaining > 0.35f && l.amps > learnPeak[i]) learnPeak[i] = l.amps;
      // blocage : butée ou obstacle
      // approche lente d'une butée : seuil réduit (s'il est réglé), pour appuyer moins fort sur la butée
      bool approach = known && slow && !halting && fabsf(l.duty - slowDuty) < 0.002f;
      l.slowMs = approach ? l.slowMs + TICK_MS : 0;
      bool settled = l.slowMs >= 200;
      float thr = (settled && !learnCal && P.iSlow[i] > 0) ? min(P.iSlow[i], P.iStall[i]) : P.iStall[i];   // jamais pendant l'apprentissage
      if (settled) {   // relevé du courant d'approche, par blocs de 50 ms validés 300 ms plus tard
        if (l.amps > l.pkBlk) l.pkBlk = l.amps;
        if (++l.pkN * TICK_MS >= 50) {
          if (l.pkPend[0] > l.slowPeak) l.slowPeak = l.pkPend[0];
          for (int k = 0; k < 5; k++) l.pkPend[k] = l.pkPend[k + 1];
          l.pkPend[5] = l.pkBlk; l.pkBlk = 0; l.pkN = 0;
        }
      }
      if (t > STALL_BLANK_MS && l.amps > thr) l.overMs += TICK_MS; else l.overMs = 0;
      if (l.overMs >= ((settled && !learnCal) ? APPROACH_HOLD_MS : STALL_HOLD_MS)) {
        l.dir = 0; l.duty = 0; ledcWrite(PIN_EN[i], 0);
        if (known && remaining > END_TOLERANCE) l.res = Res::OBSTACLE;
        else {
          l.res = Res::END;
          l.pos = open ? 1 : 0;
          if (known && l.fullRun && l.eq > 0.6f * travel && l.eq < 1.5f * travel) {   // recalage progressif de la course
            uint32_t nt = (uint32_t)(0.7f * travel + 0.3f * l.eq);
            if (fabsf((float)nt - travel) > 0.05f * travel) dirty = true;
            P.travelMs[i][open] = nt;
          }
        }
        Serial.printf("vantail %d : %s a %.2f A apres %.0f ms equivalents (seuil %.1f A, pointe en approche lente %.2f A)\n",
                      i + 1, l.res == Res::END ? "butee" : "OBSTACLE", l.amps, l.eq, thr, l.slowPeak);
      } else if (known && !learnCal && (l.dir > 0 ? l.pos > 1 + OVERRUN : l.pos < -OVERRUN)) {
        l.dir = 0; l.duty = 0; ledcWrite(PIN_EN[i], 0);
        l.res = Res::OVERRUN;
      }
      if (l.dir) anyRun = true;
      if (l.res > worst) worst = l.res;
    }
    if (worst == Res::OBSTACLE || worst == Res::OVERRUN) return worst;   // réaction immédiate, même si l'autre vantail roule
    return anyRun ? Res::RUN : worst;
  }

  void pauseThen(int dir) { stopAll(); nextDir = dir; pauseUntil = millis() + REVERSE_PAUSE_MS; setState(St::PAUSE); }

  // Arrêt commandé par l'utilisateur (next = 0) ou inversion commandée (next = +1 / -1). En ouverture ou en fermeture,
  // les moteurs décélèrent d'abord sur « arret » ms au lieu d'être freinés d'un coup (choc dans le réducteur, 8 à 9 A
  // lus au portail). Un second ordre d'arrêt pendant la décélération arrête net. Les arrêts de sécurité (obstacle,
  // entrée STOP, défaut) ne passent pas par ici : ils restent immédiats. La photocellule, qui se déclenche avant
  // tout contact, décélère sur FOTO_STOP_MS avant la réouverture.
  void halt(int8_t next) { halt(next, P.stopRampMs); }
  void halt(int8_t next, uint16_t ms) {
    bool rolling = (state == St::OPENING || state == St::CLOSING) && ms > 0 &&
                   ((L[0].dir && L[0].duty > 0) || (L[1].dir && L[1].duty > 0));
    if (!rolling || (halting && !next)) {
      if (next) pauseThen(next); else { stopAll(); setState(St::STOPPED); }
      return;
    }
    halting = true; haltNext = next; haltMs = ms;
  }

  void go(int dir) {
    if (dir < 0 && P.fotoOn && inFoto) { Serial.println("fermeture refusee : photocellule occupee"); return; }
    if (state == St::PAUSE) { nextDir = dir; reversal = false; return; }   // la pause en cours est respectée
    if (state == St::OPENING || state == St::CLOSING || state == St::BACKOFF) { reversal = false; halt(dir); return; }
    if (startMove(dir, false)) setState(dir > 0 ? St::OPENING : St::CLOSING);
  }

  // ------------------------------------------------------------ apprentissage
  // 0 : fermeture lente jusqu'aux butées ; 1 : ouverture lente chronométrée ; 2 : fermeture lente chronométrée ;
  // 3 et 4 : ouverture puis fermeture à vitesse normale, pour caler les durées de course.
  // Pourquoi 3 et 4 : la vitesse n'est pas proportionnelle au rapport cyclique. Mesurée au portail le 21 nov. 2026,
  // la course à 100 % est 10 à 19 % plus courte que ce que donnent les courses lentes ; sans calage, un vantail
  // arrivait en butée à pleine vitesse. Les courses 3 et 4 partent d'une durée volontairement réduite à 70 %
  // (le ralentissement commence donc tôt) et retiennent la durée réellement mesurée.
  void learnStart() {
    Serial.println("apprentissage : fermeture lente jusqu'aux butees");
    L[0].pos = L[1].pos = NAN; learnStep = 0; learnI[0] = learnI[1] = 0;
    learnCal = false; learnPeak[0] = learnPeak[1] = 0;
    P.learned = false;
    if (startMove(-1, true)) setState(St::LEARN);
  }
  void learnTick() {
    if (pauseUntil) {
      if ((int32_t)(millis() - pauseUntil) < 0) return;
      pauseUntil = 0;
      if (!startMove((learnStep == 1 || learnStep == 3) ? +1 : -1, learnStep <= 2)) return;
    }
    Res r = tickMove();
    if (r == Res::RUN) return;
    stopAll();
    if (r != Res::END) {   // possible seulement pendant le calage (étapes 3 et 4)
      L[0].pos = L[1].pos = NAN;
      fail("apprentissage interrompu : obstacle rencontre pendant le calage");
      return;
    }
    if (learnStep > 0) {
      int open = learnStep == 1 || learnStep == 3;
      for (int i = 0; i < 2; i++) {
        if (L[i].eq < 1500) { fail("apprentissage : course trop courte (vantail bloque ou seuil trop bas)"); return; }
        P.travelMs[i][open] = (uint32_t)L[i].eq;
        if (learnStep <= 2 && L[i].nI) learnI[i] = max(learnI[i], L[i].sumI / L[i].nI);
      }
    }
    if (learnStep == 2) {   // durées provisoires réduites pour les deux courses de calage
      for (int i = 0; i < 2; i++) for (int d = 0; d < 2; d++) P.travelMs[i][d] = (uint32_t)(0.7f * P.travelMs[i][d]);
      learnCal = true;
      Serial.println("apprentissage : calage a vitesse normale");
    }
    if (++learnStep <= 4) { pauseUntil = millis() + 1000; if (!pauseUntil) pauseUntil = 1; return; }
    learnCal = false;
    // seuil de blocage : au moins 20 % au-dessus du plus fort courant vu en marche à vitesse normale
    // (au portail, les pointes de démarrage atteignaient 2,6 à 3,0 A pour un courant moyen de 1,5 A)
    for (int i = 0; i < 2; i++)
      P.iStall[i] = constrain(max(max(2 * learnI[i], learnI[i] + 1.5f), 1.2f * learnPeak[i]), 2.5f, 8.0f);
    P.learned = true; P.save(); dirty = false;
    saveRest(1); obstCount = 0; obstruction = false;
    Serial.printf("apprentissage termine : courant moyen %.2f / %.2f A, pointe en marche %.2f / %.2f A\n", learnI[0], learnI[1], learnPeak[0], learnPeak[1]);
    setState(St::CLOSED);
  }

  // ------------------------------------------------------------ entrées
  struct Deb { bool v = false; uint8_t n = 0; bool rose = false; };
  Deb dPP, dFoto, dRadio, dStop, dBtn;
  uint32_t btnSince = 0; bool btnLong = false;
  static void deb(Deb &d, bool raw) {
    d.rose = false;
    if (raw == d.v) { d.n = 0; return; }
    if (++d.n * TICK_MS >= 30) { d.v = raw; d.n = 0; d.rose = raw; }
  }
  void readInputs() {
    deb(dPP, !digitalRead(PIN_PP));           // vrai = contact fermé
    deb(dRadio, !digitalRead(PIN_RADIO));
    deb(dFoto, !digitalRead(PIN_FOTO));
    deb(dStop, !digitalRead(PIN_STOP));
    deb(dBtn, !digitalRead(PIN_BTN_LEARN));
    inPP = dPP.v; inRadio = dRadio.v;
    inFoto = P.fotoNC ? !dFoto.v : dFoto.v;
    inStop = P.stopNC ? !dStop.v : dStop.v;
    for (int i = 0; i < 2; i++) {
      float a = analogReadMilliVolts(PIN_ISENSE[i]) / MV_PER_AMP;
      L[i].amps += 0.2f * (a - L[i].amps);
    }
    float v = analogReadMilliVolts(PIN_VSENSE) * VBUS_DIVIDER / 1000.0f;
    vbus += 0.05f * (v - vbus);
  }

  void step() {   // logique pas à pas : ouvre / stop / ferme / stop
    switch (state) {
      case St::CLOSED: go(+1); break;
      case St::OPEN: go(-1); break;
      case St::STOPPED: go(lastDir > 0 ? -1 : +1); break;
      case St::FAULT: fault = ""; setState(St::STOPPED); break;   // acquittement ; l'appui suivant relance
      default: halt(0); break;
    }
  }

  // ------------------------------------------------------------ boucle de commande
  void task() {
    esp_task_wdt_add(nullptr);
    for (int k = 0; k < 100; k++) { readInputs(); vTaskDelay(pdMS_TO_TICKS(TICK_MS)); }   // laisse les filtres s'établir
    TickType_t last = xTaskGetTickCount();
    for (;;) {
      vTaskDelayUntil(&last, pdMS_TO_TICKS(TICK_MS));
      esp_task_wdt_reset();
      readInputs();
      uint32_t now = millis();
      bool moving = state == St::OPENING || state == St::CLOSING || state == St::BACKOFF || state == St::LEARN || state == St::BENCH;

      // bouton de la carte : appui court = pas à pas, appui de 3 s = apprentissage
      Cmd c = cmd.exchange(Cmd::NONE);
      if (c == Cmd::ACK) {   // acquittement d'un défaut : ne lance jamais de mouvement
        if (state == St::FAULT) { fault = ""; setState(St::STOPPED); }
        c = Cmd::NONE;
      }
      if (dBtn.rose) { btnSince = now; btnLong = false; }
      if (dBtn.v && !btnLong && now - btnSince > 3000) { btnLong = true; c = Cmd::LEARN; }
      if (!dBtn.v && btnSince && !btnLong) { if (now - btnSince < 3000) c = Cmd::STEP; btnSince = 0; }
      if (!dBtn.v) btnSince = 0;
      if (dPP.rose || dRadio.rose) c = Cmd::STEP;

      // arrêt d'urgence : prioritaire sur tout
      if (P.stopOn && inStop) {
        if (moving || state == St::PAUSE) { stopAll(); setState(St::STOPPED); Serial.println("entree STOP active"); }
        c = Cmd::NONE;
      }
      // défaut signalé par un driver pendant qu'il est éveillé (surintensité, surchauffe...)
      if (awake && moving && now - drvPollAt >= DRV_POLL_MS) {
        drvPollAt = now;
        if (!driversOk()) { fail("defaut signale par un driver (surintensite, surchauffe, redemarrage ou liaison SPI)"); continue; }
      }
      // au repos : simple lecture de l'état des drivers une fois par seconde, pour l'affichage (aucune écriture)
      if (!moving && now - drvPollAt >= 1000) {
        drvPollAt = now;
        for (int i = 0; i < 2; i++) drvState[i] = drv::faults(i);
      }
      if (moving && now - moveStart > RUN_MAX_MS) { fail("duree maximale de mouvement depassee"); continue; }

      switch (c) {
        case Cmd::STEP: step(); break;
        case Cmd::STOP: if (state != St::FAULT && state != St::CLOSED && state != St::OPEN) halt(0); break;
        case Cmd::OPEN: if (state != St::OPEN && state != St::OPENING && state != St::FAULT && state != St::LEARN) go(+1); break;
        case Cmd::CLOSE: if (state != St::CLOSED && state != St::CLOSING && state != St::FAULT && state != St::LEARN) go(-1); break;
        case Cmd::LEARN: if (!moving) { fault = ""; pauseUntil = 0; learnStart(); } break;
        case Cmd::BENCH:
          if (!moving && state != St::PAUSE) {
            int i = constrain(benchMotor, 1, 2) - 1, pct = constrain(benchPct, -100, 100);
            if (!wake()) { fail("un driver ne repond pas ou refuse ses reglages (liaison SPI)"); break; }
            enableOutputs();
            moveStart = now; benchUntil = now + constrain(benchMs, 100, 5000);
            L[0].pos = L[1].pos = NAN;      // la position n'est plus garantie après un essai manuel
            saveRest(0);
            benchI = i; benchDir = pct >= 0 ? +1 : -1; benchTarget = abs(pct) / 100.0f;
            L[i].duty = benchRaw ? benchTarget : 0;   // benchRaw : sans rampe, uniquement pour reproduire le défaut du 19 nov.
            drive(i, benchDir, L[i].duty);            // sinon montée progressive ensuite, sur la durée « ramp »
            setState(St::BENCH);
          }
          break;
        default: break;
      }

      switch (state) {
        case St::OPENING: case St::CLOSING: {
          if (state == St::CLOSING && P.fotoOn && inFoto && !halting) {   // décélération courte, puis réouverture
            Serial.println("photocellule : reouverture"); reversal = false;
            halt(+1, FOTO_STOP_MS);
            if (state != St::CLOSING) break;
          }
          Res r = tickMove();
          if (r == Res::RUN) break;
          bool wasClosing = state == St::CLOSING;
          if (halting) {   // fin d'un arrêt commandé (ou blocage rencontré pendant la décélération)
            int8_t nx = haltNext;
            if (nx) pauseThen(nx); else { stopAll(); setState(St::STOPPED); }
            break;
          }
          stopAll();
          if (r == Res::END) {
            obstCount = 0; reversal = false;
            if (wasClosing) obstruction = false;
            saveRest(wasClosing ? 1 : 2);
            openSince = now;
            setState(wasClosing ? St::CLOSED : St::OPEN);
          } else if (r == Res::OVERRUN) {
            L[0].pos = L[1].pos = NAN;
            fail("butee non detectee : moteur debraye ou courroie/cremaillere libre ?");
          } else {   // obstacle
            obstruction = true;
            evPush(EV_OBSTACLE, wasClosing ? "obstacle a la fermeture" : "obstacle a l'ouverture", L[0].amps, L[1].amps, vbus, drvState[0], drvState[1]);
            if (++obstCount >= 2 || reversal) {   // deuxième obstacle de suite : on ne sait plus où sont les vantaux
              L[0].pos = L[1].pos = NAN; obstCount = 0; reversal = false;
              setState(St::STOPPED);
            } else if (wasClosing) { reversal = true; nextDir = +1; pauseUntil = now + REVERSE_PAUSE_MS; setState(St::PAUSE); }
            else { nextDir = -2; pauseUntil = now + REVERSE_PAUSE_MS; setState(St::PAUSE); }   // -2 : simple recul
          }
          break;
        }
        case St::PAUSE:
          if ((int32_t)(now - pauseUntil) < 0) break;
          if (nextDir == -2) {
            if (startMove(-1, true)) { backoffUntil = millis() + BACKOFF_MS; setState(St::BACKOFF); }
          } else if (nextDir < 0 && P.fotoOn && inFoto) setState(St::STOPPED);
          else if (startMove(nextDir, false)) setState(nextDir > 0 ? St::OPENING : St::CLOSING);
          break;
        case St::BACKOFF:
          if (tickMove() != Res::RUN) { L[0].pos = L[1].pos = NAN; stopAll(); setState(St::STOPPED); }   // blocage pendant le recul : position perdue
          else if ((int32_t)(now - backoffUntil) >= 0) { stopAll(); setState(St::STOPPED); }
          break;
        case St::LEARN: learnTick(); break;
        case St::BENCH:
          if (L[benchI].duty < benchTarget) {
            L[benchI].duty = min(benchTarget, L[benchI].duty + (float)TICK_MS / max<float>(P.rampMs, 50));
            drive(benchI, benchDir, L[benchI].duty);
          }
          if ((int32_t)(now - benchUntil) >= 0) {
            Serial.printf("banc : courant en fin d'essai %.2f / %.2f A\n", L[0].amps, L[1].amps);
            stopAll(); setState(St::STOPPED);
          }
          break;
        case St::OPEN:
          if (P.fotoOn && inFoto) openSince = now;
          if (P.autoCloseS && now - openSince > P.autoCloseS * 1000UL) go(-1);
          break;
        default: break;
      }

      // feu clignotant
      St s = state;
      bool lamp = s == St::OPENING || s == St::CLOSING || s == St::PAUSE || s == St::BACKOFF || s == St::LEARN;
      digitalWrite(PIN_LAMP, lamp && (!P.lampBlink || (now / 500) % 2 == 0));

      // au repos : veille des drivers, sauvegarde différée de la course recalée
      bool rest = s == St::STOPPED || s == St::CLOSED || s == St::OPEN || s == St::FAULT;
      if (rest && awake && now - idleSince > IDLE_SLEEP_MS) sleepDrivers();
      if (rest && dirty) { P.save(); dirty = false; }
    }
  }
};
