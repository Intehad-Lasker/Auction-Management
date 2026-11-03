// Ticks every row's countdown once a second. Mirrors rosehill/web/formatting.py.
(() => {
  const NOW_MS = 5 * 60 * 1000;
  const SOON_MS = 15 * 60 * 1000;

  const text = (ms) => {
    const s = Math.floor(ms / 1000);
    if (s <= 0) return "closing";
    if (s < 3600) return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    return `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}m`;
  };
  const level = (ms) => (ms <= 0 ? "closing" : ms <= NOW_MS ? "now" : ms <= SOON_MS ? "soon" : "later");

  const tick = () => {
    const now = Date.now();
    document.querySelectorAll("table[data-window]").forEach((table) => {
      const windowMs = Number(table.dataset.window) * 60 * 1000;
      table.querySelectorAll("tr[data-closes]").forEach((row) => {
        const left = Number(row.dataset.closes) - now;
        row.querySelector(".time-text").textContent = text(left);
        row.querySelector(".fuse-burn").style.width = `${Math.max(0, Math.min(1, left / windowMs)) * 100}%`;
        row.className = row.className.replace(/urgency-\w+/, `urgency-${level(left)}`);
      });
    });
  };
  setInterval(tick, 1000);
})();
