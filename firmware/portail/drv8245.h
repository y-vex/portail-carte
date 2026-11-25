// SPDX-License-Identifier: GPL-3.0-or-later
// DRV8245S-Q1 (variante SPI « S », boîtier VQFN-HR) : réglages et diagnostics par SPI.
// Carte v0.4 : la liaison SPI réutilise les fils de la v0.3, avec une sortie de données par driver.
// SPI logiciel : la donnée change sur le front montant de l'horloge et se lit sur le front descendant
// (fiche technique SLVSFJ1E, § 7.4). Appelé uniquement depuis la tâche de commande.
#pragma once
#include "config.h"

namespace drv {
// registres (§ 8.1)
constexpr uint8_t FAULT_SUMMARY = 0x01, STATUS1 = 0x02, COMMAND = 0x08, SPI_IN = 0x09,
                  CONFIG1 = 0x0A, CONFIG2 = 0x0B, CONFIG3 = 0x0C, CONFIG4 = 0x0D;
// FAULT_SUMMARY
constexpr uint8_t F_SPI_ERR = 0x80, F_POR = 0x40, F_FAULT = 0x20, F_VMOV = 0x10, F_VMUV = 0x08, F_OCP = 0x04, F_TSD = 0x02;
// valeurs écrites
constexpr uint8_t CMD_CLEAR_UNLOCK = 0x91;   // CLR_FLT, registre SPI_IN déverrouillé (10b), registres CONFIG déverrouillés (01b)
constexpr uint8_t CFG1 = 0x12;               // surtension VM (35 V) : reprise automatique ; surintensité et surchauffe : verrouillées
constexpr uint8_t CFG2 = 0x04;               // S_ITRIP = 100b : 1,98 V sur IPROPI, soit 10,6 A avec 1,2 kΩ (gain 1/6400)
// CONFIG3 : TOFF 30 µs (01b), pente S_SR sur les bits 4..2, mode PH/EN (00b).
// Pentes (fiche SLVSFJ1E § 6.5.6) : 0 = 1,5  1 = 5  2 = 9,8  3 = 14  4 = 20  5 = 26  6 = 38  7 = 50 V/µs.
// Réglable pendant les essais (« pente » dans la page web, non enregistré) ; pris en compte à la configuration suivante.
inline volatile uint8_t srCode = 7;
inline uint8_t cfg3() { return 0x40 | ((srCode & 7) << 2); }
constexpr uint8_t CFG4 = 0x04;               // DRVOFF = broche ET registre ; EN et PH = broche OU registre
constexpr uint8_t IN_OFF = 0x0C;             // S_DRVOFF = 1 : sorties en haute impédance

inline void begin() {
  pinMode(PIN_SCLK, OUTPUT); digitalWrite(PIN_SCLK, LOW);
  pinMode(PIN_SDI, OUTPUT); digitalWrite(PIN_SDI, LOW);
  for (int i = 0; i < 2; i++) {
    pinMode(PIN_CS[i], OUTPUT); digitalWrite(PIN_CS[i], HIGH);
    pinMode(PIN_SDO[i], INPUT_PULLDOWN);      // sortie en haute impédance hors trame : niveau défini
  }
}

// échange une trame de 16 bits ; renvoie le mot lu (les deux bits de poids fort valent 1 si le driver répond)
inline uint16_t xfer(int i, uint16_t out) {
  uint16_t in = 0;
  digitalWrite(PIN_SCLK, LOW);
  digitalWrite(PIN_CS[i], LOW);
  delayMicroseconds(2);
  for (int b = 15; b >= 0; b--) {
    digitalWrite(PIN_SDI, (out >> b) & 1);
    digitalWrite(PIN_SCLK, HIGH);
    delayMicroseconds(2);
    in = (in << 1) | (digitalRead(PIN_SDO[i]) ? 1 : 0);
    digitalWrite(PIN_SCLK, LOW);
    delayMicroseconds(2);
  }
  digitalWrite(PIN_CS[i], HIGH);
  delayMicroseconds(2);
  return in;
}
inline bool answered(uint16_t w) { return (w & 0xC000) == 0xC000; }
inline void wr(int i, uint8_t reg, uint8_t val) { xfer(i, ((uint16_t)(reg & 0x3F) << 8) | val); }
// lit un registre ; renvoie -1 si le driver ne répond pas (pas de 24 V, liaison coupée)
inline int rd(int i, uint8_t reg) {
  uint16_t w = xfer(i, 0x4000 | ((uint16_t)(reg & 0x3F) << 8));
  return answered(w) ? (w & 0xFF) : -1;
}

// acquitte la mise sous tension, écrit les réglages et les relit ; sorties laissées en haute impédance
inline bool configure(int i) {
  wr(i, COMMAND, CMD_CLEAR_UNLOCK);
  wr(i, SPI_IN, IN_OFF);
  wr(i, CONFIG1, CFG1);
  wr(i, CONFIG2, CFG2);
  wr(i, CONFIG3, cfg3());
  wr(i, CONFIG4, CFG4);
  wr(i, COMMAND, CMD_CLEAR_UNLOCK);
  if (rd(i, CONFIG1) != CFG1 || rd(i, CONFIG2) != CFG2 || rd(i, CONFIG3) != cfg3() || rd(i, CONFIG4) != CFG4) return false;
  if (rd(i, SPI_IN) != IN_OFF) return false;
  int f = rd(i, FAULT_SUMMARY);
  return f >= 0 && !(f & (F_POR | F_OCP | F_TSD));
}
// sens (bit S_PH_IN2) et sorties actives ; off = true : haute impédance
inline void setInputs(int i, bool ph, bool off) { wr(i, SPI_IN, (off ? IN_OFF : 0x00) | (ph ? 0x01 : 0x00)); }
// état du driver : -1 = pas de réponse, sinon FAULT_SUMMARY
inline int faults(int i) { return rd(i, FAULT_SUMMARY); }
inline void clearFaults(int i) { wr(i, COMMAND, CMD_CLEAR_UNLOCK); }
}  // namespace drv
