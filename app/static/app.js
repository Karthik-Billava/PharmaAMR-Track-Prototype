if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/static/sw.js").catch(() => {}));
}
document.querySelectorAll("form").forEach(form => {
  form.addEventListener("submit", () => {
    const btn = form.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
  });
});
