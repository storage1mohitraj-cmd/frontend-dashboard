(function () {
  const data = window.whiteoutSiteData;
  if (!data) return;

  const iconPaths = {
    Activity: '<path d="M22 12h-4l-3 8L9 4l-3 8H2"/>',
    Gift: '<path d="M20 12v10H4V12"/><path d="M2 7h20v5H2z"/><path d="M12 22V7"/><path d="M12 7H7.5a2.5 2.5 0 1 1 0-5C11 2 12 7 12 7z"/><path d="M12 7h4.5a2.5 2.5 0 1 0 0-5C13 2 12 7 12 7z"/>',
    Music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    Languages: '<path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/>',
    Calendar: '<path d="M8 2v4"/><path d="M16 2v4"/><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 10h18"/>',
    Message: '<path d="M21 15a4 4 0 0 1-4 4H7l-4 4V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/>',
    Trophy: '<path d="M10 14.66v1.626a2 2 0 0 1-.976 1.696A5 5 0 0 0 7 21h10a5 5 0 0 0-2.024-3.018A2 2 0 0 1 14 16.286V14.66"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M6 2h12v7a6 6 0 0 1-12 0z"/>',
    User: '<circle cx="10" cy="8" r="5"/><path d="M2 21a8 8 0 0 1 16 0"/><circle cx="19" cy="17" r="3"/><path d="m21.5 19.5 1.5 1.5"/>',
    Sparkles: '<path d="M9.94 15.5 8.5 20l-1.44-4.5L2.5 14l4.56-1.5L8.5 8l1.44 4.5L14.5 14z"/><path d="M18 8 17 5l-3-1 3-1 1-3 1 3 3 1-3 1z"/><path d="m19 20-.75-2.25L16 17l2.25-.75L19 14l.75 2.25L22 17l-2.25.75z"/>',
    Bot: '<rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="8" cy="16" r="1"/><circle cx="16" cy="16" r="1"/><path d="M12 11V5"/><path d="M9 5h6"/>',
    Gamepad: '<line x1="6" y1="12" x2="10" y2="12"/><line x1="8" y1="10" x2="8" y2="14"/><line x1="15" y1="13" x2="15.01" y2="13"/><line x1="18" y1="11" x2="18.01" y2="11"/><rect x="2" y="7" width="20" height="10" rx="2"/>',
    Shield: '<path d="M20 13c0 5-3.5 7.5-8 9-4.5-1.5-8-4-8-9V5l8-3 8 3z"/><path d="m9 12 2 2 4-4"/>'
  };

  function icon(name) {
    return '<svg viewBox="0 0 24 24" aria-hidden="true">' + (iconPaths[name] || iconPaths.Sparkles) + '</svg>';
  }

  document.querySelectorAll("[data-feature-grid]").forEach((grid) => {
    grid.innerHTML = data.features.map(([iconName, title, description]) => `
      <article class="feature-card">
        <div class="feature-icon">${icon(iconName)}</div>
        <h3>${title}</h3>
        <p>${description}</p>
      </article>
    `).join("");
  });

  document.querySelectorAll("[data-feature-sections]").forEach((wrap) => {
    wrap.innerHTML = data.featureSections.map((section, index) => `
      <article class="feature-section">
        <div>
          <p>${section.eyebrow}</p>
          <h2>${section.title}</h2>
          <span>${section.body}</span>
        </div>
        <div class="module-card">
          <div class="module-top"><span>module-0${index + 1}</span><b>ready</b></div>
          <ul>${section.bullets.map((item) => `<li>${item}</li>`).join("")}</ul>
          <div class="command-tags">${section.commands.map((command) => `<span>${command}</span>`).join("")}</div>
        </div>
      </article>
    `).join("");
  });

  const typed = document.getElementById("typed-phrase");
  if (typed) {
    const phrases = ["alliance tracking", "automated redeem", "auto translation", "AI chat & voice", "smart reminders"];
    let phraseIndex = 0;
    let text = "";
    let deleting = false;
    const tick = () => {
      const current = phrases[phraseIndex];
      if (!deleting && text === current) {
        deleting = true;
        setTimeout(tick, 1400);
        return;
      }
      if (deleting && text === "") {
        deleting = false;
        phraseIndex = (phraseIndex + 1) % phrases.length;
      }
      text = deleting ? current.slice(0, Math.max(0, text.length - 1)) : current.slice(0, text.length + 1);
      typed.textContent = text;
      setTimeout(tick, deleting ? 35 : 70);
    };
    tick();
  }

  const liveStats = document.querySelectorAll("[data-live-stat]");
  if (liveStats.length) {
    const setStat = (key, value) => {
      document.querySelectorAll(`[data-live-stat="${key}"]`).forEach((node) => {
        node.textContent = value;
      });
    };
    const compactNumber = (value) => {
      const number = Number(value || 0);
      if (number >= 1000000) return `${(number / 1000000).toFixed(number >= 10000000 ? 0 : 1)}M`;
      if (number >= 1000) return `${(number / 1000).toFixed(number >= 10000 ? 0 : 1)}K`;
      return String(number);
    };
    const formatUptime = (seconds) => {
      const total = Number(seconds || 0);
      const days = Math.floor(total / 86400);
      const hours = Math.floor((total % 86400) / 3600);
      const minutes = Math.floor((total % 3600) / 60);
      if (days > 0) return `${days}d ${hours}h`;
      if (hours > 0) return `${hours}h ${minutes}m`;
      return `${Math.max(1, minutes)}m`;
    };
    fetch("/api/status", { headers: { Accept: "application/json" } })
      .then((response) => {
        if (!response.ok) throw new Error("Status unavailable");
        return response.json();
      })
      .then((status) => {
        setStat("servers", compactNumber(status.servers_count ?? status.guilds_count));
        setStat("uptime", formatUptime(status.uptime_seconds));
        setStat("members", compactNumber(status.members_count));
        setStat("latency", status.latency_ms == null ? "Online" : `${status.latency_ms}ms`);
      })
      .catch(() => {
        setStat("servers", "Live");
        setStat("uptime", "Online");
        setStat("members", "Soon");
        setStat("latency", "Online");
      });
  }

  const commandList = document.querySelector("[data-command-list]");
  const categoryWrap = document.querySelector("[data-command-categories]");
  const search = document.querySelector("[data-command-search]");
  const count = document.querySelector("[data-command-count]");
  if (commandList && categoryWrap && search && count) {
    let category = "All";
    const categories = ["All", ...Array.from(new Set(data.commands.map((command) => command[2])))];
    const renderCategories = () => {
      categoryWrap.innerHTML = categories.map((item) => `<button type="button" class="${item === category ? "active" : ""}" data-category="${item}">${item}</button>`).join("");
    };
    const renderCommands = () => {
      const q = search.value.trim().toLowerCase();
      const filtered = data.commands.filter(([name, description, cat]) => {
        return (category === "All" || cat === category) && (!q || `${name} ${description} ${cat}`.toLowerCase().includes(q));
      });
      count.textContent = `Showing ${filtered.length} of ${data.commands.length} commands`;
      commandList.innerHTML = filtered.length ? filtered.map(([name, description, cat]) => `
        <article class="command-card">
          <div>
            <h3>${name}</h3>
            <p>${description}</p>
          </div>
          <span>${cat}</span>
        </article>
      `).join("") : '<div class="empty-state"><h2>No commands found</h2><p>Try a different category or search phrase.</p></div>';
    };
    categoryWrap.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      category = button.dataset.category;
      renderCategories();
      renderCommands();
    });
    search.addEventListener("input", renderCommands);
    renderCategories();
    renderCommands();
  }
})();
