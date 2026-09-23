/* Academy - persoenliche Lernoberflaeche.
   Videos werden direkt vom oeffentlichen ETH-Videoserver gestreamt, nichts wird kopiert.
   Fortschritt liegt ausschliesslich lokal im Browser (localStorage). */

const STORE = "academy.v1";
const DAILY_DEFAULT = 30;          // Minuten pro Tag
const PASS_LESSON = 0.7;           // Test bestanden ab 70 %
const PASS_EXAM = 0.75;            // Abschlusspruefung ab 75 %
const EXAM_SIZE = 15;              // Fragen in der Abschlusspruefung

let DATA = null;
const quizCache = {};

/* ---------- Speicher ---------- */
const blank = () => ({ lessons:{}, quiz:{}, exam:{}, days:{}, last:null, dailyMinutes:DAILY_DEFAULT });

function load(){
  try{
    const s = JSON.parse(localStorage.getItem(STORE));
    return s && typeof s === "object" ? Object.assign(blank(), s) : blank();
  }catch{ return blank(); }
}
function save(){ localStorage.setItem(STORE, JSON.stringify(S)); }
let S = load();

const todayKey = () => new Date().toLocaleDateString("sv-SE");   // YYYY-MM-DD, lokale Zeit
const key = (c,n) => `${c}/${n}`;

/* ---------- Helfer ---------- */
const fmtMin = ms => `${Math.round(ms/60000)} min`;
const fmtHrs = ms => `${(ms/3600000).toFixed(1)} h`;
function fmtClock(sec){
  sec = Math.max(0, Math.round(sec));
  const m = Math.floor(sec/60), s = sec%60;
  return `${m}:${String(s).padStart(2,"0")}`;
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const course = id => DATA.courses.find(c => c.id === id);
const lesson = (c,n) => course(c)?.lessons.find(l => l.nr === Number(n));

function secondsToday(){ return S.days[todayKey()] || 0; }
function addSeconds(sec){
  if (sec <= 0 || sec > 120) return;           // Ausreisser (Spruenge, Tab-Wechsel) ignorieren
  const k = todayKey();
  S.days[k] = (S.days[k] || 0) + sec;
  save();
}
function streakDays(){
  let n = 0;
  const d = new Date();
  // Heute zaehlt nur, wenn schon gelernt wurde - sonst beim gestrigen Tag anfangen.
  if (!(S.days[todayKey()] > 60)) d.setDate(d.getDate() - 1);
  for(;;){
    const k = d.toLocaleDateString("sv-SE");
    if (!(S.days[k] > 60)) break;
    n++; d.setDate(d.getDate() - 1);
  }
  return n;
}

/* Fortschritt eines Kurses: geschaute Lektionen und bestandene Tests. */
function courseProgress(c){
  const total = c.lessons.length;
  let watched = 0, passed = 0, msDone = 0, msTotal = 0;
  for (const l of c.lessons){
    const st = S.lessons[key(c.id, l.nr)] || {};
    const dur = l.durationMs || (l.estMinutes||0)*60000;
    msTotal += dur;
    if (st.watched){ watched++; msDone += dur; }
    else if (st.pos && dur) msDone += Math.min(st.pos*1000, dur);
    if ((S.quiz[key(c.id, l.nr)] || {}).passed) passed++;
  }
  return { total, watched, passed, msDone, msTotal,
           pct: msTotal ? msDone/msTotal : 0 };
}

/* Naechste offene Lektion - erst angefangene, dann die erste unberuehrte. */
function nextLesson(){
  if (S.last){
    const [cid, nr] = S.last.split("/");
    const st = S.lessons[S.last] || {};
    if (lesson(cid, nr) && !st.watched) return { cid, nr:Number(nr) };
  }
  for (const c of DATA.courses){
    for (const l of c.lessons){
      const st = S.lessons[key(c.id, l.nr)] || {};
      if (!st.watched) return { cid:c.id, nr:l.nr };
    }
  }
  return null;
}

async function getQuiz(cid){
  if (quizCache[cid]) return quizCache[cid];
  try{
    const r = await fetch(`data/quiz/${cid}.json`, {cache:"no-store"});
    quizCache[cid] = r.ok ? await r.json() : {};
  }catch{ quizCache[cid] = {}; }
  return quizCache[cid];
}

/* ---------- Navigation ---------- */
const view = () => document.getElementById("view");
function go(hash){ location.hash = hash; }
window.addEventListener("hashchange", route);

document.addEventListener("click", e => {
  const nav = e.target.closest("[data-nav]");
  if (nav) go(nav.dataset.nav === "home" ? "#/" : `#/${nav.dataset.nav}`);
});

function route(){
  stopTicker();
  const p = (location.hash || "#/").slice(2).split("/").filter(Boolean);
  if (!p.length) return renderHome();
  if (p[0] === "settings") return renderSettings();
  if (p[0] === "course") return renderCourse(p[1]);
  if (p[0] === "lesson") return renderLesson(p[1], p[2]);
  if (p[0] === "quiz")   return renderQuiz(p[1], p[2]);
  if (p[0] === "exam")   return renderExam(p[1]);
  renderHome();
}

function chrome(){
  const st = streakDays();
  document.getElementById("streak").textContent = st ? `🔥 ${st} Tag${st>1?"e":""} in Folge` : "";
  const left = Math.max(0, S.dailyMinutes*60 - secondsToday());
  document.getElementById("footNote").innerHTML = left > 0
    ? `Heute noch <b>${fmtClock(left)}</b> bis zum Tagesziel von ${S.dailyMinutes} min`
    : `✅ Tagesziel von ${S.dailyMinutes} min erreicht - ${fmtClock(secondsToday())} gelernt`;
}

/* ---------- Startseite ---------- */
function renderHome(){
  const nx = nextLesson();
  const left = Math.max(0, S.dailyMinutes*60 - secondsToday());
  const done = left <= 0;

  let html = `<h1>Deine Academy</h1>
  <p class="sub">Drei Kurse, ${DATA.courses.reduce((a,c)=>a+c.lessons.length,0)} Lektionen, je ${S.dailyMinutes} Minuten am Tag.</p>`;

  html += `<div class="today">
    <div>
      <h3>${done ? "Tagesziel erreicht 🎉" : "Deine 30 Minuten heute"}</h3>
      <p>${ nx
        ? `Weiter bei <b>${esc(course(nx.cid).title)}</b> · Lektion ${nx.nr}`
        : "Alle Lektionen geschaut. Zeit für die Abschlussprüfungen." }
        ${done ? "" : ` · noch ${fmtClock(left)}`}</p>
    </div>
    ${ nx ? `<button class="btn" data-nav="lesson/${nx.cid}/${nx.nr}">
        ${ (S.lessons[key(nx.cid,nx.nr)]||{}).pos ? "Weiterschauen" : "Jetzt starten" } →</button>`
          : `<button class="btn" data-nav="exam/${DATA.courses[0].id}">Zur Prüfung →</button>` }
  </div>`;

  html += `<div class="cards">`;
  for (const c of DATA.courses){
    const p = courseProgress(c);
    const langTag = c.kind === "external"
      ? `<span class="tag ext">extern</span>`
      : `<span class="tag ${c.lang}">${c.lang === "de" ? "Deutsch" : "Englisch"}</span>`;
    html += `<button class="card" data-nav="course/${c.id}">
      <h3>${esc(c.title)}</h3>
      <div class="meta">${esc(c.subtitle)}</div>
      <div>${langTag}<span class="tag">${c.lessons.length} Lektionen</span><span class="tag">${fmtHrs(p.msTotal)}</span></div>
      <div class="why">${esc(c.why)}</div>
      <div class="bar ${p.pct>=1?"ok":""}"><i style="width:${(p.pct*100).toFixed(1)}%"></i></div>
      <div class="barlabel"><span>${p.watched}/${p.total} geschaut · ${p.passed} Tests bestanden</span><span>${Math.round(p.pct*100)} %</span></div>
    </button>`;
  }
  html += `</div>`;
  view().innerHTML = html;
  chrome();
}

/* ---------- Kursseite ---------- */
async function renderCourse(cid){
  const c = course(cid);
  if (!c) return go("#/");
  const q = await getQuiz(cid);
  const p = courseProgress(c);
  const examState = S.exam[cid] || {};
  const canExam = p.passed >= Math.ceil(c.lessons.length * 0.6);

  let html = `<button class="crumb" data-nav="home">← Übersicht</button>
    <h1>${esc(c.title)}</h1>
    <p class="sub">${esc(c.subtitle)} · ${c.lessons.length} Lektionen · ${fmtHrs(p.msTotal)}</p>`;

  if (c.note) html += `<div class="note">${c.note}</div>`;

  html += `<div class="bar ${p.pct>=1?"ok":""}"><i style="width:${(p.pct*100).toFixed(1)}%"></i></div>
    <div class="barlabel"><span>${p.watched} von ${p.total} geschaut · ${p.passed} Tests bestanden</span><span>${Math.round(p.pct*100)} %</span></div>`;

  html += `<h2>Lektionen</h2><div class="lessons">`;
  for (const l of c.lessons){
    const st = S.lessons[key(cid,l.nr)] || {};
    const qs = S.quiz[key(cid,l.nr)] || {};
    const dur = l.durationMs || (l.estMinutes||0)*60000;
    const frac = st.watched ? 1 : (st.pos && dur ? Math.min(1, st.pos*1000/dur) : 0);
    const cls = qs.passed ? "passed" : (st.watched ? "done" : "");
    const mark = qs.passed ? "★" : (st.watched ? "✓" : l.nr);
    const hasQuiz = (q[l.nr]?.questions || []).length;
    html += `<button class="lesson ${cls}" data-nav="lesson/${cid}/${l.nr}">
      <span class="n">${mark}</span>
      <span class="t"><b>${esc(l.title)}</b>
        <span>${esc((l.topics||[]).join(" · ")) || "&nbsp;"}</span>
        ${frac>0&&frac<1 ? `<span class="miniprog"><i style="width:${frac*100}%"></i></span>` : ""}
      </span>
      <span class="r">${fmtMin(dur)}<br>${
        qs.passed ? `<span style="color:var(--accent2)">Test ${Math.round(qs.best*100)} %</span>`
        : hasQuiz ? `${hasQuiz} Fragen` : "—"}</span>
    </button>`;
  }
  html += `</div>`;

  const examCount = Object.values(q).reduce((a,v)=>a+(v.questions||[]).length,0);
  html += `<h2>Abschlussprüfung</h2>`;
  if (!examCount){
    html += `<div class="empty">Für diesen Kurs sind noch keine Fragen hinterlegt.</div>`;
  } else {
    html += `<div class="quiz">
      <p style="margin:0 0 6px"><b>${Math.min(EXAM_SIZE, examCount)} Fragen</b> quer durch den Kurs, bestanden ab ${PASS_EXAM*100} %.</p>
      <p style="margin:0; color:var(--dim); font-size:13.5px">
        ${ canExam ? "Freigeschaltet." : `Freigeschaltet, sobald ${Math.ceil(c.lessons.length*0.6)} Lektionstests bestanden sind (aktuell ${p.passed}).` }
        ${ examState.best != null ? ` Bisher bestes Ergebnis: <b>${Math.round(examState.best*100)} %</b>.` : "" }</p>
      <div class="row">
        <button class="btn" data-nav="exam/${cid}" ${canExam?"":"disabled"}>Prüfung starten</button>
      </div></div>`;
  }
  view().innerHTML = html;
  chrome();
}

/* ---------- Player ---------- */
let ticker = null, lastT = 0;
function stopTicker(){ if (ticker){ clearInterval(ticker); ticker = null; } }

async function renderLesson(cid, nr){
  const c = course(cid), l = lesson(cid, nr);
  if (!c || !l) return go("#/");
  const k = key(cid, l.nr);
  S.last = k; save();
  const st = S.lessons[k] || {};
  const q = await getQuiz(cid);
  const nQ = (q[l.nr]?.questions || []).length;

  if (c.kind === "external"){
    view().innerHTML = `<button class="crumb" data-nav="course/${cid}">← ${esc(c.title)}</button>
      <h1>${esc(l.title)}</h1>
      <p class="sub">Lektion ${l.nr} von ${c.lessons.length} · ca. ${l.estMinutes} min</p>
      <div class="note">${c.note}</div>
      <div class="quiz">
        <p style="margin-top:0"><b>Worum es geht:</b> ${esc((l.topics||[]).join(" · "))}</p>
        <div class="row">
          <a class="btn" style="text-decoration:none" href="${l.externalUrl}" target="_blank" rel="noopener">Video bei EPFL öffnen ↗</a>
          ${l.slidesUrl ? `<a class="btn sec" style="text-decoration:none" href="${l.slidesUrl}" target="_blank" rel="noopener">Folien (PDF) ↗</a>` : ""}
        </div>
      </div>
      <div class="row">
        <button class="btn sec" id="markDone">${st.watched ? "✓ Als geschaut markiert" : "Als geschaut markieren"}</button>
        ${nQ ? `<button class="btn" data-nav="quiz/${cid}/${l.nr}">Test starten (${nQ} Fragen) →</button>` : ""}
      </div>`;
    document.getElementById("markDone").onclick = () => {
      S.lessons[k] = Object.assign({}, st, { watched: !st.watched });
      save(); renderLesson(cid, nr);
    };
    chrome();
    return;
  }

  view().innerHTML = `<button class="crumb" data-nav="course/${cid}">← ${esc(c.title)}</button>
    <h1>${esc(l.title)}</h1>
    <p class="sub">Lektion ${l.nr} von ${c.lessons.length} · ${fmtMin(l.durationMs)} · ${esc((l.creators||[]).join(", "))}</p>
    <div class="playerwrap">
      <video id="v" controls preload="metadata" playsinline>
        <source src="${l.video}" type="video/mp4">
        ${l.captionLocal ? `<track default kind="subtitles" srclang="${(l.captionLang||"de").slice(0,2)}"
           label="Untertitel" src="${l.captionLocal}">` : ""}
      </video>
    </div>
    <div class="ctrls">
      <label style="color:var(--dim);font-size:13px">Tempo
        <select id="rate">
          ${[1,1.25,1.5,1.75,2].map(r=>`<option value="${r}">${String(r).replace(".",",")}×</option>`).join("")}
        </select></label>
      <button class="btn sec" id="back10">← 10 s</button>
      <span class="spacer"></span>
      <span class="budget" id="budget"></span>
    </div>
    <div class="row">
      <button class="btn sec" id="markDone">${st.watched ? "✓ Geschaut" : "Als geschaut markieren"}</button>
      ${nQ ? `<button class="btn" data-nav="quiz/${cid}/${l.nr}">Test starten (${nQ} Fragen) →</button>`
           : `<span style="color:var(--dim);font-size:13.5px">Für diese Lektion sind noch keine Fragen hinterlegt.</span>`}
      ${l.nr < c.lessons.length ? `<button class="btn sec" data-nav="lesson/${cid}/${l.nr+1}">Nächste Lektion →</button>` : ""}
    </div>
    <p style="color:var(--dim);font-size:12.5px;margin-top:18px">
      Video wird direkt von <code>video.ethz.ch</code> gestreamt · <a href="${c.portalUrl}" target="_blank" rel="noopener">Kurs im ETH-Portal ↗</a></p>`;

  const v = document.getElementById("v");
  const rate = document.getElementById("rate");
  rate.value = String(S.rate || 1);
  v.playbackRate = Number(rate.value);
  rate.onchange = () => { v.playbackRate = Number(rate.value); S.rate = Number(rate.value); save(); };
  document.getElementById("back10").onclick = () => { v.currentTime = Math.max(0, v.currentTime - 10); };

  if (st.pos) v.addEventListener("loadedmetadata", () => { v.currentTime = st.pos; }, {once:true});

  document.getElementById("markDone").onclick = () => {
    const cur = S.lessons[k] || {};
    S.lessons[k] = Object.assign({}, cur, { watched: !cur.watched });
    save(); renderLesson(cid, nr);
  };

  function budget(){
    const left = S.dailyMinutes*60 - secondsToday();
    const el = document.getElementById("budget");
    if (!el) return;
    el.className = "budget" + (left<=0 ? " over" : "");
    el.innerHTML = left > 0
      ? `Heute noch <b>${fmtClock(left)}</b>`
      : `<b>Tagesziel erreicht</b> · ${fmtClock(secondsToday())}`;
  }
  budget();

  lastT = v.currentTime;
  ticker = setInterval(() => {
    if (v.paused || v.seeking) { lastT = v.currentTime; return; }
    addSeconds((v.currentTime - lastT));
    lastT = v.currentTime;
    const cur = S.lessons[k] || {};
    cur.pos = v.currentTime;
    if (v.duration && v.currentTime / v.duration > 0.92) cur.watched = true;
    S.lessons[k] = cur; save();
    budget(); chrome();
  }, 1000);

  chrome();
}

/* ---------- Test ---------- */
function runQuiz({title, crumb, questions, onDone, passMark}){
  let i = 0, right = 0, answered = false;

  function draw(){
    if (i >= questions.length) return finish();
    const q = questions[i];
    view().innerHTML = `<button class="crumb" data-nav="${crumb.href}">← ${esc(crumb.label)}</button>
      <h1>${esc(title)}</h1>
      <div class="quiz">
        <div class="qhead"><span>Frage ${i+1} von ${questions.length}</span><span>${right} richtig</span></div>
        <p class="qtext">${esc(q.q)}</p>
        <div class="opts" id="opts">
          ${q.options.map((o,n)=>`<button class="opt" data-i="${n}">${esc(o)}</button>`).join("")}
        </div>
        <div id="why"></div>
      </div>`;
    answered = false;
    document.getElementById("opts").onclick = e => {
      const b = e.target.closest(".opt");
      if (!b || answered) return;
      answered = true;
      const pick = Number(b.dataset.i);
      const ok = pick === q.answer;
      if (ok) right++;
      [...document.querySelectorAll(".opt")].forEach((el,n) => {
        el.disabled = true;
        if (n === q.answer) el.classList.add("right");
        else if (n === pick) el.classList.add("wrong");
      });
      document.getElementById("why").innerHTML =
        `<div class="why ${ok?"":"bad"}"><b>${ok?"Richtig.":"Nicht ganz."}</b> ${esc(q.why)}</div>
         <div class="row"><button class="btn" id="next">${i+1<questions.length?"Weiter →":"Auswertung →"}</button></div>`;
      document.getElementById("next").onclick = () => { i++; draw(); };
    };
    chrome();
  }

  function finish(){
    const score = right / questions.length;
    const ok = score >= passMark;
    onDone(score);
    view().innerHTML = `<button class="crumb" data-nav="${crumb.href}">← ${esc(crumb.label)}</button>
      <div class="quiz result">
        <div>${ok ? "Bestanden" : "Noch nicht bestanden"}</div>
        <div class="big ${ok?"ok":"bad"}">${Math.round(score*100)} %</div>
        <div style="color:var(--dim)">${right} von ${questions.length} richtig · nötig sind ${Math.round(passMark*100)} %</div>
        <div class="row" style="justify-content:center">
          <button class="btn sec" id="again">Nochmal versuchen</button>
          <button class="btn" data-nav="${crumb.href}">Weiter →</button>
        </div>
      </div>`;
    document.getElementById("again").onclick = () => { i = 0; right = 0; draw(); };
    chrome();
  }
  draw();
}

async function renderQuiz(cid, nr){
  const c = course(cid), l = lesson(cid, nr);
  const q = await getQuiz(cid);
  const qs = q[nr]?.questions || [];
  if (!c || !l || !qs.length) return go(`#/course/${cid}`);
  runQuiz({
    title: `Test · ${l.title}`,
    crumb: { href:`course/${cid}`, label:c.title },
    questions: qs,
    passMark: PASS_LESSON,
    onDone: score => {
      const k = key(cid, nr), prev = S.quiz[k] || {};
      S.quiz[k] = {
        best: Math.max(prev.best || 0, score),
        passed: (prev.passed || false) || score >= PASS_LESSON,
        attempts: (prev.attempts || 0) + 1,
      };
      save();
    }
  });
}

/* Abschlusspruefung: zufaellige Mischung aus allen Lektionsfragen. */
async function renderExam(cid){
  const c = course(cid);
  const q = await getQuiz(cid);
  const pool = [];
  for (const [n, blockk] of Object.entries(q))
    for (const item of (blockk.questions || [])) pool.push({ ...item, from:n });
  if (!c || !pool.length) return go(`#/course/${cid}`);
  for (let i = pool.length-1; i > 0; i--){        // Fisher-Yates
    const j = Math.floor(Math.random()*(i+1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  runQuiz({
    title: `Abschlussprüfung · ${c.title}`,
    crumb: { href:`course/${cid}`, label:c.title },
    questions: pool.slice(0, EXAM_SIZE),
    passMark: PASS_EXAM,
    onDone: score => {
      const prev = S.exam[cid] || {};
      S.exam[cid] = {
        best: Math.max(prev.best || 0, score),
        passed: (prev.passed || false) || score >= PASS_EXAM,
        attempts: (prev.attempts || 0) + 1,
      };
      save();
    }
  });
}

/* ---------- Einstellungen ---------- */
function renderSettings(){
  const totalSec = Object.values(S.days).reduce((a,b)=>a+b,0);
  const days = Object.keys(S.days).filter(d => S.days[d] > 60).length;
  let rows = "";
  for (const c of DATA.courses){
    const p = courseProgress(c);
    rows += `<tr><td>${esc(c.title)}</td><td>${p.watched}/${p.total} geschaut · ${p.passed} Tests</td></tr>`;
  }
  view().innerHTML = `<button class="crumb" data-nav="home">← Übersicht</button>
    <h1>Einstellungen</h1>
    <div class="quiz">
      <label>Tagesziel in Minuten
        <input id="daily" type="number" min="5" max="240" value="${S.dailyMinutes}"
          style="width:80px;margin-left:10px;background:var(--panel2);color:var(--text);border:1px solid var(--line);border-radius:9px;padding:8px">
      </label>
      <div class="row"><button class="btn" id="saveDaily">Speichern</button></div>
    </div>
    <h2>Dein Stand</h2>
    <table class="stats">
      <tr><td>Insgesamt gelernt</td><td>${fmtClock(totalSec)} min</td></tr>
      <tr><td>Tage mit Lernzeit</td><td>${days}</td></tr>
      <tr><td>Aktuelle Serie</td><td>${streakDays()} Tage</td></tr>
      ${rows}
    </table>
    <h2>Fortschritt sichern</h2>
    <p style="color:var(--dim);font-size:13.5px">Alles liegt nur in diesem Browser. Vor einem Rechnerwechsel exportieren.</p>
    <div class="row">
      <button class="btn sec" id="exp">Als Datei exportieren</button>
      <button class="btn sec" id="imp">Datei einlesen</button>
      <button class="btn sec" id="rst" style="color:var(--bad)">Alles zurücksetzen</button>
    </div>
    <input type="file" id="file" accept="application/json" hidden>`;

  document.getElementById("saveDaily").onclick = () => {
    const v = Number(document.getElementById("daily").value);
    if (v >= 5 && v <= 240){ S.dailyMinutes = v; save(); }
    renderSettings();
  };
  document.getElementById("exp").onclick = () => {
    const b = new Blob([JSON.stringify(S,null,2)], {type:"application/json"});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b);
    a.download = `academy-fortschritt-${todayKey()}.json`;
    a.click(); URL.revokeObjectURL(a.href);
  };
  document.getElementById("imp").onclick = () => document.getElementById("file").click();
  document.getElementById("file").onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    try{
      S = Object.assign(blank(), JSON.parse(await f.text()));
      save(); renderSettings();
    }catch{ alert("Datei konnte nicht gelesen werden."); }
  };
  document.getElementById("rst").onclick = () => {
    if (confirm("Wirklich den gesamten Fortschritt löschen?")){ S = blank(); save(); go("#/"); }
  };
  chrome();
}

/* ---------- Start ---------- */
(async function init(){
  try{
    const r = await fetch("data/academy.json", {cache:"no-store"});
    if (!r.ok) throw new Error(r.status);
    DATA = await r.json();
  }catch(err){
    view().innerHTML = `<div class="empty">
      <b>Die Kursdaten konnten nicht geladen werden.</b><br><br>
      Die Academy muss über einen lokalen Server laufen, nicht per Doppelklick.<br>
      Im Terminal: <code>~/Projekte/academy/start.sh</code></div>`;
    return;
  }
  route();
})();
