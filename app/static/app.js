const $ = (id) => document.getElementById(id);

// Relógio
function tick() {
  const agora = new Date();
  $("relogio").textContent = agora.toLocaleTimeString("pt-BR");
  $("data").textContent = agora.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
}
tick();
setInterval(tick, 1000);

// Mapa
const mapa = L.map("mapa").setView([-15.79, -47.88], 4);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(mapa);
let marcador = null;

fetch("/api/locais")
  .then((r) => r.json())
  .then((locais) => {
    const grupo = locais.map((l) =>
      L.circle([l.latitude, l.longitude], { radius: l.raio_metros, color: "#1f6feb" })
        .bindPopup(`${l.nome} (raio ${l.raio_metros} m)`)
        .addTo(mapa)
    );
    if (grupo.length) mapa.fitBounds(L.featureGroup(grupo).getBounds().pad(0.3));
  });

// Lembra a matrícula neste aparelho
try { $("matricula").value = localStorage.getItem("matricula") || ""; } catch {}

function mostrar(msg, ok) {
  const el = $("status");
  el.className = "status " + (ok ? "ok" : "erro");
  el.textContent = msg;
}

function obterPosicao() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("Seu navegador não suporta geolocalização."));
    navigator.geolocation.getCurrentPosition(resolve, (err) => {
      const msgs = {
        1: "Permissão de localização negada. Libere o acesso nas configurações do navegador.",
        2: "Não foi possível determinar sua localização.",
        3: "Tempo esgotado ao obter a localização.",
      };
      reject(new Error(msgs[err.code] || err.message));
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
  });
}

$("bater").addEventListener("click", async () => {
  const matricula = $("matricula").value.trim();
  if (!matricula) return mostrar("Informe sua matrícula.", false);

  const botao = $("bater");
  botao.disabled = true;
  botao.textContent = "Obtendo localização...";

  try {
    const pos = await obterPosicao();
    const { latitude, longitude, accuracy } = pos.coords;

    if (marcador) marcador.remove();
    marcador = L.marker([latitude, longitude]).addTo(mapa).bindPopup("Você está aqui").openPopup();
    mapa.setView([latitude, longitude], 16);

    botao.textContent = "Registrando...";
    const resp = await fetch("/api/ponto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ matricula, latitude, longitude, precisao: accuracy }),
    });
    const dados = await resp.json();

    if (!resp.ok) return mostrar(dados.detail || "Erro ao registrar ponto.", false);

    try { localStorage.setItem("matricula", matricula); } catch {}
    const hora = new Date(dados.data_hora).toLocaleTimeString("pt-BR");
    if (dados.aceito) {
      mostrar(`✔ ${dados.tipo === "entrada" ? "Entrada" : "Saída"} registrada às ${hora}, ${dados.funcionario}. ${dados.motivo}.`, true);
    } else {
      mostrar(`✖ Ponto recusado: ${dados.motivo}.`, false);
    }
  } catch (e) {
    mostrar(e.message, false);
  } finally {
    botao.disabled = false;
    botao.textContent = "Bater ponto";
  }
});
