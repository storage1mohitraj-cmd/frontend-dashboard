(() => {
  const FLAKE_COUNT = 120;
  const MIN_SIZE = 1;
  const MAX_SIZE = 4;
  // Slightly slower snowfall for a calmer look.
  const MIN_SPEED = 0.2;
  const MAX_SPEED = 1.0;
  const WIND_STRENGTH = 0.25;
  const COLLISION_PUSH = 0.9;
  const COLLISION_SCAN_MS = 650;

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  const flakes = [];

  if (!ctx) return;

  canvas.setAttribute("aria-hidden", "true");
  canvas.style.position = "fixed";
  canvas.style.top = "0";
  canvas.style.left = "0";
  canvas.style.width = "100vw";
  canvas.style.height = "100vh";
  canvas.style.pointerEvents = "none";
  canvas.style.zIndex = "2";
  canvas.style.opacity = "0.8";

  let width = window.innerWidth;
  let height = window.innerHeight;
  let obstacles = [];
  let lastObstacleScan = 0;

  function rand(min, max) {
    return Math.random() * (max - min) + min;
  }

  function createFlake(initialY) {
    const size = rand(MIN_SIZE, MAX_SIZE);
    return {
      x: rand(0, width),
      y: initialY ?? rand(-height, 0),
      size,
      speedY: rand(MIN_SPEED, MAX_SPEED) * (size / MAX_SIZE + 0.5),
      drift: rand(-WIND_STRENGTH, WIND_STRENGTH),
      wobble: rand(0.002, 0.01),
      phase: rand(0, Math.PI * 2)
    };
  }

  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
    scanObstacles();
  }

  function scanObstacles() {
    // Bounce only on text-bearing elements, not full containers/cards.
    const selectors = [
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "p",
      "span",
      "a",
      "li",
      "button",
      "label",
      "strong",
      "em",
      "small",
      "summary"
    ];

    const seen = new Set();
    const nodes = [];
    for (const selector of selectors) {
      for (const el of document.querySelectorAll(selector)) {
        if (!el || seen.has(el)) continue;
        seen.add(el);
        nodes.push(el);
      }
    }

    obstacles = nodes.flatMap((el) => {
      const rects = Array.from(el.getClientRects());
      return rects
        .filter((r) => r.width > 8 && r.height > 8)
        .map((r) => ({
          left: r.left,
          right: r.right,
          top: r.top,
          bottom: r.bottom
        }));
    });
  }

  function bounceOffObstacles(flake) {
    // If a flake enters a content rectangle, push it out and invert drift.
    for (let i = 0; i < obstacles.length; i += 1) {
      const o = obstacles[i];
      if (
        flake.x >= o.left &&
        flake.x <= o.right &&
        flake.y >= o.top &&
        flake.y <= o.bottom
      ) {
        const dLeft = Math.abs(flake.x - o.left);
        const dRight = Math.abs(o.right - flake.x);
        const dTop = Math.abs(flake.y - o.top);
        const dBottom = Math.abs(o.bottom - flake.y);
        const min = Math.min(dLeft, dRight, dTop, dBottom);

        if (min === dTop) {
          flake.y = o.top - flake.size - 0.5;
        } else if (min === dBottom) {
          flake.y = o.bottom + flake.size + 0.5;
        } else if (min === dLeft) {
          flake.x = o.left - flake.size - 0.5;
        } else {
          flake.x = o.right + flake.size + 0.5;
        }

        flake.drift = -flake.drift || rand(-WIND_STRENGTH, WIND_STRENGTH);
        flake.y -= COLLISION_PUSH; // small "bounce" upward
        return;
      }
    }
  }

  function populate() {
    flakes.length = 0;
    for (let i = 0; i < FLAKE_COUNT; i += 1) {
      flakes.push(createFlake());
    }
  }

  function update() {
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "rgba(255, 255, 255, 0.9)";

    const now = performance.now();
    if (now - lastObstacleScan > COLLISION_SCAN_MS) {
      lastObstacleScan = now;
      scanObstacles();
    }

    for (let i = 0; i < flakes.length; i += 1) {
      const flake = flakes[i];
      flake.y += flake.speedY;
      flake.x += flake.drift + Math.sin((flake.y + flake.phase) * flake.wobble);

      bounceOffObstacles(flake);

      if (flake.y > height + 10 || flake.x < -20 || flake.x > width + 20) {
        flakes[i] = createFlake(-10);
        continue;
      }

      ctx.beginPath();
      ctx.arc(flake.x, flake.y, flake.size, 0, Math.PI * 2);
      ctx.fill();
    }

    requestAnimationFrame(update);
  }

  function mount() {
    if (!document.body) return;
    document.body.appendChild(canvas);
    resize();
    populate();
    update();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }

  window.addEventListener("resize", resize);
})();
