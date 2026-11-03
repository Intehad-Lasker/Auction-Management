// Column sort links write into the filter form and resubmit it, so the form stays the
// single source of truth: later filter changes and auto-refreshes keep the chosen sort.
// Without JavaScript the links still work as plain page loads.
document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-sort]");
  const form = document.getElementById("filters");
  if (!link || !form || !window.htmx) return;
  event.preventDefault();
  form.querySelector("#sort").value = link.dataset.sort;
  form.querySelector("#dir").value = link.dataset.dir;
  htmx.trigger(form, "submit");
});
