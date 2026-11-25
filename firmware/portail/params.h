// SPDX-License-Identifier: GPL-3.0-or-later
// Réglages persistants (NVS). Modifiables par la console série (« @p nom valeur ») et par la page web.
// Chaque réglage est enregistré sous son propre nom : ajouter un réglage dans une version future ne touche pas
// aux autres, et un réglage absent prend simplement sa valeur par défaut.
#pragma once
#include <Preferences.h>

// Ancien format (jusqu'au 20 nov. 2026) : tout dans un seul bloc « params ». Structure figée, ne plus la modifier :
// elle ne sert qu'à relire une fois ce bloc pour le recopier dans le nouveau format.
struct ParamsV0 {
  bool inv[2]; uint8_t cruisePct; uint8_t slowPct; uint16_t rampMs; uint8_t slowZonePct; float iStall[2];
  uint32_t travelMs[2][2]; bool learned; bool fotoOn; bool fotoNC; bool stopOn; bool stopNC; bool lampBlink;
  uint16_t preflashMs; uint16_t autoCloseS;
};

struct Params {
  // sens de rotation : si vrai, PH = 1 ouvre ; sinon PH = 0 ouvre. À régler au premier essai.
  bool     inv[2]        = {false, true};   // les deux vantaux coulissent en sens opposé
  uint8_t  cruisePct     = 100;             // croisière sans découpage : le DRV8245 chauffe surtout quand il commute
  uint8_t  slowPct       = 40;              // rapport cyclique lent (approche des butées, position inconnue)
  uint16_t rampMs        = 800;             // durée de la rampe 0 -> croisière
  uint8_t  slowZonePct   = 15;              // derniers % de la course parcourus au ralenti
  float    iStall[2]     = {5.0f, 5.0f};    // seuil de blocage (A)
  float    iSlow[2]      = {0, 0};          // seuil réduit pendant l'approche lente des butées (A) ; 0 = seuil normal
  uint16_t stopRampMs    = 300;             // arrêt commandé : durée de la décélération croisière -> 0 (0 = arrêt net)
  uint32_t travelMs[2][2] = {{0, 0}, {0, 0}}; // [vantail][0 = fermeture, 1 = ouverture], à la vitesse de croisière
  bool     learned       = false;
  bool     fotoOn        = true;            // photocellule utilisée
  bool     fotoNC        = true;            // contact normalement fermé (faisceau libre = contact fermé)
  bool     stopOn        = true;            // entrée STOP utilisée
  bool     stopNC        = true;            // normalement fermé : sans bouton, ponter STOP au +12V_ACC ou « @p stopOn 0 »
  bool     lampBlink     = true;            // vrai : la carte fait clignoter ; faux : feu auto-clignotant, sortie fixe
  uint16_t preflashMs    = 0;               // préavis avant mouvement
  uint16_t autoCloseS    = 0;               // fermeture automatique (0 = non)
  uint16_t openAlertMin  = 10;              // alerte HomeKit « resté ouvert » après ce nombre de minutes (0 = jamais)

  // Table des réglages entiers : nom NVS (15 caractères au plus) et accès. Les deux seuils (flottants) sont à part.
  template <typename F> void each(F f) {
    auto g = [&](const char *k, auto &ref) { uint32_t v = (uint32_t)ref; f(k, v); ref = (std::remove_reference_t<decltype(ref)>)v; };
    g("inv1", inv[0]); g("inv2", inv[1]); g("cruise", cruisePct); g("slow", slowPct); g("ramp", rampMs); g("zone", slowZonePct);
    g("t1f", travelMs[0][0]); g("t1o", travelMs[0][1]); g("t2f", travelMs[1][0]); g("t2o", travelMs[1][1]);
    g("appris", learned); g("fotoOn", fotoOn); g("fotoNC", fotoNC); g("stopOn", stopOn); g("stopNC", stopNC);
    g("clignote", lampBlink); g("preavis", preflashMs); g("autoferme", autoCloseS); g("alertemin", openAlertMin);
    g("arret", stopRampMs);
  }

  void load() {
    Preferences p;
    p.begin("portail", false);
    if (!p.isKey("fmt")) {   // premier démarrage dans le nouveau format : reprise de l'ancien bloc s'il existe
      ParamsV0 o;
      if (p.getBytesLength("params") == sizeof(o) && p.getBytes("params", &o, sizeof(o)) == sizeof(o)) {
        inv[0] = o.inv[0]; inv[1] = o.inv[1]; cruisePct = o.cruisePct; slowPct = o.slowPct; rampMs = o.rampMs;
        slowZonePct = o.slowZonePct; iStall[0] = o.iStall[0]; iStall[1] = o.iStall[1];
        memcpy(travelMs, o.travelMs, sizeof(travelMs)); learned = o.learned; fotoOn = o.fotoOn; fotoNC = o.fotoNC;
        stopOn = o.stopOn; stopNC = o.stopNC; lampBlink = o.lampBlink; preflashMs = o.preflashMs; autoCloseS = o.autoCloseS;
      }
      if (p.isKey("alerteouv")) openAlertMin = p.getUShort("alerteouv", openAlertMin);
      p.end();
      save();
      p.begin("portail", false);
      p.putUChar("fmt", 1);
      p.remove("params"); p.remove("alerteouv");
      p.end();
      return;
    }
    each([&](const char *k, uint32_t &v) { v = p.getUInt(k, v); });
    iStall[0] = p.getFloat("seuil1", iStall[0]); iStall[1] = p.getFloat("seuil2", iStall[1]);
    iSlow[0] = p.getFloat("seuilL1", iSlow[0]); iSlow[1] = p.getFloat("seuilL2", iSlow[1]);
    p.end();
  }
  void save() {   // n'écrit que ce qui a changé (ménage la mémoire flash)
    Preferences p;
    p.begin("portail", false);
    each([&](const char *k, uint32_t &v) { if (!p.isKey(k) || p.getUInt(k, ~v) != v) p.putUInt(k, v); });
    const char *fk[4] = {"seuil1", "seuil2", "seuilL1", "seuilL2"};
    float fv[4] = {iStall[0], iStall[1], iSlow[0], iSlow[1]};
    for (int i = 0; i < 4; i++) if (!p.isKey(fk[i]) || p.getFloat(fk[i], -1) != fv[i]) p.putFloat(fk[i], fv[i]);
    p.end();
  }
};

// dernier état de repos connu (0 = inconnu, 1 = fermé, 2 = ouvert)
inline uint8_t loadRest() {
  Preferences p; p.begin("portail", true); uint8_t v = p.getUChar("rest", 0); p.end(); return v;
}
inline void saveRest(uint8_t v) {
  Preferences p; p.begin("portail", false); if (p.getUChar("rest", 255) != v) p.putUChar("rest", v); p.end();
}
