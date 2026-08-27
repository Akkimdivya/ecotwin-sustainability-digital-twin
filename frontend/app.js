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
let wasteReport = null;
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

function formatEvidenceKey(key) {
  return key.replaceAll("_", " ");
}

function renderOpportunities() {
  document.querySelector("#method-version").textContent = wasteReport.method_version;
  const grid = document.querySelector("#opportunity-grid");
  grid.innerHTML = wasteReport.findings.map((finding) => {
    const chips = Object.entries(finding.evidence)
      .filter(([, value]) => typeof value !== "object" && value !== null)
      .slice(0, 4)
      .map(([key, value]) => `<span class="evidence-chip">${formatEvidenceKey(key)}: ${value}</span>`)
      .join("");
    const action = finding.waste_type === "over_provisioned_compute" ? "simulate" : "inspect";
    const buttonLabel = action === "simulate" ? "Simulate recommendation" : "Inspect evidence";
    return `
      <article class="opportunity">
        <div class="opportunity-top">
          <span class="opportunity-kind">${formatEvidenceKey(finding.waste_type)}</span>
          <span class="confidence">${finding.confidence} confidence</span>
        </div>
        <h3>${finding.title}</h3>
        <code>${finding.resource_name}</code>
        <p>${finding.reason}</p>
        <div class="evidence-strip">${chips}</div>
        <button data-resource-id="${finding.resource_id}" data-action="${action}">${buttonLabel}</button>
      </article>`;
  }).join("");
  grid.querySelectorAll("button[data-resource-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectNode(button.dataset.resourceId);
      if (button.dataset.action === "simulate") {
        prepareSimulation(button.dataset.resourceId);
        document.querySelector("#what-if-simulator").scrollIntoView({ behavior: "smooth", block: "start" });
      } else {
        document.querySelector("#evidence-card").scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });
}

function prepareSimulation(resourceId) {
  const node = twin.nodes.find((candidate) => candidate.id === resourceId);
  if (!node) return;
  selectedNodeId = resourceId;
  const currentVcpu = Number(node.configuration.vcpu);
  const currentMemory = Number(node.configuration.memory_gb);
  document.querySelector("#simulation-resource-name").textContent = node.name;
  document.querySelector("#simulation-resource-id").textContent = node.id;
  document.querySelector("#current-vcpu").textContent = `${currentVcpu} vCPU`;
  document.querySelector("#current-memory").textContent = `${currentMemory} GB memory`;
  const proposedVcpu = document.querySelector("#proposed-vcpu");
  const proposedMemory = document.querySelector("#proposed-memory");
  const targetVcpu = Math.max(1, Math.floor(currentVcpu / 2));
  const targetMemory = targetVcpu * 4;
  proposedVcpu.min = String(targetVcpu);
  proposedVcpu.max = String(targetVcpu);
  proposedVcpu.value = String(targetVcpu);
  proposedMemory.min = String(targetMemory);
  proposedMemory.max = String(targetMemory);
  proposedMemory.value = String(targetMemory);
}

function renderSimulation(result) {
  document.querySelector("#simulation-placeholder").classList.add("hidden");
  document.querySelector("#simulation-results").classList.remove("hidden");
  document.querySelector("#simulation-id").textContent = `${result.simulation_id} / ${result.method_version}`;
  const riskBadge = document.querySelector("#risk-level");
  riskBadge.textContent = `${result.risk.level} risk`;
  riskBadge.className = `risk-badge ${result.risk.level}`;
  document.querySelector("#cost-before").textContent = `$${result.before.monthly_cost_usd.toFixed(2)}`;
  document.querySelector("#cost-after").textContent = `$${result.after.monthly_cost_usd.toFixed(2)}`;
  document.querySelector("#cost-impact").textContent = `$${result.impact.monthly_cost_savings_usd.toFixed(2)} saved / ${result.impact.monthly_cost_savings_pct}%`;
  document.querySelector("#carbon-before").textContent = `${result.before.estimated_carbon_kgco2e.toFixed(2)} kg`;
  document.querySelector("#carbon-after").textContent = `${result.after.estimated_carbon_kgco2e.toFixed(2)} kg`;
  document.querySelector("#carbon-impact").textContent = `${result.impact.carbon_reduction_kgco2e.toFixed(2)} kg reduced / ${result.impact.carbon_reduction_pct}%`;
  document.querySelector("#cpu-projection").textContent = `${result.performance.current_cpu_p95_pct}% → ${result.performance.predicted_cpu_p95_pct}%`;
  document.querySelector("#memory-projection").textContent = `${result.performance.current_memory_p95_pct}% → ${result.performance.predicted_memory_p95_pct}%`;
  document.querySelector("#cpu-bar").style.width = `${result.performance.predicted_cpu_p95_pct}%`;
  document.querySelector("#memory-bar").style.width = `${result.performance.predicted_memory_p95_pct}%`;
  document.querySelector("#risk-reasons").innerHTML = result.risk.reasons.map((reason) => `<div>${reason}</div>`).join("");
  document.querySelector("#confidence-level").textContent = result.confidence;
  document.querySelector("#confidence-reason").textContent = result.confidence_reason;
  document.querySelector("#simulation-assumptions").innerHTML = result.assumptions.map((assumption) => `<li>${assumption}</li>`).join("");
}

async function runSimulation(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  const error = document.querySelector("#simulation-error");
  const resourceId = document.querySelector("#simulation-resource-id").textContent;
  button.disabled = true;
  error.classList.add("hidden");
  try {
    const simulationRequest = {
      resource_id: resourceId,
      proposed_vcpu: Number(document.querySelector("#proposed-vcpu").value),
      proposed_memory_gb: Number(document.querySelector("#proposed-memory").value),
      growth_buffer_pct: Number(document.querySelector("#growth-buffer").value),
    };
    const response = await fetch("/api/simulations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(simulationRequest),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `Simulation failed (${response.status})`);
    renderSimulation(payload);
    loadExplanation(simulationRequest);
  } catch (failure) {
    error.textContent = failure.message;
    error.classList.remove("hidden");
  } finally {
    button.disabled = false;
  }
}

async function loadExplanation(simulationRequest) {
  const loading = document.querySelector("#ai-loading");
  const content = document.querySelector("#ai-content");
  const provider = document.querySelector("#ai-provider");
  loading.textContent = "Explaining the deterministic result...";
  loading.classList.remove("hidden");
  content.classList.add("hidden");
  provider.textContent = "Preparing";
  try {
    const response = await fetch("/api/explanations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(simulationRequest),
    });
    const explanation = await response.json();
    if (!response.ok) throw new Error(explanation.detail || "Explanation unavailable");
    provider.textContent = explanation.provider === "VERTEX_AI"
      ? `Vertex AI / ${explanation.model}`
      : "Deterministic fallback";
    document.querySelector("#ai-summary").textContent = explanation.content.summary;
    document.querySelector("#ai-recommendation").textContent = explanation.content.recommendation;
    document.querySelector("#ai-rationale").textContent = explanation.content.rationale;
    document.querySelector("#ai-validation-steps").innerHTML = explanation.content.validation_steps
      .map((step) => `<li>${step}</li>`)
      .join("");
    document.querySelector("#ai-rollback").textContent = explanation.content.rollback_trigger;
    loading.classList.add("hidden");
    content.classList.remove("hidden");
  } catch (failure) {
    loading.textContent = `Explanation unavailable: ${failure.message}`;
    provider.textContent = "Unavailable";
  }
}

async function initialize() {
  try {
    const [twinResponse, findingsResponse] = await Promise.all([
      fetch("/api/twin"),
      fetch("/api/findings"),
    ]);
    if (!twinResponse.ok) throw new Error(`Twin API returned ${twinResponse.status}`);
    if (!findingsResponse.ok) throw new Error(`Findings API returned ${findingsResponse.status}`);
    twin = await twinResponse.json();
    wasteReport = await findingsResponse.json();

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
    renderOpportunities();
  } catch (error) {
    loadingState.innerHTML = `<strong>Unable to load the digital twin.</strong><span>${error.message}</span>`;
  }
}

document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => applyFilter(button.dataset.filter)));
document.querySelector("#growth-buffer").addEventListener("input", (event) => {
  document.querySelector("#growth-buffer-value").textContent = `${event.target.value}%`;
});
document.querySelector("#simulation-form").addEventListener("submit", runSimulation);
initialize();
