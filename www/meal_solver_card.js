class MealSolverCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._editingDay  = null;   // week plan inline edit
    this._tab         = 'vecka';
    this._category    = '';
    this._editing     = null;   // dish list edit form
    this._editingTag  = null;   // tag inline rename { oldName, newName }
    this._listActive  = false;  // select in list/tags tab is open → block re-render
  }

  setConfig(config) { this._config = config; }

  set hass(hass) {
    this._hass = hass;
    if (!this._editingDay && !this._editing && !this._listActive && !this._editingTag) {
      this._render();
    }
  }

  // ── Helpers ───────────────────────────────────────────────────

  _days() {
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

  _dishes() {
    const s = this._hass.states['sensor.meal_solver_matlista'];
    return s ? (s.attributes.dishes||{}) : {};
  }

  _allTags() {
    const s = this._hass.states['sensor.meal_solver_matlista'];
    const known = s ? (s.attributes.known_tags || []) : [];
    // fallback if sensor does not have known_tags yet
    if (known.length) return known;
    const defaults = ['köttfärs','nöt','fläsk','fågel','fisk','vegetarisk','korv','lamm',
                      'potatis','ris','pasta','nudlar'];
    const extra = new Set();
    for (const d of Object.values(this._dishes()))
      for (const t of (d.taggar||[])) extra.add(t);
    return [...new Set([...defaults,...extra])];
  }

  _requiresOpts(selected) {
    const dishList = Object.keys(this._dishes()).sort((a,b)=>a.localeCompare(b,'sv'));
    const opts = dishList
      .filter(n => n !== (this._editing?.oldName || ''))
      .map(n => `<option value="${n}"${selected===n?' selected':''}>${n}</option>`)
      .join('');
    return `<option value="">— none —</option>${opts}`;
  }

  _tagCounts() {
    const cnt = {};
    for (const d of Object.values(this._dishes()))
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

    const content = this._tab==='vecka' ? this._weekHTML()
                  : this._tab==='lista' ? this._listHTML()
                  :                       this._tagsHTML();

    this.shadowRoot.innerHTML = `${this._css()}<div class="card">${tabBar}${content}</div>`;
    this._attachEvents();
  }

  // ── Week plan ─────────────────────────────────────────────────

  _weekHTML() {
    const rows = this._days().map(({dag,id,typ},i) => {
      const meal=this._meal(id), locked=this._locked(id);
      const badge = locked ? `<span class="badge badge-locked">locked</span>`
                           : `<span class="badge badge-${typ}">${typ}</span>`;
      return `${i===4?'<div class="hdiv"></div>':''}
        <div class="row" data-id="${id}">
          <span class="day">${dag.substring(0,3)}</span>
          <span class="dish">${meal}</span>
          ${badge}
          <div class="actions">
            <button class="icon-btn edit-btn" data-id="${id}" data-meal="${meal.replace(/"/g,'&quot;')}">${this._iEdit()}</button>
            <button class="icon-btn lock-btn${locked?' locked':''}" data-id="${id}" data-locked="${locked}">${locked?this._iLocked():this._iUnlocked()}</button>
          </div>
        </div>`;
    }).join('');
    return `
      <div class="week-header">
        <span class="title">This week's dinners</span>
        <button class="btn-shuffle" id="shuffle-btn">${this._iRefresh()} Shuffle</button>
      </div>
      <div class="hdiv"></div>${rows}<div class="hdiv"></div>
      <div class="footer"><span>Meal Solver 3000</span><span>Sunday 17:00</span></div>`;
  }

  // ── Dish list ─────────────────────────────────────────────────

  _listHTML() {
    if (this._editing) return this._editFormHTML();
    const dishes = this._dishes();
    if (!this._hass.states['sensor.meal_solver_matlista'])
      return `<div class="empty">Loading dish list…</div>`;

    const cnt = { vardag:0, helg:0, båda:0 };
    for (const d of Object.values(dishes)) cnt[d.dagar] = (cnt[d.dagar]||0) + 1;
    const total = Object.keys(dishes).length;
    const stats = `<div class="stats-row">
      <span class="stat-pill stat-total">${total} total</span>
      <span class="stat-pill stat-vardag">${cnt.vardag||0} weekday</span>
      <span class="stat-pill stat-helg">${cnt.helg||0} weekend</span>
      <span class="stat-pill stat-both">${cnt.båda||0} both</span>
    </div>`;

    const catOpts = ['vardag','helg','båda'].map(k=>
      `<option value="${k}"${this._category===k?' selected':''}>${k}</option>`).join('');

    let dishSelect = '';
    if (this._category) {
      const dishList = Object.entries(dishes)
        .filter(([,d])=>this._category==='båda'?d.dagar==='båda':(d.dagar===this._category||d.dagar==='båda'))
        .sort(([a],[b])=>a.localeCompare(b,'sv'));
      dishSelect = `<div class="field"><label>Dish</label>
        <select id="dish-select" class="sel">
          <option value="">— select dish —</option>
          ${dishList.map(([n])=>`<option value="${n}">${n}</option>`).join('')}
        </select></div>`;
    }
    return `<div class="wrap">
      ${stats}
      <div class="field"><label>Category</label>
        <select id="cat-select" class="sel">
          <option value="">— select category —</option>${catOpts}
        </select></div>
      ${dishSelect}
      <button class="btn-new" id="new-btn">+ New dish</button>
    </div>`;
  }

  _editFormHTML() {
    const e = this._editing;
    const chips = this._allTags().map(t=>{
      const on=e.tags.has(t);
      return `<span class="chip${on?' on':''}" data-tag="${t}">${t}</span>`;
    }).join('');
    const dayRadios = ['vardag','helg','båda'].map(d=>
      `<label class="rl"><input type="radio" name="ed" value="${d}"${e.days===d?' checked':''}> ${d}</label>`
    ).join('');
    const dayOpts = ['','måndag','tisdag','onsdag','torsdag','fredag','lördag','söndag'].map(d=>
      `<option value="${d}"${e.lockedDay===d?' selected':''}>${d||'— none —'}</option>`).join('');
    return `<div class="wrap">
      <div class="edit-head">
        <span>${e.isNew?'New dish':'Edit'}</span>
        <button class="icon-btn txt-btn" id="cancel-btn">✕</button>
      </div><div class="hdiv"></div>
      <div class="field"><label>Name</label>
        <input class="inp" id="edit-name" type="text" value="${e.name.replace(/"/g,'&quot;')}" autocomplete="off"></div>
      <div class="field"><label>Days</label>
        <div class="radio-row">${dayRadios}</div></div>
      <div class="field"><label>Tags</label>
        <div class="chips" id="chips">${chips}</div>
        <div class="tag-row">
          <input class="inp tag-inp" id="new-tag" type="text" placeholder="Add tag…">
          <button class="btn-add" id="add-tag">+</button>
        </div></div>
      <div class="field"><label>Locked day</label>
        <select class="inp sel" id="edit-locked">${dayOpts}</select></div>
      <div class="field"><label>Requires dish same week</label>
        <select class="inp sel" id="edit-requires">${this._requiresOpts(e.requires)}</select></div>
      <div class="hdiv"></div>
      <div class="edit-foot">
        <button class="btn-save" id="save-btn">Save</button>
        ${!e.isNew?`<button class="btn-delete" id="delete-btn">Delete</button>`:''}
      </div>
    </div>`;
  }

  // ── Tags ──────────────────────────────────────────────────────

  _tagsHTML() {
    if (this._editingTag) return this._tagEditFormHTML();

    const cnt = this._tagCounts();

    // Show all known tags (including unused ones)
    const allKnown = this._allTags();
    const allRows = allKnown.map(tag => {
      const n = cnt[tag] || 0;
      return `<div class="tag-item">
        <span class="tag-pill${n===0?' tag-pill-unused':''}">${tag}</span>
        <span class="tag-cnt">${n===0?'unused':`${n} dish${n!==1?'es':''}`}</span>
        <div class="actions">
          <button class="icon-btn edit-tag-btn" data-tag="${tag}">${this._iEdit()}</button>
          <button class="icon-btn del-tag-btn txt-btn" data-tag="${tag}">✕</button>
        </div>
      </div>`;
    }).join('');

    return `<div class="wrap">
      ${allRows}
      <div class="hdiv"></div>
      <div class="field">
        <label>New tag</label>
        <div class="tag-row">
          <input class="inp tag-inp" id="new-tag-inp" type="text" placeholder="Enter tag name…" autocomplete="off">
          <button class="btn-add" id="new-tag-btn">+</button>
        </div>
      </div>
    </div>`;
  }

  _tagEditFormHTML() {
    const t = this._editingTag;
    return `<div class="wrap">
      <div class="edit-head">
        <span>Rename tag</span>
        <button class="icon-btn txt-btn" id="cancel-tag-btn">✕</button>
      </div><div class="hdiv"></div>
      <div class="field"><label>Current name</label>
        <div style="padding:6px 0"><span class="tag-pill">${t.oldName}</span></div></div>
      <div class="field"><label>New name</label>
        <input class="inp" id="tag-new-name" type="text" value="${t.oldName}" autocomplete="off"></div>
      <div class="hdiv"></div>
      <div class="edit-foot">
        <button class="btn-save" id="save-tag-btn">Save</button>
      </div>
    </div>`;
  }

  // ── Events ────────────────────────────────────────────────────

  _attachEvents() {
    const sr = this.shadowRoot;
    sr.querySelectorAll('.tab-btn').forEach(b=>b.addEventListener('click',()=>{
      this._tab=b.dataset.tab; this._editing=null; this._editingTag=null; this._render();
    }));
    if (this._tab==='vecka')  this._weekEvents();
    else if (this._tab==='lista') this._listEvents();
    else this._tagsEvents();
  }

  _weekEvents() {
    const sr=this.shadowRoot;
    sr.getElementById('shuffle-btn')?.addEventListener('click',()=>
      this._hass.callService('meal_solver_3000','generate_week',{}));
    sr.querySelectorAll('.lock-btn').forEach(b=>b.addEventListener('click',e=>{
      const id=e.currentTarget.dataset.id, on=e.currentTarget.dataset.locked==='true';
      this._hass.callService('input_boolean',on?'turn_off':'turn_on',{entity_id:`input_boolean.${id}_last`});
    }));
    sr.querySelectorAll('.edit-btn').forEach(b=>b.addEventListener('click',e=>
      this._startInlineEdit(e.currentTarget.dataset.id,e.currentTarget.dataset.meal)));
  }

  _listEvents() {
    const sr=this.shadowRoot;

    // Block re-render while select is open
    sr.querySelectorAll('.sel').forEach(sel=>{
      sel.addEventListener('focus', ()=>{ this._listActive=true; });
      sel.addEventListener('blur',  ()=>{ this._listActive=false; });
    });

    sr.getElementById('cat-select')?.addEventListener('change',e=>{
      this._listActive=false; this._category=e.target.value; this._render();
    });
    sr.getElementById('dish-select')?.addEventListener('change',e=>{
      this._listActive=false;
      const name=e.target.value; if(!name) return;
      const d=this._dishes()[name]||{};
      this._editing={oldName:name,name,days:d.dagar||'vardag',
        tags:new Set(d.taggar||[]),lockedDay:d.låst_dag||'',
        requires:d.kräver||'',isNew:false};
      this._render();
    });
    sr.getElementById('new-btn')?.addEventListener('click',()=>{
      this._editing={oldName:'',name:'',days:this._category||'vardag',
        tags:new Set(),lockedDay:'',requires:'',isNew:true};
      this._render();
    });
    if (this._editing) this._editFormEvents();
  }

  _editFormEvents() {
    const sr=this.shadowRoot, e=this._editing;
    sr.getElementById('cancel-btn')?.addEventListener('click',()=>{this._editing=null;this._render();});

    sr.querySelectorAll('.chip').forEach(c=>c.addEventListener('click',()=>{
      const t=c.dataset.tag;
      e.tags.has(t)?(e.tags.delete(t),c.classList.remove('on')):(e.tags.add(t),c.classList.add('on'));
    }));

    const addTag=()=>{
      const inp=sr.getElementById('new-tag'), t=inp.value.trim().toLowerCase(); if(!t) return;
      e.tags.add(t); inp.value='';
      const c=document.createElement('span');
      c.className='chip on'; c.dataset.tag=t; c.textContent=t;
      c.addEventListener('click',()=>{e.tags.delete(t);c.classList.remove('on');});
      sr.getElementById('chips').appendChild(c);
    };
    sr.getElementById('add-tag')?.addEventListener('click',addTag);
    sr.getElementById('new-tag')?.addEventListener('keydown',ev=>{if(ev.key==='Enter'){ev.preventDefault();addTag();}});

    sr.getElementById('save-btn')?.addEventListener('click',()=>{
      const name=sr.getElementById('edit-name').value.trim();
      const days=sr.querySelector('input[name="ed"]:checked')?.value||e.days;
      const tags=[...e.tags];
      const locked_day=sr.getElementById('edit-locked').value;
      const requires=sr.getElementById('edit-requires').value;
      if(!name) return;
      const svc=e.isNew?'add_dish':'update_dish';
      const data=e.isNew
        ?{name,days,tags,...(locked_day?{locked_day}:{}),...(requires?{requires}:{})}
        :{old_name:e.oldName,name,days,tags,...(locked_day?{locked_day}:{}),...(requires?{requires}:{})};
      this._hass.callService('meal_solver_3000',svc,data);
      this._editing=null; this._render();
    });
    sr.getElementById('delete-btn')?.addEventListener('click',()=>{
      this._hass.callService('meal_solver_3000','remove_dish',{name:e.oldName});
      this._editing=null; this._render();
    });

    // Block re-render on select in edit form
    sr.querySelectorAll('.sel').forEach(sel=>{
      sel.addEventListener('focus',()=>{this._listActive=true;});
      sel.addEventListener('blur', ()=>{this._listActive=false;});
    });
  }

  _tagsEvents() {
    const sr=this.shadowRoot;

    if (this._editingTag) {
      const inp=sr.getElementById('tag-new-name');
      inp?.focus(); inp?.select();
      sr.getElementById('cancel-tag-btn')?.addEventListener('click',()=>{this._editingTag=null;this._render();});
      sr.getElementById('save-tag-btn')?.addEventListener('click',()=>{
        const newName=sr.getElementById('tag-new-name').value.trim();
        if(newName && newName!==this._editingTag.oldName)
          this._hass.callService('meal_solver_3000','rename_tag',
            {old_name:this._editingTag.oldName,new_name:newName});
        this._editingTag=null; this._render();
      });
      inp?.addEventListener('keydown',ev=>{
        if(ev.key==='Enter'){sr.getElementById('save-tag-btn').click();}
        if(ev.key==='Escape'){this._editingTag=null;this._render();}
      });
      return;
    }

    sr.querySelectorAll('.edit-tag-btn').forEach(b=>b.addEventListener('click',e=>{
      const tag=e.currentTarget.dataset.tag;
      this._editingTag={oldName:tag}; this._render();
    }));
    sr.querySelectorAll('.del-tag-btn').forEach(b=>b.addEventListener('click',e=>{
      const tag=e.currentTarget.dataset.tag;
      this._hass.callService('meal_solver_3000','remove_tag',{name:tag});
    }));

    // New tag
    const addNewTag = () => {
      const inp = sr.getElementById('new-tag-inp');
      const name = inp.value.trim().toLowerCase();
      if (!name) return;
      this._hass.callService('meal_solver_3000','create_tag',{name});
      inp.value = '';
    };
    sr.getElementById('new-tag-btn')?.addEventListener('click', addNewTag);
    sr.getElementById('new-tag-inp')?.addEventListener('keydown', ev => {
      if (ev.key === 'Enter') { ev.preventDefault(); addNewTag(); }
    });
    // Block re-render while input field is active
    sr.getElementById('new-tag-inp')?.addEventListener('focus', ()=>{ this._listActive=true; });
    sr.getElementById('new-tag-inp')?.addEventListener('blur',  ()=>{ this._listActive=false; });
  }

  // ── Week plan inline edit ─────────────────────────────────────

  _startInlineEdit(id,currentMeal) {
    this._editingDay=id;
    const row=this.shadowRoot.querySelector(`.row[data-id="${id}"]`); if(!row) return;
    row.querySelector('.dish').innerHTML=`<input class="edit-input" type="text" value="${currentMeal}">`;
    row.querySelector('.actions').innerHTML=`<button class="save-btn">Save</button>`;
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
    .btn-shuffle{display:flex;align-items:center;gap:6px;font-size:12px;padding:5px 10px;border:0.5px solid var(--divider-color);border-radius:8px;background:transparent;color:var(--primary-text-color);cursor:pointer}
    .btn-shuffle:hover{background:var(--secondary-background-color)}
    .row{display:flex;align-items:center;padding:9px 16px;gap:10px;border-bottom:0.5px solid var(--divider-color)}
    .day{font-size:12px;color:var(--secondary-text-color);width:32px;flex-shrink:0}
    .dish{flex:1;font-size:14px;color:var(--primary-text-color)}
    .badge{font-size:10px;padding:2px 7px;border-radius:6px;flex-shrink:0}
    .badge-helg{background:#E1F5EE;color:#0F6E56}
    .badge-vardag{background:#E6F1FB;color:#185FA5}
    .badge-locked{background:#FAEEDA;color:#854F0B}
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
    .stats-row{display:flex;gap:6px;flex-wrap:wrap}
    .stat-pill{font-size:11px;padding:3px 9px;border-radius:20px;font-weight:500}
    .stat-total{background:var(--secondary-background-color);color:var(--primary-text-color)}
    .stat-vardag{background:#E6F1FB;color:#185FA5}
    .stat-helg{background:#E1F5EE;color:#0F6E56}
    .stat-both{background:#F3EEFF;color:#5B2DAB}
    .btn-new{align-self:flex-start;font-size:12px;padding:6px 12px;border:0.5px solid var(--primary-color,#03a9f4);border-radius:8px;background:transparent;color:var(--primary-color,#03a9f4);cursor:pointer}
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
    .btn-save{flex:1;padding:9px;border:none;background:var(--primary-color,#03a9f4);color:#fff;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500}
    .btn-save:hover{opacity:.9}
    .btn-delete{padding:9px 16px;border:0.5px solid #ef5350;border-radius:8px;background:transparent;color:#ef5350;cursor:pointer;font-size:13px}
    .btn-delete:hover{background:#ffebee}
    .tag-item{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:0.5px solid var(--divider-color)}
    .tag-item:last-child{border-bottom:none}
    .tag-pill{font-size:12px;padding:3px 10px;border-radius:20px;background:var(--secondary-background-color);border:0.5px solid var(--divider-color);color:var(--primary-text-color)}
    .tag-cnt{flex:1;font-size:12px;color:var(--secondary-text-color)}
    .tag-pill-unused{opacity:.45}
  </style>`; }
}

customElements.define('meal-solver-card', MealSolverCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'meal-solver-card',
  name: 'Meal Solver 3000',
  description: 'Week plan with shuffle, locking, dish list and tags'
});
// v4
