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

  const hasDiscordToken = Boolean(localStorage.getItem("discord_access_token"));
  document.querySelectorAll("[data-dashboard-link]").forEach((link) => {
    link.setAttribute("href", hasDiscordToken ? "dashboard.html" : "login.html");
  });

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
        setStat("members", compactNumber(status.total_members ?? status.members_count));
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

  const chatRoot = document.querySelector("[data-global-chat]");
  if (chatRoot) {
    const chat = {
      panel: chatRoot.querySelector("[data-chat-panel]"),
      toggle: chatRoot.querySelector("[data-chat-toggle]"),
      unread: chatRoot.querySelector("[data-chat-unread]"),
      online: chatRoot.querySelector("[data-chat-online]"),
      close: chatRoot.querySelector("[data-chat-close]"),
      login: chatRoot.querySelector("[data-chat-login]"),
      name: chatRoot.querySelector("[data-chat-name]"),
      guest: chatRoot.querySelector("[data-chat-guest]"),
      discord: chatRoot.querySelector("[data-chat-discord]"),
      identity: chatRoot.querySelector("[data-chat-identity]"),
      status: chatRoot.querySelector("[data-chat-status]"),
      messages: chatRoot.querySelector("[data-chat-messages]"),
      form: chatRoot.querySelector("[data-chat-form]"),
      input: chatRoot.querySelector("[data-chat-input]"),
      file: chatRoot.querySelector("[data-chat-file]"),
      attachments: chatRoot.querySelector("[data-chat-attachments]"),
      emoji: chatRoot.querySelector("[data-chat-emoji]"),
      emojiPanel: chatRoot.querySelector("[data-chat-emoji-panel]")
    };

    const DISCORD_CLIENT_ID = "1399025185046134866";
    const STORAGE_KEYS = {
      guestId: "wos_global_chat_guest_id",
      guestName: "wos_global_chat_guest_name",
      lastSeen: "wos_global_chat_last_seen_at"
    };
    const emojis = ["😀", "😂", "🔥", "❄️", "🎁", "⚔️", "🛡️", "🏆", "💎", "✅", "👀", "🤝", "🙏", "🚀", "💬", "❤️"];
    let pendingAttachments = [];
    let currentUser = null;
    let pollTimer = null;
    let presenceTimer = null;
    let isLoadingMessages = false;
    let latestMessageAt = null;
    let firstMessageSync = true;

    const setStatus = (message, isError = false) => {
      chat.status.textContent = message;
      chat.status.classList.toggle("is-error", isError);
    };

    const getToken = () => localStorage.getItem("discord_access_token");

    const authHeaders = () => {
      const token = getToken();
      return token ? { Authorization: `Bearer ${token}` } : {};
    };

    const getGuestId = () => {
      let guestId = localStorage.getItem(STORAGE_KEYS.guestId);
      if (!guestId) {
        guestId = `guest-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
        localStorage.setItem(STORAGE_KEYS.guestId, guestId);
      }
      return guestId;
    };

    const getGuestName = () => localStorage.getItem(STORAGE_KEYS.guestName) || "";

    const setGuestName = (name) => {
      const cleaned = name.trim().slice(0, 32);
      if (cleaned) localStorage.setItem(STORAGE_KEYS.guestName, cleaned);
      return cleaned;
    };

    const setUnread = (count) => {
      if (!chat.unread) return;
      if (count > 0) {
        chat.unread.hidden = false;
        chat.unread.textContent = count > 99 ? "99+" : String(count);
      } else {
        chat.unread.hidden = true;
        chat.unread.textContent = "0";
      }
    };

    const markSeen = () => {
      if (!latestMessageAt) return;
      localStorage.setItem(STORAGE_KEYS.lastSeen, latestMessageAt);
      setUnread(0);
    };

    const buildDiscordAuthUrl = () => {
      const base = "https://discord.com/api/oauth2/authorize";
      const redirect = `${window.location.origin}/oauth-callback.html`;
      const scope = encodeURIComponent("identify guilds");
      return `${base}?client_id=${DISCORD_CLIENT_ID}&redirect_uri=${encodeURIComponent(redirect)}&response_type=code&scope=${scope}&prompt=consent`;
    };

    const updateIdentityView = () => {
      const guestName = getGuestName();
      if (currentUser) {
        chat.identity.textContent = `Discord: ${currentUser.global_name || currentUser.username}`;
        chat.login.classList.add("is-hidden");
        return;
      }
      if (guestName) {
        chat.identity.textContent = `Guest: ${guestName}`;
        chat.login.classList.add("is-hidden");
        return;
      }
      chat.identity.textContent = "Guest access";
      chat.login.classList.remove("is-hidden");
    };

    const resolveDiscordIdentity = async () => {
      if (!getToken()) {
        updateIdentityView();
        return;
      }
      try {
        const response = await fetch("/api/auth/me", { headers: authHeaders() });
        if (!response.ok) throw new Error("Discord login expired");
        currentUser = await response.json();
      } catch (error) {
        currentUser = null;
      } finally {
        updateIdentityView();
      }
    };

    const initials = (name) => {
      const parts = String(name || "Guest").trim().split(/\s+/).slice(0, 2);
      return parts.map((part) => part[0] || "").join("").toUpperCase() || "G";
    };

    const formatTime = (iso) => {
      const date = new Date(iso);
      if (Number.isNaN(date.getTime())) return "now";
      const local = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      const utc = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
      return `${local} local / ${utc} UTC`;
    };

    const isImageAttachment = (attachment) => {
      const type = attachment.type || "";
      return type.startsWith("image/") || /\.(png|jpe?g|gif|webp|apng)$/i.test(attachment.url || "");
    };

    const isAudioAttachment = (attachment) => {
      const type = attachment.type || "";
      return type.startsWith("audio/") || /\.(webm|ogg|mp3|wav|m4a|aac)$/i.test(attachment.url || "");
    };

    const renderMessage = (message) => {
      const article = document.createElement("article");
      article.className = "chat-message";

      const avatar = document.createElement("div");
      avatar.className = "chat-avatar";
      const author = message.author || {};
      if (author.avatar_url) {
        const image = document.createElement("img");
        image.src = author.avatar_url;
        image.alt = "";
        avatar.appendChild(image);
      } else {
        avatar.textContent = initials(author.name);
      }

      const bubble = document.createElement("div");
      bubble.className = "chat-bubble";

      const top = document.createElement("div");
      top.className = "chat-bubble-top";

      const name = document.createElement("div");
      name.className = "chat-author";
      name.textContent = author.name || "Guest Player";

      const time = document.createElement("time");
      time.className = "chat-meta";
      time.dateTime = message.created_at || "";
      time.textContent = formatTime(message.created_at);
      time.title = `${new Date(message.created_at).toUTCString()} | Sender zone: ${message.timezone || "unknown"}`;

      top.append(name, time);
      bubble.appendChild(top);

      if (message.reply_to) {
        const reply = document.createElement("div");
        reply.className = "chat-reply-context";
        const replyName = document.createElement("strong");
        replyName.textContent = message.reply_to.author_name || "Player";
        const replyText = document.createElement("span");
        replyText.textContent = message.reply_to.content || "Attachment";
        reply.append(replyName, replyText);
        bubble.appendChild(reply);
      }

      if (message.content) {
        const content = document.createElement("p");
        content.className = "chat-content";
        content.textContent = message.content;
        bubble.appendChild(content);
      }

      if (Array.isArray(message.reactions) && message.reactions.length) {
        const reactions = document.createElement("div");
        reactions.className = "chat-reactions";
        message.reactions.forEach((reaction) => {
          const pill = document.createElement("span");
          pill.className = "chat-reaction-pill";
          pill.textContent = `${reaction.emoji} ${reaction.count}`;
          reactions.appendChild(pill);
        });
        bubble.appendChild(reactions);
      }

      if (Array.isArray(message.attachments) && message.attachments.length) {
        const list = document.createElement("div");
        list.className = "chat-message-attachments";
        message.attachments.forEach((attachment) => {
          if (isImageAttachment(attachment)) {
            const link = document.createElement("a");
            link.href = attachment.url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            const image = document.createElement("img");
            image.src = attachment.preview_url || attachment.url;
            image.alt = attachment.name || "Chat attachment";
            link.appendChild(image);
            list.appendChild(link);
          } else if (isAudioAttachment(attachment)) {
            const audio = document.createElement("audio");
            audio.controls = true;
            audio.src = attachment.url;
            list.appendChild(audio);
          } else {
            const link = document.createElement("a");
            link.className = "chat-file-link";
            link.href = attachment.url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = attachment.name || "Download file";
            list.appendChild(link);
          }
        });
        bubble.appendChild(list);
      }

      if (message.content) {
        const actions = document.createElement("div");
        actions.className = "chat-message-actions";
        const translate = document.createElement("button");
        translate.className = "chat-translate-button";
        translate.type = "button";
        translate.title = "Translate to English";
        translate.textContent = "EN";
        translate.addEventListener("click", () => translateMessage(message, bubble, translate));
        actions.appendChild(translate);
        bubble.appendChild(actions);
      }

      article.append(avatar, bubble);
      return article;
    };

    const renderMessages = (messages) => {
      chat.messages.replaceChildren();
      messages.forEach((message) => chat.messages.appendChild(renderMessage(message)));
      chat.messages.scrollTop = chat.messages.scrollHeight;
    };

    const refreshMessages = async () => {
      if (isLoadingMessages) return;
      isLoadingMessages = true;
      try {
        const response = await fetch("/api/chat/messages?limit=80", { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error("Chat unavailable");
        const payload = await response.json();
        const messages = payload.messages || [];
        renderMessages(messages);
        if (chat.online) chat.online.textContent = String(payload.online_count || 0);
        latestMessageAt = messages.length ? messages[messages.length - 1].created_at : latestMessageAt;
        const lastSeen = localStorage.getItem(STORAGE_KEYS.lastSeen);
        if (firstMessageSync && !lastSeen && latestMessageAt) {
          localStorage.setItem(STORAGE_KEYS.lastSeen, latestMessageAt);
        }
        firstMessageSync = false;
        if (chat.panel.hidden) {
          const seenAt = localStorage.getItem(STORAGE_KEYS.lastSeen) || latestMessageAt;
          const unseen = messages.filter((message) => message.created_at && message.created_at > seenAt).length;
          setUnread(unseen);
        } else {
          markSeen();
        }
        setStatus((payload.messages || []).length ? "Live global room" : "No messages yet");
      } catch (error) {
        setStatus("Global chat is offline right now", true);
      } finally {
        isLoadingMessages = false;
      }
    };

    const sendPresence = async () => {
      try {
        const body = {
          display_name: getGuestName() || chat.name.value,
          guest_id: getGuestId(),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
        };
        const response = await fetch("/api/chat/presence", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify(body)
        });
        if (!response.ok) return;
        const data = await response.json();
        if (chat.online) chat.online.textContent = String(data.online_count || 0);
      } catch (error) {
        // Presence should never block chat.
      }
    };

    const translateMessage = async (message, bubble, button) => {
      const existing = bubble.querySelector(".chat-translation");
      if (existing) {
        existing.remove();
        button.textContent = "EN";
        return;
      }

      button.textContent = "...";
      button.disabled = true;
      try {
        const response = await fetch("/api/chat/translate", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ text: message.content })
        });
        if (!response.ok) throw new Error("Translation unavailable");
        const data = await response.json();
        const translated = document.createElement("div");
        translated.className = "chat-translation";
        translated.textContent = data.translated_text || message.content;
        bubble.appendChild(translated);
        button.textContent = "Hide";
      } catch (error) {
        setStatus("Translation is unavailable", true);
        button.textContent = "EN";
      } finally {
        button.disabled = false;
      }
    };

    const renderPendingAttachments = () => {
      chat.attachments.hidden = pendingAttachments.length === 0;
      chat.attachments.replaceChildren();
      pendingAttachments.forEach((attachment, index) => {
        const chip = document.createElement("div");
        chip.className = "chat-attachment-chip";
        const label = document.createElement("span");
        label.textContent = attachment.name || "file";
        const remove = document.createElement("button");
        remove.className = "chat-attachment-remove";
        remove.type = "button";
        remove.textContent = "x";
        remove.title = "Remove file";
        remove.addEventListener("click", () => {
          pendingAttachments.splice(index, 1);
          renderPendingAttachments();
        });
        chip.append(label, remove);
        chat.attachments.appendChild(chip);
      });
    };

    const uploadFiles = async (files) => {
      const remainingSlots = Math.max(0, 4 - pendingAttachments.length);
      const selected = Array.from(files).slice(0, remainingSlots);
      for (const file of selected) {
        if (file.size > 8 * 1024 * 1024) {
          setStatus(`${file.name} is larger than 8 MB`, true);
          continue;
        }
        const formData = new FormData();
        formData.append("file", file);
        setStatus(`Uploading ${file.name}...`);
        try {
          const response = await fetch("/api/chat/upload", {
            method: "POST",
            headers: authHeaders(),
            body: formData
          });
          if (!response.ok) throw new Error("Upload failed");
          const data = await response.json();
          pendingAttachments.push(data.attachment);
          renderPendingAttachments();
          setStatus("File ready to send");
        } catch (error) {
          setStatus(`Could not upload ${file.name}`, true);
        }
      }
      chat.file.value = "";
    };

    const sendMessage = async () => {
      const content = chat.input.value.trim();
      const guestName = getGuestName() || setGuestName(chat.name.value);
      if (!currentUser && !guestName) {
        chat.login.classList.remove("is-hidden");
        chat.name.focus();
        setStatus("Add a player name or login with Discord", true);
        return;
      }
      if (!content && !pendingAttachments.length) return;

      const body = {
        content,
        display_name: guestName,
        guest_id: getGuestId(),
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        client_time: new Date().toISOString(),
        attachments: pendingAttachments
      };

      try {
        const response = await fetch("/api/chat/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify(body)
        });
        if (!response.ok) throw new Error("Message failed");
        chat.input.value = "";
        chat.input.style.height = "";
        pendingAttachments = [];
        renderPendingAttachments();
        updateIdentityView();
        await refreshMessages();
      } catch (error) {
        setStatus("Message was not sent", true);
      }
    };

    const insertEmoji = (emoji) => {
      const start = chat.input.selectionStart || chat.input.value.length;
      const end = chat.input.selectionEnd || chat.input.value.length;
      chat.input.value = `${chat.input.value.slice(0, start)}${emoji}${chat.input.value.slice(end)}`;
      chat.input.focus();
      chat.input.selectionStart = chat.input.selectionEnd = start + emoji.length;
      chat.input.dispatchEvent(new Event("input"));
    };

    emojis.forEach((emoji) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = emoji;
      button.title = emoji;
      button.addEventListener("click", () => insertEmoji(emoji));
      chat.emojiPanel.appendChild(button);
    });

    chat.discord.href = buildDiscordAuthUrl();
    chat.name.value = getGuestName();
    updateIdentityView();
    resolveDiscordIdentity();
    refreshMessages();
    sendPresence();
    pollTimer = window.setInterval(refreshMessages, 5000);
    presenceTimer = window.setInterval(sendPresence, 25000);

    chat.toggle.addEventListener("click", () => {
      const opening = chat.panel.hidden;
      chat.panel.hidden = !opening;
      chat.toggle.setAttribute("aria-expanded", String(opening));
      if (opening) {
        markSeen();
        if (!currentUser && !getGuestName()) chat.name.focus();
      }
    });

    chat.close.addEventListener("click", () => {
      chat.panel.hidden = true;
      chat.toggle.setAttribute("aria-expanded", "false");
      markSeen();
    });

    chat.guest.addEventListener("click", () => {
      const name = setGuestName(chat.name.value);
      if (!name) {
        setStatus("Enter a player name first", true);
        chat.name.focus();
        return;
      }
      currentUser = null;
      updateIdentityView();
      setStatus("Guest login ready");
      sendPresence();
      chat.input.focus();
    });

    chat.form.addEventListener("submit", (event) => {
      event.preventDefault();
      sendMessage();
    });

    chat.file.addEventListener("change", (event) => {
      uploadFiles(event.target.files || []);
    });

    chat.emoji.addEventListener("click", () => {
      chat.emojiPanel.hidden = !chat.emojiPanel.hidden;
    });

    chat.input.addEventListener("input", () => {
      chat.input.style.height = "auto";
      chat.input.style.height = `${Math.min(chat.input.scrollHeight, 112)}px`;
    });

    chat.input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });

    document.addEventListener("click", (event) => {
      if (!chat.emojiPanel.hidden && !chat.emojiPanel.contains(event.target) && !chat.emoji.contains(event.target)) {
        chat.emojiPanel.hidden = true;
      }
    });
  }
})();
