// SPDX-License-Identifier: GPL-3.0-or-later
// Journal des événements, conservé en mémoire permanente (NVS) : démarrages et leur cause, défauts, obstacles,
// reconnexions Wi-Fi. Les JOURNAL_N derniers sont gardés ; le plus ancien est écrasé.
// La tâche de commande ne touche jamais à la mémoire flash : elle dépose l'événement dans une file (evPush),
// et la boucle principale l'enregistre (journalPoll).
#pragma once
#include <Arduino.h>
#include <Preferences.h>
#include <esp_system.h>
#include <time.h>

enum : uint8_t { EV_BOOT = 1, EV_FAULT = 2, EV_OBSTACLE = 3, EV_WIFI = 4 };
constexpr int JOURNAL_N = 20;

struct JEntry {
  uint32_t t;        // heure (secondes Unix), 0 = inconnue
  uint32_t up;       // secondes écoulées depuis le démarrage
  uint16_t boot;     // numéro du démarrage
  uint8_t kind;      // EV_*, 0 = case vide
  uint8_t drv[2];    // état des drivers (FAULT_SUMMARY, 0xFF = pas de réponse)
  int16_t cA[2];     // courants, en centièmes d'ampère
  uint16_t dV;       // tension du bus, en dixièmes de volt
  char msg[60];
};

struct Ev { uint8_t kind; uint8_t drv[2]; int16_t cA[2]; uint16_t dV; uint32_t ms; char msg[60]; };
inline QueueHandle_t evQ = nullptr;

// dépôt d'un événement, sans attente : utilisable depuis la tâche de commande
inline void evPush(uint8_t kind, const char *msg, float i1 = 0, float i2 = 0, float vbus = 0, int d1 = 0, int d2 = 0) {
  if (!evQ) return;
  Ev e{};
  e.kind = kind; e.ms = millis();
  e.cA[0] = (int16_t)(i1 * 100); e.cA[1] = (int16_t)(i2 * 100); e.dV = (uint16_t)(vbus * 10);
  e.drv[0] = (uint8_t)d1; e.drv[1] = (uint8_t)d2;
  strlcpy(e.msg, msg, sizeof(e.msg));
  for (char *p = e.msg; *p; p++) if (*p == '"' || *p == '\\' || (uint8_t)*p < 32) *p = ' ';   // reste valide en JSON
  xQueueSend(evQ, &e, 0);
}

namespace journal {
inline JEntry ent[JOURNAL_N];
inline uint8_t head = 0;          // prochaine case à écrire
inline uint16_t boots = 0;
inline bool timeKnown = false;

inline uint32_t nowEpoch() { time_t t = time(nullptr); return t > 1700000000 ? (uint32_t)t : 0; }

inline void store(int i) {
  Preferences p; p.begin("journal", false);
  char k[6]; snprintf(k, sizeof(k), "e%d", i);
  p.putBytes(k, &ent[i], sizeof(JEntry));
  p.putUChar("head", head);
  p.end();
}

inline void add(const Ev &e) {
  JEntry &j = ent[head];
  j = JEntry{};
  j.t = nowEpoch(); j.up = e.ms / 1000; j.boot = boots; j.kind = e.kind;
  j.drv[0] = e.drv[0]; j.drv[1] = e.drv[1]; j.cA[0] = e.cA[0]; j.cA[1] = e.cA[1]; j.dV = e.dV;
  memcpy(j.msg, e.msg, sizeof(j.msg)); j.msg[sizeof(j.msg) - 1] = 0;
  int i = head;
  head = (head + 1) % JOURNAL_N;
  store(i);
}

inline void clear() {   // efface les événements ; le compteur de démarrages est gardé
  for (int i = 0; i < JOURNAL_N; i++) ent[i] = JEntry{};
  head = 0;
  Preferences p; p.begin("journal", false);
  for (int i = 0; i < JOURNAL_N; i++) { char k[6]; snprintf(k, sizeof(k), "e%d", i); p.remove(k); }
  p.putUChar("head", 0);
  p.end();
}

inline const char *resetCause() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON: return "mise sous tension ou bouton RESET";
    case ESP_RST_SW: return "redemarrage logiciel (mise a jour)";
    case ESP_RST_PANIC: return "PLANTAGE du programme";
    case ESP_RST_INT_WDT: case ESP_RST_TASK_WDT: case ESP_RST_WDT: return "CHIEN DE GARDE : programme bloque";
    case ESP_RST_BROWNOUT: return "CHUTE DE TENSION de l'alimentation 3,3 V";
    case ESP_RST_USB: return "redemarrage demande par USB";
    default: return "cause inconnue";
  }
}
}  // namespace journal

inline void journalBegin() {
  using namespace journal;
  Preferences p; p.begin("journal", false);
  for (int i = 0; i < JOURNAL_N; i++) {
    char k[6]; snprintf(k, sizeof(k), "e%d", i);
    if (p.getBytesLength(k) != sizeof(JEntry) || p.getBytes(k, &ent[i], sizeof(JEntry)) != sizeof(JEntry)) ent[i] = JEntry{};
    ent[i].msg[sizeof(ent[i].msg) - 1] = 0;
  }
  head = p.getUChar("head", 0) % JOURNAL_N;
  boots = p.getUShort("boots", 0) + 1;
  p.putUShort("boots", boots);
  p.end();
  char m[60]; snprintf(m, sizeof(m), "demarrage : %s", resetCause());
  evPush(EV_BOOT, m);
}

inline void journalPoll() {   // boucle principale
  using namespace journal;
  Ev e;
  while (evQ && xQueueReceive(evQ, &e, 0) == pdTRUE) add(e);
  // dès que l'heure est connue (NTP), date les événements de ce démarrage enregistrés sans heure
  if (!timeKnown && nowEpoch()) {
    timeKnown = true;
    uint32_t now = nowEpoch(), up = millis() / 1000;
    for (int i = 0; i < JOURNAL_N; i++)
      if (ent[i].kind && ent[i].boot == boots && ent[i].t == 0) { ent[i].t = now - (up - ent[i].up); store(i); }
  }
}
