const $ = (id) => document.getElementById(id);
let token = "";
try { token = sessionStorage.getItem("adminToken") || ""; } catch {}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(caminho, opcoes = {}) {
  const resp = await fetch(caminho, {
    ...opcoes,
    headers: { "Content-Type": "application/json", "X-Admin-Token": token, ...(opcoes.headers || {}) },
  });
  if (resp.status === 401) throw new Error("Token inválido.");
  if (!resp.ok) {
    const erro = await resp.json().catch(() => ({}));
    throw new Error(typeof erro.detail === "string" ? erro.detail : "Erro na requisição.");
  }
  return resp.status === 204 ? null : resp;
}

// ---------- Login ----------
async function entrar() {
  try {
    await api("/api/funcionarios");
    try { sessionStorage.setItem("adminToken", token); } catch {}
    $("login").classList.add("escondido");
    $("painel").classList.remove("escondido");
    iniciarMapa();
    carregarTudo();
  } catch (e) {
    $("login-status").className = "status erro";
    $("login-status").textContent = e.message;
  }
}
$("entrar").addEventListener("click", () => { token = $("token").value; entrar(); });
if (token) entrar();

function carregarTudo() {
  carregarRegistros();
  carregarLocais();
  carregarFuncionarios();
}

// ---------- Registros ----------
function filtros() {
  const p = new URLSearchParams();
  if ($("f-dia").value) p.set("dia", $("f-dia").value);
  if ($("f-mat").value.trim()) p.set("matricula", $("f-mat").value.trim());
  return p.toString();
}

async function carregarRegistros() {
  const dados = await (await api("/api/registros?" + filtros())).json();
  $("registros").innerHTML = dados.map((r) => `
    <tr>
      <td>${new Date(r.data_hora + (r.data_hora.endsWith("Z") || r.data_hora.includes("+") ? "" : "Z")).toLocaleString("pt-BR")}</td>
      <td>${esc(r.nome)} <span class="sub">(${esc(r.matricula)})</span></td>
      <td>${esc(r.tipo)}</td>
      <td><span class="tag ${r.aceito ? "ok" : "erro"}">${r.aceito ? "aceito" : "recusado"}</span></td>
      <td>${esc(r.motivo)}</td>
      <td>${r.distancia_metros != null ? r.distancia_metros.toFixed(0) + " m" : "-"}</td>
      <td>${r.precisao_metros.toFixed(0)} m</td>
      <td>${esc(r.ip)}</td>
    </tr>`).join("") || `<tr><td colspan="8" class="sub">Nenhum registro.</td></tr>`;
}
$("filtrar").addEventListener("click", carregarRegistros);

$("csv").addEventListener("click", async () => {
  const blob = await (await api("/api/registros.csv?" + filtros())).blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "registros.csv";
  a.click();
  URL.revokeObjectURL(a.href);
});

// ---------- Locais ----------
let mapa, camada;
function iniciarMapa() {
  if (mapa) return;
  mapa = L.map("mapa").setView([-15.79, -47.88], 4);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    subdomains: "abcd",
    maxZoom: 20,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  }).addTo(mapa);
  camada = L.featureGroup().addTo(mapa);
  mapa.on("click", (e) => {
    $("l-lat").value = e.latlng.lat.toFixed(6);
    $("l-lon").value = e.latlng.lng.toFixed(6);
});
}

async function carregarLocais() {
  const locais = await (await fetch("/api/locais")).json();
  camada.clearLayers();
  locais.forEach((l) =>
    L.circle([l.latitude, l.longitude], { radius: l.raio_metros }).bindPopup(esc(l.nome)).addTo(camada));
  if (locais.length) mapa.fitBounds(camada.getBounds().pad(0.3));

  $("locais").innerHTML = locais.map((l) => `
    <tr>
      <td>${esc(l.nome)}</td><td>${l.latitude}</td><td>${l.longitude}</td><td>${l.raio_metros} m</td>
      <td><button class="secundario" data-remover="${l.id}">Remover</button></td>
    </tr>`).join("") || `<tr><td colspan="5" class="sub">Nenhum local cadastrado.</td></tr>`;
}

$("locais").addEventListener("click", async (e) => {
  const id = e.target.dataset.remover;
  if (!id || !confirm("Remover este local?")) return;
  await api(`/api/locais/${id}`, { method: "DELETE" });
  carregarLocais();
});

$("add-local").addEventListener("click", async () => {
  try {
    await api("/api/locais", {
      method: "POST",
      body: JSON.stringify({
        nome: $("l-nome").value,
        latitude: parseFloat($("l-lat").value),
        longitude: parseFloat($("l-lon").value),
        raio_metros: parseFloat($("l-raio").value),
      }),
    });
    $("l-nome").value = "";
    carregarLocais();
  } catch (e) { alert(e.message); }
});

// ---------- Funcionários ----------
async function carregarFuncionarios() {
  const lista = await (await api("/api/funcionarios")).json();
  $("funcionarios").innerHTML = lista.map((f) =>
    `<tr><td>${esc(f.nome)}</td><td>${esc(f.matricula)}</td><td>${f.ativo ? "sim" : "não"}</td></tr>`
  ).join("") || `<tr><td colspan="3" class="sub">Nenhum funcionário cadastrado.</td></tr>`;
}

$("add-func").addEventListener("click", async () => {
  try {
    await api("/api/funcionarios", {
      method: "POST",
      body: JSON.stringify({ nome: $("fn-nome").value, matricula: $("fn-mat").value }),
    });
    $("fn-nome").value = "";
    $("fn-mat").value = "";
    carregarFuncionarios();
  } catch (e) { alert(e.message); }
});
