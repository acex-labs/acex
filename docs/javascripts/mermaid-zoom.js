document.addEventListener("DOMContentLoaded", () => {
  const backdrop = document.createElement("div");
  backdrop.className = "mermaid-backdrop";
  document.body.appendChild(backdrop);

  function close() {
    const zoomed = document.querySelector(".mermaid.mermaid-zoomed");
    if (zoomed) zoomed.classList.remove("mermaid-zoomed");
    backdrop.classList.remove("active");
  }

  backdrop.addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });

  function attachZoom() {
    document.querySelectorAll(".mermaid").forEach((el) => {
      if (el.dataset.zoomAttached) return;
      el.dataset.zoomAttached = "1";
      el.style.cursor = "zoom-in";
      el.addEventListener("click", () => {
        if (el.classList.contains("mermaid-zoomed")) {
          close();
        } else {
          el.classList.add("mermaid-zoomed");
          backdrop.classList.add("active");
        }
      });
    });
  }

  const observer = new MutationObserver(attachZoom);
  observer.observe(document.body, { childList: true, subtree: true });
  attachZoom();
});
