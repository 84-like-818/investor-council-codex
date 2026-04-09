const state = {
  bootstrap: null,
  mentors: { ready: [], planned: [] },
  mentorMap: new Map(),
  selectedMentorId: null,
  drawerMentorId: null,
  latestHandoff: null,
  runtime: null,
  submitMode: "continue",
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function postJson(url, payload) {
  return fetchJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function statusClass(ok, warn = false) {
  if (ok) return "success";
  return warn ? "warn" : "danger";
}

function modeLabel(mode) {
  if (mode === "auto_sent") return "已自动发送";
  if (mode === "clipboard_fallback") return "已复制，待手动发送";
  if (mode === "clipboard_only") return "仅保留剪贴板";
  return "等待操作";
}

function getSelectedMentor() {
  return state.mentorMap.get(state.selectedMentorId) || null;
}

function updateWindowTitle(mentor) {
  const base = state.bootstrap?.brand || "投资大师智能团";
  document.title = mentor ? `${base} · ${mentor.display_name_zh}` : base;
}

function renderBrand(bootstrap) {
  document.getElementById("brandMark").src = bootstrap.brand_icon || "";
  document.getElementById("brandTitle").textContent = bootstrap.brand;
  document.getElementById("brandSubtitle").textContent = bootstrap.subline || bootstrap.headline || "";
}

function renderStatusStrip(runtime) {
  const strip = document.getElementById("statusStrip");
  strip.innerHTML = "";
  const items = [
    {
      label: runtime.blocking
        ? (runtime.codex_installed ? "还差一步可开始" : "需要先安装 Codex")
        : "产品已就绪",
      tone: runtime.blocking ? statusClass(false, true) : statusClass(true),
    },
    {
      label: runtime.skill_installed ? "人物入口已同步" : "人物入口待修复",
      tone: runtime.skill_installed ? statusClass(true) : statusClass(false, true),
    },
    {
      label: runtime.market_data_ready ? "实时市场数据可用" : "实时数据存在缺口",
      tone: runtime.market_data_ready ? statusClass(true) : statusClass(false, true),
    },
  ];
  items.forEach((item) => {
    const node = document.createElement("span");
    node.className = `status-pill ${item.tone}`;
    node.textContent = item.label;
    strip.appendChild(node);
  });
}

function renderBlocking(runtime) {
  const banner = document.getElementById("blockingBanner");
  if (!runtime.blocking) {
    banner.classList.add("hidden");
    return;
  }
  document.getElementById("blockingTitle").textContent = "还差一步才能开始对话";
  document.getElementById("blockingMessage").textContent = runtime.blocking_message || "当前环境还没有完全准备好。";
  document.getElementById("blockingAction").textContent = runtime.blocking_action || "请先处理阻塞项，再继续交接。";
  banner.classList.remove("hidden");
}

function renderRuntimeSummary(runtime) {
  const box = document.getElementById("runtimeSummary");
  box.innerHTML = "";
  const items = [
    {
      text: runtime.codex_running ? "Codex 正在运行" : "Codex 会在交接时自动拉起",
      tone: statusClass(runtime.codex_running, true),
    },
    {
      text: runtime.auto_injection_available ? "支持自动粘贴并发送" : "将回退为剪贴板发送",
      tone: statusClass(runtime.auto_injection_available, true),
    },
    {
      text: runtime.product_home_writable ? "本地状态目录可写" : "本地状态目录不可写",
      tone: statusClass(runtime.product_home_writable),
    },
  ];
  items.forEach((item) => {
    const chip = document.createElement("span");
    chip.className = `mini-pill ${item.tone}`;
    chip.textContent = item.text;
    box.appendChild(chip);
  });
}

function renderDiagnostics(runtime) {
  const list = document.getElementById("diagnosticsList");
  list.innerHTML = "";
  (runtime.checks || []).forEach((item) => {
    const node = document.createElement("article");
    node.className = "diagnostic-item";
    node.innerHTML = `
      <div class="diagnostic-head">
        <strong>${escapeHtml(item.label)}</strong>
        <span class="status-pill ${statusClass(item.ok, item.warn)}">${item.ok ? "正常" : item.warn ? "关注" : "阻塞"}</span>
      </div>
      <p class="diagnostic-message">${escapeHtml(item.message || "")}</p>
      <p class="diagnostic-action">${escapeHtml(item.action || "")}</p>
    `;
    list.appendChild(node);
  });
}

function createReadyCard(mentor) {
  const template = document.getElementById("mentorCardTemplate");
  const node = template.content.firstElementChild.cloneNode(true);
  if (mentor.id === state.selectedMentorId) node.classList.add("selected");
  node.querySelector(".mentor-avatar").src = mentor.avatar_path;
  node.querySelector(".mentor-name").textContent = mentor.display_name_zh;
  node.querySelector(".mentor-en-name").textContent = mentor.display_name_en;
  node.querySelector(".mentor-label").textContent = mentor.selection_label;
  node.querySelector(".mentor-summary").textContent = mentor.summary || "";
  node.querySelector(".mentor-status").textContent = "可直接开始";
  const button = node.querySelector(".mentor-action-btn");
  button.textContent = `进入 ${mentor.display_name_zh}`;
  button.addEventListener("click", () => selectMentor(mentor.id));
  node.addEventListener("dblclick", () => {
    selectMentor(mentor.id);
    document.getElementById("questionInput").focus();
  });
  return node;
}

function createPlannedCard(mentor) {
  const template = document.getElementById("plannedCardTemplate");
  const node = template.content.firstElementChild.cloneNode(true);
  node.querySelector(".planned-avatar").src = mentor.avatar_path;
  node.querySelector(".planned-name").textContent = mentor.display_name_zh;
  node.querySelector(".planned-label").textContent = mentor.selection_label;
  node.querySelector(".planned-action").addEventListener("click", () => openDrawer(mentor.id));
  return node;
}

function renderMentors(payload) {
  state.mentors = payload;
  state.mentorMap = new Map([...payload.ready, ...payload.planned].map((mentor) => [mentor.id, mentor]));
  document.getElementById("readyCount").textContent = `${payload.ready.length}`;
  document.getElementById("plannedCount").textContent = `${payload.planned.length}`;
  const readyBox = document.getElementById("readyMentors");
  const plannedBox = document.getElementById("plannedMentors");
  readyBox.innerHTML = "";
  plannedBox.innerHTML = "";
  payload.ready.forEach((mentor) => readyBox.appendChild(createReadyCard(mentor)));
  payload.planned.forEach((mentor) => plannedBox.appendChild(createPlannedCard(mentor)));
}

function renderSelectedMentor(mentor) {
  const title = document.getElementById("selectedMentorTitle");
  const tag = document.getElementById("selectedMentorTag");
  const card = document.getElementById("selectedMentorCard");
  const continueBtn = document.getElementById("continueBtn");
  const newThreadBtn = document.getElementById("newThreadBtn");

  if (!mentor) {
    title.textContent = "先选择一位投资大师";
    tag.textContent = "未选择";
    card.className = "mentor-focus empty-state";
    card.innerHTML = "<p>从左侧选定一位人物后，这里会显示人物定位、当前目标线程和本轮问题输入区。</p>";
    continueBtn.textContent = "继续该人物对话";
    newThreadBtn.textContent = "新开该人物线程";
    renderThreadPlan(null);
    updateWindowTitle(null);
    return;
  }

  title.textContent = mentor.display_name_zh;
  tag.textContent = mentor.selection_label;
  card.className = "mentor-focus";
  card.innerHTML = `
    <div class="focus-top">
      <img class="focus-avatar" src="${mentor.avatar_path}" alt="${escapeHtml(mentor.display_name_zh)} 头像">
      <div>
        <p class="focus-en-name">${escapeHtml(mentor.display_name_en)}</p>
        <h3>${escapeHtml(mentor.display_name_zh)}</h3>
        <p class="focus-summary">${escapeHtml(mentor.summary || mentor.style || "")}</p>
      </div>
    </div>
    <div class="focus-meta">
      <span class="focus-pill">${escapeHtml(mentor.selection_label)}</span>
      <span class="focus-pill muted">${escapeHtml(mentor.thread_title || "")}</span>
    </div>
  `;
  continueBtn.textContent = `继续 ${mentor.display_name_zh} 的线程`;
  newThreadBtn.textContent = `新开 ${mentor.display_name_zh} 的线程`;
  renderThreadPlan(mentor);
  updateWindowTitle(mentor);
}

function renderThreadPlan(mentor) {
  const title = document.getElementById("threadPlanTitle");
  const copy = document.getElementById("threadPlanCopy");
  const pill = document.getElementById("threadModePill");
  if (!mentor) {
    title.textContent = "尚未选择人物";
    copy.textContent = "默认会优先回到该人物自己的 Codex 线程；如果你想把这次问题单独拆开，也可以强制新开。";
    pill.textContent = "优先延续专属线程";
    return;
  }
  title.textContent = mentor.thread_title || `${mentor.display_name_zh}｜投资大师智能团`;
  copy.textContent = `默认会先尝试回到「${mentor.display_name_zh}」自己的 Codex 线程，让这个人物的上下文自然延续。`;
  pill.textContent = "可继续，也可强制新开";
}

function renderLatestHandoff(record) {
  state.latestHandoff = record || null;
  document.getElementById("resultMode").textContent = modeLabel(record?.mode);
  document.getElementById("resultMode").className = `status-pill ${record?.delivery_ok || record?.ok ? "success" : "neutral"}`;
  document.getElementById("lastSentAt").textContent = record?.sent_at_label || record?.updated_at || "尚未发送";
  document.getElementById("lastThreadTitle").textContent = record?.thread_title || "尚未发送";
  document.getElementById("threadRouteHint").textContent = record?.message || "开始交接后，这里会明确告诉你是回到了已有线程，还是新开了该人物线程。";
  document.getElementById("lastSendContent").textContent = record?.display_prompt || "暂时还没有可展示的提交内容。";
}

function renderRecentThreads(history) {
  const list = document.getElementById("recentThreadList");
  list.innerHTML = "";
  if (!history || history.length === 0) {
    list.innerHTML = "<p class='empty-mini'>还没有可展示的线程记录。</p>";
    return;
  }
  history.slice(0, 5).forEach((item) => {
    const node = document.createElement("article");
    node.className = "thread-list-item";
    node.innerHTML = `
      <div>
        <strong>${escapeHtml(item.thread_title || item.mentor_name || "人物线程")}</strong>
        <p>${escapeHtml(item.message || item.display_prompt || "")}</p>
      </div>
      <span class="thread-list-time">${escapeHtml(item.sent_at_label || "")}</span>
    `;
    list.appendChild(node);
  });
}

function renderNoticeCenter(noticeCenter) {
  const list = document.getElementById("noticeList");
  list.innerHTML = "";
  if (!noticeCenter) {
    list.innerHTML = "<p class='empty-mini'>说明文档暂时不可用。</p>";
    return;
  }
  [noticeCenter.prerequisites, noticeCenter.risk, noticeCenter.privacy].filter(Boolean).forEach((item) => {
    const node = document.createElement("details");
    node.className = "notice-item";
    const bullets = (item.bullets || []).map((bullet) => `<li>${escapeHtml(bullet)}</li>`).join("");
    node.innerHTML = `
      <summary>
        <span>${escapeHtml(item.title || "说明")}</span>
        <span class="notice-tag">查看</span>
      </summary>
      <p class="notice-summary">${escapeHtml(item.summary || "")}</p>
      <ul class="notice-bullets">${bullets}</ul>
    `;
    list.appendChild(node);
  });
}

async function refreshRuntime() {
  try {
    const runtime = await fetchJson("/api/runtime");
    state.runtime = runtime;
    renderStatusStrip(runtime);
    renderRuntimeSummary(runtime);
    renderDiagnostics(runtime);
    renderBlocking(runtime);
  } catch (error) {
    console.error(error);
  }
}

function selectMentor(mentorId) {
  state.selectedMentorId = mentorId;
  renderMentors(state.mentors);
  renderSelectedMentor(getSelectedMentor());
}

async function openDrawer(mentorId) {
  try {
    const mentor = await fetchJson(`/api/mentors/${mentorId}`);
    state.drawerMentorId = mentorId;
    document.getElementById("drawerAvatar").src = mentor.avatar_path;
    document.getElementById("drawerStatus").textContent = mentor.status === "ready" ? "已就绪人物" : mentor.interested ? "已关注上线" : "筹备中人物";
    document.getElementById("drawerTitle").textContent = mentor.display_name_zh;
    document.getElementById("drawerSummary").textContent = mentor.summary || "";
    document.getElementById("drawerLabel").textContent = mentor.selection_label || "";
    document.getElementById("drawerStyle").textContent = mentor.style || "人物风格";
    document.getElementById("drawerPersona").textContent = mentor.persona_preview || mentor.summary || "";
    document.getElementById("drawerContract").textContent = mentor.answer_contract_preview || "";
    document.getElementById("drawerPrimaryBtn").textContent = mentor.interested ? "已关注上线" : mentor.status === "ready" ? `进入 ${mentor.display_name_zh}` : "关注上线";
    document.getElementById("drawerPrimaryBtn").disabled = mentor.interested && mentor.status !== "ready";
    const drawer = document.getElementById("mentorDrawer");
    drawer.classList.remove("hidden");
    drawer.setAttribute("aria-hidden", "false");
  } catch (error) {
    console.error(error);
  }
}

function closeDrawer() {
  const drawer = document.getElementById("mentorDrawer");
  drawer.classList.add("hidden");
  drawer.setAttribute("aria-hidden", "true");
  state.drawerMentorId = null;
}

async function submitHandoff(event) {
  event.preventDefault();
  const mentor = getSelectedMentor();
  if (!mentor) {
    alert("请先选择一位投资人物。");
    return;
  }

  const payload = {
    mentor_id: mentor.id,
    market_notes: document.getElementById("marketNotes").value,
    position: document.getElementById("positionInput").value,
    symbol: document.getElementById("symbolInput").value,
    question: document.getElementById("questionInput").value,
    force_new_thread: state.submitMode === "new_thread",
  };

  const activeButton = state.submitMode === "new_thread" ? document.getElementById("newThreadBtn") : document.getElementById("continueBtn");
  const originalText = activeButton.textContent;
  activeButton.disabled = true;
  activeButton.textContent = state.submitMode === "new_thread" ? "正在新开线程..." : "正在交接到 Codex...";

  try {
    const result = await postJson("/api/handoff", payload);
    renderLatestHandoff(result.latest_handoff || result);
    renderRecentThreads(result.recent_handoffs || []);
    await refreshRuntime();
  } catch (error) {
    console.error(error);
    alert("交接失败，请稍后重试。");
  } finally {
    activeButton.disabled = false;
    activeButton.textContent = originalText;
    state.submitMode = "continue";
  }
}

async function markInterest() {
  if (!state.drawerMentorId) return;
  const detail = await postJson("/api/planned-interest", {
    mentor_id: state.drawerMentorId,
    interested: true,
  });
  const mentors = await fetchJson("/api/mentors");
  renderMentors(mentors);
  await openDrawer(detail.id);
}

async function repairRuntime() {
  const button = document.getElementById("repairRuntimeBtn");
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "正在修复...";
  try {
    const payload = await postJson("/api/repair", {});
    state.runtime = payload.runtime;
    renderStatusStrip(payload.runtime);
    renderRuntimeSummary(payload.runtime);
    renderDiagnostics(payload.runtime);
    renderBlocking(payload.runtime);
    renderLatestHandoff(payload.latest_handoff || state.latestHandoff);
    renderRecentThreads(payload.recent_handoffs || []);
  } catch (error) {
    console.error(error);
    alert("修复失败，请稍后重试。");
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

async function bootstrap() {
  const [bootstrapPayload, mentors] = await Promise.all([
    fetchJson("/api/bootstrap"),
    fetchJson("/api/mentors"),
  ]);
  state.bootstrap = bootstrapPayload;
  state.runtime = bootstrapPayload.runtime;
  renderBrand(bootstrapPayload);
  renderStatusStrip(bootstrapPayload.runtime);
  renderRuntimeSummary(bootstrapPayload.runtime);
  renderDiagnostics(bootstrapPayload.runtime);
  renderBlocking(bootstrapPayload.runtime);
  renderMentors(mentors);
  renderLatestHandoff(bootstrapPayload.latest_handoff || null);
  renderNoticeCenter(bootstrapPayload.notice_center || null);
  renderRecentThreads(bootstrapPayload.recent_handoffs || []);

  const defaultMentor = mentors.ready.find((mentor) => mentor.id === bootstrapPayload.default_mentor) || mentors.ready[0] || null;
  if (defaultMentor) {
    selectMentor(defaultMentor.id);
  } else {
    renderSelectedMentor(null);
  }
}

function registerEvents() {
  document.getElementById("handoffForm").addEventListener("submit", submitHandoff);
  document.getElementById("continueBtn").addEventListener("click", () => {
    state.submitMode = "continue";
  });
  document.getElementById("newThreadBtn").addEventListener("click", () => {
    state.submitMode = "new_thread";
  });
  document.getElementById("refreshRuntimeBtn").addEventListener("click", refreshRuntime);
  document.getElementById("repairRuntimeBtn").addEventListener("click", repairRuntime);
  document.getElementById("toggleDiagnosticsBtn").addEventListener("click", () => {
    const panel = document.getElementById("diagnosticsPanel");
    panel.open = !panel.open;
  });
  document.getElementById("drawerBackdrop").addEventListener("click", closeDrawer);
  document.getElementById("closeDrawerBtn").addEventListener("click", closeDrawer);
  document.getElementById("drawerSecondaryBtn").addEventListener("click", closeDrawer);
  document.getElementById("drawerPrimaryBtn").addEventListener("click", async () => {
    if (!state.drawerMentorId) return;
    const mentor = state.mentorMap.get(state.drawerMentorId);
    if (mentor?.status === "ready") {
      closeDrawer();
      selectMentor(mentor.id);
      document.getElementById("questionInput").focus();
      return;
    }
    await markInterest();
  });

  document.querySelectorAll(".quick-chip").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById("questionInput").value = button.dataset.question || "";
      document.getElementById("questionInput").focus();
    });
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  registerEvents();
  try {
    await bootstrap();
  } catch (error) {
    console.error(error);
    alert("壳应用初始化失败，请稍后重试。");
  }
});


