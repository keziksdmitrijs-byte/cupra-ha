/*
 * Cupra card for Home Assistant
 * Served by the "cupra" integration – no separate install needed.
 * Layout follows the powertrain (EV / PHEV / ICE), the outline follows the model.
 */
const CARD_VERSION = "0.2.1";

const I18N = {
  en: {
    charging: "Charging", moving: "Driving", climatising: "Climatising", open: "Open",
    unlocked: "Unlocked", parked: "Parked", unknown: "No data",
    locked: "Locked", unlockedShort: "Unlocked", battery: "Battery", fuel: "Fuel",
    range: "Range", total: "Total range", electric: "Electric", odometer: "Odometer",
    outside: "Outside", service: "Service", oil: "Oil change", days: "d", km: "km",
    left: "left", power: "Power", target: "Target", plugged: "Cable connected",
    unplugged: "Cable not connected", climate: "Climate", on: "On", off: "Off",
    lock: "Lock", unlock: "Unlock", flash: "Flash", refresh: "Refresh", charge: "Charge",
    ago: "ago", now: "just now", min: "min", h: "h", stale: "Data is old – the car may be asleep",
    readonly: "Read-only: EU Data Act", live: "Live: My Cupra",
    waiting: "Waiting for the first EU Data Act snapshot", nosub: "Create a continuous data request on the EU Data Act portal",
    doors: "Doors", windows: "Windows", allClosed: "All closed", tyres: "Tyres", v12: "12V battery",
    pickEntity: "Choose the Cupra vehicle sensor", trip: "Trip", consumption: "Consumption",
    lockLbl: "Central lock", somethingOpen: "Something is open", trunk: "Tailgate", hood: "Bonnet", sunroof: "Sunroof",
  },
  ru: {
    charging: "Заряжается", moving: "В движении", climatising: "Работает климат", open: "Открыт",
    unlocked: "Не заперт", parked: "Припаркован", unknown: "Нет данных",
    locked: "Закрыт", unlockedShort: "Открыт", battery: "Батарея", fuel: "Топливо",
    range: "Запас хода", total: "Общий запас", electric: "Электро", odometer: "Пробег",
    outside: "Снаружи", service: "ТО", oil: "Замена масла", days: "дн", km: "км",
    left: "осталось", power: "Мощность", target: "Цель", plugged: "Кабель подключён",
    unplugged: "Кабель не подключён", climate: "Климат", on: "Вкл", off: "Выкл",
    lock: "Закрыть", unlock: "Открыть", flash: "Фары", refresh: "Обновить", charge: "Зарядка",
    ago: "назад", now: "только что", min: "мин", h: "ч", stale: "Данные устарели — машина, возможно, спит",
    readonly: "Только чтение: EU Data Act", live: "Онлайн: My Cupra",
    waiting: "Ждём первый снимок EU Data Act", nosub: "Создайте непрерывный запрос данных на портале EU Data Act",
    doors: "Двери", windows: "Окна", allClosed: "Всё закрыто", tyres: "Шины", v12: "АКБ 12V",
    pickEntity: "Выберите сенсор автомобиля Cupra", trip: "Поездка", consumption: "Расход",
    lockLbl: "Центральный замок", somethingOpen: "Что-то открыто", trunk: "Багажник", hood: "Капот", sunroof: "Люк",
  },
  lv: {
    charging: "Uzlādējas", moving: "Brauc", climatising: "Klimatizē", open: "Atvērta",
    unlocked: "Atslēgta", parked: "Novietota", unknown: "Nav datu",
    locked: "Aizslēgta", unlockedShort: "Atslēgta", battery: "Akumulators", fuel: "Degviela",
    range: "Nobraukums", total: "Kopējais", electric: "Elektro", odometer: "Odometrs",
    outside: "Ārā", service: "Apkope", oil: "Eļļas maiņa", days: "d", km: "km",
    left: "atlicis", power: "Jauda", target: "Mērķis", plugged: "Kabelis pievienots",
    unplugged: "Kabelis nav pievienots", climate: "Klimats", on: "Iesl.", off: "Izsl.",
    lock: "Aizslēgt", unlock: "Atslēgt", flash: "Lukturi", refresh: "Atjaunot", charge: "Uzlāde",
    ago: "atpakaļ", now: "tikko", min: "min", h: "h", stale: "Dati ir veci — auto, iespējams, guļ",
    readonly: "Tikai lasīšana: EU Data Act", live: "Tiešsaistē: My Cupra",
    waiting: "Gaidām pirmo EU Data Act momentuzņēmumu", nosub: "Izveidojiet nepārtrauktu datu pieprasījumu EU Data Act portālā",
    doors: "Durvis", windows: "Logi", allClosed: "Viss aizvērts", tyres: "Riepas", v12: "12V akumulators",
    pickEntity: "Izvēlieties Cupra auto sensoru", trip: "Brauciens", consumption: "Patēriņš",
    lockLbl: "Centrālā atslēga", somethingOpen: "Kaut kas atvērts", trunk: "Bagāžnieks", hood: "Pārsegs", sunroof: "Lūka",
  },
};

const MODELS = {
  born: { name: "Born", body: "hatch", powertrain: "ev" },
  tavascan: { name: "Tavascan", body: "coupe_suv", powertrain: "ev" },
  raval: { name: "Raval", body: "hatch", powertrain: "ev" },
  terramar: { name: "Terramar", body: "suv" },
  formentor: { name: "Formentor", body: "coupe_suv" },
  leon: { name: "Leon", body: "hatch" },
  leon_st: { name: "Leon Sportstourer", body: "estate" },
  ateca: { name: "Ateca", body: "suv", powertrain: "ice" },
};

/* Top-view proportions per body style (viewBox 0 0 200 400, nose up). */
const BODIES = {
  hatch:     { len: 318, wid: 150, nose: 32, tail: 20, hood: 0.27, wind: 0.11, roof: 0.33, rear: 0.07, rails: false },
  estate:    { len: 362, wid: 150, nose: 32, tail: 16, hood: 0.24, wind: 0.10, roof: 0.42, rear: 0.06, rails: true },
  suv:       { len: 350, wid: 166, nose: 22, tail: 18, hood: 0.25, wind: 0.10, roof: 0.38, rear: 0.07, rails: true },
  coupe_suv: { len: 352, wid: 160, nose: 30, tail: 30, hood: 0.26, wind: 0.11, roof: 0.25, rear: 0.17, rails: false },
};

const STYLE = `
  :host { --cu-copper: #c58b5c; --cu-copper-2: color-mix(in srgb, #e2b48a 75%, var(--primary-text-color, #fff)); --cu-alert: #e05a47; --cu-ok: #3fb68b; --cu-muted: var(--secondary-text-color); }
  ha-card { overflow: hidden; padding: 16px; position: relative; }
  .head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
  .title { font-size: 1.25em; font-weight: 600; letter-spacing: .02em; line-height: 1.2; }
  .sub { color: var(--cu-muted); font-size: .85em; margin-top: 2px; }
  .chip { display: inline-flex; align-items: center; gap: 4px; border-radius: 14px; padding: 3px 10px; font-size: .8em; font-weight: 600;
          background: color-mix(in srgb, var(--cu-copper) 18%, transparent); color: var(--cu-copper-2); white-space: nowrap; }
  .chip.charging { background: color-mix(in srgb, var(--cu-ok) 20%, transparent); color: var(--cu-ok); }
  .chip.open, .chip.unlocked { background: color-mix(in srgb, var(--cu-alert) 20%, transparent); color: var(--cu-alert); }
  .chip ha-icon { --mdc-icon-size: 16px; }
  .hero { display: grid; grid-template-columns: 1fr 1.05fr; gap: 12px; align-items: center; margin-top: 10px; }
  .car { position: relative; display: flex; justify-content: center; }
  .car svg { width: 100%; max-width: 170px; height: auto; }
  .hero.photo { grid-template-columns: 1fr; gap: 6px; }
  .car.photo { flex-direction: column; align-items: center; }
  .car.photo img { width: 100%; max-width: 460px; max-height: 220px; object-fit: contain; display: block; border-radius: 10px; }
  .car.photo .fallback { display: none; }
  .car.photo.broken img { display: none; }
  .car.photo.broken .fallback { display: flex; justify-content: center; }
  .hero.photo .energy { max-width: 460px; width: 100%; margin: 0 auto; }
  .energy { display: flex; flex-direction: column; gap: 12px; }
  .ring { position: relative; width: 100%; max-width: 170px; margin: 0 auto; }
  .ring svg { width: 100%; height: auto; display: block; }
  .ring .center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .big { font-size: 2em; font-weight: 700; line-height: 1; }
  .big small { font-size: .45em; font-weight: 600; margin-left: 2px; color: var(--cu-muted); }
  .muted { color: var(--cu-muted); font-size: .8em; }
  .bar { display: flex; flex-direction: column; gap: 4px; }
  .bar .row { display: flex; justify-content: space-between; align-items: baseline; font-size: .85em; }
  .bar .row b { font-size: 1.35em; }
  .track { height: 10px; border-radius: 6px; background: var(--divider-color, rgba(127,127,127,.25)); position: relative; overflow: hidden; }
  .fill { position: absolute; inset: 0 auto 0 0; border-radius: 6px; background: linear-gradient(90deg, var(--cu-copper), var(--cu-copper-2)); transition: width .6s ease; }
  .fill.fuel { background: linear-gradient(90deg, #8a8f98, #c9ced6); }
  .fill.low { background: var(--cu-alert); }
  .marker { position: absolute; top: -2px; bottom: -2px; width: 2px; background: var(--primary-text-color); opacity: .6; }
  .total { display: flex; align-items: center; gap: 6px; font-size: .9em; }
  .total b { font-size: 1.2em; }
  .chargebox { display: flex; gap: 10px; flex-wrap: wrap; font-size: .82em; color: var(--cu-ok); }
  .chargebox span { display: inline-flex; align-items: center; gap: 3px; }
  .chargebox ha-icon { --mdc-icon-size: 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: 8px; margin-top: 14px; }
  .tile { background: var(--secondary-background-color, rgba(127,127,127,.08)); border-radius: 12px; padding: 8px 10px; min-width: 0; }
  .tile .lbl { color: var(--cu-muted); font-size: .72em; display: flex; align-items: center; gap: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tile .lbl ha-icon { --mdc-icon-size: 14px; }
  .tile .val { font-size: 1.05em; font-weight: 600; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tile .val small { display: block; font-size: .72em; font-weight: 500; color: var(--cu-muted); }
  .tile.warn .val { color: var(--cu-alert); }
  .actions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
  .btn { flex: 1 1 0; min-width: 64px; display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 8px 4px; border-radius: 12px; cursor: pointer;
         background: var(--secondary-background-color, rgba(127,127,127,.08)); border: 1px solid transparent; color: var(--primary-text-color); font: inherit; font-size: .75em; }
  .btn:hover { border-color: var(--cu-copper); }
  .btn.active { background: color-mix(in srgb, var(--cu-copper) 22%, transparent); color: var(--cu-copper-2); }
  .btn[disabled] { opacity: .4; cursor: default; border-color: transparent; }
  .btn ha-icon { --mdc-icon-size: 22px; }
  .foot { display: flex; justify-content: space-between; gap: 8px; margin-top: 10px; font-size: .72em; color: var(--cu-muted); }
  .warnline { margin-top: 10px; font-size: .8em; color: var(--warning-color, #e0a030); display: flex; gap: 6px; align-items: center; }
  .warnline ha-icon { --mdc-icon-size: 18px; }
  .open-list { font-size: .8em; color: var(--cu-alert); margin-top: 6px; text-align: center; }
  @media (max-width: 420px) { .hero { grid-template-columns: 1fr; } .car svg { max-width: 140px; } }
`;

function num(v) { return typeof v === "number" && isFinite(v) ? v : null; }
function fmt(v, d = 0) { return v == null ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d }); }

class CupraCard extends HTMLElement {
  static getConfigElement() { return document.createElement("cupra-card-editor"); }

  static getStubConfig(hass) {
    const ent = Object.keys(hass.states).find((e) => e.startsWith("sensor.") && hass.states[e].attributes.integration === "cupra");
    return { entity: ent || "" };
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = { show_actions: true, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._sig = null;
  }

  set hass(hass) {
    this._hass = hass;
    const st = this._config && this._config.entity ? hass.states[this._config.entity] : null;
    const sig = st ? `${st.last_updated}|${st.state}|${JSON.stringify(this._entityStates(st))}|${hass.language}` : `none|${hass.language}`;
    if (sig === this._sig) return;
    this._sig = sig;
    this._render();
  }

  getCardSize() { return 6; }
  getGridOptions() { return { columns: 12, rows: "auto", min_columns: 6 }; }

  _entityStates(st) {
    const ents = (st.attributes && st.attributes.entities) || {};
    const out = {};
    for (const k of ["door_lock", "climate", "charging_switch"]) {
      if (ents[k] && this._hass.states[ents[k]]) out[k] = this._hass.states[ents[k]].state;
    }
    return out;
  }

  _t(key) {
    const lang = ((this._hass && this._hass.language) || "en").slice(0, 2);
    return (I18N[lang] || I18N.en)[key] || I18N.en[key] || key;
  }

  _render() {
    const root = this.shadowRoot;
    const cfg = this._config;
    const st = cfg.entity ? this._hass.states[cfg.entity] : null;
    if (!st) {
      root.innerHTML = `<style>${STYLE}</style><ha-card><div class="muted">${cfg.entity ? `Entity not found: ${cfg.entity}` : this._t("pickEntity")}</div></ha-card>`;
      return;
    }
    const a = st.attributes;
    const s = a.state || {};
    const modelKey = cfg.model && cfg.model !== "auto" ? cfg.model : a.model;
    const model = MODELS[modelKey] || {};
    const body = BODIES[cfg.body || model.body || a.body] || BODIES.hatch;
    let pt = cfg.powertrain && cfg.powertrain !== "auto" ? cfg.powertrain : a.powertrain || model.powertrain;
    if (!pt) pt = num(s.soc) != null ? (num(s.fuel_level) != null ? "phev" : "ev") : "ice";
    const name = cfg.name || a.vehicle_name || "Cupra";
    const modelName = model.name || a.model_name || "";
    const statusKey = st.state in I18N.en ? st.state : "unknown";
    const statusIcon = { charging: "mdi:ev-station", moving: "mdi:car-speed-limiter", climatising: "mdi:air-conditioner", open: "mdi:car-door", unlocked: "mdi:lock-open-variant", parked: "mdi:parking", unknown: "mdi:help" }[statusKey];

    const energy = pt === "ev" ? this._ev(s) : pt === "phev" ? this._phev(s) : this._ice(s);
    const src = a.sources || {};
    const euda = src.eu_data_act || {};
    let warn = "";
    if (euda.status === "no_subscription") warn = this._t("nosub");
    else if (euda.status === "waiting_for_data" && !Object.keys(s).length) warn = this._t("waiting");
    else if (a.stale) warn = this._t("stale");

    root.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="head">
          <div><div class="title">${this._esc(name)}</div><div class="sub">${this._esc(modelName)}${modelName ? " · " : ""}${this._ptLabel(pt)}</div></div>
          <div class="chip ${statusKey}"><ha-icon icon="${statusIcon}"></ha-icon>${this._t(statusKey)}</div>
        </div>
        <div class="hero${cfg.image ? " photo" : ""}">
          ${cfg.image
            ? `<div class="car photo"><img src="${this._esc(cfg.image)}" alt="${this._esc(name)}"><div class="fallback">${this._carSvg(body, s, pt)}</div></div>`
            : `<div class="car">${this._carSvg(body, s, pt)}</div>`}
          <div class="energy">${energy}</div>
        </div>
        ${this._openList(s)}
        <div class="grid">${this._tiles(s, pt)}</div>
        ${cfg.show_actions ? this._actions(a, s, pt) : ""}
        ${warn ? `<div class="warnline"><ha-icon icon="mdi:alert-circle-outline"></ha-icon>${warn}</div>` : ""}
        <div class="foot"><span>${a.commands_available ? this._t("live") : this._t("readonly")}</span><span>${this._age(a.last_seen)}</span></div>
      </ha-card>`;
    const img = root.querySelector(".car.photo img");
    if (img) img.addEventListener("error", () => img.parentElement.classList.add("broken"));
    root.querySelectorAll("[data-act]").forEach((el) => el.addEventListener("click", (ev) => this._act(ev.currentTarget.dataset.act)));
    root.querySelectorAll("[data-more]").forEach((el) => el.addEventListener("click", (ev) => this._more(ev.currentTarget.dataset.more)));
  }

  _esc(v) { return String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  _ptLabel(pt) { return { ev: "EV", phev: "e-HYBRID", ice: "TSI / TDI" }[pt] || ""; }

  _age(iso) {
    if (!iso) return "";
    const diff = (Date.now() - new Date(iso).getTime()) / 60000;
    if (diff < 2) return this._t("now");
    if (diff < 90) return `${Math.round(diff)} ${this._t("min")} ${this._t("ago")}`;
    if (diff < 48 * 60) return `${Math.round(diff / 60)} ${this._t("h")} ${this._t("ago")}`;
    return new Date(iso).toLocaleString();
  }

  /* ---------- energy blocks ---------- */

  _ring(pct, color, inner) {
    const r = 52, c = 2 * Math.PI * r, arc = 0.75;
    const p = Math.max(0, Math.min(100, pct || 0)) / 100;
    return `<div class="ring"><svg viewBox="0 0 120 120">
      <defs><linearGradient id="cg" x1="0" x2="1"><stop offset="0" stop-color="var(--cu-copper)"/><stop offset="1" stop-color="var(--cu-copper-2)"/></linearGradient></defs>
      <circle cx="60" cy="60" r="${r}" fill="none" stroke="var(--divider-color, rgba(127,127,127,.25))" stroke-width="9" stroke-linecap="round"
        stroke-dasharray="${c * arc} ${c}" transform="rotate(135 60 60)"/>
      <circle cx="60" cy="60" r="${r}" fill="none" stroke="${color}" stroke-width="9" stroke-linecap="round"
        stroke-dasharray="${c * arc * p} ${c}" transform="rotate(135 60 60)" style="transition: stroke-dasharray .6s ease"/>
    </svg><div class="center">${inner}</div></div>`;
  }

  _chargeInfo(s) {
    const parts = [];
    if (s.charging) {
      if (num(s.charge_power) != null) parts.push(`<span><ha-icon icon="mdi:flash"></ha-icon>${fmt(s.charge_power, 1)} kW</span>`);
      if (num(s.charge_remaining_min) != null) parts.push(`<span><ha-icon icon="mdi:timer-outline"></ha-icon>${this._dur(s.charge_remaining_min)}</span>`);
      if (num(s.target_soc) != null) parts.push(`<span><ha-icon icon="mdi:flag-checkered"></ha-icon>${fmt(s.target_soc)}%</span>`);
    } else if (s.plug_connected === true) {
      parts.push(`<span><ha-icon icon="mdi:power-plug"></ha-icon>${this._t("plugged")}</span>`);
    }
    return parts.length ? `<div class="chargebox">${parts.join("")}</div>` : "";
  }

  _dur(min) { const h = Math.floor(min / 60), m = Math.round(min % 60); return h ? `${h} ${this._t("h")} ${m} ${this._t("min")}` : `${m} ${this._t("min")}`; }

  _ev(s) {
    const soc = num(s.soc);
    const color = soc != null && soc < 15 ? "var(--cu-alert)" : "url(#cg)";
    const inner = `<div class="big">${fmt(soc)}<small>%</small></div>
      <div class="muted">${fmt(num(s.range_electric) ?? num(s.range_total))} ${this._t("km")}</div>`;
    return `<div data-more="soc" style="cursor:pointer">${this._ring(soc, color, inner)}</div>${this._chargeInfo(s)}`;
  }

  _bar(label, icon, pct, range, cls, target, moreKey) {
    const p = Math.max(0, Math.min(100, pct ?? 0));
    const low = pct != null && pct < 15 ? " low" : "";
    return `<div class="bar" data-more="${moreKey}" style="cursor:pointer">
      <div class="row"><span class="muted"><ha-icon icon="${icon}" style="--mdc-icon-size:15px"></ha-icon> ${label}</span>
        <span><b>${fmt(pct)}</b>%&nbsp;&nbsp;<span class="muted">${fmt(range)} ${this._t("km")}</span></span></div>
      <div class="track"><div class="fill ${cls}${low}" style="width:${p}%"></div>${target != null ? `<div class="marker" style="left:${target}%"></div>` : ""}</div>
    </div>`;
  }

  _phev(s) {
    const total = num(s.range_total) ?? ((num(s.range_electric) || 0) + (num(s.range_fuel) || 0) || null);
    return `
      <div class="total"><ha-icon icon="mdi:map-marker-distance"></ha-icon><span class="muted">${this._t("total")}</span><b>${fmt(total)}</b> ${this._t("km")}</div>
      ${this._bar(this._t("battery"), "mdi:battery-charging-high", num(s.soc), num(s.range_electric), "", num(s.target_soc), "soc")}
      ${this._bar(this._t("fuel"), "mdi:gas-station", num(s.fuel_level), num(s.range_fuel), "fuel", null, "fuel_level")}
      ${this._chargeInfo(s)}`;
  }

  _ice(s) {
    const lvl = num(s.fuel_level);
    const color = lvl != null && lvl < 15 ? "var(--cu-alert)" : "url(#cg)";
    const inner = `<ha-icon icon="mdi:gas-station" style="color:var(--cu-muted)"></ha-icon>
      <div class="big">${fmt(lvl)}<small>%</small></div>
      <div class="muted">${fmt(num(s.range_fuel) ?? num(s.range_total))} ${this._t("km")}</div>`;
    return `<div data-more="fuel_level" style="cursor:pointer">${this._ring(lvl, color, inner)}</div>`;
  }

  /* ---------- tiles ---------- */

  _tiles(s, pt) {
    const t = [];
    const tile = (icon, label, val, more, warn = false) =>
      t.push(`<div class="tile${warn ? " warn" : ""}" ${more ? `data-more="${more}" style="cursor:pointer"` : ""}><div class="lbl"><ha-icon icon="${icon}"></ha-icon>${label}</div><div class="val">${val}</div></div>`);
    if (num(s.mileage) != null) tile("mdi:counter", this._t("odometer"), `${fmt(s.mileage)} ${this._t("km")}`, "mileage");
    if (num(s.outside_temp) != null) tile("mdi:thermometer", this._t("outside"), `${fmt(s.outside_temp, 1)} °C`, "outside_temp");
    if (typeof s.locked === "boolean") {
      const openNow = s.doors_open || s.windows_open;
      tile(s.locked ? "mdi:lock" : "mdi:lock-open-variant", this._t("lockLbl"),
        `${s.locked ? this._t("locked") : this._t("unlockedShort")}<small>${openNow ? this._t("somethingOpen") : this._t("allClosed")}</small>`, "locked", !s.locked || openNow);
    }
    if (typeof s.climate_on === "boolean" && pt !== "ice")
      tile("mdi:air-conditioner", this._t("climate"), s.climate_on ? `${this._t("on")}${num(s.climate_remaining_min) ? `<small>${fmt(s.climate_remaining_min)} ${this._t("min")} ${this._t("left")}</small>` : ""}` : this._t("off"), "climate_on");
    if (num(s.inspection_days) != null || num(s.inspection_km) != null) {
      const parts = [];
      if (num(s.inspection_days) != null) parts.push(`${fmt(s.inspection_days)} ${this._t("days")}`);
      if (num(s.inspection_km) != null) parts.push(`${fmt(s.inspection_km)} ${this._t("km")}`);
      tile("mdi:car-wrench", this._t("service"), parts[0] + (parts[1] ? `<small>${parts[1]}</small>` : ""), "inspection_days", (num(s.inspection_days) ?? 99) < 30);
    }
    if (pt !== "ev" && (num(s.oil_days) != null || num(s.oil_km) != null)) {
      const parts = [];
      if (num(s.oil_days) != null) parts.push(`${fmt(s.oil_days)} ${this._t("days")}`);
      if (num(s.oil_km) != null) parts.push(`${fmt(s.oil_km)} ${this._t("km")}`);
      tile("mdi:oil", this._t("oil"), parts[0] + (parts[1] ? `<small>${parts[1]}</small>` : ""), "oil_days", (num(s.oil_days) ?? 99) < 30 || (num(s.oil_km) ?? 9999) < 1000);
    }
    if (num(s.battery_12v) != null) tile("mdi:car-battery", this._t("v12"), `${fmt(s.battery_12v, 1)} V`, "battery_12v", s.battery_12v < 11.8);
    const cons = pt === "ice" ? num(s.trip_long_fuel) : pt === "ev" ? num(s.trip_long_electric) : num(s.trip_long_fuel) ?? num(s.trip_long_electric);
    if (cons != null) tile("mdi:chart-line", this._t("consumption"), `${fmt(cons, 1)} ${pt === "ev" || (pt === "phev" && num(s.trip_long_fuel) == null) ? "kWh" : "L"}/100`, pt === "ev" ? "trip_long_electric" : "trip_long_fuel");
    return t.join("");
  }

  _openList(s) {
    const arrows = { fl: "↖", fr: "↗", rl: "↙", rr: "↘" };
    const open = [];
    const doors = ["fl", "fr", "rl", "rr"].filter((k) => s["door_" + k] === true).map((k) => arrows[k]);
    if (doors.length) open.push(`${this._t("doors")} ${doors.join(" ")}`);
    if (s.trunk === true) open.push(this._t("trunk"));
    if (s.hood === true) open.push(this._t("hood"));
    const wins = ["fl", "fr", "rl", "rr"].filter((k) => s["window_" + k] === true).map((k) => arrows[k]);
    if (wins.length) open.push(`${this._t("windows")} ${wins.join(" ")}`);
    if (s.sunroof === true) open.push(this._t("sunroof"));
    return open.length ? `<div class="open-list"><ha-icon icon="mdi:alert" style="--mdc-icon-size:14px"></ha-icon> ${open.join(" · ")}</div>` : "";
  }

  /* ---------- car outline ---------- */

  _carSvg(b, s, pt) {
    const W = 200, H = 400, L = b.len, w = b.wid;
    const x0 = (W - w) / 2, x1 = x0 + w, y0 = (H - L) / 2, y1 = y0 + L;
    const yHood = y0 + L * b.hood, yWind = yHood + L * b.wind, yRoof = yWind + L * b.roof, yRear = yRoof + L * b.rear;
    const body = `M ${x0 + b.nose} ${y0}
      Q ${W / 2} ${y0 - 6} ${x1 - b.nose} ${y0}
      Q ${x1} ${y0 + 4} ${x1} ${y0 + b.nose * 1.6}
      L ${x1} ${y1 - b.tail * 1.4}
      Q ${x1} ${y1} ${x1 - b.tail} ${y1}
      L ${x0 + b.tail} ${y1}
      Q ${x0} ${y1} ${x0} ${y1 - b.tail * 1.4}
      L ${x0} ${y0 + b.nose * 1.6}
      Q ${x0} ${y0 + 4} ${x0 + b.nose} ${y0} Z`;
    const open = (v) => v === true;
    const alert = "var(--cu-alert)";
    const glass = "color-mix(in srgb, var(--primary-text-color) 22%, transparent)";
    const glassOpen = "color-mix(in srgb, var(--cu-alert) 55%, transparent)";
    const paint = "color-mix(in srgb, var(--cu-copper) 30%, var(--card-background-color, #222))";
    const stroke = "var(--cu-copper)";
    const ix = 14; // glass inset
    const midDoor = yWind + (yRoof - yWind) * 0.5;
    const wheel = (cx, cy) => `<rect x="${cx - 9}" y="${cy - 24}" width="18" height="48" rx="7" fill="var(--primary-text-color)" opacity=".75"/>`;
    const wy1 = y0 + L * 0.2, wy2 = y1 - L * 0.19;
    const door = (side, front, isOpen) => {
      const x = side === "l" ? x0 - 2 : x1 - 2;
      const ya = front ? yWind + 6 : midDoor + 2, yb = front ? midDoor - 2 : yRoof - 4;
      if (!isOpen) return "";
      const dx = side === "l" ? -16 : 16;
      return `<path d="M ${x + 2} ${ya} L ${x + 2 + dx} ${ya + 10} L ${x + 2 + dx} ${yb - 4} L ${x + 2} ${yb}" fill="color-mix(in srgb, var(--cu-alert) 25%, transparent)" stroke="${alert}" stroke-width="2.5" stroke-linejoin="round"/>`;
    };
    const sideWin = (side, front, isOpen) => {
      const x = side === "l" ? x0 + 3 : x1 - 9;
      const ya = front ? yWind + 8 : midDoor + 3, yb = front ? midDoor - 3 : yRoof - 6;
      return `<rect x="${x}" y="${ya}" width="6" height="${yb - ya}" rx="3" fill="${isOpen ? glassOpen : glass}" ${isOpen ? `stroke="${alert}" stroke-width="1.5"` : ""}/>`;
    };
    const hoodOpen = open(s.hood), trunkOpen = open(s.trunk);
    const lockIcon = s.locked === false
      ? `<path d="M -7 -2 h 14 v 11 h -14 z M -4 -2 v -5 a 4 4 0 0 1 8 0" fill="none" stroke="${alert}" stroke-width="2.2" stroke-linecap="round"/>`
      : s.locked === true
        ? `<path d="M -7 -2 h 14 v 11 h -14 z M -4 -2 v -4 a 4 4 0 0 1 8 0 v 4" fill="none" stroke="var(--cu-ok)" stroke-width="2.2" stroke-linecap="round"/>`
        : "";
    const plug = s.plug_connected === true
      ? `<g transform="translate(${pt === "ev" ? x1 + 2 : x0 - 2} ${pt === "ev" ? y1 - L * 0.22 : y0 + L * 0.28})"><circle r="9" fill="${s.charging ? "var(--cu-ok)" : "var(--cu-copper)"}"/><path d="M -3 -5 v 4 M 3 -5 v 4 M -5 -1 h 10 v 3 a 5 5 0 0 1 -10 0 z M 0 7 v 3" stroke="#fff" stroke-width="1.6" fill="none" stroke-linecap="round"/></g>`
      : "";
    const tyre = (k, x, y, anchor) => (num(s[k]) != null ? `<text x="${x}" y="${y}" text-anchor="${anchor}" font-size="11" fill="var(--secondary-text-color)">${fmt(s[k], 1)}</text>` : "");
    return `<svg viewBox="-28 0 256 ${H}" role="img" aria-label="car">
      ${wheel(x0 + 2, wy1)}${wheel(x1 - 2, wy1)}${wheel(x0 + 2, wy2)}${wheel(x1 - 2, wy2)}
      <path d="${body}" fill="${paint}" stroke="${stroke}" stroke-width="2"/>
      <!-- bonnet -->
      <path d="M ${x0 + 10} ${yHood} Q ${W / 2} ${yHood + 6} ${x1 - 10} ${yHood}" fill="none" stroke="${hoodOpen ? alert : stroke}" stroke-width="${hoodOpen ? 3 : 1}" opacity="${hoodOpen ? 1 : 0.6}"/>
      ${hoodOpen ? `<path d="M ${x0 + 12} ${yHood} L ${x0 + 18} ${y0 - 10} L ${x1 - 18} ${y0 - 10} L ${x1 - 12} ${yHood}" fill="color-mix(in srgb, var(--cu-alert) 18%, transparent)" stroke="${alert}" stroke-width="2"/>` : ""}
      <!-- windscreen -->
      <path d="M ${x0 + ix} ${yWind} Q ${W / 2} ${yHood + 4} ${x1 - ix} ${yWind} L ${x1 - ix - 4} ${yWind + 6} Q ${W / 2} ${yWind - 2} ${x0 + ix + 4} ${yWind + 6} Z" fill="${glass}"/>
      <!-- roof -->
      <rect x="${x0 + ix + 2}" y="${yWind + 8}" width="${w - 2 * ix - 4}" height="${yRoof - yWind - 12}" rx="10" fill="color-mix(in srgb, var(--primary-text-color) 8%, transparent)"/>
      ${b.rails ? `<line x1="${x0 + ix + 4}" y1="${yWind + 10}" x2="${x0 + ix + 4}" y2="${yRoof - 6}" stroke="var(--primary-text-color)" stroke-width="2.5" opacity=".35" stroke-linecap="round"/><line x1="${x1 - ix - 4}" y1="${yWind + 10}" x2="${x1 - ix - 4}" y2="${yRoof - 6}" stroke="var(--primary-text-color)" stroke-width="2.5" opacity=".35" stroke-linecap="round"/>` : ""}
      ${typeof s.sunroof === "boolean" ? `<rect x="${x0 + ix + 14}" y="${yWind + 18}" width="${w - 2 * ix - 28}" height="${(yRoof - yWind) * 0.35}" rx="6" fill="${s.sunroof ? glassOpen : glass}" ${s.sunroof ? `stroke="${alert}" stroke-width="1.5"` : ""}/>` : ""}
      <!-- rear window -->
      <path d="M ${x0 + ix + 4} ${yRoof} L ${x1 - ix - 4} ${yRoof} L ${x1 - ix - 8} ${yRear} Q ${W / 2} ${yRear + 4} ${x0 + ix + 8} ${yRear} Z" fill="${glass}"/>
      <!-- tailgate -->
      <path d="M ${x0 + 12} ${yRear + 8} Q ${W / 2} ${yRear + 12} ${x1 - 12} ${yRear + 8}" fill="none" stroke="${trunkOpen ? alert : stroke}" stroke-width="${trunkOpen ? 3 : 1}" opacity="${trunkOpen ? 1 : 0.6}"/>
      ${trunkOpen ? `<path d="M ${x0 + 14} ${yRear + 8} L ${x0 + 20} ${y1 + 14} L ${x1 - 20} ${y1 + 14} L ${x1 - 14} ${yRear + 8}" fill="color-mix(in srgb, var(--cu-alert) 18%, transparent)" stroke="${alert}" stroke-width="2"/>` : ""}
      <!-- side glass -->
      ${sideWin("l", true, open(s.window_fl))}${sideWin("r", true, open(s.window_fr))}${sideWin("l", false, open(s.window_rl))}${sideWin("r", false, open(s.window_rr))}
      <!-- door seams -->
      <line x1="${x0}" y1="${midDoor}" x2="${x0 + 10}" y2="${midDoor}" stroke="${stroke}" opacity=".6"/>
      <line x1="${x1 - 10}" y1="${midDoor}" x2="${x1}" y2="${midDoor}" stroke="${stroke}" opacity=".6"/>
      ${door("l", true, open(s.door_fl))}${door("r", true, open(s.door_fr))}${door("l", false, open(s.door_rl))}${door("r", false, open(s.door_rr))}
      <!-- mirrors -->
      <path d="M ${x0} ${yWind + 2} l -10 4 l 2 6 l 8 -2 z" fill="${paint}" stroke="${stroke}"/>
      <path d="M ${x1} ${yWind + 2} l 10 4 l -2 6 l -8 -2 z" fill="${paint}" stroke="${stroke}"/>
      <g transform="translate(${W / 2} ${(yWind + yRoof) / 2 + 4})">${lockIcon}</g>
      ${plug}
      ${tyre("tyre_fl", x0 - 14, wy1 + 4, "end")}${tyre("tyre_fr", x1 + 14, wy1 + 4, "start")}
      ${tyre("tyre_rl", x0 - 14, wy2 + 4, "end")}${tyre("tyre_rr", x1 + 14, wy2 + 4, "start")}
    </svg>`;
  }

  /* ---------- actions ---------- */

  _actions(a, s, pt) {
    const ents = a.entities || {};
    const live = !!a.commands_available;
    const btns = [];
    const add = (act, icon, label, enabled, active = false) =>
      btns.push(`<button class="btn${active ? " active" : ""}" data-act="${act}" ${enabled ? "" : "disabled"}><ha-icon icon="${icon}"></ha-icon>${label}</button>`);
    if (live && ents.door_lock) {
      const locked = s.locked !== false;
      add(locked ? "unlock" : "lock", locked ? "mdi:lock" : "mdi:lock-open-variant", locked ? this._t("unlock") : this._t("lock"), true, !locked);
    }
    if (live && ents.climate && pt !== "ice") add("climate", "mdi:air-conditioner", this._t("climate"), true, s.climate_on === true);
    if (live && ents.charging_switch && pt !== "ice") add("charging", "mdi:ev-station", this._t("charge"), s.plug_connected !== false, s.charging === true);
    if (live && ents.flash) add("flash", "mdi:car-light-high", this._t("flash"), num(s.latitude) != null);
    if (ents.refresh) add("refresh", "mdi:refresh", this._t("refresh"), true);
    return btns.length ? `<div class="actions">${btns.join("")}</div>` : "";
  }

  _act(act) {
    const ents = this._hass.states[this._config.entity].attributes.entities || {};
    const call = (domain, service, entity_id) => this._hass.callService(domain, service, { entity_id });
    switch (act) {
      case "lock": return call("lock", "lock", ents.door_lock);
      case "unlock":
        if (!confirm(this._t("unlock") + "?")) return;
        return call("lock", "unlock", ents.door_lock);
      case "climate": return call("switch", "toggle", ents.climate);
      case "charging": return call("switch", "toggle", ents.charging_switch);
      case "flash": return call("button", "press", ents.flash);
      case "refresh": return call("button", "press", ents.refresh);
    }
  }

  _more(key) {
    const ents = this._hass.states[this._config.entity].attributes.entities || {};
    const entityId = ents[key] || this._config.entity;
    this.dispatchEvent(new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId } }));
  }
}

/* ---------------- visual editor ---------------- */

class CupraCardEditor extends HTMLElement {
  setConfig(config) { this._config = { ...config }; this._render(); }
  set hass(hass) { this._hass = hass; if (this._form) this._form.hass = hass; else this._render(); }

  _schema() {
    const opt = (v, l) => ({ value: v, label: l });
    return [
      { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "cupra" } } },
      { name: "name", selector: { text: {} } },
      {
        type: "grid", name: "", schema: [
          { name: "model", selector: { select: { mode: "dropdown", options: [opt("auto", "Auto"), ...Object.entries(MODELS).map(([k, m]) => opt(k, m.name))] } } },
          { name: "powertrain", selector: { select: { mode: "dropdown", options: [opt("auto", "Auto"), opt("ev", "EV"), opt("phev", "PHEV (e-HYBRID)"), opt("ice", "Petrol / diesel")] } } },
        ],
      },
      { name: "image", selector: { text: {} } },
      { name: "show_actions", selector: { boolean: {} } },
    ];
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => ({ entity: "Vehicle", name: "Name", model: "Model", powertrain: "Powertrain", show_actions: "Show buttons", image: "Own picture URL (e.g. /local/my_car.png)" }[s.name] || s.name);
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = this._schema();
    this._form.data = { model: "auto", powertrain: "auto", show_actions: true, ...this._config };
  }
}

if (!customElements.get("cupra-card")) customElements.define("cupra-card", CupraCard);
if (!customElements.get("cupra-card-editor")) customElements.define("cupra-card-editor", CupraCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "cupra-card")) {
  window.customCards.push({
    type: "cupra-card",
    name: "Cupra",
    description: "Cupra vehicle card: battery/fuel, range, doors, windows, service and remote actions.",
    preview: true,
    documentationURL: "https://github.com/keziksdmitrijs-byte/cupra-ha",
  });
}
console.info(`%c CUPRA-CARD %c ${CARD_VERSION} `, "background:#c58b5c;color:#000;font-weight:700", "background:#1d1d1b;color:#e2b48a");
