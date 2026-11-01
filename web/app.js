import { BOSSES, BOSS_ALIASES, evaluate } from "./scoring.mjs";

const $ = (selector) => document.querySelector(selector);
const form = $("#run-form");
let current;
for (const [id, name] of Object.entries(BOSSES)) {
  const option = document.createElement('option');
  option.value = id; option.textContent = name;
  form.elements.namedItem('boss').append(option);
}
form.elements.namedItem('boss').value = 'isshin';
let rankToken = 0;
const rankCache = new Map();

function read() {
  const data = new FormData(form);
  return {
    boss: data.get("boss"),
    heals: Number(data.get("heals")),
    revives: Number(data.get("revives")),
    ...Object.fromEntries(
      ["charmless", "bell", "prosthetic", "art", "cleared"].map((key) => [
        key,
        data.has(key),
      ]),
    ),
  };
}

function tags(run) {
  return [
    run.charmless ? "Charmless" : "Charm retained",
    run.bell ? "Demon Bell active" : "Demon Bell inactive",
  ];
}

function toolsLine(run) {
  const used = (flag) => (flag ? "used" : "not used");
  return `Prosthetics: ${used(run.prosthetic)} · Combat Arts: ${used(run.art)}`;
}

function render(run, state) {
  ++rankToken;
  const result = evaluate(run);
  current = { run, result };
  $("#result-boss").textContent = result.boss;
  $("#grade").textContent = result.grade;
  $("#grade-title").textContent = result.title;
  $("#badges").replaceChildren(
    ...tags(run).map((text) => {
      const badge = document.createElement("span");
      badge.textContent = text;
      return badge;
    }),
  );
  for (const [id, value, suffix] of [
    ["heals-out", run.heals, "uses"],
    ["revives-out", run.revives, "times"],
    ["score-out", result.score, "/100"],
  ]) {
    const element = $("#" + id);
    element.textContent = value;
    const small = document.createElement("small");
    small.textContent = suffix;
    element.append(small);
  }
  const minimum = result.score === 0 ? " (minimum 0)" : "";
  $("#reason").textContent =
    `100 base points − ${run.heals} healing uses × 5 − ` +
    `${run.revives} resurrections × 15 = ${result.score} points${minimum}. ` +
    `Grade ${result.grade}.`;
  $("#tools-out").textContent = toolsLine(run) + " · Boss rematch";
  $("#result-state").textContent = state;
  $("#share-status").textContent = "";
  $("#rank-out").textContent = "";
  current.rank = "";
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    const run = read();
    render(run, "YOUR VICTORY RECORD");
    showRank(run);
    $("#error").textContent = "";
    if (innerWidth < 801)
      $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    $("#error").textContent = error.message;
  }
});
// Ask the backend where this record ranks. Failure never blocks the card itself.
function rankText(result, run) {
  const p = result.percentile;
  if (p.status === "ok") {
    return (
      `Top ${p.top_percent}% of ${p.n} submitted records ` +
      "for this boss and challenge setting · self-reported"
    );
  }
  return (
    `Rankings unlock at ${p.min_n} records ` +
    `for this boss and setting (${p.n} so far).`
  );
}

async function showRank(run) {
  const token = ++rankToken;
  const key = JSON.stringify(run);
  const out = $("#rank-out");
  const set = (text) => {
    if (token === rankToken) {
      out.textContent = text;
      current.rank = text;
    }
  };
  if (rankCache.has(key)) return set(rankCache.get(key));
  set("Checking your rank…");
  try {
    const response = await fetch("/api/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: key,
    });
    if (response.status === 429)
      return set("Too many submissions. Try again in a while.");
    if (!response.ok) return set("Community rankings are temporarily unavailable.");
    const text = rankText(await response.json(), run);
    rankCache.set(key, text);
    set(text);
  } catch {
    set("Community rankings are temporarily unavailable."); // local card still works
  }
}

form.addEventListener("input", () => {
  $("#result-state").textContent = "CHANGES PENDING · REVEAL AGAIN";
});

$("#share").addEventListener("click", async () => {
  const url = new URL(location.href);
  url.hash = new URLSearchParams({
    v: "1",
    ...Object.fromEntries(
      Object.entries(current.run).map(([key, value]) => [key, String(value)]),
    ),
  }).toString();
  try {
    await navigator.clipboard.writeText(url.href);
    $("#share-status").textContent =
      "Record link copied. Anyone with access to the site can open this result.";
  } catch {
    $("#share-status").replaceChildren("Copy this record link: ");
    const input = document.createElement("input");
    input.value = url.href;
    input.readOnly = true;
    input.style.width = "100%";
    $("#share-status").append(input);
    input.select();
  }
});

// Draw the same moon-and-katana motif without relying on external images.
function drawMark(context, x, y) {
  context.save();
  context.translate(x, y);
  context.fillStyle = "#c9d7cb";
  context.beginPath();
  context.arc(0, 0, 40, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = "#9db2a9";
  context.beginPath();
  context.arc(12, -12, 11, 0, Math.PI * 2);
  context.arc(-13, 15, 8, 0, Math.PI * 2);
  context.fill();
  context.rotate(Math.PI / 5);
  context.fillStyle = "#132b33";
  context.fillRect(-5, -44, 10, 34);
  context.strokeStyle = "#bfd0c3";
  context.lineWidth = 2;
  for (let i = -40; i < -12; i += 7) {
    context.beginPath();
    context.moveTo(-4, i);
    context.lineTo(4, i + 6);
    context.stroke();
  }
  context.fillStyle = "#68867e";
  context.fillRect(-16, -10, 32, 5);
  context.fillStyle = "#edf3e9";
  context.beginPath();
  context.moveTo(-4, -5);
  context.lineTo(6, -5);
  context.quadraticCurveTo(12, 41, -10, 59);
  context.quadraticCurveTo(0, 29, -4, -5);
  context.fill();
  context.restore();
}

$("#download").addEventListener("click", async () => {
  try {
    await document.fonts.ready;
    const { run, result } = current;
    const canvas = document.createElement("canvas");
    canvas.width = 1200;
    canvas.height = 800;
    const context = canvas.getContext("2d");
    const background = context.createLinearGradient(0, 0, 1200, 800);
    background.addColorStop(0, "#29434b");
    background.addColorStop(1, "#10232b");
    context.fillStyle = background;
    context.fillRect(0, 0, 1200, 800);
    context.strokeStyle = "#58777a";
    context.lineWidth = 2;
    context.strokeRect(32, 32, 1136, 736);
    drawMark(context, 1080, 105);
    context.fillStyle = "#b3cbc5";
    context.font = "20px Arial";
    context.fillText("SEKIRO / REFLECTION OF STRENGTH", 70, 95);
    context.fillStyle = "#e4ece1";
    context.font = "48px Georgia";
    context.fillText(result.boss, 70, 180, 1040);
    context.fillStyle = "#d7e4d9";
    context.font = "230px Georgia";
    context.fillText(result.grade, 65, 420);
    context.fillStyle = "#e4ece1";
    context.font = "36px Georgia";
    context.fillText(result.title, 300, 300);
    context.font = "22px Arial";
    context.fillText("Performance grade · Prototype rules v0.1", 300, 350);
    context.fillText(tags(run).join("  /  "), 70, 485);
    context.fillText(
      `Healing: ${run.heals} uses     ` +
        `Resurrections: ${run.revives}     ` +
        `Score: ${result.score}/100`,
      70,
      540,
    );
    context.font = "19px Arial";
    context.fillText(toolsLine(run), 70, 585);
    if (current.rank && current.rank.startsWith("Top ")) {
      context.fillStyle = "#d7e4d9";
      context.font = "20px Arial";
      context.fillText(current.rank.replace(" · self-reported", ""), 70, 615, 1040);
    }
    context.fillStyle = "#b3cbc5";
    context.font = "18px Arial";
    context.fillText(
      "Self-reported · Unverified / Provisional rules, not a global player ranking",
      70,
      645,
    );
    context.fillStyle = "#e4ece1";
    context.font = "bold 28px Arial";
    context.fillText("skillissue.gg", 70, 720);
    canvas.toBlob((blob) => {
      if (!blob) {
        $("#share-status").textContent = "Could not create the card image.";
        return;
      }
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `skillissue-${run.boss}-${result.grade}.png`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      $("#share-status").textContent = "Your card image is ready. Check your downloads.";
    }, "image/png");
  } catch {
    $("#share-status").textContent =
      "Could not create the image. Try copying the record link instead.";
  }
});

render(read(), "EXAMPLE RECORD");
if (location.hash.includes("v=")) {
  try {
    const params = new URLSearchParams(location.hash.slice(1));
    if (params.get("v") !== "1") throw Error();
    const run = {
      boss: BOSS_ALIASES[params.get("boss")] || params.get("boss"),
      heals: Number(params.get("heals")),
      revives: Number(params.get("revives")),
    };
    for (const key of ["heals", "revives"])
      if (!params.has(key) || params.get(key) === "") throw Error();
    for (const key of ["charmless", "bell", "prosthetic", "art", "cleared"]) {
      if (!["true", "false"].includes(params.get(key))) throw Error();
      run[key] = params.get(key) === "true";
    }
    evaluate(run);
    for (const [key, value] of Object.entries(run)) {
      const element = form.elements.namedItem(key);
      if (typeof value === "boolean") element.checked = value;
      else element.value = value;
    }
    render(run, "SHARED RECORD · UNVERIFIED");
  } catch {
    $("#error").textContent =
      "This record link is invalid. Enter a new run to get started.";
  }
}
