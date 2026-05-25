(function(){
  async function loadPresets() {
    try {
      const res = await fetch('/assets/presets/presets.json');
      const data = await res.json();
      const presets = data.presets || [];
      const list = document.getElementById('preset-list');
      if (!list) return;
      list.innerHTML = '';
      presets.forEach(p => {
        const card = document.createElement('div');
        card.className = 'preset-card';
        card.style.cssText = `
          background: rgba(255,255,255,0.02);
          border-radius: 10px;
          overflow: hidden;
          cursor: pointer;
          border: 1px solid rgba(255,255,255,0.08);
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 8px;
          transition: all 0.3s ease;
          position: relative;
        `;

        const img = document.createElement('img');
        img.src = p.thumbnail_url || p.image_url;
        img.alt = p.title;
        img.style.cssText = 'width:100%; height:96px; object-fit:cover; border-radius:6px; background:#000;';

        const title = document.createElement('div');
        title.textContent = p.title;
        title.style.cssText = 'margin-top:8px; font-size:0.85rem; color:var(--text-main); font-weight:600; text-align:center;';

        const badge = document.createElement('div');
        badge.textContent = p.badge || 'Event';
        badge.style.cssText = `
          margin-top: 4px;
          font-size: 0.7rem;
          padding: 2px 8px;
          background: rgba(99,102,241,0.3);
          color: var(--primary);
          border-radius: 4px;
          font-weight: 700;
          text-transform: uppercase;
        `;

        card.appendChild(img);
        card.appendChild(title);
        card.appendChild(badge);

        card.onmouseenter = () => {
          card.style.transform = 'translateY(-4px)';
          card.style.boxShadow = '0 8px 20px rgba(99,102,241,0.2), 0 0 1px rgba(255,255,255,0.1)';
          card.style.borderColor = 'rgba(99,102,241,0.4)';
        };

        card.onmouseleave = () => {
          if (window.__selectedReminderPreset !== p) {
            card.style.transform = 'translateY(0)';
            card.style.boxShadow = '';
            card.style.borderColor = 'rgba(255,255,255,0.08)';
          }
        };

        card.onclick = () => {
          document.querySelectorAll('#preset-list .preset-card').forEach(c => {
            c.style.boxShadow = '';
            c.style.transform = 'translateY(0)';
            c.style.borderColor = 'rgba(255,255,255,0.08)';
            c.style.background = 'rgba(255,255,255,0.02)';
          });
          card.style.boxShadow = '0 10px 30px rgba(99,102,241,0.3), 0 0 1px rgba(255,255,255,0.1)';
          card.style.transform = 'translateY(-4px)';
          card.style.borderColor = 'rgba(99,102,241,0.6)';
          card.style.background = 'rgba(99,102,241,0.1)';
          window.__selectedReminderPreset = p;

          const imageInput = document.querySelector('input[name="image_url"], input#image_url');
          const thumbInput = document.querySelector('input[name="thumbnail_url"], input#thumbnail_url');
          if (imageInput) imageInput.value = p.image_url;
          if (thumbInput) thumbInput.value = p.thumbnail_url || p.image_url;

          const preview = document.getElementById('preset-selection-preview');
          if (preview) { preview.src = p.image_url; preview.style.display = 'block'; }
        };

        list.appendChild(card);
      });
    } catch (e) { console.error('Failed to load presets', e); }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('open-reminder-presets');
    if (btn) {
      btn.addEventListener('click', (e)=>{
        const modal = document.getElementById('reminder-preset-modal');
        if (!modal) return;
        modal.style.display = 'flex';
        loadPresets();
      });
    }

    // Close modal on outside click
    document.addEventListener('click', (e)=>{
      const modal = document.getElementById('reminder-preset-modal');
      if (!modal || modal.style.display !== 'flex') return;
      if (e.target === modal) modal.style.display = 'none';
    });
  });

  // Helper for external integration: apply selected preset to a specific form element
  window.applySelectedReminderPresetToForm = function(formSelector){
    const p = window.__selectedReminderPreset;
    if (!p) return false;
    const form = typeof formSelector === 'string' ? document.querySelector(formSelector) : formSelector;
    if (!form) return false;
    const imageInput = form.querySelector('input[name="image_url"], input#image_url');
    const thumbInput = form.querySelector('input[name="thumbnail_url"], input#thumbnail_url');
    if (imageInput) imageInput.value = p.image_url;
    if (thumbInput) thumbInput.value = p.thumbnail_url || p.image_url;
    return true;
  };
})();
