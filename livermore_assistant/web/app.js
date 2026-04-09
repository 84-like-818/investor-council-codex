const state = { history: [], marketTimer: null };

function createMessage(role, content) {
  const template = document.getElementById("messageTemplate");
  const node = template.content.firstElementChild.cloneNode(true);
  node.classList.add(role === "assistant" ? "assistant" : "user");
  node.querySelector(".message-role").textContent = role === "assistant" ? "利弗莫尔" : "你";
  node.querySelector(".message-body").textContent = content;
  document.getElementById("messages").appendChild(node);
  node.scrollIntoView({ behavior: "smooth", block: "end" });
}

function renderTags(tags = []) {
  const box = document.getElementById("capabilityTags");
  box.innerHTML = "";
  tags.forEach((tag) => {
    const item = document.createElement("span");
    item.className = "pill";
    item.textContent = tag;
    box.appendChild(item);
  });
}

function renderStarters(items = []) {
  const list = document.getElementById("starterList");
  list.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });
}

function formatSigned(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  const num = Number(value);
  return `${num >= 0 ? "+" : ""}${num.toFixed(2)}%`;
}

function renderMarketOverview(data) {
  const status = document.getElementById("marketStatus");
  const updated = document.getElementById("marketUpdated");
  const grid = document.getElementById("marketGrid");
  grid.innerHTML = "";

  if (!data.available) {
    status.textContent = data.message || "当前未能拿到实时行情。";
    updated.textContent = "暂不可用";
    return;
  }

  status.textContent = "当前显示的是实时 A 股指数快照，可用于盘前和盘中快速定性。";
  updated.textContent = `刷新时间 ${data.updated_at || "刚刚"}`;

  (data.indices || []).forEach((item) => {
    const card = document.createElement("article");
    const pct = Number(item.pct || 0);
    card.className = `market-card ${pct >= 0 ? "up" : "down"}`;
    card.innerHTML = `
      <div class="market-name">${item.name}</div>
      <div class="market-price">${Number(item.price || 0).toFixed(2)}</div>
      <div class="market-move">${formatSigned(item.pct)}</div>
    `;
    grid.appendChild(card);
  });
}

async function loadBootstrap() {
  const response = await fetch("/api/bootstrap");
  const data = await response.json();

  document.title = data.brand;
  document.getElementById("brandTitle").textContent = data.headline || data.brand;
  document.getElementById("snapshotText").textContent = data.subline;
  document.getElementById("disclaimerText").textContent = data.disclaimer || "";
  document.getElementById("avatar").src = data.avatar_path;
  renderTags(data.capability_tags || []);
  renderStarters(data.starter_prompts || []);

  createMessage(
    "assistant",
    "我已经准备好了。你可以直接告诉我当前市场结构、你的仓位、持有什么标的，以及你最纠结的决定，我会用利弗莫尔的方式和你一起读市场。"
  );
}

async function refreshMarketOverview() {
  const button = document.getElementById("refreshMarketBtn");
  button.disabled = true;
  button.textContent = "刷新中...";
  try {
    const response = await fetch("/api/market/overview");
    const data = await response.json();
    renderMarketOverview(data);
  } catch (error) {
    renderMarketOverview({ available: false, message: "实时行情刷新失败，请稍后再试。" });
  } finally {
    button.disabled = false;
    button.textContent = "刷新";
  }
}

async function sendQuestion(event) {
  event.preventDefault();
  const questionInput = document.getElementById("questionInput");
  const marketNotes = document.getElementById("marketNotes");
  const sendBtn = document.getElementById("sendBtn");
  const message = questionInput.value.trim();
  if (!message) return;

  createMessage("user", message);
  state.history.push({ role: "user", content: message });
  questionInput.value = "";
  sendBtn.disabled = true;
  sendBtn.textContent = "判断中...";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        market_notes: marketNotes.value.trim(),
        history: state.history,
      }),
    });
    const data = await response.json();
    createMessage("assistant", data.answer || "这次判断没有成功生成，请再试一次。");
    state.history.push({ role: "assistant", content: data.answer || "" });
  } catch (error) {
    createMessage("assistant", "这次请求没有成功送达本地服务，请确认助手还在运行，然后再试一次。");
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "开始判断";
  }
}

function bindEvents() {
  document.getElementById("chatForm").addEventListener("submit", sendQuestion);
  document.getElementById("refreshMarketBtn").addEventListener("click", refreshMarketOverview);
  document.getElementById("questionInput").addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      document.getElementById("chatForm").requestSubmit();
    }
  });
}

async function boot() {
  bindEvents();
  await loadBootstrap();
  await refreshMarketOverview();
  state.marketTimer = window.setInterval(refreshMarketOverview, 45000);
}

boot();
