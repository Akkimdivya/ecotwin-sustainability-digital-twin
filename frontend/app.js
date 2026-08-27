const svg = document.querySelector("#twin-graph");
const loadingState = document.querySelector("#loading-state");
const emptyEvidence = document.querySelector("#empty-evidence");
const evidenceContent = document.querySelector("#evidence-content");

const positions = {
  "lb-public-01": [105, 260],
  "vm-web-01": [300, 145],
  "vm-api-01": [300, 330],
  "vm-batch-02": [300, 500],
  "disk-api-boot": [500, 120],
  "sql-orders-01": [520, 330],
  "disk-orders-data": [710, 235],
  "bucket-orders-archive": [770, 425],
  "disk-orphan-01": [710, 75],
};

const typeLabels = {
  load_balancer: "Load balancer",
  compute_instance: "Compute",
  cloud_sql: "Cloud SQL",
  persistent_disk: "Disk",
  storage_bucket: "Bucket",
};

const typeSymbols = {
  load_balancer: "LB",
  compute_instance: "VM",
  cloud_sql: "DB",
  persistent_disk: "PD",
  storage_bucket: "CS",
};

const stateLabels = {
  healthy: "Healthy",
  idle: "Idle",
  over_provisioned: "Right-size",
  storage_waste: "Storage waste",
  unassessed: "Unassessed",
};

let twin = null;
let selectedNodeId = null;

function svgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function nodePosition(node, index) {
  return positions[node.id] || [120 + (index % 4) * 210, 90 + Math.floor(index / 4) * 180];
}

function edgePath(source, target) {
  const dx = target[0] - source[0];
  const controlX = source[0] + dx * 0.5;
  return `M ${source[0] + 35} ${source[1]} C ${controlX} ${source[1]}, ${controlX} ${target[1]}, ${target[0] - 35} ${target[1]}`;
}

function renderGraph() {
  svg.replaceChildren();
  const defs = svgElement("defs");
  const marker = svgElement("marker", {
    id: "arrow",
    viewBox: "0 0 10 10",
    refX: "8",
    refY: "5",
    markerWidth: "5",
    markerHeight: "5",
    orient: "auto-start-reverse",
  });
  marker.append(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "rgba(142,170,157,.45)" }));
  defs.append(marker);
  svg.append(defs);

  const nodeMap = new Map(twin.nodes.map((node, index) => [node.id, { node, position: nodePosition(node, index) }]));
  twin.edges.forEach((edge) => {
    const source = nodeMap.get(edge.source)?.position;
    const target = nodeMap.get(edge.target)?.position;
    if (!source || !target) return;
    const path = svgElement("path", { class: "edge", d: edgePath(source, target), "marker-end": "url(#arrow)" });
    svg.append(path);
    const label = svgElement("text", {
      class: "edge-label",
      x: String((source[0] + target[0]) / 2),
      y: String((source[1] + target[1]) / 2 - 7),
    });
    label.textContent = edge.relationship.replace("_", " ");
    svg.append(label);
  });

  twin.nodes.forEach((node, index) => {
    const [x, y] = nodePosition(node, index);
    const group = svgElement("g", {
      class: `node${node.id === selectedNodeId ? " selected" : ""}`,
      transform: `translate(${x} ${y})`,
      tabindex: "0",
      role: "button",
      "aria-label": `${node.name}, ${stateLabels[node.state]}`,
      "data-id": node.id,
      "data-state": node.state,
    });
    group.append(svgElement("circle", { class: "node-halo", r: "39" }));
    group.append(svgElement("circle", { class: "node-core", r: "31" }));
    const symbol = svgElement("text", { class: "node-symbol", y: "1" });
    symbol.textContent = typeSymbols[node.type] || "R";
    group.append(symbol);
    const name = svgElement("text", { class: "node-name", y: "52" });
    name.textContent = node.name.length > 18 ? `${node.name.slice(0, 16)}...` : node.name;
    group.append(name);
    const type = svgElement("text", { class: "node-type", y: "66" });
    type.textContent = typeLabels[node.type] || node.type;
    group.append(type);
    group.addEventListener("click", () => selectNode(node.id));
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode(node.id);
      }
    });
    svg.append(group);
  });
}

function fact(label, value) {
  if (value === null || value === undefined || value === "") return "";
  return `<div><dt>${label}</dt><dd>${value}</dd></div>`;
}

function formatNumber(value, suffix = "") {
  return value === null || value === undefined ? "No signal" : `${Number(value).toFixed(1)}${suffix}`;
}

function connectionMarkup(edge, direction) {
  const peerId = direction === "in" ? edge.source : edge.target;
  const peer = twin.nodes.find((node) => node.id === peerId);
  const arrow = direction === "in" ? "Incoming" : "Outgoing";
  return `<div class="connection"><span>${arrow} / ${edge.relationship.replace("_", " ")}</span><strong>${peer?.name || peerId}</strong></div>`;
}

function selectNode(nodeId) {
  selectedNodeId = nodeId;
  renderGraph();
  const node = twin.nodes.find((candidate) => candidate.id === nodeId);
  const incoming = twin.edges.filter((edge) => edge.target === nodeId);
  const outgoing = twin.edges.filter((edge) => edge.source === nodeId);

  emptyEvidence.classList.add("hidden");
  evidenceContent.classList.remove("hidden");
  document.querySelector("#node-type").textContent = typeLabels[node.type] || node.type;
  document.querySelector("#node-name").textContent = node.name;
  document.querySelector("#node-id").textContent = node.id;
  const state = document.querySelector("#node-state");
  state.textContent = stateLabels[node.state];
  state.className = `state-pill ${node.state}`;
  document.querySelector("#node-reason").textContent = node.state_reason;

  const configuration = {
    Region: node.region,
    Zone: node.zone,
    Status: node.provider_status,
    ...Object.fromEntries(Object.entries(node.configuration).map(([key, value]) => [key.replaceAll("_", " "), value])),
  };
  document.querySelector("#configuration-facts").innerHTML = Object.entries(configuration)
    .map(([label, value]) => fact(label, value))
    .join("");

  const metrics = node.metrics;
  document.querySelector("#metric-facts").innerHTML = [
    fact("Sample days", metrics.sample_days),
    fact("CPU mean", formatNumber(metrics.cpu_mean_pct, "%")),
    fact("CPU p95", formatNumber(metrics.cpu_p95_pct, "%")),
    fact("Memory p95", formatNumber(metrics.memory_p95_pct, "%")),
    fact("Network mean", formatNumber(metrics.network_gb_mean, " GB")),
    fact("Disk used", formatNumber(metrics.disk_used_pct, "%")),
  ].join("");

  const connections = [...incoming.map((edge) => connectionMarkup(edge, "in")), ...outgoing.map((edge) => connectionMarkup(edge, "out"))];
  document.querySelector("#connection-list").innerHTML = connections.length
    ? connections.join("")
    : '<div class="connection empty">No dependency edges</div>';
}

function applyFilter(filter) {
  document.querySelectorAll(".filter").forEach((button) => button.classList.toggle("active", button.dataset.filter === filter));
  document.querySelectorAll(".node").forEach((element) => {
    const shouldDim = filter === "review" && element.dataset.state === "healthy";
    element.classList.toggle("dimmed", shouldDim);
  });
}

async function initialize() {
  try {
    const response = await fetch("/api/twin");
    if (!response.ok) throw new Error(`Twin API returned ${response.status}`);
    twin = await response.json();

    document.querySelector("#source-badge").textContent = `${twin.data_mode} / ${twin.active_repository}`;
    document.querySelector("#total-nodes").textContent = twin.summary.total_nodes;
    document.querySelector("#total-edges").textContent = twin.summary.total_edges;
    document.querySelector("#review-count").textContent = twin.summary.idle + twin.summary.over_provisioned + twin.summary.storage_waste;
    document.querySelector("#snapshot-id").textContent = twin.snapshot_id.replace("twin-", "");
    document.querySelector("#snapshot-time").textContent = new Date(twin.snapshot_at).toLocaleDateString();
    document.querySelector("#graph-caption").textContent = `${twin.summary.total_nodes} nodes / ${twin.summary.total_edges} immutable edges`;
    document.querySelector("#data-version").textContent = `Data ${twin.data_version}`;
    loadingState.classList.add("hidden");
    renderGraph();
  } catch (error) {
    loadingState.innerHTML = `<strong>Unable to load the digital twin.</strong><span>${error.message}</span>`;
  }
}

document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => applyFilter(button.dataset.filter)));
initialize();
