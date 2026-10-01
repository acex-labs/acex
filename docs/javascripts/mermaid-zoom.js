document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.createElement("div");
  overlay.className = "mermaid-overlay";
  document.body.appendChild(overlay);

  overlay.addEventListener("click", () => overlay.classList.remove("active"));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") overlay.classList.remove("active");
  });

  function attachZoom() {
    document.querySelectorAll(".mermaid svg").forEach((svg) => {
      if (svg.dataset.zoomAttached) return;
      svg.dataset.zoomAttached = "1";
      svg.addEventListener("click", () => {
        overlay.innerHTML = "";
        overlay.appendChild(svg.cloneNode(true));
        overlay.classList.add("active");
      });
    });
  }

  // Mermaid renders asynchronously — observe for SVG insertion
  const observer = new MutationObserver(attachZoom);
  observer.observe(document.body, { childList: true, subtree: true });
  attachZoom();
});
