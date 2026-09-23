/* Academy - persönliche Lernoberfläche.
   Videos werden direkt vom öffentlichen ETH-Videoserver gestreamt, nichts wird kopiert.
   Fortschritt liegt ausschließlich lokal im Browser (localStorage). */

const STORE = "academy.v1";
const DAILY_DEFAULT = 30;          // Minuten pro Tag
const PASS_LESSON = 0.7;           // Test bestanden ab 70 %
const PASS_EXAM = 0.75;            // Abschlussprüfung ab 75 %
const EXAM_SIZE = 15;              // Fragen in der Abschlussprüfung
const EXAM_UNLOCK = 0.6;           // Anteil bestandener Lektionstests, ab dem die Prüfung offen ist
const WATCHED_AT = 0.92;           // ab diesem Anteil gilt ein Video als geschaut
const SPEEDS = [1, 1.25, 1.5, 1.75, 2];
const GOALS = [15, 20, 30, 45, 60];

let DATA = null;
const QUIZ = {};

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
window.addEventListener("storage", e => {
  if (e.key !== STORE || e.storageArea !== localStorage) return;
  S = load();
  applyTheme(); chrome();                 // Laufende Videos und Tests ohne Neuaufbau erhalten.
});

const todayKey = () => new Date().toLocaleDateString("sv-SE");   // YYYY-MM-DD, lokale Zeit
const key = (c,n) => `${c}/${n}`;

/* ---------- Helfer ---------- */
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct = x => `${Math.round(x*100)} %`;
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const fmtMin = ms => `${Math.max(1, Math.round(ms/60000))} min`;
const fmtHrs = ms => `${(ms/3600000).toFixed(1).replace(".", ",")} h`;
function fmtClock(sec){
  sec = Math.max(0, Math.round(sec));
  return `${Math.floor(sec/60)}:${String(sec%60).padStart(2,"0")}`;
}
function fmtSpan(sec){                                  // 95 min -> "1 h 35 min"
  const m = Math.round(sec/60);
  return m < 60 ? `${m} min` : `${Math.floor(m/60)} h ${m%60} min`;
}
const person = n => n.includes(",") ? n.split(",").map(s => s.trim()).reverse().join(" ") : n;  // Nachname, Vorname
const course = id => DATA.courses.find(c => c.id === id);
const lesson = (c,n) => course(c)?.lessons.find(l => l.nr === Number(n));
const lessonMs = l => l.durationMs || (l.estMinutes||0)*60000;
// Einzige Brücke zum alten Datenformat; der Player arbeitet ausschließlich mit Clips.
const clipsOf = l => l.clips?.length ? l.clips : [{
  opencastId:l.opencastId, title:l.title, video:l.video, captionLocal:l.captionLocal,
  captionLang:l.captionLang, durationMs:lessonMs(l),
}];
const quizOf = (cid, nr) => QUIZ[cid]?.[nr]?.questions || [];
const langTag = c => c.kind === "external" ? `<span class="tag ext">Extern</span>`
  : `<span class="tag ${esc(c.lang)}">${c.lang === "de" ? "Deutsch" : "Englisch"}</span>`;
const runningTag = c => c.running ? `<span class="tag running">Läuft</span>` : "";
function shuffle(a){
  a = a.slice();
  for (let i = a.length-1; i > 0; i--){                // Fisher-Yates
    const j = Math.floor(Math.random()*(i+1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const ICONS = {
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  arrowLeft:  '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  check:      '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  x:          '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  play:       '<path d="M8 5.6v12.8a.9.9 0 0 0 1.37.77l10.2-6.4a.9.9 0 0 0 0-1.54L9.37 4.83A.9.9 0 0 0 8 5.6z"/>',
  star:       '<path d="M12 3.6l2.5 5.2 5.7.8-4.1 4 1 5.7L12 16.6l-5.1 2.7 1-5.7-4.1-4 5.7-.8z"/>',
  flame:      '<path d="M12 2.5c2.2 3 5.5 6.2 5.5 11a5.5 5.5 0 0 1-11 0c0-2.4 1.1-4.1 2.3-5.4.1 1.6.8 2.7 1.9 3.2C10.3 8.4 11 5.2 12 2.5z"/>',
  sliders:    '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  external:   '<path d="M14 4h6v6M20 4l-9 9M19 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4 18.5v-12A1.5 1.5 0 0 1 5.5 5H10"/>',
  info:       '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.8v.1"/>',
  doc:        '<path d="M7 3h7l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
  again:      '<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3M4.5 4.5v4h4"/>',
};
const icon = (name, cls = "") => `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;

/* Fortschrittsring; frac 0..1, stroke in Einheiten der 100er-Viewbox. */
function ring(frac, size, stroke, label = "", tone = ""){
  frac = Math.max(0, Math.min(1, frac || 0));
  const r = 50 - stroke/2, c = 2*Math.PI*r;
  return `<span class="ringwrap" style="width:${size}px;height:${size}px">
    <svg class="ring ${tone || (frac >= 1 ? "ok" : "")}" viewBox="0 0 100 100" width="${size}" height="${size}" aria-hidden="true">
      <circle class="ring-track" cx="50" cy="50" r="${r}" stroke-width="${stroke}"/>
      ${frac > 0 ? `<circle class="ring-val" cx="50" cy="50" r="${r}" stroke-width="${stroke}"
        stroke-dasharray="${c.toFixed(2)}" stroke-dashoffset="${(c*(1-frac)).toFixed(2)}" transform="rotate(-90 50 50)"/>` : ""}
    </svg>${label ? `<span class="ringlabel">${label}</span>` : ""}</span>`;
}
function bar(frac, cls = ""){
  const value = Math.max(0, Math.min(1, frac || 0))*100;
  return `<div class="bar ${esc(cls)} ${value >= 100 ? "done" : ""}" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(value)}"><i style="width:${value.toFixed(1)}%"></i></div>`;
}

/* ---------- Lernzeit ---------- */
function secondsToday(){ return S.days[todayKey()] || 0; }
function addSeconds(sec){
  if (!(sec > 0) || sec > 90) return;            // Lange Segmente nach Ruhezustand/Sleep verwerfen.
  const k = todayKey();
  S.days[k] = (S.days[k] || 0) + sec;
}
function streakDays(){
  let n = 0;
  const d = new Date();
  // Heute zählt nur, wenn schon gelernt wurde - sonst beim gestrigen Tag anfangen.
  if (!(S.days[todayKey()] > 60)) d.setDate(d.getDate() - 1);
  for(;;){
    const k = d.toLocaleDateString("sv-SE");
    if (!(S.days[k] > 60)) break;
    n++; d.setDate(d.getDate() - 1);
  }
  return n;
}

/* ---------- Fortschritt ---------- */
function lessonState(cid, l){
  const st = S.lessons[key(cid, l.nr)] || {}, qz = S.quiz[key(cid, l.nr)] || {};
  const dur = lessonMs(l);
  return {
    watched: !!st.watched,
    frac: st.watched ? 1 : (st.pos && dur ? Math.min(1, st.pos*1000/dur) : 0),
    passed: !!qz.passed, best: qz.best || 0, attempts: qz.attempts || 0,
  };
}
function courseProgress(c){
  let watched = 0, passed = 0, msDone = 0, msTotal = 0;
  for (const l of c.lessons){
    const s = lessonState(c.id, l), dur = lessonMs(l);
    msTotal += dur; msDone += dur*s.frac;
    if (s.watched) watched++;
    if (s.passed) passed++;
  }
  return { total:c.lessons.length, watched, passed, msTotal, pct: msTotal ? msDone/msTotal : 0 };
}
const examNeed = c => Math.ceil(c.lessons.length * EXAM_UNLOCK);
const examReady = c => !c.running && courseProgress(c).passed >= examNeed(c);

/* Erste ungeschaute Lektion, bevorzugt im zuletzt benutzten Kurs. */
function firstUnwatched(preferCid){
  for (const c of new Set([course(preferCid), ...DATA.courses].filter(Boolean))){
    if (S.last?.startsWith(c.id + "/")){
      const l = lesson(c.id, S.last.split("/")[1]);
      if (l && !lessonState(c.id, l).watched) return { cid:c.id, l };
    }
    const l = c.lessons.find(l => !lessonState(c.id, l).watched);
    if (l) return { cid:c.id, l };
  }
  return null;
}
/* Was als Nächstes dran ist: angefangene Lektion, offener Test dazu, nächste Lektion, Prüfung. */
function nextStep(){
  const [lastCid, lastNr] = (S.last || "").split("/");
  const last = lesson(lastCid, lastNr);
  if (last){
    const s = lessonState(lastCid, last);
    if (!s.watched) return { kind:"lesson", cid:lastCid, l:last };
    if (!s.passed && quizOf(lastCid, last.nr).length) return { kind:"quiz", cid:lastCid, l:last };
  }
  const nx = firstUnwatched(lastCid);
  if (nx) return { kind:"lesson", ...nx };
  for (const c of DATA.courses){
    const l = c.lessons.find(l => !lessonState(c.id, l).passed && quizOf(c.id, l.nr).length);
    if (l) return { kind:"quiz", cid:c.id, l };
  }
  const c = DATA.courses.find(c => examReady(c) && !(S.exam[c.id] || {}).passed);
  return c ? { kind:"exam", cid:c.id } : null;
}

/* ---------- Navigation ---------- */
const view = () => document.getElementById("view");
const leaving = [];
const onLeave = fn => leaving.push(fn);
function go(hash){ location.hash = hash; }
window.addEventListener("hashchange", route);

function route(){
  if (!DATA) return;                                  // init() ruft route() auf, sobald die Daten da sind
  for (const fn of leaving.splice(0)) fn();
  const [page, a, b] = (location.hash || "#/").replace(/^#\/?/, "").split("/").filter(Boolean);
  window.scrollTo(0, 0);
  if (!page) renderHome();
  else if (page === "settings") renderSettings();
  else if (page === "course") renderCourse(a);
  else if (page === "lesson") renderLesson(a, b);
  else if (page === "quiz") renderQuiz(a, b);
  else if (page === "exam") renderExam(a);
  else return go("#/");
  view().focus({ preventScroll:true });
}

function mount(html, { title = "", narrow = false } = {}){
  const v = view();
  v.className = narrow ? "narrow" : "";
  v.innerHTML = html;
  void v.offsetWidth;                    // Einblendung nur beim Neuaufbau erneut starten.
  v.classList.add("enter");
  document.title = title ? `${title} · Academy` : "Academy";
  chrome();
}

/* Kopfzeile: Serie, heutige Lernzeit, Einstellungen. */
function chrome(){
  const st = streakDays(), done = secondsToday(), goal = S.dailyMinutes*60;
  const here = location.hash.startsWith("#/settings") ? ' aria-current="page"' : "";
  document.getElementById("status").innerHTML = `
    ${st ? `<span class="pill streak" title="${plural(st, "Tag", "Tage")} in Folge gelernt">
      ${icon("flame", "fill")}<b>${st}</b><span class="sr">Tage in Folge</span></span>` : ""}
    <span class="pill" title="Heute ${fmtSpan(done)} von ${S.dailyMinutes} min gelernt">
      ${ring(done/goal, 18, 16)}<span><b>${Math.floor(done/60)}</b><span class="unit"> / ${S.dailyMinutes} min</span></span></span>
    <a class="iconbtn" href="#/settings" title="Einstellungen" aria-label="Einstellungen"${here}>${icon("sliders")}</a>`;
}

/* ---------- Startseite ---------- */
function renderHome(){
  const lessons = DATA.courses.reduce((a, c) => a + c.lessons.length, 0);
  const date = new Date().toLocaleDateString("de-CH", { weekday:"long", day:"numeric", month:"long" });
  mount(`
    <p class="eyebrow">${esc(date)}</p>
    <h1>Deine Academy</h1>
    <p class="lede">${plural(DATA.courses.length, "Kurs", "Kurse")} · ${lessons} Lektionen · ${S.dailyMinutes} Minuten am Tag</p>
    ${todayCard()}
    <h2>Kurse</h2>
    <div class="courses">${DATA.courses.map(courseCard).join("")}</div>`);
}

function todayCard(){
  const step = nextStep(), done = secondsToday(), goal = S.dailyMinutes*60;
  let body;
  if (!step){
    body = `<p class="eyebrow">Alles erledigt</p>
      <h3 class="today-title">Alle Lektionen, Tests und Prüfungen sind geschafft.</h3>
      <p class="today-meta">Zeit für einen neuen Kurs.</p>`;
  } else if (step.kind === "lesson"){
    const c = course(step.cid), l = step.l, s = lessonState(c.id, l), started = s.frac > 0;
    body = `<p class="eyebrow">${started ? "Weiter bei" : "Als Nächstes"} · ${esc(c.title)}</p>
      <h3 class="today-title">${esc(l.title)}</h3>
      <p class="today-meta">Lektion ${esc(l.nr)} von ${c.lessons.length} · ${started ? `noch ${fmtMin(lessonMs(l)*(1-s.frac))}` : fmtMin(lessonMs(l))}</p>
      ${started ? bar(s.frac, "thin") : ""}
      <div class="actions">
        <a class="btn btn-primary btn-lg" href="#/lesson/${esc(c.id)}/${esc(l.nr)}">${icon("play", "fill")} ${started ? "Weiterschauen" : "Lektion starten"}</a>
      </div>`;
  } else if (step.kind === "quiz"){
    const c = course(step.cid), l = step.l, s = lessonState(c.id, l), n = quizOf(c.id, l.nr).length;
    const after = firstUnwatched(c.id);
    body = `<p class="eyebrow">Test offen · ${esc(c.title)}</p>
      <h3 class="today-title">${esc(l.title)}</h3>
      <p class="today-meta">Lektion ${esc(l.nr)} ist geschaut. ${n} Fragen${s.attempts ? `, bisher ${pct(s.best)}` : ""}, bestanden ab ${pct(PASS_LESSON)}.</p>
      <div class="actions">
        <a class="btn btn-primary btn-lg" href="#/quiz/${esc(c.id)}/${esc(l.nr)}">Test starten ${icon("arrowRight")}</a>
        ${after ? `<a class="btn btn-ghost" href="#/lesson/${esc(after.cid)}/${esc(after.l.nr)}">Später, erst Lektion ${esc(after.l.nr)}</a>` : ""}
      </div>`;
  } else {
    const c = course(step.cid);
    body = `<p class="eyebrow">Abschlussprüfung · ${esc(c.title)}</p>
      <h3 class="today-title">Genug Tests bestanden. Bereit für die Prüfung?</h3>
      <p class="today-meta">${EXAM_SIZE} Fragen quer durch den Kurs, bestanden ab ${pct(PASS_EXAM)}.</p>
      <div class="actions"><a class="btn btn-primary btn-lg" href="#/exam/${esc(c.id)}">Prüfung starten ${icon("arrowRight")}</a></div>`;
  }
  return `<section class="card today" aria-label="Heute">
    <div>${body}</div>
    <div class="today-side">
      ${ring(done/goal, 108, 9, `<b>${Math.floor(done/60)}</b><span>von ${S.dailyMinutes} min</span>`)}
      <p class="today-goal ${done >= goal ? "ok" : ""}">${done >= goal ? "Tagesziel erreicht" : `Heute noch ${Math.ceil((goal-done)/60)} min`}</p>
      ${weekStrip()}
    </div>
  </section>`;
}

/* Die letzten sieben Tage als Punkte: leer, angefangen, Ziel erreicht. */
function weekStrip(){
  const d = new Date(), out = [];
  d.setDate(d.getDate() - 6);
  for (let i = 0; i < 7; i++){
    const sec = S.days[d.toLocaleDateString("sv-SE")] || 0;
    const cls = sec >= S.dailyMinutes*60 ? "full" : sec > 60 ? "part" : "";
    const day = d.toLocaleDateString("de-CH", { weekday:"long", day:"numeric", month:"long" });
    out.push(`<span class="d ${i === 6 ? "is-today" : ""}" title="${esc(day)}: ${fmtSpan(sec)}">
      <i class="dot ${cls}"></i>${esc(d.toLocaleDateString("de-CH", { weekday:"short" }).slice(0, 2))}</span>`);
    d.setDate(d.getDate() + 1);
  }
  return `<div class="week" aria-label="Lernzeit der letzten sieben Tage">${out.join("")}</div>`;
}

function courseCard(c){
  const p = courseProgress(c);
  return `<a class="card course-card" href="#/course/${esc(c.id)}">
    <div class="tags">${langTag(c)}${runningTag(c)}<span class="tag">${c.lessons.length} Lektionen</span><span class="tag">${fmtHrs(p.msTotal)}</span></div>
    <h3>${esc(c.title)}</h3>
    <p class="src">${esc(c.subtitle)}</p>
    <p class="why">${esc(c.why)}</p>
    <div class="progress">
      ${bar(p.pct)}
      <div class="barlabel"><span>${p.watched}/${p.total} geschaut · ${plural(p.passed, "Test", "Tests")} bestanden</span><span>${pct(p.pct)}</span></div>
    </div>
  </a>`;
}

/* ---------- Kursseite ---------- */
function renderCourse(cid){
  const c = course(cid);
  if (!c) return go("#/");
  const p = courseProgress(c);
  const nx = firstUnwatched(cid);
  const next = nx && nx.cid === cid ? nx.l : null;
  const started = next && lessonState(cid, next).frac > 0;
  mount(`
    <a class="back" href="#/">${icon("arrowLeft")} Übersicht</a>
    <header class="course-head">
      <div>
        <div class="tags">${langTag(c)}${runningTag(c)}</div>
        <h1>${esc(c.title)}</h1>
        <p class="lede">${esc(c.subtitle)} · ${c.lessons.length} Lektionen · ${fmtHrs(p.msTotal)}</p>
      </div>
      ${next ? `<a class="btn btn-primary btn-lg" href="#/lesson/${esc(cid)}/${esc(next.nr)}">${icon("play", "fill")} ${started ? "Weiterschauen" : "Starten"} · Lektion ${esc(next.nr)}</a>` : ""}
    </header>
    <p class="course-why">${esc(c.why)}</p>
    ${c.note ? `<div class="callout">${icon("info")}<p>${esc(c.note)}</p></div>` : ""}
    <div class="stats">
      <div class="card stat"><div class="v">${pct(p.pct)}</div><div class="l">Fortschritt</div>${bar(p.pct)}</div>
      <div class="card stat"><div class="v">${p.watched}<small>/${p.total}</small></div><div class="l">Lektionen geschaut</div></div>
      <div class="card stat"><div class="v">${p.passed}<small>/${p.total}</small></div><div class="l">Tests bestanden</div></div>
    </div>
    <h2>Lektionen</h2>
    <div class="card lesson-list">${c.lessons.map(l => lessonRow(c, l, next)).join("")}</div>
    <h2>Abschlussprüfung</h2>
    ${examCard(c, p)}`, { title:c.title });
}

function lessonRow(c, l, next){
  const s = lessonState(c.id, l), n = quizOf(c.id, l.nr).length;
  const isNext = next && next.nr === l.nr;
  const cls = [s.passed ? "passed" : s.watched ? "watched" : "", isNext ? "is-next" : ""].join(" ");
  const mark = s.passed ? `${icon("star", "fill")}<span class="sr">Test bestanden</span>`
             : s.watched ? `${icon("check")}<span class="sr">geschaut</span>` : esc(l.nr);
  const quiz = s.passed ? `<span class="score">Test ${pct(s.best)}</span>`
             : s.attempts ? `<span class="retry">Test ${pct(s.best)}</span>`
             : n ? `${n} Fragen` : "";
  return `<a class="lrow ${cls}" href="#/lesson/${esc(c.id)}/${esc(l.nr)}">
    <span class="lnum">${mark}</span>
    <span class="lbody">
      <span class="ltitle">${esc(l.title)}${isNext ? `<span class="tag next">${s.frac > 0 ? "Angefangen" : "Als Nächstes"}</span>` : ""}</span>
      <span class="ltopics">${esc((l.topics || []).join(" · "))}</span>
      ${s.frac > 0 && s.frac < 1 ? bar(s.frac, "thin") : ""}
    </span>
    <span class="lmeta">${fmtMin(lessonMs(l))}<br>${quiz}</span>
  </a>`;
}

function examCard(c, p){
  if (c.running) return `<section class="card exam">
    <div><h3>Abschlussprüfung</h3><p>Die Abschlussprüfung öffnet, wenn der Kurs abgeschlossen ist.</p></div>
    <button type="button" class="btn btn-secondary" disabled>Prüfung starten</button>
  </section>`;
  const n = Object.values(QUIZ[c.id] || {}).reduce((a, b) => a + (b.questions || []).length, 0);
  if (!n) return `<div class="card empty">Für diesen Kurs sind noch keine Fragen hinterlegt.</div>`;
  const need = examNeed(c), ready = p.passed >= need, ex = S.exam[c.id] || {};
  const best = ex.best != null ? ` Bestes Ergebnis: <b>${pct(ex.best)}</b>${ex.passed ? ", bestanden" : ""}.` : "";
  return `<section class="card exam">
    <div>
      <h3>${Math.min(EXAM_SIZE, n)} Fragen quer durch den Kurs</h3>
      <p>Bestanden ab ${pct(PASS_EXAM)}. ${ready ? "Freigeschaltet." : `Wird freigeschaltet, sobald ${need} Lektionstests bestanden sind.`}${best}</p>
      ${ready ? "" : `${bar(p.passed/need)}<div class="barlabel"><span>${p.passed} von ${need} Tests bestanden</span></div>`}
    </div>
    ${ready ? `<a class="btn btn-primary" href="#/exam/${esc(c.id)}">Prüfung starten ${icon("arrowRight")}</a>`
            : `<button type="button" class="btn btn-secondary" disabled>Prüfung starten</button>`}
  </section>`;
}

/* ---------- Lektion ---------- */
const markLabel = w => w ? `${icon("check")} Geschaut` : "Als geschaut markieren";
function markBtn(k){
  const w = !!(S.lessons[k] || {}).watched;
  return `<button type="button" class="btn btn-secondary ${w ? "is-on" : ""}" id="markDone" aria-pressed="${w}">${markLabel(w)}</button>`;
}
function syncMark(k){
  const b = document.getElementById("markDone");
  if (!b) return;
  const w = !!(S.lessons[k] || {}).watched;
  b.classList.toggle("is-on", w);
  b.setAttribute("aria-pressed", String(w));
  b.innerHTML = markLabel(w);
}
function wireMark(k){
  // Nur den Knopf umschalten - ein Neuaufbau der Seite würde das laufende Video abbrechen.
  document.getElementById("markDone").onclick = () => {
    const cur = S.lessons[k] || {};
    cur.watched = !cur.watched;
    S.lessons[k] = cur; save(); syncMark(k);
  };
}

function renderLesson(cid, nr){
  const c = course(cid), l = lesson(cid, nr);
  if (!c || !l) return go(c ? `#/course/${cid}` : "#/");
  const k = key(cid, l.nr);
  S.last = k; save();
  const n = quizOf(cid, l.nr).length;
  const prev = lesson(cid, l.nr - 1), next = lesson(cid, l.nr + 1);
  const ext = c.kind === "external";
  const clips = ext ? [] : clipsOf(l);
  const meta = ext ? [`ca. ${fmtMin(lessonMs(l))}`, "Video extern"]
                   : [fmtMin(lessonMs(l)), ...(l.creators || []).map(person), c.lang === "de" ? "Deutsch" : "Englisch"];
  const saved = S.lessons[k] || {};
  if (!saved.watched && saved.pos > 5) meta.push(`fortsetzen bei ${fmtClock(saved.pos)}`);
  const testBtn = (cls = "btn-primary") => n
    ? `<a class="btn ${esc(cls)}" href="#/quiz/${esc(cid)}/${esc(l.nr)}">Test starten · ${n} Fragen ${icon("arrowRight")}</a>`
    : `<span class="muted">Für diese Lektion sind noch keine Fragen hinterlegt.</span>`;
  const topics = (l.topics || []).map(t => `<span class="chip">${esc(t)}</span>`).join("");

  const body = ext ? `
    <div class="callout">${icon("info")}<p>${esc(c.note)}</p></div>
    <section class="card ext-card">
      <h3>Worum es geht</h3>
      <div class="chips">${topics}</div>
      <div class="actions">
        <a class="btn btn-primary" href="${esc(l.externalUrl)}" target="_blank" rel="noopener">Auf ${esc(new URL(l.externalUrl).hostname.replace(/^www\./, ""))} öffnen ${icon("external")}</a>
        ${l.slidesUrl ? `<a class="btn btn-secondary" href="${esc(l.slidesUrl)}" target="_blank" rel="noopener">${icon("doc")} Folien (PDF)</a>` : ""}
      </div>
    </section>
    <div class="actions">${markBtn(k)}${testBtn("btn-secondary")}</div>`
  : `
    <div class="player">
      <video id="v" controls controlslist="nodownload" preload="metadata" playsinline></video>
    </div>
    <p class="player-error" id="playerError" role="status" hidden>Das Video konnte nicht geladen werden.
      <a href="${esc(c.portalUrl)}" target="_blank" rel="noopener">Kurs im ETH-Portal öffnen ${icon("external")}</a></p>
    ${clips.length > 1 ? `<ol class="card clip-list" aria-label="Clips dieser Lektion">${clips.map((clip, i) => `
      <li><button type="button" class="clip-row" data-clip="${esc(i)}">
        <span class="lnum">${esc(i+1)}</span><span class="clip-title">${esc(clip.title)}</span>
        <span class="clip-meta"><span class="clip-state">Offen</span><span>${esc(fmtClock(clip.durationMs/1000))}</span></span>
      </button></li>`).join("")}</ol>` : ""}
    <div class="toolbar">
      <div class="seg" role="group" aria-label="Tempo">${SPEEDS.map(r =>
        `<button type="button" data-rate="${r}" aria-pressed="${r === (S.rate || 1)}">${String(r).replace(".", ",")}×</button>`).join("")}</div>
      <button type="button" class="btn btn-secondary btn-sm" id="back10" title="10 Sekunden zurück">−10 s</button>
      <button type="button" class="btn btn-secondary btn-sm" id="fwd10" title="10 Sekunden vor">+10 s</button>
      <span class="spacer"></span>
      <span class="budget" id="budget"></span>
    </div>
    <div class="actions">${markBtn(k)}${testBtn()}</div>
    ${topics ? `<div class="topics"><h3>Themen</h3><div class="chips">${topics}</div></div>` : ""}`;

  mount(`
    <a class="back" href="#/course/${esc(cid)}">${icon("arrowLeft")} ${esc(c.title)}</a>
    <p class="eyebrow">Lektion ${esc(l.nr)} von ${c.lessons.length}</p>
    <h1>${esc(l.title)}</h1>
    <p class="lede">${meta.map(esc).join(" · ")}</p>
    ${body}
    <nav class="pager" aria-label="Lektionen">
      ${prev ? `<a class="pg" href="#/lesson/${esc(cid)}/${esc(prev.nr)}"><span>${icon("arrowLeft")} Lektion ${esc(prev.nr)}</span><b>${esc(prev.title)}</b></a>` : ""}
      ${next ? `<a class="pg next" href="#/lesson/${esc(cid)}/${esc(next.nr)}"><span>Lektion ${esc(next.nr)} ${icon("arrowRight")}</span><b>${esc(next.title)}</b></a>`
             : `<a class="pg next" href="#/course/${esc(cid)}"><span>${c.running ? "Zum Kurs" : "Zum Abschluss"} ${icon("arrowRight")}</span><b>${c.running ? "Zur Kursübersicht" : "Zur Abschlussprüfung"}</b></a>`}
    </nav>
    ${ext ? "" : `<p class="source"><a href="${esc(c.portalUrl)}" target="_blank" rel="noopener">Kurs im ETH-Portal ${icon("external")}</a></p>`}`,
    { title:l.title });

  wireMark(k);
  if (!ext) wirePlayer(k, clips, c.lang);
}

function wirePlayer(k, clips, lang){
  const v = document.getElementById("v");
  const error = document.getElementById("playerError"), rows = [...document.querySelectorAll("[data-clip]")];
  const durations = clips.map(clip => Math.max(0, Number(clip.durationMs) || 0)/1000), offsets = [];
  const total = durations.reduce((sum, duration) => { offsets.push(sum); return sum + duration; }, 0);
  const resume = Number((S.lessons[k] || {}).pos) || 0;
  let active = -1, pendingTime = null, segmentStart = null, playing = false, alive = true;
  let version = 0, metadata = null, autoplay = false;
  const events = new AbortController();
  const listen = (type, fn, capture = false) => v.addEventListener(type, fn, { signal:events.signal, capture });

  // Videoposition und Lernzeit bleiben unabhängig: auch ein Sprung zählt nur verstrichene Uhrzeit.
  const finishSegment = () => {
    if (segmentStart === null) return;
    addSeconds((performance.now() - segmentStart)/1000);
    segmentStart = null;
  };
  const startSegment = () => {
    if (alive && playing && pendingTime === null && !v.paused && !v.seeking && !v.ended && v.readyState >= 3)
      segmentStart = performance.now();
  };
  const position = () => active < 0 ? resume
    : offsets[active] + Math.min(durations[active], Math.max(0, pendingTime ?? v.currentTime));
  const updateClips = () => {
    const pos = position(), watched = (S.lessons[k] || {}).watched;
    rows.forEach((row, i) => {
      const current = i === active, done = watched || pos >= offsets[i] + durations[i]*WATCHED_AT;
      row.classList.toggle("is-current", current);
      row.classList.toggle("watched", !!done);
      if (current) row.setAttribute("aria-current", "true");
      else row.removeAttribute("aria-current");
      row.querySelector(".clip-state").textContent = current ? "Aktuell" : done ? "Geschaut" : "Offen";
    });
  };
  const savePos = (checkWatched = false, finished = false) => {
    if (active < 0) return;
    const cur = S.lessons[k] || {};
    cur.pos = finished ? total : position();
    if (finished || (checkWatched && total > 0 && cur.pos/total >= WATCHED_AT)) cur.watched = true;
    S.lessons[k] = cur; save(); syncMark(k); updateClips();
  };
  const applyRate = () => { v.defaultPlaybackRate = v.playbackRate = S.rate || 1; };

  // Ein Übergang für Auswahl, Fortsetzen, automatische Folge und absolute Sprünge.
  function selectClip(i, localTime = 0, play = false){
    finishSegment(); savePos();
    playing = false;
    v.pause();
    if (metadata) v.removeEventListener("loadedmetadata", metadata);
    const clip = clips[i], selected = ++version;
    active = i; pendingTime = Math.max(0, Math.min(durations[i], localTime)); autoplay = play;
    error.hidden = true;
    v.innerHTML = `<source src="${esc(clip.video)}" type="video/mp4">
      ${clip.captionLocal ? `<track default kind="subtitles" srclang="${esc((clip.captionLang || lang || "de").slice(0, 2))}" label="Untertitel" src="${esc(clip.captionLocal)}">` : ""}`;
    metadata = () => {
      if (!alive || selected !== version || v.readyState < 1 || pendingTime === null) return;
      v.removeEventListener("loadedmetadata", metadata);
      v.currentTime = Math.min(pendingTime, Number.isFinite(v.duration) ? v.duration : pendingTime);
      pendingTime = null;
      applyRate(); savePos();
      if (autoplay) v.play().catch(e => {
        if (alive && selected === version && e.name !== "AbortError" && e.name !== "NotAllowedError") showError();
      });
    };
    v.addEventListener("loadedmetadata", metadata);
    v.load();
    savePos();
  }
  function seekTo(pos, play){
    pos = Math.max(0, Math.min(total, pos));
    let i = 0;
    while (i < clips.length - 1 && pos >= offsets[i+1]) i++;
    selectClip(i, pos - offsets[i], play);
  }

  document.querySelector(".seg").onclick = e => {
    const b = e.target.closest("[data-rate]");
    if (!b) return;
    finishSegment();
    S.rate = Number(b.dataset.rate); applyRate(); startSegment(); save();
    document.querySelectorAll("[data-rate]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
  };
  const wantsPlay = () => pendingTime !== null ? autoplay : !v.paused && !v.ended;
  document.getElementById("back10").onclick = () => seekTo(position() - 10, wantsPlay());
  document.getElementById("fwd10").onclick = () => seekTo(position() + 10, wantsPlay());
  rows.forEach((row, i) => { row.onclick = () => selectClip(i, 0, wantsPlay()); });
  document.getElementById("markDone").addEventListener("click", updateClips);

  const budget = () => {
    const el = document.getElementById("budget");
    if (!el) return;
    const done = secondsToday(), left = S.dailyMinutes*60 - done;
    el.className = "budget" + (left <= 0 ? " ok" : "");
    el.innerHTML = ring(done/(S.dailyMinutes*60), 18, 16)
      + (left > 0 ? `<span>Heute noch <b>${fmtClock(left)}</b></span>` : `<b>Tagesziel erreicht</b>`);
  };
  budget();

  const stop = () => {
    finishSegment(); playing = false; savePos(); budget(); chrome();
  };
  function showError(){ stop(); error.hidden = false; }
  listen("playing", () => { finishSegment(); playing = true; startSegment(); });
  for (const type of ["pause", "seeking", "waiting", "emptied"]) listen(type, stop);
  listen("seeked", () => savePos());
  listen("ratechange", () => { finishSegment(); startSegment(); save(); });
  listen("ended", () => {
    stop();
    if (active < clips.length - 1) selectClip(active + 1, 0, true);
    else savePos(false, true);
  });
  // Bei <source> meldet der Browser den Ladefehler am Kind statt am Video.
  listen("error", e => { if (e.target === v || e.target.tagName === "SOURCE") showError(); }, true);

  const tick = setInterval(() => {
    if (!playing) return;
    finishSegment(); startSegment(); savePos(true);
    budget(); chrome();
  }, 1000);
  const pageHide = () => { stop(); v.pause(); };
  window.addEventListener("pagehide", pageHide);
  onLeave(() => {
    clearInterval(tick); stop(); alive = false; events.abort();
    if (metadata) v.removeEventListener("loadedmetadata", metadata);
    window.removeEventListener("pagehide", pageHide);
    v.pause();
  });
  seekTo(resume, false);
}

/* ---------- Test ---------- */
function runQuiz({ eyebrow, title, back, deal, passMark, onDone, cont }){
  const KEYS = "ABCDEFGH";
  let qs = deal(), i = 0, answers = [];

  function onKey(e){
    if (e.metaKey || e.ctrlKey || e.altKey || e.target.closest?.("input, textarea, select")) return;
    if (i >= qs.length) return;
    if (answers.length <= i){
      const k = e.key.toUpperCase();
      let n = "123456789".indexOf(k);
      if (n < 0) n = KEYS.indexOf(k);
      if (n >= 0 && n < qs[i].options.length){ e.preventDefault(); choose(n); }
    } else if ((e.key === "Enter" && !e.target.closest?.("button, a")) || e.key === "ArrowRight"){
      e.preventDefault(); advance();
    }
  }
  document.addEventListener("keydown", onKey);
  onLeave(() => document.removeEventListener("keydown", onKey));

  const backLink = `<a class="back" href="#/${esc(back.href)}">${icon("arrowLeft")} ${esc(back.label)}</a>`;

  function draw(){
    if (i >= qs.length) return finish();
    const q = qs[i], right = answers.filter(a => a.ok).length;
    mount(`${backLink}
      <p class="eyebrow">${esc(eyebrow)}</p>
      <h1>${esc(title)}</h1>
      <div class="qhead"><span>Frage ${i+1} von ${qs.length}</span><span id="score">${right} richtig</span></div>
      <div class="qprog" aria-hidden="true">${qs.map((_, n) =>
        `<i class="${n < answers.length ? (answers[n].ok ? "ok" : "bad") : n === i ? "cur" : ""}"></i>`).join("")}</div>
      <section class="card qcard">
        <p class="qtext">${esc(q.q)}</p>
        <div class="opts" role="group" aria-label="Antworten">${q.options.map((o, n) =>
          `<button type="button" class="opt" data-opt="${n}"><span class="k">${KEYS[n]}</span><span>${esc(o)}</span><span class="mark"></span></button>`).join("")}
        </div>
        <div id="feedback" aria-live="polite"></div>
      </section>
      <div class="qfoot">
        <span class="hint"><kbd>A</kbd>–<kbd>${KEYS[q.options.length-1]}</kbd> wählt, <kbd>Enter</kbd> geht weiter</span>
        <span id="nextSlot"></span>
      </div>`, { narrow:true, title });
    window.scrollTo(0, 0);
    document.querySelector(".opts").onclick = e => {
      const b = e.target.closest("[data-opt]");
      if (b) choose(Number(b.dataset.opt));
    };
  }

  function choose(n){
    if (answers.length > i) return;
    const q = qs[i], ok = n === q.answer;
    answers.push({ pick:n, ok });
    document.querySelectorAll("[data-opt]").forEach((el, m) => {
      el.disabled = true;
      if (m === q.answer){ el.classList.add("right"); el.querySelector(".mark").innerHTML = icon("check"); }
      else if (m === n){ el.classList.add("wrong"); el.querySelector(".mark").innerHTML = icon("x"); }
      else el.classList.add("dim");
    });
    document.querySelector(".qprog").children[i].className = ok ? "ok" : "bad";
    document.getElementById("score").textContent = `${answers.filter(a => a.ok).length} richtig`;
    document.getElementById("feedback").innerHTML =
      `<div class="explain ${ok ? "ok" : "bad"}"><b>${ok ? "Richtig." : "Nicht ganz."}</b>${esc(q.why)}</div>`;
    document.getElementById("nextSlot").innerHTML =
      `<button type="button" class="btn btn-primary" id="next">${i+1 < qs.length ? "Weiter" : "Auswertung"} ${icon("arrowRight")}</button>`;
    const nb = document.getElementById("next");
    nb.onclick = advance;
    nb.focus({ preventScroll:true });
    nb.scrollIntoView({ block:"nearest", behavior:"smooth" });
  }

  function advance(){ i++; draw(); }

  function finish(){
    const right = answers.filter(a => a.ok).length, score = right / qs.length, ok = score >= passMark;
    onDone(score);
    const missed = qs.map((q, n) => ({ q, a:answers[n] })).filter(x => !x.a.ok);
    const c = cont(ok);
    mount(`${backLink}
      <section class="card result">
        ${ring(score, 136, 8, `<b>${pct(score)}</b><span>${right} von ${qs.length}</span>`, ok ? "ok" : "warn")}
        <h1>${ok ? "Bestanden" : "Noch nicht bestanden"}</h1>
        <p class="lede">${ok ? "" : `Nötig sind ${pct(passMark)}. `}${missed.length ? "Was nicht gesessen hat, steht unten zum Nachlesen." : "Alles richtig."}</p>
        <div class="actions center">
          <button type="button" class="btn btn-secondary" id="again">${icon("again")} Nochmal</button>
          ${c ? `<a class="btn btn-primary" href="${esc(c.href)}">${esc(c.label)} ${icon("arrowRight")}</a>` : ""}
        </div>
      </section>
      ${missed.length ? `<h2>Zum Nachlesen</h2>
      <div class="card">${missed.map(({ q, a }) => `<div class="review-item">
        <p class="q">${esc(q.q)}</p>
        <p class="a mine">${icon("x")}<span>${esc(q.options[a.pick])}</span></p>
        <p class="a good">${icon("check")}<span>${esc(q.options[q.answer])}</span></p>
        <p class="why">${esc(q.why)}</p>
      </div>`).join("")}</div>` : ""}`, { narrow:true, title });
    window.scrollTo(0, 0);
    document.getElementById("again").onclick = () => { qs = deal(); i = 0; answers = []; draw(); };
  }

  draw();
}

function renderQuiz(cid, nr){
  const c = course(cid), l = lesson(cid, nr), qs = l ? quizOf(cid, l.nr) : [];
  if (!c || !l || !qs.length) return go(c ? `#/course/${cid}` : "#/");
  const next = lesson(cid, l.nr + 1);
  runQuiz({
    eyebrow: `Test · Lektion ${l.nr}`, title: l.title,
    back: { href:`course/${cid}`, label:c.title },
    deal: () => qs, passMark: PASS_LESSON,
    cont: ok => !ok ? { href:`#/lesson/${cid}/${l.nr}`, label:"Zur Lektion" }
              : next ? { href:`#/lesson/${cid}/${next.nr}`, label:"Nächste Lektion" }
              : { href:`#/course/${cid}`, label:"Zum Kurs" },
    onDone: score => {
      const k = key(cid, l.nr), prev = S.quiz[k] || {};
      S.quiz[k] = {
        best: Math.max(prev.best || 0, score),
        passed: (prev.passed || false) || score >= PASS_LESSON,
        attempts: (prev.attempts || 0) + 1,
      };
      save();
    },
  });
}

/* Abschlussprüfung: zufällige Mischung aus allen Lektionsfragen. */
function renderExam(cid){
  const c = course(cid);
  if (!c) return go("#/");
  const pool = Object.values(QUIZ[cid] || {}).flatMap(b => b.questions || []);
  if (!pool.length || !examReady(c)) return go(`#/course/${cid}`);
  runQuiz({
    eyebrow: "Abschlussprüfung", title: c.title,
    back: { href:`course/${cid}`, label:c.title },
    deal: () => shuffle(pool).slice(0, EXAM_SIZE), passMark: PASS_EXAM,
    cont: () => ({ href:`#/course/${cid}`, label:"Zum Kurs" }),
    onDone: score => {
      const prev = S.exam[cid] || {};
      S.exam[cid] = {
        best: Math.max(prev.best || 0, score),
        passed: (prev.passed || false) || score >= PASS_EXAM,
        attempts: (prev.attempts || 0) + 1,
      };
      save();
    },
  });
}

/* ---------- Einstellungen ---------- */
function applyTheme(){
  if (S.theme === "light" || S.theme === "dark") document.documentElement.dataset.theme = S.theme;
  else delete document.documentElement.dataset.theme;
}

function renderSettings(){
  const totalSec = Object.values(S.days).reduce((a, b) => a + b, 0);
  const days = Object.values(S.days).filter(s => s > 60).length;
  const all = DATA.courses.reduce((a, c) => a + c.lessons.length, 0);
  const passed = DATA.courses.reduce((a, c) => a + courseProgress(c).passed, 0);
  const theme = S.theme || "system";
  mount(`
    <a class="back" href="#/">${icon("arrowLeft")} Übersicht</a>
    <h1>Einstellungen</h1>
    <h2>Lernen</h2>
    <section class="card settings">
      <div class="setting">
        <div><p class="t">Tagesziel</p><p class="d">Minuten Video pro Tag. Gezählt wird echte Zeit, auch bei schnellerem Tempo.</p></div>
        <div class="ctl">
          <div class="seg" id="goals" role="group" aria-label="Tagesziel">${GOALS.map(g =>
            `<button type="button" data-goal="${g}" aria-pressed="${S.dailyMinutes === g}">${g}</button>`).join("")}</div>
          <input class="num" id="daily" type="number" min="5" max="240" step="5" value="${S.dailyMinutes}" aria-label="Eigenes Tagesziel in Minuten">
          <span class="unit">min</span>
        </div>
      </div>
      <div class="setting">
        <div><p class="t">Darstellung</p><p class="d">Hell, dunkel oder wie das System.</p></div>
        <div class="ctl"><div class="seg" id="theme" role="group" aria-label="Darstellung">${[["system", "System"], ["light", "Hell"], ["dark", "Dunkel"]].map(([v, t]) =>
          `<button type="button" data-theme-set="${v}" aria-pressed="${theme === v}">${t}</button>`).join("")}</div></div>
      </div>
    </section>

    <h2>Dein Stand</h2>
    <div class="statgrid">
      <div class="card stat"><div class="v">${fmtSpan(totalSec)}</div><div class="l">insgesamt gelernt</div></div>
      <div class="card stat"><div class="v">${days}</div><div class="l">${days === 1 ? "Lerntag" : "Lerntage"}</div></div>
      <div class="card stat"><div class="v">${streakDays()}</div><div class="l">Tage in Folge</div></div>
      <div class="card stat"><div class="v">${passed}<small>/${all}</small></div><div class="l">Tests bestanden</div></div>
    </div>
    <div class="card courses-table">${DATA.courses.map(c => {
      const p = courseProgress(c);
      return `<a class="ctrow" href="#/course/${esc(c.id)}"><span>${esc(c.title)}</span>
        <span>${p.watched}/${p.total} geschaut · ${plural(p.passed, "Test", "Tests")} · ${pct(p.pct)}</span></a>`;
    }).join("")}</div>

    <h2>Fortschritt sichern</h2>
    <p class="note">Alles liegt nur in diesem Browser. Vor einem Rechner- oder Browserwechsel als Datei sichern.</p>
    <div class="actions flush">
      <button type="button" class="btn btn-secondary" id="exp">Als Datei sichern</button>
      <button type="button" class="btn btn-secondary" id="imp">Datei einlesen</button>
      <button type="button" class="btn btn-ghost btn-danger" id="rst">Alles zurücksetzen</button>
    </div>
    <input type="file" id="file" accept="application/json,.json" hidden>`, { narrow:true, title:"Einstellungen" });

  const setGoal = v => { if (v >= 5 && v <= 240){ S.dailyMinutes = Math.round(v); save(); } renderSettings(); };
  document.getElementById("goals").onclick = e => { const b = e.target.closest("[data-goal]"); if (b) setGoal(Number(b.dataset.goal)); };
  document.getElementById("daily").onchange = e => setGoal(Number(e.target.value));
  document.getElementById("theme").onclick = e => {
    const b = e.target.closest("[data-theme-set]");
    if (!b) return;
    S.theme = b.dataset.themeSet; save(); applyTheme(); renderSettings();
  };
  document.getElementById("exp").onclick = () => {
    const b = new Blob([JSON.stringify(S, null, 2)], { type:"application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b);
    a.download = `academy-fortschritt-${todayKey()}.json`;
    a.click(); URL.revokeObjectURL(a.href);
  };
  document.getElementById("imp").onclick = () => document.getElementById("file").click();
  document.getElementById("file").onchange = async e => {
    const f = e.target.files[0];
    if (!f) return;
    try{
      S = Object.assign(blank(), JSON.parse(await f.text()));
      save(); applyTheme(); renderSettings();
    }catch{ alert("Datei konnte nicht gelesen werden."); }
  };
  document.getElementById("rst").onclick = () => {
    if (confirm("Wirklich den gesamten Fortschritt löschen?")){ S = blank(); save(); applyTheme(); go("#/"); }
  };
}

/* ---------- Start ---------- */
(async function init(){
  applyTheme();
  try{
    const r = await fetch("data/academy.json", { cache:"no-store" });
    if (!r.ok) throw new Error(r.status);
    const data = await r.json();
    await Promise.all(data.courses.map(async c => {
      try{
        const q = await fetch(`data/quiz/${c.id}.json`, { cache:"no-store" });
        QUIZ[c.id] = q.ok ? await q.json() : {};
      }catch{ QUIZ[c.id] = {}; }
    }));
    DATA = data;          // erst jetzt - route() rechnet damit, dass auch die Fragen schon da sind
  }catch{
    view().innerHTML = `<section class="card empty">
      <p><b>Die Kursdaten konnten nicht geladen werden.</b></p>
      <p>Die Academy muss über einen lokalen Server laufen, nicht per Doppelklick.
      Im Terminal: <span class="mono">~/Projekte/academy/start.sh</span></p></section>`;
    return;
  }
  route();
})();
