class MealSolverCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._editingDay = null;
  }

  setConfig(config) {
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._editingDay) this._render();
  }

  _dagar() {
    return [
      { dag: 'måndag',  id: 'mandag',  typ: 'vardag' },
      { dag: 'tisdag',  id: 'tisdag',  typ: 'vardag' },
      { dag: 'onsdag',  id: 'onsdag',  typ: 'vardag' },
      { dag: 'torsdag', id: 'torsdag', typ: 'vardag' },
      { dag: 'fredag',  id: 'fredag',  typ: 'helg' },
      { dag: 'lördag',  id: 'lordag',  typ: 'helg' },
      { dag: 'söndag',  id: 'sondag',  typ: 'helg' },
    ];
  }

  _meal(id) {
    const s = this._hass.states[`input_text.${id}_middag`];
    return s ? s.state : '—';
  }

  _locked(id) {
    const s = this._hass.states[`input_boolean.${id}_last`];
    return s && s.state === 'on';
  }

  _iconEdit() {
    return `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`;
  }

  _iconLocked() {
    return `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;
  }

  _iconUnlocked() {
    return `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>`;
  }

  _iconRefresh() {
    return `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>`;
  }

  _render() {
    const dagar = this._dagar();

    const rows = dagar.map(({ dag, id, typ }, i) => {
      const meal   = this._meal(id);
      const locked = this._locked(id);
      const badge  = locked ? `<span class="badge badge-last">låst</span>`
                            : `<span class="badge badge-${typ}">${typ}</span>`;
      const divider = i === 4 ? `<div class="divider"></div>` : '';

      return `${divider}<div class="row" data-id="${id}">
        <span class="dag">${dag.substring(0,3)}</span>
        <span class="ratt">${meal}</span>
        ${badge}
        <div class="actions">
          <button class="icon-btn edit-btn" data-id="${id}" data-meal="${meal.replace(/"/g,'&quot;')}" aria-label="Redigera ${dag}">${this._iconEdit()}</button>
          <button class="icon-btn lock-btn${locked ? ' locked' : ''}" data-id="${id}" data-locked="${locked}" aria-label="${locked ? 'Lås upp' : 'Lås'} ${dag}">${locked ? this._iconLocked() : this._iconUnlocked()}</button>
        </div>
      </div>`;
    }).join('');

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block}
        .card{background:var(--ha-card-background,var(--card-background-color,#fff));border-radius:var(--ha-card-border-radius,12px);border:0.5px solid var(--divider-color,#e0e0e0);overflow:hidden}
        .header{display:flex;align-items:center;justify-content:space-between;padding:14px 16px 10px}
        .title{font-size:15px;font-weight:500;color:var(--primary-text-color);display:flex;align-items:center;gap:8px}
        .btn-slumpa{display:flex;align-items:center;gap:6px;font-size:12px;padding:5px 10px;border:0.5px solid var(--divider-color);border-radius:8px;background:transparent;color:var(--primary-text-color);cursor:pointer}
        .btn-slumpa:hover{background:var(--secondary-background-color)}
        .btn-slumpa:active{opacity:0.7}
        .divider{height:0.5px;background:var(--divider-color,#e0e0e0)}
        .row{display:flex;align-items:center;padding:9px 16px;gap:10px;border-bottom:0.5px solid var(--divider-color)}
        .row:last-child{border-bottom:none}
        .dag{font-size:12px;color:var(--secondary-text-color);width:32px;flex-shrink:0;text-transform:capitalize}
        .ratt{flex:1;font-size:14px;color:var(--primary-text-color)}
        .badge{font-size:10px;padding:2px 7px;border-radius:6px;flex-shrink:0}
        .badge-helg{background:#E1F5EE;color:#0F6E56}
        .badge-vardag{background:#E6F1FB;color:#185FA5}
        .badge-last{background:#FAEEDA;color:#854F0B}
        .actions{display:flex;gap:4px;flex-shrink:0}
        .icon-btn{width:28px;height:28px;border:none;background:transparent;display:flex;align-items:center;justify-content:center;cursor:pointer;border-radius:6px;color:var(--secondary-text-color);padding:0}
        .icon-btn:hover{background:var(--secondary-background-color)}
        .icon-btn.locked{color:#854F0B}
        .footer{padding:8px 16px;display:flex;align-items:center;justify-content:space-between}
        .footer span{font-size:11px;color:var(--secondary-text-color)}
        .edit-input{flex:1;font-size:13px;padding:3px 6px;border:0.5px solid var(--primary-color,#03a9f4);border-radius:6px;background:var(--secondary-background-color);color:var(--primary-text-color);min-width:0}
        .save-btn{font-size:11px;padding:4px 9px;border:none;background:var(--primary-color,#03a9f4);color:#fff;border-radius:6px;cursor:pointer;flex-shrink:0}
      </style>
      <div class="card">
        <div class="header">
          <span class="title">Veckans middagar</span>
          <button class="btn-slumpa" id="slumpa-btn">${this._iconRefresh()} Slumpa om</button>
        </div>
        <div class="divider"></div>
        ${rows}
        <div class="divider"></div>
        <div class="footer">
          <span>Meal Solver 3000</span>
          <span>Söndag 17:00</span>
        </div>
      </div>`;

    this.shadowRoot.getElementById('slumpa-btn').addEventListener('click', () => {
      this._hass.callService('meal_solver_3000', 'generera_vecka', {});
    });

    this.shadowRoot.querySelectorAll('.lock-btn').forEach(btn => {
      btn.addEventListener('click', e => {
        const id     = e.currentTarget.dataset.id;
        const locked = e.currentTarget.dataset.locked === 'true';
        this._hass.callService('input_boolean', locked ? 'turn_off' : 'turn_on',
                               { entity_id: `input_boolean.${id}_last` });
      });
    });

    this.shadowRoot.querySelectorAll('.edit-btn').forEach(btn => {
      btn.addEventListener('click', e => {
        this._startEdit(e.currentTarget.dataset.id, e.currentTarget.dataset.meal);
      });
    });
  }

  _startEdit(id, currentMeal) {
    this._editingDay = id;
    const row = this.shadowRoot.querySelector(`.row[data-id="${id}"]`);
    if (!row) return;

    row.querySelector('.ratt').innerHTML =
      `<input class="edit-input" type="text" value="${currentMeal}" />`;
    row.querySelector('.actions').innerHTML =
      `<button class="save-btn">Spara</button>`;

    const input = row.querySelector('.edit-input');
    input.focus();
    input.select();

    const save = () => {
      const val = input.value.trim();
      if (val) this._hass.callService('input_text', 'set_value',
                                      { entity_id: `input_text.${id}_middag`, value: val });
      this._editingDay = null;
    };

    row.querySelector('.save-btn').addEventListener('click', save);
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter')  save();
      if (e.key === 'Escape') { this._editingDay = null; this._render(); }
    });
  }
}

customElements.define('meal-solver-card', MealSolverCard);
// v2 — använder meal_solver_3000 custom component
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'meal-solver-card',
  name: 'Meal Solver 3000',
  description: 'Veckans middagar med slumpning och låsning'
});
