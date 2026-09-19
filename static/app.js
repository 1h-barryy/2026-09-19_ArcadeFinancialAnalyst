"use strict";
const $ = id => document.getElementById(id);
let state = null, remainingAt = 0, sampledAt = 0, asking = false, transitioning = false, pollBusy = false;
let renderedRound = null, renderedPhase = null, historySnapshot = "";

async function api(path, body) {
  const options = body === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json", "X-Arcade":"1"}, body:JSON.stringify(body)};
  const response = await fetch(`/api/${path}`, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Invalid request. Check your input.");
  return data;
}
function showError(message) { $("error").textContent = message; $("error").hidden = !message; }
function format(value, unit = "") { return value === null ? "Unavailable" : `${Number(value).toLocaleString(undefined,{maximumFractionDigits:2})}${unit}`; }
function controls() {
  const active = state?.phase === "research" && !transitioning && secondsLeft() > 0;
  document.querySelectorAll("[data-choice]").forEach(b => b.disabled = !active);
  $("ask").disabled = !active || asking || state?.asking || !state?.analyst_available;
  $("question").disabled = !active || !state?.analyst_available;
  $("ask").firstChild.textContent = asking || state?.asking ? "Reading the evidence… " : "Ask analyst ";
  document.querySelectorAll("[data-question]").forEach(b => b.disabled = !active || asking || !state?.analyst_available);
}
function secondsLeft() { return Math.max(0, remainingAt - (performance.now() - sampledAt) / 1000); }
function tick() {
  if (!state) return;
  const seconds = state.phase === "research" ? Math.ceil(secondsLeft()) : state.phase === "ready" ? 60 : 0;
  $("timer").textContent = `${String(Math.floor(seconds/60)).padStart(2,"0")}:${String(seconds%60).padStart(2,"0")}`;
  $("timer").parentElement.classList.toggle("urgent", seconds <= 10 && state.phase === "research");
  controls();
}
function element(tag, text, className) { const node = document.createElement(tag); node.textContent = text; if(className) node.className = className; return node; }
function addMessage(label, className, contents) {
  const div = element("div", "", `message ${className}`);
  div.append(element("div", label, "message-label"));
  contents.forEach(node => div.append(node));
  $("conversation").append(div);
  $("conversation").scrollTop = $("conversation").scrollHeight;
}
function renderHistory() {
  $("conversation").replaceChildren();
  if (!state.history.length) {
    $("conversation").append(element("p", "You make the call. The analyst helps you inspect the evidence.", "conversation-intro"));
  }
  state.history.forEach(entry => {
    addMessage("YOU", "user", [element("p", entry.question)]);
    const reply = entry.reply;
    const nodes = reply.facts.map(f => element("p", `${f.label}: ${format(f.value,f.unit)}`, "evidence-line"));
    reply.explanations.forEach(text => nodes.push(element("p",text)));
    reply.limitations.forEach(text => nodes.push(element("p",text,"limitation")));
    nodes.push(element("p",`${reply.usage.input_tokens} input / ${reply.usage.output_tokens} output tokens · Verified evidence`,"fine"));
    if (!reply.usage_saved) nodes.push(element("p","Usage retained in memory; local usage log could not be saved.","fine"));
    addMessage("ANALYST / OPENAI", "analyst-reply", nodes);
  });
}
function render(data) {
  const changed = renderedRound !== data.round_id, phaseChanged = renderedPhase !== data.phase;
  state = data; remainingAt = data.remaining; sampledAt = performance.now();
  $("welcome").hidden = true; $("terminal").hidden = false;
  $("asset").textContent = data.label; $("round").textContent = `0${data.round} / 03`;
  $("score").textContent = String(data.score).padStart(3,"0"); $("combo").textContent = data.combo ? `${data.combo}×` : "—";
  $("source").textContent = data.notice; $("source").classList.toggle("demo",data.synthetic);
  $("analyst-status").textContent = data.analyst_available ? (data.analyst_verified ? "OPENAI CONNECTED · VERIFIED EVIDENCE" : "OPENAI KEY CONFIGURED · CONNECTION NOT YET VERIFIED") : "Analyst temporarily unavailable · No OpenAI key configured";
  $("analyst-dot").classList.toggle("online",data.analyst_verified);
  if(changed) {
    $("question").value = ""; historySnapshot = "";
    $("metrics").replaceChildren();
    for (const key of ["return_5","rsi","volatility","volume_ratio"]) {
      const f=data.evidence[key], item=element("div","","metric");
      item.title=f.explanation; item.append(element("span",f.label.toUpperCase()),element("b",format(f.value,f.unit))); $("metrics").append(item);
    }
  }
  const updatedHistory = JSON.stringify(data.history);
  if(changed || updatedHistory !== historySnapshot) {
    renderHistory(); historySnapshot = updatedHistory;
  }
  $("call-area").hidden=!!data.result; $("result").hidden=!data.result; $("future-key").hidden=!data.result;
  if(data.result) {
    const r=data.result;
    $("result-kicker").textContent=data.complete ? "SHIFT COMPLETE / FINAL SCORE" : "THE NEXT FIVE SESSIONS";
    $("result-title").textContent=data.complete ? `${data.score} points. Shift closed.` : r.choice === "No call" ? "Time’s up. No call." : r.correct ? "Good read. Call confirmed." : "The tape had other plans.";
    $("result-details").textContent=`Your call: ${r.choice} · Outcome: ${r.answer} · ${format(r.change,"%")} over five sessions.`;
    $("result-points").textContent=`+${r.points} points = ${r.accuracy} accuracy + ${r.speed} speed + ${r.combo_bonus} combo`;
    $("identity").textContent=`${data.synthetic ? "FICTIONAL · " : ""}${r.symbol} · ${r.start_date} → ${r.cutoff_date} | Revealed through ${r.end_date} · ${r.price_basis}`;
    $("next").textContent=data.complete ? "Start another shift ↗" : "Next round →";
  }
  renderedRound=data.round_id; renderedPhase=data.phase;
  if(changed || phaseChanged) drawChart();
  tick();
}

function drawChart() {
  if(!state) return;
  const canvas=$("chart"), box=canvas.getBoundingClientRect(), ratio=window.devicePixelRatio || 1;
  canvas.width=box.width*ratio; canvas.height=box.height*ratio;
  const ctx=canvas.getContext("2d"); ctx.scale(ratio,ratio);
  const width=box.width, height=box.height, left=25, right=width-57, top=24, bottom=height-95;
  const bars=[...state.chart,...(state.result?.future || [])];
  const prices=bars.map(b=>b.close), lo=Math.min(...prices), hi=Math.max(...prices), padding=Math.max((hi-lo)*.17,1);
  const ymin=lo-padding, ymax=hi+padding;
  const x=day=>left+(day+59)/64*(right-left), y=value=>bottom-(value-ymin)/(ymax-ymin)*(bottom-top);
  ctx.font="10px Consolas, monospace"; ctx.lineWidth=1;
  for(let i=0;i<5;i++) {
    const value=ymin+(ymax-ymin)*i/4, pos=y(value);
    ctx.strokeStyle="#22303b";ctx.beginPath();ctx.moveTo(left,pos);ctx.lineTo(right,pos);ctx.stroke();
    ctx.fillStyle="#8395a2";ctx.fillText(value.toFixed(1),right+9,pos+3);
  }
  const cutoff=x(0);
  ctx.fillStyle="#e5bd7a08";ctx.fillRect(cutoff,top,right-cutoff,bottom-top);
  ctx.setLineDash([3,4]);ctx.strokeStyle="#5c655e";ctx.beginPath();ctx.moveTo(cutoff,top);ctx.lineTo(cutoff,height-30);ctx.stroke();ctx.setLineDash([]);
  ctx.beginPath();state.chart.forEach((b,i)=>i?ctx.lineTo(x(b.day),y(b.close)):ctx.moveTo(x(b.day),y(b.close)));ctx.lineTo(cutoff,bottom);ctx.lineTo(left,bottom);ctx.closePath();
  const gradient=ctx.createLinearGradient(0,top,0,bottom);gradient.addColorStop(0,"#8ce4ba22");gradient.addColorStop(1,"#8ce4ba00");ctx.fillStyle=gradient;ctx.fill();
  function line(series,color) {ctx.beginPath();series.forEach((b,i)=>i?ctx.lineTo(x(b.day),y(b.close)):ctx.moveTo(x(b.day),y(b.close)));ctx.lineWidth=2;ctx.strokeStyle=color;ctx.stroke();}
  line(state.chart,"#8ce4ba");if(state.result) line([state.chart.at(-1),...state.result.future],"#e5bd7a");
  const maxVolume=Math.max(...bars.map(b=>b.volume),1);
  bars.forEach((b,i)=>{const h=b.volume/maxVolume*42;ctx.fillStyle=b.day>0?"#e5bd7a88":i && b.close<bars[i-1].close?"#e9959944":"#8ce4ba55";ctx.fillRect(x(b.day)-2,height-33-h,4,h);});
  ctx.fillStyle="#8395a2";ctx.font="9px Consolas, monospace";ctx.fillText("VOLUME",left,bottom+18);
  for(const day of [-59,-40,-20,0,5]) {ctx.fillStyle=day>0?"#e5bd7a":"#8395a2";ctx.fillText(day>0?"+5":String(day),x(day)-6,height-12);}
  canvas.setAttribute("aria-label",`Indexed closing price and volume for 60 research sessions${state.result ? " plus 5 revealed sessions" : ""}. First close 100; last research close ${format(state.evidence.last.value)}.`);
}

async function readyAfterPaint(data) {
  render(data);
  if(data.phase === "ready") {
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    render(await api("ready",{round_id:data.round_id}));
  }
}
async function startGame() {
  transitioning=true;$("start").disabled=true;$("next").disabled=true;showError("");
  try { await readyAfterPaint(await api("game",{})); }
  catch(error) { showError(error.message); }
  finally { transitioning=false;$("start").disabled=false;$("next").disabled=false;controls(); }
}
$("start").addEventListener("click",startGame);
$("next").addEventListener("click",async()=> {
  if(state.complete) return startGame();
  transitioning=true;$("next").disabled=true;showError("");
  try {await readyAfterPaint(await api("next",{round_id:state.round_id}));}
  catch(error){showError(error.message);}
  finally{transitioning=false;$("next").disabled=false;controls();}
});
document.querySelectorAll("[data-choice]").forEach(button=>button.addEventListener("click",async()=>{
  transitioning=true;controls();showError("");
  try{render(await api("predict",{round_id:state.round_id,choice:button.dataset.choice}));}
  catch(error){showError(error.message);try{render(await api("game"));}catch{}}
  finally{transitioning=false;controls();}
}));
$("question-form").addEventListener("submit",async event=>{
  event.preventDefault();const question=$("question").value.trim();
  if(!question || asking || state.phase!=="research") return;
  const roundId=state.round_id;asking=true;controls();showError("");
  try{await api("ask",{round_id:roundId,question});if(state.round_id===roundId){$("question").value="";render(await api("game"));}}
  catch(error){if(state.round_id===roundId) addMessage("CONNECTION STATUS","",[element("p",error.message,"limitation")]);}
  finally{asking=false;controls();}
});
document.querySelectorAll("[data-question]").forEach(button=>button.addEventListener("click",()=>{$("question").value=button.dataset.question;$("question").focus();}));
window.addEventListener("resize",drawChart);
setInterval(tick,100);
setInterval(async()=>{
  if(!state || state.phase!=="research" || pollBusy || transitioning) return;
  pollBusy=true;
  const roundId=state.round_id;
  try{const data=await api("game");if(!transitioning && state.round_id===roundId && !(state.phase==="result" && data.phase==="research")) render(data);}
  catch(error){showError(`Connection interrupted. The server clock continues. ${error.message}`);}
  finally{pollBusy=false;}
},1000);
(async()=>{
  try{const status=await api("status");$("startup-status").textContent=`Stock mode: ${status.mode.toUpperCase()} · ${status.analyst_available?"OpenAI configured; connection unverified":"Analyst unavailable until a key is configured"}`;
    try{await readyAfterPaint(await api("game"));}catch(error){if(!error.message.startsWith("No active game"))throw error;}
  }catch(error){showError(error.message);}
})();
