/* ============================================================
   SeeTouch Debugger — Frontend Logic
   WebSocket 通信 + UI 状态管理 + 截图 canvas 标注
   ============================================================ */

// ======================== 全局状态 ========================

const socket = io();
let currentState = "idle";
let stepHistory = [];        // StepData[]
let activeStepIndex = -1;    // 当前显示的步骤(0-indexed in stepHistory)

// ======================== DOM 元素 ========================

const $ = (id) => document.getElementById(id);

const els = {
    connectionDot:   $("connectionDot"),
    connectionText:  $("connectionText"),
    stateBadge:      $("stateBadge"),
    stepIndicator:   $("stepIndicator"),
    screenshotPlaceholder: $("screenshotPlaceholder"),
    screenshotCanvas: $("screenshotCanvas"),
    actionType:      $("actionType"),
    actionParams:    $("actionParams"),
    resultBadge:     $("resultBadge"),
    actionSummary:   $("actionSummary"),
    screenSummary:   $("screenSummary"),
    notesSection:    $("notesSection"),
    notesList:       $("notesList"),
    promptText:      $("promptText"),
    reasoningSection: $("reasoningSection"),
    reasoningText:   $("reasoningText"),
    rawOutputText:   $("rawOutputText"),
    reasoningTime:   $("reasoningTime"),
    executionTime:   $("executionTime"),
    tokensIn:        $("tokensIn"),
    tokensOut:       $("tokensOut"),
    tokensThinking:  $("tokensThinking"),
    thinkingMetric:  $("thinkingMetric"),
    instructionInput: $("instructionInput"),
    maxStepsInput:   $("maxStepsInput"),
    btnStep:         $("btnStep"),
    btnRun:          $("btnRun"),
    btnPause:        $("btnPause"),
    btnStop:         $("btnStop"),
    timeline:        $("timeline"),
    toastContainer:  $("toastContainer"),
};

// ======================== WebSocket 事件 ========================

socket.on("connect", () => {
    els.connectionDot.classList.add("connected");
    els.connectionText.textContent = "已连接";
});

socket.on("disconnect", () => {
    els.connectionDot.classList.remove("connected");
    els.connectionText.textContent = "已断开";
});

socket.on("status", (data) => {
    updateState(data.state);
});

socket.on("step_result", (data) => {
    stepHistory.push(data);
    activeStepIndex = stepHistory.length - 1;
    renderStepData(data);
    addTimelineStep(data);
    // 状态可能已经变了(stepping -> paused)
    if (data.terminal) {
        updateState("finished");
    }
});

socket.on("task_finished", (data) => {
    updateState("finished");
    const msg = data.completed
        ? `✅ 任务完成! 共 ${data.total_steps} 步`
        : `⏹ 任务终止: ${data.aborted_reason || "unknown"} (${data.total_steps} 步)`;
    showToast(msg, data.completed ? "success" : "info");
});

socket.on("error", (data) => {
    showToast(data.message, "error");
});

// ======================== 按钮事件 ========================

els.btnStep.addEventListener("click", () => {
    if (currentState === "idle" || currentState === "finished") {
        // 首次启动:先 start 再 step
        startTask("step");
    } else if (currentState === "paused") {
        socket.emit("step");
    }
});

els.btnRun.addEventListener("click", () => {
    if (currentState === "idle" || currentState === "finished") {
        startTask("run");
    } else if (currentState === "paused") {
        socket.emit("run");
    }
});

els.btnPause.addEventListener("click", () => {
    socket.emit("pause");
    updateState("paused");
});

els.btnStop.addEventListener("click", () => {
    socket.emit("stop");
    updateState("idle");
});

// 回车键启动
els.instructionInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        if (currentState === "idle" || currentState === "finished") {
            startTask("step");
        }
    }
});

function startTask(mode) {
    const instruction = els.instructionInput.value.trim();
    if (!instruction) {
        showToast("请输入任务指令", "error");
        els.instructionInput.focus();
        return;
    }
    const maxSteps = parseInt(els.maxStepsInput.value) || 45;

    // 清空历史
    stepHistory = [];
    activeStepIndex = -1;
    els.timeline.innerHTML = "";
    resetInfoPanel();

    socket.emit("start", { instruction, max_steps: maxSteps });

    // start 后等 paused 状态,然后自动触发 step 或 run
    const waitForReady = () => {
        socket.once("status", (data) => {
            updateState(data.state);
            if (data.state === "paused") {
                if (mode === "step") {
                    socket.emit("step");
                } else {
                    socket.emit("run");
                }
            }
        });
    };
    waitForReady();
}

// ======================== 状态管理 ========================

function updateState(state) {
    currentState = state;

    // Badge
    els.stateBadge.textContent = state;
    els.stateBadge.className = "state-badge " + state;

    // 按钮状态
    const canStart = state === "idle" || state === "finished";
    const canStep = state === "paused" || canStart;
    const canRun = state === "paused" || canStart;
    const canPause = state === "running";
    const canStop = state !== "idle";

    els.btnStep.disabled = !canStep;
    els.btnRun.disabled = !canRun;
    els.btnPause.disabled = !canPause;
    els.btnStop.disabled = !canStop;

    // 输入框
    const inputDisabled = state === "running" || state === "stepping";
    els.instructionInput.disabled = inputDisabled;
    els.maxStepsInput.disabled = inputDisabled;
}

// ======================== 渲染步骤数据 ========================

function renderStepData(data) {
    // 步号
    els.stepIndicator.textContent = `Step ${data.step}`;

    // 截图
    renderScreenshot(data);

    // Action
    els.actionType.textContent = data.action_type;
    els.actionParams.textContent = formatParams(data.action_params);

    // 执行结果
    if (data.execution_success === true) {
        els.resultBadge.textContent = "✅ 成功";
        els.resultBadge.className = "result-badge success";
    } else if (data.execution_success === false) {
        els.resultBadge.textContent = "❌ 失败";
        els.resultBadge.className = "result-badge failure";
    } else {
        els.resultBadge.textContent = "⏸ 跳过";
        els.resultBadge.className = "result-badge pending";
    }
    els.actionSummary.textContent = data.action_summary || "";

    // Screen Summary
    els.screenSummary.textContent = data.screen_summary || "—";

    // Notes
    if (data.notes && data.notes.length > 0) {
        els.notesSection.style.display = "";
        els.notesList.innerHTML = data.notes
            .map(n => `<div class="note-item">${escapeHtml(n)}</div>`)
            .join("");
    } else {
        els.notesSection.style.display = "none";
    }

    // Prompt
    els.promptText.textContent = data.prompt_text || "—";

    // 思维链:thinking 开启时才有内容,空则隐藏整个区块
    if (data.reasoning_content) {
        els.reasoningSection.style.display = "";
        els.reasoningText.textContent = data.reasoning_content;
    } else {
        els.reasoningSection.style.display = "none";
    }

    // Model Output
    els.rawOutputText.textContent = data.raw_output || "—";

    // Metrics
    els.reasoningTime.textContent = data.reasoning_time + "s";
    els.executionTime.textContent = data.execution_time + "s";

    if (data.usage) {
        els.tokensIn.textContent = formatNumber(data.usage.input_tokens || 0);
        els.tokensOut.textContent = formatNumber(data.usage.output_tokens || 0);
        if (data.usage.reasoning_tokens) {
            els.thinkingMetric.style.display = "";
            els.tokensThinking.textContent = formatNumber(data.usage.reasoning_tokens);
        } else {
            els.thinkingMetric.style.display = "none";
        }
    } else {
        els.tokensIn.textContent = "—";
        els.tokensOut.textContent = "—";
        els.thinkingMetric.style.display = "none";
    }
}

function resetInfoPanel() {
    els.stepIndicator.textContent = "—";
    els.screenshotPlaceholder.style.display = "";
    els.screenshotCanvas.style.display = "none";
    els.actionType.textContent = "—";
    els.actionParams.textContent = "";
    els.resultBadge.textContent = "—";
    els.resultBadge.className = "result-badge";
    els.actionSummary.textContent = "";
    els.screenSummary.textContent = "—";
    els.notesSection.style.display = "none";
    els.promptText.textContent = "—";
    els.reasoningSection.style.display = "none";
    els.reasoningText.textContent = "—";
    els.rawOutputText.textContent = "—";
    els.reasoningTime.textContent = "—";
    els.executionTime.textContent = "—";
    els.tokensIn.textContent = "—";
    els.tokensOut.textContent = "—";
    els.thinkingMetric.style.display = "none";
}

// ======================== 截图 Canvas + 标注 ========================

function renderScreenshot(data) {
    const canvas = els.screenshotCanvas;
    const ctx = canvas.getContext("2d");

    const img = new Image();
    img.onload = () => {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);

        // 动作标注
        drawActionOverlay(ctx, data, img.width, img.height);

        els.screenshotPlaceholder.style.display = "none";
        canvas.style.display = "block";
    };
    img.src = "data:image/jpeg;base64," + data.screenshot_b64;
}

function drawActionOverlay(ctx, data, canvasW, canvasH) {
    const params = data.action_params;

    if (data.action_type === "CLICK" && params.point) {
        const [nx, ny] = params.point;
        const px = (nx / 1000) * canvasW;
        const py = (ny / 1000) * canvasH;

        // 外圈脉冲
        ctx.beginPath();
        ctx.arc(px, py, 18, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(248, 113, 113, 0.6)";
        ctx.lineWidth = 2;
        ctx.stroke();

        // 内圈实心
        ctx.beginPath();
        ctx.arc(px, py, 8, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(248, 113, 113, 0.9)";
        ctx.fill();

        // 十字准星
        ctx.strokeStyle = "rgba(255, 255, 255, 0.7)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(px - 24, py); ctx.lineTo(px + 24, py);
        ctx.moveTo(px, py - 24); ctx.lineTo(px, py + 24);
        ctx.stroke();
    }

    if (data.action_type === "SCROLL" && params.start_point && params.end_point) {
        const [sx, sy] = params.start_point;
        const [ex, ey] = params.end_point;
        const spx = (sx / 1000) * canvasW, spy = (sy / 1000) * canvasH;
        const epx = (ex / 1000) * canvasW, epy = (ey / 1000) * canvasH;

        // 轨迹线
        ctx.beginPath();
        ctx.moveTo(spx, spy);
        ctx.lineTo(epx, epy);
        ctx.strokeStyle = "rgba(91, 158, 244, 0.8)";
        ctx.lineWidth = 3;
        ctx.setLineDash([8, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // 起点
        ctx.beginPath();
        ctx.arc(spx, spy, 6, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(91, 158, 244, 0.8)";
        ctx.fill();

        // 箭头
        const angle = Math.atan2(epy - spy, epx - spx);
        const headLen = 14;
        ctx.beginPath();
        ctx.moveTo(epx, epy);
        ctx.lineTo(epx - headLen * Math.cos(angle - 0.4), epy - headLen * Math.sin(angle - 0.4));
        ctx.moveTo(epx, epy);
        ctx.lineTo(epx - headLen * Math.cos(angle + 0.4), epy - headLen * Math.sin(angle + 0.4));
        ctx.strokeStyle = "rgba(91, 158, 244, 0.9)";
        ctx.lineWidth = 3;
        ctx.stroke();
    }
}

// ======================== 时间线 ========================

function addTimelineStep(data) {
    const el = document.createElement("div");
    el.className = "timeline-step";
    el.textContent = data.step;
    el.dataset.index = stepHistory.length - 1;

    if (data.terminal) {
        el.classList.add("terminal");
    } else if (data.execution_success === false) {
        el.classList.add("failure");
    } else {
        el.classList.add("success");
    }

    // 标记当前活跃
    document.querySelectorAll(".timeline-step.active").forEach(s => s.classList.remove("active"));
    el.classList.add("active");

    el.addEventListener("click", () => {
        const idx = parseInt(el.dataset.index);
        activeStepIndex = idx;
        renderStepData(stepHistory[idx]);

        // 更新活跃状态
        document.querySelectorAll(".timeline-step.active").forEach(s => s.classList.remove("active"));
        el.classList.add("active");
    });

    els.timeline.appendChild(el);

    // 自动滚到最新
    els.timeline.scrollLeft = els.timeline.scrollWidth;
}

// ======================== 工具函数 ========================

function formatParams(params) {
    if (!params || Object.keys(params).length === 0) return "";
    return JSON.stringify(params);
}

function formatNumber(n) {
    if (n >= 1000) return (n / 1000).toFixed(1) + "k";
    return String(n);
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    els.toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// 折叠/展开
function toggleSection(id) {
    const el = document.getElementById(id);
    el.classList.toggle("open");
    // 更新箭头
    const header = el.previousElementSibling || el.parentElement.querySelector(".collapsible-header");
    if (header) {
        const arrow = header.querySelector("span:first-child");
        if (arrow) {
            arrow.textContent = el.classList.contains("open")
                ? "▼ " + arrow.textContent.substring(2)
                : "▶ " + arrow.textContent.substring(2);
        }
        const hint = header.querySelector(".collapse-hint");
        if (hint) {
            hint.textContent = el.classList.contains("open") ? "点击收起" : "点击展开";
        }
    }
}

// 全局暴露给 HTML onclick
window.toggleSection = toggleSection;

// ======================== 初始化 ========================

updateState("idle");
