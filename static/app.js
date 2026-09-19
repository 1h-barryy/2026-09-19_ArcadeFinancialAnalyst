"use strict";
const $ = id => document.getElementById(id);
let state = null, preparedState = null, remainingAt = 0, sampledAt = 0;
let transitioning = false, pollBusy = false, pendingAsk = null;
let renderedRound = null, renderedPhase = null, historySnapshot = "";
let chartView = "line", hoverDay = null, summaryOpen = false;

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json", "X-Arcade": "1"},
    body: JSON.stringify(body)
  };
  const response = await fetch("/api/" + path, options);
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "Invalid request. Check your input.");
    error.status = response.status;
    throw error;
  }
  return data;
}
function showError(message) { $("error").textContent = message; $("error").hidden = !message; }
function format(value, unit = "") {
  return value === null ? "Unavailable" : Number(value).toLocaleString(undefined, {maximumFractionDigits: 2}) + unit;
}
function element(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}
function secondsLeft() { return Math.max(0, remainingAt - (performance.now() - sampledAt) / 1000); }
function controls() {
  const active = state?.phase === "research" && !transitioning && secondsLeft() > 0;
  const waiting = !!pendingAsk || state?.asking;
  document.querySelectorAll("[data-choice]").forEach(b => b.disabled = !active);
  $("ask").disabled = !active || waiting || !state?.analyst_available || !$("question").value.trim();
  $("question").disabled = !active || !state?.analyst_available;
  $("ask-label").textContent = waiting ? "Reviewing…" : "Send message";
  $("message-count").textContent = $("question").value.length + " / 600";
  $("composer-hint").textContent = !state?.analyst_available
    ? "Chat unavailable · Configure your OpenAI key locally."
    : state.complete ? "Shift complete · Play Again to start a new conversation."
    : state.phase === "result" ? "Research closed · Continue to the next round to chat."
    : "Enter to send · Shift + Enter for a new line";
  document.querySelectorAll("[data-question]").forEach(b => b.disabled = !active || waiting || !state?.analyst_available);
  $("pending-question").hidden = !pendingAsk || pendingAsk.roundId !== state?.round_id;
  for (const id of ["start", "next", "play-again"]) $(id).disabled = transitioning;
}
function tick() {
  if (!state) return;
  const seconds = state.phase === "research" ? Math.ceil(secondsLeft()) : state.phase === "ready" ? 60 : 0;
  $("timer").textContent = String(Math.floor(seconds / 60)).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
  $("timer").parentElement.classList.toggle("urgent", seconds <= 10 && state.phase === "research");
  controls();
}
function addMessage(label, className, contents) {
  const div = element("div", "", "message " + className);
  const header = element("div", "", "message-role");
  const avatar = element("span", className === "user" ? "Y" : className === "analyst-reply" ? "AI" : "!", "message-avatar");
  avatar.setAttribute("aria-hidden", "true");
  header.append(avatar, element("span", label, "message-label"));
  const bubble = element("div", "", "message-bubble");
  bubble.append(...contents);
  div.append(header, bubble);
  $("conversation").append(div);
}
function renderHistory() {
  $("conversation").replaceChildren();
  if (!state.history.length) {
    const intro = element("div", "", "conversation-intro");
    intro.append(element("span", "START A CONVERSATION", "empty-kicker"),
      element("h3", "What’s catching your eye?"),
      element("p", "Ask about a move in the chart, compare signals, or explore the risk. Your analyst brings the evidence. You make the call."),
      element("span", "Try: “Is momentum supported by volume?”", "empty-example"));
    $("conversation").append(intro);
  }
  state.history.forEach(entry => {
    addMessage("YOU", "user", [element("p", entry.question)]);
    const reply = entry.reply;
    const nodes = reply.explanations.map(text => element("p", text));
    if (reply.facts.length) {
      const card = element("div", "", "evidence-card");
      card.append(element("div", "✓ VERIFIED EVIDENCE", "evidence-heading"),
        element("div", "Calculated from this round’s visible data", "evidence-caption"));
      reply.facts.forEach(f => {
        const row = element("div", "", "evidence-row");
        row.title = f.explanation;
        row.append(element("span", f.label), element("b", format(f.value, f.unit)));
        card.append(row);
      });
      nodes.push(card);
    }
    reply.limitations.forEach(text => nodes.push(element("p", text, "limitation")));
    nodes.push(element("p", "OpenAI-selected evidence · " + reply.usage.input_tokens + " input / " + reply.usage.output_tokens + " output tokens", "fine"));
    if (!reply.usage_saved) nodes.push(element("p", "Usage retained in memory; local usage log could not be saved.", "fine"));
    addMessage("AI ANALYST", "analyst-reply", nodes);
  });
  // Keep the question and beginning of the reply visible, rather than jumping
  // past the prose to the bottom of a long evidence attachment.
  const conversation = $("conversation");
  const questions = conversation.querySelectorAll(".message.user");
  const latestQuestion = questions[questions.length - 1];
  if (latestQuestion) {
    conversation.scrollTop += latestQuestion.getBoundingClientRect().top - conversation.getBoundingClientRect().top - 12;
  } else {
    conversation.scrollTop = 0;
  }
}
function showSummary() {
  if (!state?.complete) return;
  summaryOpen = true;
  $("terminal").hidden = true;
  $("welcome").hidden = true;
  $("end-screen").hidden = false;
  $("final-score").textContent = state.score;
  $("final-correct").textContent = state.summary.correct_predictions + " / 3";
  $("final-combo").textContent = state.summary.best_combo + "×";
  $("final-questions").textContent = state.summary.analyst_questions;
  $("end-source").textContent = state.notice;
  $("end-source").classList.toggle("demo", state.synthetic);
  $("end-title").focus({preventScroll: true});
  window.scrollTo({top: 0, behavior: "instant"});
}
function render(data) {
  const changed = renderedRound !== data.round_id, phaseChanged = renderedPhase !== data.phase;
  state = data;
  remainingAt = data.remaining;
  sampledAt = performance.now();
  $("welcome").hidden = true;
  $("terminal").hidden = summaryOpen && data.complete;
  $("end-screen").hidden = !summaryOpen || !data.complete;
  $("asset").textContent = data.result ? data.result.symbol : data.label;
  $("asset-status").textContent = data.result ? (data.synthetic ? "FICTIONAL ASSET / REVEALED" : "REAL TICKER / REVEALED") : "ANONYMOUS ASSET";
  $("round").textContent = "0" + data.round + " / 03";
  $("score").textContent = String(data.score).padStart(3, "0");
  $("combo").textContent = data.combo ? data.combo + "×" : "—";
  $("source").textContent = data.notice;
  $("source").classList.toggle("demo", data.synthetic);
  $("analyst-status").textContent = data.analyst_available
    ? (data.analyst_verified ? "OPENAI CONNECTED · VERIFIED EVIDENCE" : "OPENAI CONFIGURED · CONNECTION NOT YET VERIFIED")
    : "Analyst temporarily unavailable · No OpenAI key configured";
  $("analyst-dot").classList.toggle("online", data.analyst_verified);
  if (changed) {
    $("question").value = "";
    historySnapshot = "";
    hoverDay = null;
    $("metrics").replaceChildren();
    for (const key of ["return_5", "rsi", "volatility", "volume_ratio"]) {
      const f = data.evidence[key], item = element("div", "", "metric");
      item.title = f.explanation;
      item.append(element("span", f.label.toUpperCase()), element("b", format(f.value, f.unit)));
      $("metrics").append(item);
    }
  }
  const updatedHistory = JSON.stringify(data.history);
  if (changed || updatedHistory !== historySnapshot) {
    renderHistory();
    historySnapshot = updatedHistory;
  }
  $("call-area").hidden = !!data.result;
  $("result").hidden = !data.result;
  $("future-key").hidden = !data.result;
  if (data.result) {
    const r = data.result;
    $("result-title").textContent = r.choice === "No call" ? "Time expired. No call." : r.correct ? "Correct call." : "Call missed.";
    $("result-earned").textContent = "+" + r.points + " PTS";
    $("result-call").textContent = r.choice;
    $("result-return").textContent = (r.change > 0 ? "+" : "") + format(r.change, "%");
    $("result-direction").textContent = r.answer;
    $("result-points").textContent = r.accuracy + " accuracy  +  " + r.speed + " speed  +  " + r.combo_bonus + " combo  =  " + r.points + " points";
    $("identity").textContent = (data.synthetic ? "FICTIONAL · " : "") + r.symbol + " · " + r.start_date + " → " + r.cutoff_date + " | Revealed through " + r.end_date + " · " + r.price_basis;
    $("next").textContent = data.complete ? "View shift summary →" : "Next round →";
  }
  renderedRound = data.round_id;
  renderedPhase = data.phase;
  if (changed || phaseChanged) drawChart();
  tick();
}

// Only research bars and the server-authorized result are available to either view.
function visibleBars() { return state ? [...state.chart, ...(state.result?.future || [])] : []; }
function chartGeometry() {
  const box = $("chart").getBoundingClientRect();
  return {width: box.width, height: box.height, left: 22, right: box.width - 58, top: 14, bottom: box.height - 90};
}
function updateChartReadout() {
  const bar = visibleBars().find(b => b.day === hoverDay);
  $("chart-readout").textContent = bar
    ? "DAY " + (bar.day > 0 ? "+" : "") + bar.day + "   O " + format(bar.open) + "   H " + format(bar.high) + "   L " + format(bar.low) + "   C " + format(bar.close) + "   VOL " + format(bar.volume)
    : hoverDay > 0 && !state.result
      ? "Future sessions are locked until your call or timeout."
      : "Hover over a session to inspect indexed OHLC and volume.";
}
function drawChart() {
  if (!state || $("terminal").hidden) return;
  const canvas = $("chart"), ratio = window.devicePixelRatio || 1;
  const {width, height, left, right, top, bottom} = chartGeometry();
  if (!width) return;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  const bars = visibleBars();
  const lo = Math.min(...bars.map(b => chartView === "candle" ? b.low : b.close));
  const hi = Math.max(...bars.map(b => chartView === "candle" ? b.high : b.close));
  const padding = Math.max((hi - lo) * .13, .5), ymin = lo - padding, ymax = hi + padding;
  // Leave half a session at each edge so the first and last candle cannot be clipped.
  const step = (right - left) / 65;
  const x = day => left + (day + 59.5) * step;
  const y = value => bottom - (value - ymin) / (ymax - ymin) * (bottom - top);
  const cutoff = x(.5);
  ctx.font = "10px Consolas, monospace";
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) {
    const value = ymin + (ymax - ymin) * i / 4, pos = y(value);
    ctx.strokeStyle = "#22303b";
    ctx.beginPath(); ctx.moveTo(left, pos); ctx.lineTo(right, pos); ctx.stroke();
    ctx.fillStyle = "#96a5b1"; ctx.fillText(value.toFixed(1), right + 8, pos + 3);
  }
  ctx.fillStyle = state.result ? "#d7b78512" : "#d7b78507";
  ctx.fillRect(cutoff, top, right - cutoff, height - top - 28);
  ctx.setLineDash([3, 4]); ctx.strokeStyle = "#68716b";
  ctx.beginPath(); ctx.moveTo(cutoff, top); ctx.lineTo(cutoff, height - 28); ctx.stroke(); ctx.setLineDash([]);
  if (chartView === "candle") {
    const candleWidth = Math.max(2, Math.min(8, step * .65));
    bars.forEach(b => {
      const color = b.close >= b.open ? "#9ac8b0" : "#cf969b";
      ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x(b.day), y(b.high)); ctx.lineTo(x(b.day), y(b.low)); ctx.stroke();
      ctx.fillRect(x(b.day) - candleWidth / 2, Math.min(y(b.open), y(b.close)), candleWidth, Math.max(1, Math.abs(y(b.open) - y(b.close))));
    });
  } else {
    ctx.beginPath();
    state.chart.forEach((b, i) => i ? ctx.lineTo(x(b.day), y(b.close)) : ctx.moveTo(x(b.day), y(b.close)));
    ctx.lineTo(x(0), bottom); ctx.lineTo(x(-59), bottom); ctx.closePath();
    const gradient = ctx.createLinearGradient(0, top, 0, bottom);
    gradient.addColorStop(0, "#9ac8b018"); gradient.addColorStop(1, "#9ac8b000");
    ctx.fillStyle = gradient; ctx.fill();
    function line(series, color) {
      ctx.beginPath();
      series.forEach((b, i) => i ? ctx.lineTo(x(b.day), y(b.close)) : ctx.moveTo(x(b.day), y(b.close)));
      ctx.lineWidth = 1.7; ctx.strokeStyle = color; ctx.stroke();
    }
    line(state.chart, "#9ac8b0");
    if (state.result) line([state.chart.at(-1), ...state.result.future], "#d7b785");
  }
  const maxVolume = Math.max(...bars.map(b => b.volume), 1), barWidth = Math.max(2, Math.min(7, step * .65));
  bars.forEach(b => {
    const h = b.volume / maxVolume * 39;
    ctx.fillStyle = b.close >= b.open ? "#9ac8b066" : "#cf969b66";
    ctx.fillRect(x(b.day) - barWidth / 2, height - 29 - h, barWidth, h);
  });
  ctx.fillStyle = "#96a5b1"; ctx.font = "9px Consolas, monospace";
  ctx.fillText("VOLUME", left, bottom + 17);
  for (const day of [-59, -40, -20, 0, 5]) {
    ctx.fillStyle = day > 0 ? "#d7b785" : "#96a5b1";
    ctx.fillText(day > 0 ? "+5" : String(day), x(day) - 6, height - 9);
  }
  if (hoverDay !== null && bars.some(b => b.day === hoverDay)) {
    ctx.setLineDash([2, 3]); ctx.strokeStyle = "#8a99a5"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x(hoverDay), top); ctx.lineTo(x(hoverDay), height - 28); ctx.stroke(); ctx.setLineDash([]);
  }
  canvas.dataset.sessions = String(bars.length);
  canvas.dataset.view = chartView;
  canvas.setAttribute("aria-label", (chartView === "candle" ? "OHLC candlesticks" : "Closing price line") + " and volume for 60 research sessions" + (state.result ? " plus 5 revealed sessions" : "; future sessions locked") + ". First close 100.");
  $("chart-legend").textContent = chartView === "candle" ? "OHLC · green close ≥ open / red close < open" : "— Closing price";
  updateChartReadout();
}
document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => {
  chartView = button.dataset.view;
  document.querySelectorAll("[data-view]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.view === chartView)));
  drawChart();
}));
$("chart").addEventListener("pointermove", event => {
  if (!state) return;
  const box = $("chart").getBoundingClientRect(), {left, right} = chartGeometry();
  const pointerX = event.clientX - box.left;
  hoverDay = pointerX < left || pointerX > right ? null : Math.max(-59, Math.min(5, Math.round((pointerX - left) / (right - left) * 65 - 59.5)));
  drawChart();
});
$("chart").addEventListener("pointerleave", () => { hoverDay = null; drawChart(); });
window.addEventListener("resize", drawChart);

async function readyAfterPaint(data) {
  render(data);
  if (data.phase === "ready") {
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    render(await api("ready", {round_id: data.round_id}));
  }
}
async function startGame(usePrepared = false) {
  if (transitioning) return;
  transitioning = true; controls(); showError("");
  try {
    const data = usePrepared && preparedState ? preparedState : await api("game", {});
    preparedState = null; pendingAsk = null; summaryOpen = false;
    renderedRound = null; renderedPhase = null; historySnapshot = ""; hoverDay = null;
    chartView = "line";
    document.querySelectorAll("[data-view]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.view === chartView)));
    $("question").value = "";
    await readyAfterPaint(data);
  } catch (error) { showError(error.message); }
  finally { transitioning = false; controls(); }
}
$("start").addEventListener("click", () => startGame(true));
$("play-again").addEventListener("click", () => startGame());
$("review").addEventListener("click", () => {
  summaryOpen = false; render(state); drawChart();
});
$("next").addEventListener("click", async () => {
  if (state.complete) return showSummary();
  if (transitioning) return;
  transitioning = true; controls(); showError("");
  try { await readyAfterPaint(await api("next", {round_id: state.round_id})); }
  catch (error) { showError(error.message); }
  finally { transitioning = false; controls(); }
});
document.querySelectorAll("[data-choice]").forEach(button => button.addEventListener("click", async () => {
  if (transitioning) return;
  transitioning = true; controls(); showError("");
  try { render(await api("predict", {round_id: state.round_id, choice: button.dataset.choice})); }
  catch (error) {
    showError(error.message);
    try { render(await api("game")); } catch {}
  } finally { transitioning = false; controls(); }
}));
$("question-form").addEventListener("submit", async event => {
  event.preventDefault();
  const question = $("question").value.trim();
  if (!question || pendingAsk || state.phase !== "research") return;
  const request = {roundId: state.round_id};
  pendingAsk = request; $("pending-text").textContent = question; controls(); showError("");
  try {
    await api("ask", {round_id: request.roundId, question});
    if (state.round_id === request.roundId) {
      $("question").value = "";
      const data = await api("game");
      if (state.round_id === request.roundId) render(data);
    }
  } catch (error) {
    if (state.round_id === request.roundId) {
      addMessage("YOU", "user", [element("p", question)]);
      addMessage("CONNECTION STATUS", "", [element("p", error.message, "limitation")]);
      $("conversation").scrollTop = $("conversation").scrollHeight;
    }
  } finally {
    if (pendingAsk === request) pendingAsk = null;
    controls();
  }
});
$("question").addEventListener("input", controls);
$("question").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing && !$("ask").disabled) {
    event.preventDefault();
    $("question-form").requestSubmit();
  }
});
document.querySelectorAll("[data-question]").forEach(button => button.addEventListener("click", () => {
  $("question").value = button.dataset.question; $("question").focus(); controls();
}));
setInterval(tick, 100);
setInterval(async () => {
  if (!state || (state.phase !== "research" && !state.asking) || pollBusy || transitioning) return;
  pollBusy = true;
  const roundId = state.round_id;
  try {
    const data = await api("game");
    if (!transitioning && state.round_id === roundId && !(state.phase === "result" && data.phase === "research")) render(data);
  } catch (error) { showError("Connection interrupted. The server clock continues. " + error.message); }
  finally { pollBusy = false; }
}, 1000);
(async () => {
  try {
    const status = await api("status");
    $("startup-status").textContent = (status.mode === "demo" ? "SYNTHETIC DEMO · Fictional market data" : "Stock mode: " + status.mode.toUpperCase()) +
      " · " + (status.analyst_available ? "OpenAI configured" : "Analyst unavailable until a key is configured");
    try {
      const saved = await api("game");
      // Restoring an unstarted round must never acknowledge readiness automatically.
      if (saved.phase === "ready") preparedState = saved;
      else {
        render(saved);
        if (saved.complete) showSummary();
      }
    } catch (error) { if (error.status !== 404) throw error; }
  } catch (error) { showError(error.message); }
})();
