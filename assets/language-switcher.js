(function () {
  if (window.__whiteoutLanguageSwitcherLoaded) return;
  window.__whiteoutLanguageSwitcherLoaded = true;

  const STORAGE_KEY = "wos_site_language";
  const COOKIE_NAME = "googtrans";
  const PAGE_LANGUAGE = "en";
  const languages = [
    ["en", "English", "EN"],
    ["hi", "Hindi", "HI"],
    ["es", "Spanish", "ES"],
    ["fr", "French", "FR"],
    ["de", "German", "DE"],
    ["it", "Italian", "IT"],
    ["pt", "Portuguese", "PT"],
    ["ru", "Russian", "RU"],
    ["ar", "Arabic", "AR"],
    ["tr", "Turkish", "TR"],
    ["id", "Indonesian", "ID"],
    ["vi", "Vietnamese", "VI"],
    ["th", "Thai", "TH"],
    ["ja", "Japanese", "JA"],
    ["ko", "Korean", "KO"],
    ["zh-CN", "Chinese Simplified", "ZH"],
    ["zh-TW", "Chinese Traditional", "ZT"],
    ["pl", "Polish", "PL"],
    ["nl", "Dutch", "NL"],
    ["sv", "Swedish", "SV"]
  ];

  const languageMap = new Map(languages.map((language) => [language[0], language]));

  function getSavedLanguage() {
    const saved = localStorage.getItem(STORAGE_KEY);
    return languageMap.has(saved) ? saved : PAGE_LANGUAGE;
  }

  function setTranslateCookie(language) {
    const value = language === PAGE_LANGUAGE ? "" : `/${PAGE_LANGUAGE}/${language}`;
    const expires = language === PAGE_LANGUAGE ? "Thu, 01 Jan 1970 00:00:00 GMT" : "Fri, 31 Dec 9999 23:59:59 GMT";
    const hostParts = location.hostname.split(".");
    const domains = [location.hostname];

    if (hostParts.length > 2) {
      domains.push(`.${hostParts.slice(-2).join(".")}`);
    }

    domains.forEach((domain) => {
      document.cookie = `${COOKIE_NAME}=${value}; expires=${expires}; path=/; domain=${domain}; SameSite=Lax`;
    });
    document.cookie = `${COOKIE_NAME}=${value}; expires=${expires}; path=/; SameSite=Lax`;
  }

  function getCombo() {
    return document.querySelector(".goog-te-combo");
  }

  function applyGoogleLanguage(language) {
    const combo = getCombo();
    if (!combo) return false;
    combo.value = language === PAGE_LANGUAGE ? "" : language;
    combo.dispatchEvent(new Event("change"));
    return true;
  }

  function injectGoogleTranslate() {
    if (!document.getElementById("google_translate_element")) {
      const mount = document.createElement("div");
      mount.id = "google_translate_element";
      mount.setAttribute("aria-hidden", "true");
      document.body.appendChild(mount);
    }

    window.googleTranslateElementInit = function () {
      new window.google.translate.TranslateElement({
        pageLanguage: PAGE_LANGUAGE,
        includedLanguages: languages.map((language) => language[0]).join(","),
        autoDisplay: false
      }, "google_translate_element");

      const saved = getSavedLanguage();
      if (saved !== PAGE_LANGUAGE) {
        window.setTimeout(() => applyGoogleLanguage(saved), 350);
      }
    };

    if (!document.querySelector('script[src*="translate_a/element.js"]')) {
      const script = document.createElement("script");
      script.src = "https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit";
      script.async = true;
      document.head.appendChild(script);
    }
  }

  function injectStyles() {
    if (document.getElementById("wos-language-switcher-style")) return;
    const style = document.createElement("style");
    style.id = "wos-language-switcher-style";
    style.textContent = `
      .wos-language-switcher {
        position: relative;
        z-index: 120;
        font-family: var(--font-body, "DM Sans", ui-sans-serif, system-ui, sans-serif);
      }

      .wos-language-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.42rem;
        min-width: 3rem;
        min-height: 3rem;
        border: 1px solid rgba(221, 234, 244, 0.26);
        border-radius: 999px !important;
        background:
          linear-gradient(180deg, rgba(255, 255, 255, 0.13), rgba(255, 255, 255, 0.035)),
          radial-gradient(120% 120% at 20% 0%, rgba(141, 232, 255, 0.22), transparent 58%),
          rgba(8, 12, 22, 0.66);
        color: rgba(247, 251, 255, 0.95);
        box-shadow:
          inset 0 1px 0 rgba(255, 255, 255, 0.16),
          0 18px 34px -28px rgba(141, 232, 255, 0.9);
        cursor: pointer;
        clip-path: none !important;
        padding: 0 0.78rem;
        transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
      }

      .wos-language-button:hover,
      .wos-language-switcher.is-open .wos-language-button {
        transform: translateY(-1px);
        border-color: rgba(141, 232, 255, 0.62);
        background:
          linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.05)),
          radial-gradient(120% 120% at 20% 0%, rgba(141, 232, 255, 0.32), transparent 58%),
          rgba(12, 18, 32, 0.84);
        box-shadow:
          inset 0 1px 0 rgba(255, 255, 255, 0.24),
          0 20px 42px -26px rgba(141, 232, 255, 0.95);
      }

      .wos-language-button svg {
        width: 1.08rem;
        height: 1.08rem;
        flex: 0 0 auto;
      }

      .wos-language-current {
        min-width: 1.45rem;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-align: left;
      }

      .wos-language-menu {
        position: absolute;
        top: calc(100% + 0.7rem);
        right: 0;
        width: min(18rem, calc(100vw - 1.5rem));
        max-height: min(28rem, calc(100vh - 7rem));
        overflow: auto;
        border: 1px solid rgba(221, 234, 244, 0.18);
        border-radius: 0.75rem;
        background:
          linear-gradient(180deg, rgba(18, 27, 42, 0.96), rgba(6, 10, 19, 0.96)),
          rgba(6, 10, 19, 0.96);
        box-shadow:
          0 24px 60px -28px rgba(0, 0, 0, 0.9),
          0 0 34px -22px rgba(141, 232, 255, 0.9),
          inset 0 1px 0 rgba(255, 255, 255, 0.12);
        padding: 0.45rem;
        opacity: 0;
        pointer-events: none;
        transform: translateY(-0.4rem) scale(0.98);
        transform-origin: top right;
        transition: opacity 0.18s ease, transform 0.18s ease;
      }

      .wos-language-switcher.is-open .wos-language-menu {
        opacity: 1;
        pointer-events: auto;
        transform: translateY(0) scale(1);
      }

      .wos-language-heading {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 0.55rem 0.65rem 0.45rem;
        color: rgba(229, 237, 244, 0.68);
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
      }

      .wos-language-option {
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        gap: 0.9rem;
        border: 1px solid transparent;
        border-radius: 0.55rem !important;
        background: transparent;
        color: rgba(247, 251, 255, 0.92);
        cursor: pointer;
        clip-path: none !important;
        min-height: auto !important;
        padding: 0.68rem 0.72rem;
        font: inherit;
        text-align: left;
      }

      [data-theme="cyberpunk-cool"] .wos-language-switcher .wos-language-option,
      [data-theme="cyberpunk-cool"] .wos-language-switcher .wos-language-button {
        clip-path: none !important;
      }

      [data-theme="cyberpunk-cool"] .wos-language-switcher .wos-language-option {
        border-color: transparent !important;
        background: transparent !important;
        color: rgba(247, 251, 255, 0.92) !important;
        box-shadow: none !important;
      }

      .wos-language-option:hover,
      .wos-language-option:focus-visible {
        border-color: rgba(141, 232, 255, 0.28) !important;
        background: rgba(141, 232, 255, 0.08) !important;
        outline: none;
      }

      .wos-language-option.is-active {
        border-color: rgba(141, 232, 255, 0.42) !important;
        background: linear-gradient(90deg, rgba(141, 232, 255, 0.16), rgba(154, 99, 240, 0.08)) !important;
      }

      .wos-language-name {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-weight: 700;
      }

      .wos-language-code {
        flex: 0 0 auto;
        border: 1px solid rgba(221, 234, 244, 0.16);
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.055);
        color: rgba(229, 237, 244, 0.72);
        padding: 0.15rem 0.4rem;
        font-size: 0.68rem;
        font-weight: 800;
      }

      #google_translate_element,
      .goog-te-banner-frame,
      .goog-te-balloon-frame,
      .skiptranslate iframe {
        display: none !important;
      }

      body {
        top: 0 !important;
      }

      body > .skiptranslate {
        display: none !important;
      }

      @media (max-width: 640px) {
        .wos-language-button {
          min-width: 2.72rem;
          min-height: 2.72rem;
          padding: 0 0.68rem;
        }

        .wos-language-current {
          display: none;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function setActiveLanguage(root, language) {
    const current = languageMap.get(language) || languageMap.get(PAGE_LANGUAGE);
    const label = root.querySelector(".wos-language-current");
    if (label) label.textContent = current[2];

    root.querySelectorAll(".wos-language-option").forEach((option) => {
      const isActive = option.dataset.language === language;
      option.classList.toggle("is-active", isActive);
      option.setAttribute("aria-selected", String(isActive));
    });
  }

  function chooseLanguage(root, language) {
    localStorage.setItem(STORAGE_KEY, language);
    document.documentElement.lang = language;
    setActiveLanguage(root, language);
    setTranslateCookie(language);

    if (language === PAGE_LANGUAGE) {
      location.reload();
      return;
    }

    if (!applyGoogleLanguage(language)) {
      location.reload();
    }
  }

  function createSwitcher() {
    const root = document.createElement("div");
    root.className = "wos-language-switcher notranslate";
    root.setAttribute("translate", "no");
    root.innerHTML = `
      <button class="wos-language-button" type="button" aria-haspopup="listbox" aria-expanded="false" aria-label="Select website language" title="Select website language">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="10"></circle>
          <path d="M2 12h20"></path>
          <path d="M12 2a15.3 15.3 0 0 1 0 20"></path>
          <path d="M12 2a15.3 15.3 0 0 0 0 20"></path>
        </svg>
        <span class="wos-language-current">EN</span>
      </button>
      <div class="wos-language-menu" role="listbox" aria-label="Website language">
        <div class="wos-language-heading"><span>Website language</span><span>Translate</span></div>
        ${languages.map(([code, name, shortCode]) => `
          <button class="wos-language-option" type="button" role="option" data-language="${code}">
            <span class="wos-language-name">${name}</span>
            <span class="wos-language-code">${shortCode}</span>
          </button>
        `).join("")}
      </div>
    `;

    const button = root.querySelector(".wos-language-button");
    const close = () => {
      root.classList.remove("is-open");
      button.setAttribute("aria-expanded", "false");
    };
    const toggle = () => {
      const isOpen = root.classList.toggle("is-open");
      button.setAttribute("aria-expanded", String(isOpen));
    };

    button.addEventListener("click", (event) => {
      event.stopPropagation();
      toggle();
    });

    root.querySelectorAll(".wos-language-option").forEach((option) => {
      option.addEventListener("click", () => {
        chooseLanguage(root, option.dataset.language);
        close();
      });
    });

    document.addEventListener("click", (event) => {
      if (!root.contains(event.target)) close();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });

    setActiveLanguage(root, getSavedLanguage());
    return root;
  }

  function mountSwitcher() {
    if (document.querySelector(".wos-language-switcher")) return;
    injectStyles();

    const root = createSwitcher();
    const themeToggle = document.getElementById("theme-toggle");
    const actions = themeToggle && themeToggle.parentElement;
    const header = document.querySelector(".header-actions, .account-area, .top-bar-right, header > div:last-child, header");

    if (actions) {
      actions.insertBefore(root, themeToggle.nextSibling);
    } else if (header) {
      header.appendChild(root);
    } else {
      document.body.prepend(root);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      mountSwitcher();
      injectGoogleTranslate();
    });
  } else {
    mountSwitcher();
    injectGoogleTranslate();
  }
})();
