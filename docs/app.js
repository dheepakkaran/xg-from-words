/* Figures are drawn from data.json, which src/site_data.py generates from the
   results — so a rerun that changes a number changes the page, and the two
   cannot quietly disagree. */

const SVG = "http://www.w3.org/2000/svg";
const el = (n, a = {}) => {
  const e = document.createElementNS(SVG, n);
  for (const [k, v] of Object.entries(a)) e.setAttribute(k, v);
  return e;
};
const fmt = {
  auc: v => v.toFixed(3),
  pct: v => (v * 100).toFixed(0) + "%",
  int: v => v.toLocaleString("en-GB"),
  xg: v => v.toFixed(2),
};

/* ---------- one bar chart, reused ----------
   Horizontal bars: the labels are words, and words want to be read
   left-to-right rather than rotated under an axis.

   Bars start at their real zero. For a score where 0.50 is a coin toss, that
   zero is 0.50 -- so a bar's length is skill above chance, and the model with
   none draws nothing. Starting the axis at 0.48 to "fit" the data would make
   a coin toss look like it had a fifth of the ceiling's skill. */
function barChart(svg, rows, opts = {}) {
  const {
    format = fmt.auc, min = 0, max = null, labelWidth = 172,
    barH = 26, gap = 12, refValue = null, refLabel = "",
  } = opts;
  const top = 8, right = 56, bottom = refValue == null ? 8 : 26;
  const hi = max ?? Math.max(...rows.map(r => r.value)) * 1.06;
  const h = top + rows.length * (barH + gap) - gap + bottom;
  const W = 760;
  const plotW = W - labelWidth - right;
  const x = v => labelWidth + ((v - min) / (hi - min)) * plotW;

  svg.setAttribute("viewBox", `0 0 ${W} ${h}`);
  svg.replaceChildren();

  if (refValue != null) {
    const rx = x(refValue);
    svg.append(el("line", { x1: rx, x2: rx, y1: top - 2, y2: h - bottom + 4,
                            class: "ref" }));
    const t = el("text", { x: rx, y: h - 6, "text-anchor": "middle",
                           "font-size": 12 });
    t.textContent = refLabel;
    svg.append(t);
  }

  rows.forEach((r, i) => {
    const y = top + i * (barH + gap);
    const g = el("g", { class: "row" });
    const tip = g.appendChild(el("title"));
    tip.textContent = `${r.label}: ${format(r.value)}`;

    const lab = el("text", { x: labelWidth - 12, y: y + barH * 0.72,
                             "text-anchor": "end" });
    lab.textContent = r.label;
    if (r.emphasis) lab.setAttribute("font-weight", "600");
    g.append(lab);

    /* 2px surface gap under the fill keeps adjacent bars from touching */
    g.append(el("rect", { x: labelWidth, y, width: plotW, height: barH,
                          rx: 4, class: "track" }));
    g.append(el("rect", {
      x: labelWidth, y, width: Math.max(4, x(r.value) - labelWidth),
      height: barH, rx: 4, class: "bar",
      fill: r.color || "var(--series-1)",
      "fill-opacity": r.muted ? 0.45 : 1,
    }));

    const v = el("text", { x: Math.max(x(r.value), labelWidth) + 10,
                           y: y + barH * 0.72, class: "value" });
    v.textContent = format(r.value);
    g.append(v);
    svg.append(g);
  });
}

/* Every chart ships a table, so nothing is carried by colour alone. */
function table(host, head, rows) {
  const t = document.createElement("table");
  const th = t.createTHead().insertRow();
  head.forEach(h => { const c = document.createElement("th");
                      c.textContent = h; th.append(c); });
  const tb = t.createTBody();
  rows.forEach(r => { const tr = tb.insertRow();
                      r.forEach(v => tr.insertCell().textContent = v); });
  host.replaceChildren(t);
}

function legend(host, items) {
  host.replaceChildren(...items.map(([label, color]) => {
    const b = document.createElement("b");
    const i = document.createElement("i");
    i.style.background = color;
    b.append(i, document.createTextNode(label));
    return b;
  }));
}

/* ---------- the match timeline ---------- */
function replayChart(svg, replay) {
  const f = replay.frames, W = 760, H = 300;
  const pad = { t: 16, r: 130, b: 40, l: 44 };
  const hi = Math.max(...f.flatMap(d => [d.home_xg, d.away_xg])) * 1.15 || 1;
  const x = m => pad.l + (m / 95) * (W - pad.l - pad.r);
  const y = v => H - pad.b - (v / hi) * (H - pad.t - pad.b);

  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.replaceChildren();

  for (let v = 0; v <= hi; v += 0.5) {
    svg.append(el("line", { x1: pad.l, x2: W - pad.r, y1: y(v), y2: y(v),
                            class: "rule" }));
    const t = el("text", { x: pad.l - 10, y: y(v) + 4, "text-anchor": "end",
                           "font-size": 12 });
    t.textContent = v.toFixed(1);
    svg.append(t);
  }
  [15, 45, 75].forEach(m => {
    const t = el("text", { x: x(m), y: H - 14, "text-anchor": "middle",
                           "font-size": 12 });
    t.textContent = m + "'";
    svg.append(t);
  });

  const line = (key, color, name) => {
    const d = f.map((p, i) => `${i ? "L" : "M"}${x(p.minute)} ${y(p[key])}`).join(" ");
    svg.append(el("path", { d, fill: "none", stroke: color, "stroke-width": 2,
                            "stroke-linejoin": "round", "stroke-linecap": "round" }));
    f.forEach(p => {
      const c = el("circle", { cx: x(p.minute), cy: y(p[key]), r: 4.5,
                               fill: color, stroke: "var(--surface-1)",
                               "stroke-width": 2 });
      c.appendChild(el("title")).textContent =
        `${name}, ${p.minute}' — ${fmt.xg(p[key])} chances created`;
      svg.append(c);
    });
    const last = f[f.length - 1];
    const t = el("text", { x: x(last.minute) + 12, y: y(last[key]) + 4,
                           class: "value", "font-size": 13 });
    t.textContent = `${fmt.xg(last[key])} · ${name.split(" ")[0]}`;
    svg.append(t);
  };
  line("home_xg", "var(--series-1)", replay.home);
  line("away_xg", "var(--series-2)", replay.away);

  /* Goals, marked where they landed. The tick down to the line is what ties a
     marker to a side -- colour alone would leave it to the legend. */
  f.forEach((p, i) => {
    const prev = f[i - 1] || { home_goals: 0, away_goals: 0 };
    [["home", "series-1"], ["away", "series-2"]].forEach(([side, col]) => {
      const n = p[side + "_goals"] - prev[side + "_goals"];
      if (n <= 0) return;
      const c = `var(--${col})`;
      svg.append(el("line", {
        x1: x(p.minute), x2: x(p.minute), y1: pad.t + 12,
        y2: y(p[side + "_xg"]) - 8, stroke: c, "stroke-width": 1.5,
        "stroke-dasharray": "2 3", "stroke-opacity": 0.7 }));
      const t = el("text", { x: x(p.minute), y: pad.t + 6,
                             "text-anchor": "middle", class: "value",
                             "font-size": 12, fill: c });
      t.textContent = n > 1 ? `${n} goals` : "goal";
      svg.append(t);
    });
  });
}

/* ---------- wire it up ---------- */
const data = await fetch("data.json").then(r => r.json());

/* Every number on the page comes from data.json. A literal typed into the
   markup goes stale the moment a rerun changes it -- the headline sat at 90.1%
   for two commits after the result moved, because it was hardcoded. */
const pick = path => path.split(".").reduce((o, k) => o?.[k], data);

/* data-format says how to render, rather than the code guessing from the
   value -- 1.0 is a whole number and an AUC of 1.0000 at the same time. */
const FORMATS = {
  int: fmt.int, auc: v => v.toFixed(4), score: v => v.toFixed(2),
  pct: fmt.pct, goals: v => v.toFixed(3),
};

document.querySelectorAll("[data-fill]").forEach(node => {
  const v = pick(node.dataset.fill);
  if (v == null) return;
  const f = FORMATS[node.dataset.format] || (typeof v === "number" ? fmt.int : String);
  node.textContent = f(v);
});

barChart(document.getElementById("chart-momentum"),
  data.momentum.map(d => ({
    label: d.label, value: d.auc,
    color: d.ceiling ? "var(--ink-3)" : "var(--series-1)",
    muted: d.ceiling, emphasis: d.ceiling })),
  { min: 0.5, max: 0.63 });
legend(document.getElementById("legend-momentum"),
  [["a real model", "var(--series-1)"], ["shown the future", "var(--ink-3)"]]);
table(document.getElementById("table-momentum"), ["Model", "Score"],
  data.momentum.map(d => [d.label, fmt.auc(d.auc)]));

barChart(document.getElementById("chart-chances"),
  data.chances.map(d => ({ label: d.label, value: d.rate })),
  { format: fmt.pct, labelWidth: 210 });
table(document.getElementById("table-chances"), ["Kind of chance", "Scored", "Shots"],
  data.chances.map(d => [d.label, fmt.pct(d.rate), fmt.int(d.n)]));

const v = data.validation;
barChart(document.getElementById("chart-validation"), [
  { label: "From the words", value: v.ours, color: "var(--series-1)" },
  { label: "From cameras", value: v.theirs, color: "var(--series-2)" },
], { min: 0.5, max: 0.83, labelWidth: 180 });
legend(document.getElementById("legend-validation"),
  [["one English sentence", "var(--series-1)"],
   ["coordinates and player positions", "var(--series-2)"]]);
table(document.getElementById("table-validation"),
  ["Model", "Score", "Average rating given"],
  [["From the words", fmt.auc(v.ours), v.mean_ours.toFixed(3)],
   ["From cameras", fmt.auc(v.theirs), v.mean_theirs.toFixed(3)]]);

barChart(document.getElementById("chart-leagues"),
  data.leagues.map(d => ({
    label: d.name, value: d.auc,
    color: d.home ? "var(--series-2)" : "var(--series-1)",
    emphasis: d.home })),
  { min: 0.5, max: 0.8, labelWidth: 180 });
table(document.getElementById("table-leagues"), ["Competition", "Score", "Shots"],
  data.leagues.map(d => [d.name + (d.home ? " (trained here)" : ""),
                         fmt.auc(d.auc), fmt.int(d.shots)]));

const openers = document.getElementById("openers");
openers.replaceChildren(...data.leak.openers.map(o => {
  const d = document.createElement("div");
  d.className = "opener";
  d.dataset.goal = o.rate > 0.5 ? "1" : "0";
  const p = document.createElement("span");
  p.textContent = `"${o.phrase}…"`;
  const b = document.createElement("b");
  b.textContent = o.rate > 0.5 ? "always a goal" : "never a goal";
  d.append(p, b);
  return d;
}));

if (data.replay) {
  const r = data.replay;
  replayChart(document.getElementById("chart-replay"), r);
  legend(document.getElementById("legend-replay"),
    [[r.home, "var(--series-1)"], [r.away, "var(--series-2)"]]);
  const last = r.frames[r.frames.length - 1];
  document.getElementById("replay-caption").textContent =
    `${r.home} ${last.home_goals}–${last.away_goals} ${r.away}. ` +
    `The lines are chances created; the score is written above them.`;
  table(document.getElementById("table-replay"),
    ["Minute", "Score", r.home, r.away],
    r.frames.map(f => [f.minute + "'",
                       `${f.home_goals}–${f.away_goals}`,
                       fmt.xg(f.home_xg), fmt.xg(f.away_xg)]));
}

/* the headline number counts up, once, and only if motion is welcome */
const hero = document.querySelector("[data-count]");
if (hero) {
  const target = Number(pick(hero.dataset.count));
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const show = v => hero.innerHTML =
    `${(v * 100).toFixed(v === target ? 1 : 0)}<sup>%</sup>`;
  if (still) show(target);
  else new IntersectionObserver((entries, obs) => {
    if (!entries[0].isIntersecting) return;
    obs.disconnect();
    const t0 = performance.now(), ms = 1100;
    const tick = now => {
      const k = Math.min(1, (now - t0) / ms);
      show(target * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, { threshold: 0.6 }).observe(hero);
}

/* progress bar, sticky header, and the fallback reveal for browsers without
   scroll-driven animations */
const bar = document.querySelector("progress.scrollbar");
const topbar = document.querySelector(".topbar");
addEventListener("scroll", () => {
  const max = document.body.scrollHeight - innerHeight;
  bar.value = max > 0 ? scrollY / max : 0;
  topbar.classList.toggle("scrolled", scrollY > 8);
}, { passive: true });

if (!CSS.supports("animation-timeline: view()")) {
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add("seen"); io.unobserve(e.target); }
  }), { threshold: 0.15 });
  document.querySelectorAll("section").forEach(s => io.observe(s));
}

const themeBtn = document.getElementById("theme");
themeBtn.addEventListener("click", () => {
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  const now = document.documentElement.dataset.theme || (dark ? "dark" : "light");
  document.documentElement.dataset.theme = now === "dark" ? "light" : "dark";
});


/* ---------- ours against the professional model ---------- */

const tiles = (host, items) => host.replaceChildren(...items.map(([n, label, tone]) => {
  const d = document.createElement("div");
  if (tone) d.dataset.tone = tone;
  const b = document.createElement("b"); b.textContent = n;
  const s = document.createElement("span"); s.textContent = label;
  d.append(b, s);
  return d;
}));

const h2h = data.head_to_head;
if (h2h) {
  /* Error in goals, and the real zero is zero -- a model that was never wrong
     draws nothing. Lower is better, which the caption says out loud. */
  barChart(document.getElementById("chart-h2h"), [
    { label: "Ours, from words", value: h2h.ours.mean_error,
      color: "var(--series-1)" },
    { label: "StatsBomb, cameras", value: h2h.theirs.mean_error,
      color: "var(--series-2)" },
  ], { format: v => `${v.toFixed(3)} goals`, min: 0,
       max: Math.max(h2h.ours.mean_error, h2h.theirs.mean_error) * 1.25,
       labelWidth: 190 });
  legend(document.getElementById("legend-h2h"),
    [["one English sentence per shot", "var(--series-1)"],
     ["cameras tracking every player", "var(--series-2)"]]);
  table(document.getElementById("table-h2h"),
    ["Model", "Average error (goals)", "Points", "Closer in"],
    [["Ours, from words", h2h.ours.mean_error.toFixed(3),
      h2h.ours.points, `${h2h.split.ours_closer} innings`],
     ["StatsBomb, cameras", h2h.theirs.mean_error.toFixed(3),
      h2h.theirs.points, `${h2h.split.theirs_closer} innings`],
     ["Level", "—", "—", `${h2h.split.level} innings`]]);

  const gap = h2h.ours.mean_error - h2h.theirs.mean_error;
  document.getElementById("h2h-verdict").innerHTML =
    `The commercial model is better, by <strong>${gap.toFixed(3)} of a goal` +
    `</strong> per side per match. That is the whole difference between a` +
    ` sentence of English and a stadium full of cameras.`;

  tiles(document.getElementById("h2h-score"), [
    [h2h.ours.points, "points, ours", "ours"],
    [h2h.theirs.points, "points, StatsBomb", "theirs"],
    [`${(h2h.theirs.points / h2h.innings * 100).toFixed(0)}%`,
     "of innings they were closer"],
  ]);

  const t = document.getElementById("table-h2h-matches");
  t.innerHTML =
    "<thead><tr><th>Match</th><th>Side</th><th>Goals</th>" +
    "<th>Ours</th><th>StatsBomb</th><th>Point</th></tr></thead>";
  const tb = t.appendChild(document.createElement("tbody"));
  h2h.examples.slice(0, 12).forEach(e => {
    const tr = tb.insertRow();
    [`${e.home} v ${e.away}`, e.side, e.goals, e.ours.toFixed(2),
     e.theirs.toFixed(2),
     e.point === 1 ? "ours" : e.point === 0 ? "StatsBomb" : "shared"]
      .forEach(v => tr.insertCell().textContent = v);
  });
}

const sc = data.scorecard;
if (sc) {
  const decisive = sc.called - sc.drawn;
  tiles(document.getElementById("scorecard"), [
    [`${(sc.hit_rate * 100).toFixed(0)}%`, "of decisive matches called right", "ours"],
    [sc.right, "right"],
    [sc.wrong, "wrong"],
    [sc.drawn, "ended level"],
  ]);
  document.getElementById("scorecard-note").textContent =
    `Of ${sc.matches} matches last season, the model put one side clearly ` +
    `ahead in ${sc.called}. ${sc.drawn} of those finished level, which no ` +
    `chance-quality reading can be blamed for. Of the ${decisive} that had a ` +
    `winner, it called ${sc.right}.`;
}

/* ---------- what is happening right now ----------
   live.json is written by the matchday job to the live-data branch, so main's
   history stays for changes to the project rather than a feed. When nothing is
   in progress the panel falls back to the fixture list, which a daily job
   refreshes from ESPN. */

const LIVE_URL =
  "https://raw.githubusercontent.com/dheepakkaran/xg-from-words/live-data/docs/live.json";

const verdict = form =>
  form > 0.7 ? "finishing above what the chances deserved"
  : form < -0.7 ? "wasteful — created more than they have scored"
  : "scoring about what the chances deserved";

const when = iso => {
  const t = new Date(iso), h = (t - Date.now()) / 3.6e6;
  const day = t.toLocaleDateString("en-GB",
    { weekday: "long", day: "numeric", month: "long" });
  /* The viewer's own clock, labelled -- an unlabelled 15:00 next to a UTC
     kickoff time in the repository is how people miss matches. */
  const time = t.toLocaleTimeString("en-GB",
    { hour: "2-digit", minute: "2-digit", timeZoneName: "short" });
  const away = h < 0 ? "under way"
    : h < 1 ? `in ${Math.round(h * 60)} minutes`
    : h < 24 ? `in ${Math.round(h)} hours`
    : `in ${Math.round(h / 24)} days`;
  return { day, time, away };
};

async function renderNow() {
  const head = document.getElementById("now-head");
  const body = document.getElementById("now-body");
  const note = document.getElementById("now-note");

  let live = null;
  try {
    live = await fetch(`${LIVE_URL}?t=${Date.now()}`, { cache: "no-store" })
      .then(r => r.ok ? r.json() : null);
  } catch { /* the branch does not exist until the first matchday */ }

  if (live?.matches?.length) {
    head.textContent = live.matches.length === 1
      ? "One match is under way." : `${live.matches.length} matches are under way.`;
    body.replaceChildren(...live.matches.map(m => {
      const card = document.createElement("div");
      card.className = "now-match";
      const lead = m.sides.reduce((a, b) => (b.xg > a.xg ? b : a), m.sides[0]);
      const h = document.createElement("header");
      h.innerHTML = `<span>${m.clock ?? ""}</span><span>chances created</span>`;
      card.append(h);
      m.sides.forEach(s => {
        const row = document.createElement("div");
        row.className = "now-side";
        row.dataset.lead = s.team === lead.team ? "1" : "0";
        row.innerHTML =
          `<span class="team">${s.team}</span>` +
          `<span class="goals">${s.goals} ${s.goals === 1 ? "goal" : "goals"}</span>` +
          `<span class="xg">${fmt.xg(s.xg)}</span>`;
        card.append(row);
      });
      const v = document.createElement("div");
      v.className = "now-verdict";
      v.textContent = `${lead.team} have created the most. ` +
        `${lead.team} are ${verdict(lead.form)}.`;
      card.append(v);
      return card;
    }));
    const lag = live.matches.map(m => m.commentary_lag_seconds)
      .filter(x => x != null);
    note.textContent = lag.length
      ? `Read from commentary published ${Math.round(Math.min(...lag))} seconds ago.`
      : "Chances created, not chances coming — this does not predict the next goal.";
    return;
  }

  const fx = await fetch("fixtures.json").then(r => r.json()).catch(() => null);
  const next = fx?.next?.find(f => !f.completed);
  if (!next) {
    head.textContent = "No Premier League match is in progress.";
    return;
  }
  const w = when(next.kickoff);
  head.textContent = "No match is in progress.";
  const card = document.createElement("div");
  card.className = "now-match now-next";
  card.innerHTML =
    `<b>${next.home} v ${next.away}</b>` +
    `<span>${w.day}, ${w.time} — ${w.away}</span>`;
  body.replaceChildren(card);
  note.textContent = `${fx.upcoming} fixtures still to play this season. ` +
    `A job wakes up at kickoff and reads the match as the commentary arrives.`;
}

renderNow();
