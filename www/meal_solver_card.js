class MealSolverCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._editingDay  = null;   // veckoplan inline-edit
    this._tab         = 'vecka';
    this._kat         = '';
    this._editing     = null;   // matlista edit-form
    this._editingTag  = null;   // taggar inline rename { gammalt, nytt }
    this._listaActive = false;  // select i lista/taggar-flik är öppen → blockera re-render
  }

  setConfig(config) { this._config = config; }

  set hass(hass) {
    this._hass = hass;
    if (!this._editingDay && !this._editing && !this._listaActive && !this._editingTag) {
      this._render();
    }
  }

  // ── Helpers ───────────────────────────────────────────────────

  _dagar() {
    return [
      { dag:'måndag',  id:'mandag',  typ:'vardag' },
      { dag:'tisdag',  id:'tisdag',  typ:'vardag' },
      { dag:'onsdag',  id:'onsdag',  typ:'vardag' },
      { dag:'torsdag', id:'torsdag', typ:'vardag' },
      { dag:'fredag',  id:'fredag',  typ:'helg'   },
      { dag:'lördag',  id:'lordag',  typ:'helg'   },
      { dag:'söndag',  id:'sondag',  typ:'helg'   },
    ];
  }

  _meal(id)   { const s=this._hass.states[`input_text.${id}_middag`];   return s?s.state:'—'; }
  _locked(id) { const s=this._hass.states[`input_boolean.${id}_last`]; return s&&s.state==='on'; }

  _matratter() {
    const s = this._hass.states['sensor.meal_solver_matlista'];
    return s ? (s.attributes.matratter||{}) : {};
  }

  _allaTagger() {
    const std = ['köttfärs','nöt','fläsk','fågel','fisk','vegetarisk','korv','lamm',
                 'potatis','ris','pasta','nudlar'];
    const extra = new Set();
    for (const d of Object.values(this._matratter()))
      for (const t of (d.taggar||[])) extra.add(t);
    return [...new Set([...std,...extra])];
  }

  _taggRakning() {
    const cnt = {};
    for (const d of Object.values(this._matratter()))
      for (const t of (d.taggar||[])) cnt[t]=(cnt[t]||0)+1;
    return cnt;
  }

  // ── Icons ─────────────────────────────────────────────────────

  _iEdit()    { return `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`; }
  _iLocked()  { return `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`; }
  _iUnlocked(){ return `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>`; }
  _iRefresh() { return `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>`; }

  // ── Render ────────────────────────────────────────────────────

  _render() {
    const tabs = ['vecka','lista','taggar'];
    const tabBar = `<div class="tab-bar">${
      tabs.map(t=>`<button class="tab-btn${this._tab===t?' active':''}" data-tab="${t}">${
        t==='vecka'?'Veckoplan':t==='lista'?'Matlistan':'Taggar'
      }</button>`).join('')
    }</div><div class="hdiv"></div>`;

    const content = this._tab==='vecka' ? this._veckaHTML()
                  : this._tab==='lista' ? this._listaHTML()
                  :                       this._taggarHTML();

    this.shadowRoot.innerHTML = `${this._css()}<div class="card">${tabBar}${content}</div>`;
    this._attachEvents();
  }

  // ── Veckoplan ─────────────────────────────────────────────────

  _veckaHTML() {
    const rows = this._dagar().map(({dag,id,typ},i) => {
      const meal=this._meal(id), locked=this._locked(id);
      const badge = locked ? `<span class="badge badge-last">låst</span>`
                           : `<span class="badge badge-${typ}">${typ}</span>`;
      return `${i===4?'<div class="hdiv"></div>':''}
        <div class="row" data-id="${id}">
          <span class="dag">${dag.substring(0,3)}</span>
          <span class="ratt">${meal}</span>
          ${badge}
          <div class="actions">
            <button class="icon-btn edit-btn" data-id="${id}" data-meal="${meal.replace(/"/g,'&quot;')}">${this._iEdit()}</button>
            <button class="icon-btn lock-btn${locked?' locked':''}" data-id="${id}" data-locked="${locked}">${locked?this._iLocked():this._iUnlocked()}</button>
          </div>
        </div>`;
    }).join('');
    return `
      <div class="week-header">
        <span class="title">Veckans middagar</span>
        <button class="btn-slumpa" id="slumpa-btn">${this._iRefresh()} Slumpa om</button>
      </div>
      <div class="hdiv"></div>${rows}<div class="hdiv"></div>
      <div class="footer"><span>Meal Solver 3000</span><span>Söndag 17:00</span></div>`;
  }

  // ── Matlista ──────────────────────────────────────────────────

  _listaHTML() {
    if (this._editing) return this._editFormHTML();
    const matratter = this._matratter();
    if (!this._hass.states['sensor.meal_solver_matlista'])
      return `<div class="empty">Laddar matlistan…</div>`;

    const katOpts = ['vardag','helg','båda'].map(k=>
      `<option value="${k}"${this._kat===k?' selected':''}>${k}</option>`).join('');

    let rattSelect = '';
    if (this._kat) {
      const ratter = Object.entries(matratter)
        .filter(([,d])=>this._kat==='båda'||d.dagar===this._kat||d.dagar==='båda')
        .sort(([a],[b])=>a.localeCompare(b,'sv'));
      rattSelect = `<div class="field"><label>Maträtt</label>
        <select id="ratt-select" class="sel">
          <option value="">— välj maträtt —</option>
          ${ratter.map(([n])=>`<option value="${n}">${n}</option>`).join('')}
        </select></div>`;
    }
    return `<div class="wrap">
      <div class="field"><label>Kategori</label>
        <select id="kat-select" class="sel">
          <option value="">— välj kategori —</option>${katOpts}
        </select></div>
      ${rattSelect}
      <button class="btn-ny" id="ny-btn">+ Ny maträtt</button>
    </div>`;
  }

  _editFormHTML() {
    const e = this._editing;
    const chips = this._allaTagger().map(t=>{
      const on=e.taggar.has(t);
      return `<span class="chip${on?' on':''}" data-tag="${t}">${t}</span>`;
    }).join('');
    const dagRadios = ['vardag','helg','båda'].map(d=>
      `<label class="rl"><input type="radio" name="ed" value="${d}"${e.dagar===d?' checked':''}> ${d}</label>`
    ).join('');
    const dagOpts = ['','måndag','tisdag','onsdag','torsdag','fredag','lördag','söndag'].map(d=>
      `<option value="${d}"${e.låst_dag===d?' selected':''}>${d||'— ingen —'}</option>`).join('');
    return `<div class="wrap">
      <div class="edit-head">
        <span>${e.isNew?'Ny maträtt':'Redigera'}</span>
        <button class="icon-btn txt-btn" id="cancel-btn">✕</button>
      </div><div class="hdiv"></div>
      <div class="field"><label>Namn</label>
        <input class="inp" id="edit-namn" type="text" value="${e.namn.replace(/"/g,'&quot;')}" autocomplete="off"></div>
      <div class="field"><label>Dagar</label>
        <div class="radio-row">${dagRadios}</div></div>
      <div class="field"><label>Taggar</label>
        <div class="chips" id="chips">${chips}</div>
        <div class="tag-row">
          <input class="inp tag-inp" id="new-tag" type="text" placeholder="Lägg till tagg…">
          <button class="btn-add" id="add-tag">+</button>
        </div></div>
      <div class="field"><label>Låst dag</label>
        <select class="inp sel" id="edit-last">${dagOpts}</select></div>
      <div class="hdiv"></div>
      <div class="edit-foot">
        <button class="btn-spara" id="spara-btn">Spara</button>
        ${!e.isNew?`<button class="btn-bort" id="bort-btn">Ta bort</button>`:''}
      </div>
    </div>`;
  }

  // ── Taggar ────────────────────────────────────────────────────

  _taggarHTML() {
    if (this._editingTag) return this._tagEditFormHTML();

    const cnt = this._taggRakning();
    const tags = Object.entries(cnt).sort(([a],[b])=>a.localeCompare(b,'sv'));

    if (!tags.length) return `<div class="empty">Inga taggar ännu — lägg till maträtter med taggar först.</div>`;

    const rows = tags.map(([tag,n])=>`
      <div class="tag-item">
        <span class="tag-pill">${tag}</span>
        <span class="tag-cnt">${n} rätt${n!==1?'er':''}</span>
        <div class="actions">
          <button class="icon-btn edit-tag-btn" data-tag="${tag}">${this._iEdit()}</button>
          <button class="icon-btn del-tag-btn txt-btn" data-tag="${tag}">✕</button>
        </div>
      </div>`).join('');

    return `<div class="wrap">${rows}</div>`;
  }

  _tagEditFormHTML() {
    const t = this._editingTag;
    return `<div class="wrap">
      <div class="edit-head">
        <span>Byt namn på tagg</span>
        <button class="icon-btn txt-btn" id="cancel-tag-btn">✕</button>
      </div><div class="hdiv"></div>
      <div class="field"><label>Nuvarande namn</label>
        <div style="padding:6px 0"><span class="tag-pill">${t.gammalt}</span></div></div>
      <div class="field"><label>Nytt namn</label>
        <input class="inp" id="tag-nytt-namn" type="text" value="${t.gammalt}" autocomplete="off"></div>
      <div class="hdiv"></div>
      <div class="edit-foot">
        <button class="btn-spara" id="spara-tag-btn">Spara</button>
      </div>
    </div>`;
  }

  // ── Events ────────────────────────────────────────────────────

  _attachEvents() {
    const sr = this.shadowRoot;
    sr.querySelectorAll('.tab-btn').forEach(b=>b.addEventListener('click',()=>{
      this._tab=b.dataset.tab; this._editing=null; this._editingTag=null; this._render();
    }));
    if (this._tab==='vecka')  this._veckaEvents();
    else if (this._tab==='lista') this._listaEvents();
    else this._taggarEvents();
  }

  _veckaEvents() {
    const sr=this.shadowRoot;
    sr.getElementById('slumpa-btn')?.addEventListener('click',()=>
      this._hass.callService('meal_solver_3000','generera_vecka',{}));
    sr.querySelectorAll('.lock-btn').forEach(b=>b.addEventListener('click',e=>{
      const id=e.currentTarget.dataset.id, on=e.currentTarget.dataset.locked==='true';
      this._hass.callService('input_boolean',on?'turn_off':'turn_on',{entity_id:`input_boolean.${id}_last`});
    }));
    sr.querySelectorAll('.edit-btn').forEach(b=>b.addEventListener('click',e=>
      this._startInlineEdit(e.currentTarget.dataset.id,e.currentTarget.dataset.meal)));
  }

  _listaEvents() {
    const sr=this.shadowRoot;

    // Blockera re-render medan select är öppen
    sr.querySelectorAll('.sel').forEach(sel=>{
      sel.addEventListener('focus', ()=>{ this._listaActive=true; });
      sel.addEventListener('blur',  ()=>{ this._listaActive=false; });
    });

    sr.getElementById('kat-select')?.addEventListener('change',e=>{
      this._listaActive=false; this._kat=e.target.value; this._render();
    });
    sr.getElementById('ratt-select')?.addEventListener('change',e=>{
      this._listaActive=false;
      const namn=e.target.value; if(!namn) return;
      const d=this._matratter()[namn]||{};
      this._editing={gammaltNamn:namn,namn,dagar:d.dagar||'vardag',
        taggar:new Set(d.taggar||[]),låst_dag:d.låst_dag||'',isNew:false};
      this._render();
    });
    sr.getElementById('ny-btn')?.addEventListener('click',()=>{
      this._editing={gammaltNamn:'',namn:'',dagar:this._kat||'vardag',
        taggar:new Set(),låst_dag:'',isNew:true};
      this._render();
    });
    if (this._editing) this._editFormEvents();
  }

  _editFormEvents() {
    const sr=this.shadowRoot, e=this._editing;
    sr.getElementById('cancel-btn')?.addEventListener('click',()=>{this._editing=null;this._render();});

    sr.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{
      const t=c.dataset.tag;
      e.taggar.has(t)?(e.taggar.delete(t),c.classList.remove('on')):(e.taggar.add(t),c.classList.add('on'));
    }));

    const addTag=()=>{
      const inp=sr.getElementById('new-tag'), t=inp.value.trim().toLowerCase(); if(!t) return;
      e.taggar.add(t); inp.value='';
      const c=document.createElement('span');
      c.className='chip on'; c.dataset.tag=t; c.textContent=t;
      c.addEventListener('click',()=>{e.taggar.delete(t);c.classList.remove('on');});
      sr.getElementById('chips').appendChild(c);
    };
    sr.getElementById('add-tag')?.addEventListener('click',addTag);
    sr.getElementById('new-tag')?.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();addTag();}});

    sr.getElementById('spara-btn')?.addEventListener('click',()=>{
      const namn=sr.getElementById('edit-namn').value.trim();
      const dagar=sr.querySelector('input[name="ed"]:checked')?.value||e.dagar;
      const taggar=[...e.taggar];
      const last_dag=sr.getElementById('edit-last').value;
      if(!namn) return;
      const svc=e.isNew?'lagg_till_ratt':'uppdatera_ratt';
      const data=e.isNew
        ?{namn,dagar,taggar,...(last_dag?{låst_dag:last_dag}:{})}
        :{gammalt_namn:e.gammaltNamn,namn,dagar,taggar,...(last_dag?{låst_dag:last_dag}:{})};
      this._hass.callService('meal_solver_3000',svc,data);
      this._editing=null; this._render();
    });
    sr.getElementById('bort-btn')?.addEventListener('click',()=>{
      this._hass.callService('meal_solver_3000','ta_bort_ratt',{namn:e.gammaltNamn});
      this._editing=null; this._render();
    });

    // Blockera re-render på select i edit-form
    sr.querySelectorAll('.sel').forEach(sel=>{
      sel.addEventListener('focus',()=>{this._listaActive=true;});
      sel.addEventListener('blur', ()=>{this._listaActive=false;});
    });
  }

  _taggarEvents() {
    const sr=this.shadowRoot;

    if (this._editingTag) {
      const inp=sr.getElementById('tag-nytt-namn');
      inp?.focus(); inp?.select();
      sr.getElementById('cancel-tag-btn')?.addEventListener('click',()=>{this._editingTag=null;this._render();});
      sr.getElementById('spara-tag-btn')?.addEventListener('click',()=>{
        const nytt=sr.getElementById('tag-nytt-namn').value.trim();
        if(nytt && nytt!==this._editingTag.gammalt)
          this._hass.callService('meal_solver_3000','byt_namn_pa_tagg',
            {gammalt_namn:this._editingTag.gammalt,nytt_namn:nytt});
        this._editingTag=null; this._render();
      });
      inp?.addEventListener('keydown',ev=>{
        if(ev.key==='Enter'){sr.getElementById('spara-tag-btn').click();}
        if(ev.key==='Escape'){this._editingTag=null;this._render();}
      });
      return;
    }

    sr.querySelectorAll('.edit-tag-btn').forEach(b=>b.addEventListener('click',e=>{
      const tag=e.currentTarget.dataset.tag;
      this._editingTag={gammalt:tag}; this._render();
    }));
    sr.querySelectorAll('.del-tag-btn').forEach(b=>b.addEventListener('click',e=>{
      const tag=e.currentTarget.dataset.tag;
      this._hass.callService('meal_solver_3000','ta_bort_tagg',{namn:tag});
    }));
  }

  // ── Veckoplan inline edit ─────────────────────────────────────

  _startInlineEdit(id,currentMeal) {
    this._editingDay=id;
    const row=this.shadowRoot.querySelector(`.row[data-id="${id}"]`); if(!row) return;
    row.querySelector('.ratt').innerHTML=`<input class="edit-input" type="text" value="${currentMeal}">`;
    row.querySelector('.actions').innerHTML=`<button class="save-btn">Spara</button>`;
    const input=row.querySelector('.edit-input'); input.focus(); input.select();
    const save=()=>{
      const val=input.value.trim();
      if(val) this._hass.callService('input_text','set_value',{entity_id:`input_text.${id}_middag`,value:val});
      this._editingDay=null;
    };
    row.querySelector('.save-btn').addEventListener('click',save);
    input.addEventListener('keydown',ev=>{
      if(ev.key==='Enter') save();
      if(ev.key==='Escape'){this._editingDay=null;this._render();}
    });
  }

  // ── CSS ───────────────────────────────────────────────────────

  _css() { return `<style>
    :host{display:block}
    .card{background:var(--ha-card-background,var(--card-background-color,#fff));border-radius:var(--ha-card-border-radius,12px);border:0.5px solid var(--divider-color,#e0e0e0);overflow:hidden}
    .hdiv{height:0.5px;background:var(--divider-color,#e0e0e0)}
    .tab-bar{display:flex;padding:10px 16px 0;gap:2px}
    .tab-btn{flex:1;padding:8px 0;border:none;background:transparent;font-size:13px;color:var(--secondary-text-color);cursor:pointer;border-bottom:2px solid transparent;border-radius:0}
    .tab-btn.active{color:var(--primary-color,#03a9f4);border-bottom-color:var(--primary-color,#03a9f4);font-weight:500}
    .week-header{display:flex;align-items:center;justify-content:space-between;padding:12px 16px 10px}
    .title{font-size:15px;font-weight:500;color:var(--primary-text-color)}
    .btn-slumpa{display:flex;align-items:center;gap:6px;font-size:12px;padding:5px 10px;border:0.5px solid var(--divider-color);border-radius:8px;background:transparent;color:var(--primary-text-color);cursor:pointer}
    .btn-slumpa:hover{background:var(--secondary-background-color)}
    .row{display:flex;align-items:center;padding:9px 16px;gap:10px;border-bottom:0.5px solid var(--divider-color)}
    .dag{font-size:12px;color:var(--secondary-text-color);width:32px;flex-shrink:0}
    .ratt{flex:1;font-size:14px;color:var(--primary-text-color)}
    .badge{font-size:10px;padding:2px 7px;border-radius:6px;flex-shrink:0}
    .badge-helg{background:#E1F5EE;color:#0F6E56}
    .badge-vardag{background:#E6F1FB;color:#185FA5}
    .badge-last{background:#FAEEDA;color:#854F0B}
    .actions{display:flex;gap:4px;flex-shrink:0}
    .icon-btn{width:28px;height:28px;border:none;background:transparent;display:flex;align-items:center;justify-content:center;cursor:pointer;border-radius:6px;color:var(--secondary-text-color);padding:0}
    .icon-btn:hover{background:var(--secondary-background-color)}
    .txt-btn{font-size:15px}
    .icon-btn.locked{color:#854F0B}
    .footer{padding:8px 16px;display:flex;align-items:center;justify-content:space-between}
    .footer span{font-size:11px;color:var(--secondary-text-color)}
    .edit-input{flex:1;font-size:13px;padding:3px 6px;border:0.5px solid var(--primary-color,#03a9f4);border-radius:6px;background:var(--secondary-background-color);color:var(--primary-text-color);min-width:0}
    .save-btn{font-size:11px;padding:4px 9px;border:none;background:var(--primary-color,#03a9f4);color:#fff;border-radius:6px;cursor:pointer}
    .empty{padding:24px 16px;text-align:center;color:var(--secondary-text-color);font-size:13px}
    .wrap{padding:14px 16px;display:flex;flex-direction:column;gap:12px}
    .field{display:flex;flex-direction:column;gap:5px}
    label{font-size:11px;color:var(--secondary-text-color);text-transform:uppercase;letter-spacing:.4px}
    .inp,.sel{padding:8px 10px;border:0.5px solid var(--divider-color);border-radius:8px;background:var(--secondary-background-color);color:var(--primary-text-color);font-size:13px;width:100%;box-sizing:border-box}
    .inp:focus,.sel:focus{outline:none;border-color:var(--primary-color,#03a9f4)}
    .btn-ny{align-self:flex-start;font-size:12px;padding:6px 12px;border:0.5px solid var(--primary-color,#03a9f4);border-radius:8px;background:transparent;color:var(--primary-color,#03a9f4);cursor:pointer}
    .edit-head{display:flex;align-items:center;justify-content:space-between}
    .edit-head span{font-size:14px;font-weight:500;color:var(--primary-text-color)}
    .radio-row{display:flex;gap:16px}
    .rl{font-size:13px;color:var(--primary-text-color);display:flex;align-items:center;gap:5px;cursor:pointer;text-transform:none;letter-spacing:0}
    .chips{display:flex;flex-wrap:wrap;gap:6px}
    .chip{font-size:12px;padding:4px 10px;border-radius:20px;border:0.5px solid var(--divider-color);cursor:pointer;color:var(--secondary-text-color);background:transparent;user-select:none}
    .chip.on{background:var(--primary-color,#03a9f4);border-color:var(--primary-color,#03a9f4);color:#fff}
    .tag-row{display:flex;gap:8px;margin-top:6px}
    .tag-inp{flex:1;width:auto}
    .btn-add{padding:0 14px;border:0.5px solid var(--divider-color);border-radius:8px;background:transparent;color:var(--primary-text-color);cursor:pointer;font-size:18px;line-height:1}
    .edit-foot{display:flex;gap:8px}
    .btn-spara{flex:1;padding:9px;border:none;background:var(--primary-color,#03a9f4);color:#fff;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500}
    .btn-spara:hover{opacity:.9}
    .btn-bort{padding:9px 16px;border:0.5px solid #ef5350;border-radius:8px;background:transparent;color:#ef5350;cursor:pointer;font-size:13px}
    .btn-bort:hover{background:#ffebee}
    .tag-item{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:0.5px solid var(--divider-color)}
    .tag-item:last-child{border-bottom:none}
    .tag-pill{font-size:12px;padding:3px 10px;border-radius:20px;background:var(--secondary-background-color);border:0.5px solid var(--divider-color);color:var(--primary-text-color)}
    .tag-cnt{flex:1;font-size:12px;color:var(--secondary-text-color)}
  </style>`; }
}

customElements.define('meal-solver-card', MealSolverCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'meal-solver-card',
  name: 'Meal Solver 3000',
  description: 'Veckans middagar med slumpning, låsning, matlista och taggar'
});
// v4
