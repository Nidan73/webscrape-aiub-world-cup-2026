// Theme toggle: respects OS default unless user overrides, persists choice.
(function () {
  const root = document.documentElement;
  const toggle = document.getElementById("theme-toggle");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const saved = localStorage.getItem("theme");
  let theme = saved || (prefersDark ? "dark" : "light");
  root.setAttribute("data-theme", theme);
  if (!toggle) return;
  toggle.setAttribute("aria-pressed", String(theme === "dark"));
  toggle.addEventListener("click", () => {
    theme = theme === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
    toggle.setAttribute("aria-pressed", String(theme === "dark"));
  });
})();

// Background refresh: POST /refresh, poll /refresh/status, reload when done.
(function () {
  const btn = document.getElementById("refresh-btn");
  if (!btn) return;
  let timer = null;

  function poll() {
    fetch("/refresh/status").then((r) => r.json()).then((s) => {
      if (s.state === "running") {
        btn.textContent = "Refreshing…";
        btn.disabled = true;
      } else if (s.state === "done") {
        clearInterval(timer);
        location.reload();
      } else if (s.state === "error") {
        clearInterval(timer);
        btn.disabled = false;
        btn.textContent = "Refresh failed — retry";
      }
    });
  }

  btn.addEventListener("click", () => {
    btn.disabled = true;
    btn.textContent = "Refreshing…";
    fetch("/refresh", { method: "POST" }).then(() => {
      if (timer) clearInterval(timer);
      timer = setInterval(poll, 2000);
    });
  });
})();
