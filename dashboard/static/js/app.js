// Theme toggle persistence (respects OS default unless user overrides).
(function () {
  const saved = localStorage.getItem("theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
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
