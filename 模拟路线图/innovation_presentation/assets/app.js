(function () {
  const order = [
    "index.html",
    "01-object.html",
    "02-architecture.html",
    "03-diagnosis.html",
    "04-relation-graph.html",
    "05-evaluation.html",
    "workflow.html"
  ];

  const file = location.pathname.split(/[\\/]/).pop() || "index.html";
  const index = order.indexOf(file);

  document.addEventListener("keydown", (event) => {
    if (event.target && ["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return;
    if (event.key === "ArrowRight" && index >= 0 && index < order.length - 1) {
      location.href = order[index + 1];
    }
    if (event.key === "ArrowLeft" && index > 0) {
      location.href = order[index - 1];
    }
  });
})();
