/* ────────────── Hero animation trigger ────────────── */
// 只在 Hero 区域真正进入浏览器视口时才触发动画，防止后台加载时提前跑完
(function initHeroAnimation() {
  const hero = document.getElementById("hero");
  if (!hero) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          document.body.classList.add("loaded");
          observer.disconnect();
        }
      });
    },
    { threshold: 0.1 }
  );
  observer.observe(hero);
})();

/* ────────────── State ────────────── */
let selectedFile = null;
let activeTab = "file";
let chatMessages = []; // 本地聊天历史 [{role, content}]
let sessionId = localStorage.getItem("ra_session_id") || crypto.randomUUID();
localStorage.setItem("ra_session_id", sessionId);

/* ────────────── DOM refs ────────────── */
const $ = (sel) => document.querySelector(sel);

const tabFile      = $('[data-tab="file"]');
const tabText       = $('[data-tab="text"]');
const panelFile     = $("#panel-file");
const panelText     = $("#panel-text");
const dropZone      = $("#drop-zone");
const fileInput     = $("#file-input");
const fileNameEl    = $("#file-name");
const textArea      = $("#text-area");
const btnAnalyze    = $("#btn-analyze");
const inputHint     = $("#input-hint");
const loadingSec    = $("#loading-section");
const thinkingSec   = $("#thinking-section");
const chatHistory   = $("#chat-history");
const chatMsgContainer = $("#chat-messages");
const reportSec     = $("#report-section");
const reportContent = $("#report-content");
const reportMeta    = $("#report-meta");
const loadingLabel  = $("#loading-label");

const steps = {
  parse:   $('.step[data-step="parse"]'),
  extract: $('.step[data-step="extract"]'),
  verify:  $('.step[data-step="verify"]'),
  calc:    $('.step[data-step="calc"]'),
  report:  $('.step[data-step="report"]'),
  review:  $('.step[data-step="review"]'),
};

/* ────────────── Tab switching ────────────── */
tabFile.addEventListener("click", () => switchTab("file"));
tabText.addEventListener("click", () => switchTab("text"));

function switchTab(tab) {
  activeTab = tab;
  tabFile.classList.toggle("active", tab === "file");
  tabText.classList.toggle("active", tab === "text");
  panelFile.classList.toggle("active", tab === "file");
  panelText.classList.toggle("active", tab === "text");
  // Tab 切换只改变视图，不销毁用户已填写的数据。
  // 文件和文本内容保留，直到刷新页面或重新上传/输入。
}

/* ────────────── File handling ────────────── */
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) {
    selectedFile = fileInput.files[0];
    fileNameEl.textContent = selectedFile.name;
  }
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});
dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("drag-over");
});
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  if (e.dataTransfer.files.length) {
    selectedFile = e.dataTransfer.files[0];
    fileNameEl.textContent = selectedFile.name;
  }
});

/* ────────────── Analyze ────────────── */
btnAnalyze.addEventListener("click", () => {
  if (activeTab === "file" && selectedFile) {
    analyzeFile();
  } else if (activeTab === "text" && textArea.value.trim()) {
    analyzeText(textArea.value.trim());
  }
});

async function analyzeFile() {
  hideResults();
  showLoading();

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const resp = await fetch("/api/analyze/file", { method: "POST", body: formData });
    const data = await resp.json();
    handleResult(data);
  } catch (err) {
    hideLoading();
    loadingLabel.textContent = "请求失败: " + err.message;
    alert("请求失败: " + err.message);
  }
}

async function analyzeText(message) {
  // 预显示用户消息，清空输入框
  addMessage("user", message);
  textArea.value = "";

  hideResults();
  showThinking();

  try {
    const resp = await fetch("/api/analyze/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    const data = await resp.json();
    hideThinking();

    if (data.type === "chat") {
      // 前端自维护聊天记录，不依赖后端 messages 返回值
      addMessage("assistant", data.reply || "(空回复)");
    } else if (data.type === "report") {
      // 研报结果：在聊天历史中追加一条系统提示，再显示报告卡片
      addMessage("assistant", "研报分析已完成，报告如下：");
      reportContent.innerHTML = marked.parse(data.report);
      reportMeta.innerHTML = data.review_passed
        ? '<span class="badge badge-pass">审核通过</span>'
        : '<span class="badge badge-fail">审核未通过</span>' +
          (data.review_feedback
            ? '<span class="badge badge-fail">' + escapeHtml(data.review_feedback) + "</span>"
            : "");
      reportSec.classList.remove("hidden");
      reportSec.scrollIntoView({ behavior: "smooth" });
    } else if (data.type === "error") {
      addMessage("assistant", "错误: " + (data.message || "未知错误"));
    }
  } catch (err) {
    hideThinking();
    alert("请求失败: " + err.message);
  }
}

function handleResult(data) {
  hideLoading();

  if (data.type === "report") {
    // 研报结果：在聊天历史中追加提示，再显示报告卡片
    addMessage("assistant", "研报分析已完成，报告如下：");
    reportContent.innerHTML = marked.parse(data.report);
    reportMeta.innerHTML = data.review_passed
      ? '<span class="badge badge-pass">审核通过</span>'
      : '<span class="badge badge-fail">审核未通过</span>' +
        (data.review_feedback
          ? '<span class="badge badge-fail">' + escapeHtml(data.review_feedback) + "</span>"
          : "");
    reportSec.classList.remove("hidden");
    reportSec.scrollIntoView({ behavior: "smooth" });
  } else if (data.type === "error") {
    addMessage("assistant", "错误: " + (data.message || "未知错误"));
  }
}

/* ────────────── Chat message helpers ────────────── */
function addMessage(role, content) {
  chatMessages.push({ role, content });
  renderChatMessages();
}

function renderChatMessages() {
  if (!chatMsgContainer) return;
  chatMsgContainer.innerHTML = chatMessages
    .map(
      (msg) => `
    <div class="chat-message ${msg.role}">
      <div class="chat-message-bubble">${escapeHtml(msg.content)}</div>
    </div>`
    )
    .join("");

  if (chatMessages.length > 0) {
    chatHistory.classList.remove("hidden");
  }
  // 聊天区内部滚动到底部，不滚动整页
  chatMsgContainer.scrollTop = chatMsgContainer.scrollHeight;
}

/* ────────────── Loading animation ────────────── */
let _loadingTimers = [];

function showLoading() {
  loadingSec.classList.remove("hidden");

  // 重置步骤
  Object.values(steps).forEach((s) => {
    s.classList.remove("active", "done");
  });

  // 重置进度条（重新触发动画）
  const fill = $(".loading-fill");
  if (fill) {
    fill.style.animation = "none";
    fill.offsetHeight; // 触发回流
    fill.style.animation = "";
  }

  // 模拟步骤推进（用户体验反馈）
  const sequence = [
    { key: "parse",   delay:  500, label: "正在解析文档…" },
    { key: "extract", delay: 1500, label: "正在提取关键数据…" },
    { key: "verify",  delay: 3000, label: "正在联网验证数据…" },
    { key: "calc",    delay: 4500, label: "正在计算财务指标…" },
    { key: "report",  delay: 6000, label: "正在生成分析报告…" },
    { key: "review",  delay: 7500, label: "正在审核报告质量…" },
  ];

  _loadingTimers = sequence.map(({ key, delay, label }) =>
    setTimeout(() => {
      steps[key].classList.add("active");
      loadingLabel.textContent = label;

      const keys = Object.keys(steps);
      const idx = keys.indexOf(key);
      if (idx > 0) {
        steps[keys[idx - 1]].classList.replace("active", "done");
      }
    }, delay)
  );
}

function hideLoading() {
  _loadingTimers.forEach(clearTimeout);
  _loadingTimers = [];
  loadingSec.classList.add("hidden");
}

function showThinking() {
  thinkingSec.classList.remove("hidden");
}

function hideThinking() {
  thinkingSec.classList.add("hidden");
}

function hideResults() {
  reportSec.classList.add("hidden");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
