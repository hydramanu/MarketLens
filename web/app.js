"use strict";
const $ = (id) => document.getElementById(id);
let current = null,
  catalog = [],
  requestId = 0,
  pollTimer = null,
  quoteBusy = false;
const money = (n) =>
  n == null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
      }).format(n);
const pct = (n) => (n == null ? "—" : `${n.toFixed(2)}%`);
function message(text, error = false) {
  $("notice").textContent = text;
  $("notice").className = error ? "error" : "";
}
async function api(path, body) {
  const r = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const data = await r.json();
  if (!r.ok) throw Error(data.error || "Request failed");
  return data;
}
function element(tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
async function loadCatalog(select) {
  catalog = await api("/api/catalog");
  $("dataset").replaceChildren(
    ...catalog.map((d) => {
      const o = element("option", d.name);
      o.value = d.id;
      return o;
    }),
  );
  if (select && catalog.some((d) => d.id === select))
    $("dataset").value = select;
  const d = catalog.find((d) => d.id === $("dataset").value);
  if (d) {
    $("cutoff").min = d.first;
    $("cutoff").max = d.last;
    $("cutoff").value = d.last;
  }
  await load();
}
async function load() {
  const id = ++requestId;
  try {
    message("Calculating from source data…");
    if (!$("dataset").value)
      throw Error("Import a CSV or fetch a public dataset to begin.");
    const params = new URLSearchParams({
      dataset: $("dataset").value,
      window: $("window").value,
      cutoff: $("cutoff").value,
    });
    const data = await api("/api/analysis?" + params);
    if (id !== requestId) return;
    current = data;
    render();
    message(
      `Analysis ready · ${data.receipt.rows} observations · as of ${data.receipt.end}`,
    );
  } catch (e) {
    if (id !== requestId) return;
    current = null;
    message(e.message, true);
    $("source").textContent =
      "Analysis unavailable — change the date or load another dataset";
    for (const key of ["close", "period_return", "volatility", "max_drawdown"])
      $(key).textContent = "—";
    for (const key of [
      "priceChart",
      "drawdownChart",
      "volChart",
      "findings",
      "sqlRows",
      "alerts",
      "qualityRows",
    ])
      $(key).replaceChildren();
    $("range").textContent = "";
    $("hash").textContent = "";
    $("volume_ratio").textContent = "—";
    $("volumeChange").textContent = "";
    $("tailRisk").textContent = "";
  }
}
const ns = "http://www.w3.org/2000/svg";
function svgEl(name, attrs) {
  const e = document.createElementNS(ns, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}
function chart(id, key, color, secondary) {
  const pts = current.points;
  const values = pts
    .flatMap((p) => [p[key], secondary ? p[secondary] : null])
    .filter((v) => v !== null);
  if (!values.length) {
    $(id).textContent = "Not enough observations";
    return;
  }
  const w = 720,
    h = 240,
    pad = 45;
  let min = Math.min(...values),
    max = Math.max(...values);
  if (max === min) {
    max += 1;
    min -= 1;
  }
  const y = (v) => h - pad - ((v - min) / (max - min)) * (h - pad - 14),
    x = (i) => pad + (i / (pts.length - 1)) * (w - pad - 12);
  const svg = svgEl("svg", {
    viewBox: `0 0 ${w} ${h}`,
    role: "img",
    "aria-label": `${key} from ${current.receipt.start} to ${current.receipt.end}`,
  });
  for (let i = 0; i < 4; i++) {
    const v = min + ((max - min) * i) / 3,
      yy = y(v);
    svg.append(
      svgEl("line", {
        x1: pad,
        x2: w,
        y1: yy,
        y2: yy,
        stroke: "#eaf0ed",
        "stroke-dasharray": "3 4",
      }),
    );
    const t = svgEl("text", { x: 0, y: yy + 4 });
    t.textContent = v.toFixed(1);
    svg.append(t);
  }
  function path(k, c, dash) {
    let d = "",
      active = false;
    pts.forEach((p, i) => {
      if (p[k] === null) {
        active = false;
        return;
      }
      d += `${active ? "L" : "M"}${x(i).toFixed(2)},${y(p[k]).toFixed(2)} `;
      active = true;
    });
    svg.append(
      svgEl("path", {
        d,
        fill: "none",
        stroke: c,
        "stroke-width": 2.2,
        ...(dash ? { "stroke-dasharray": "5 4" } : {}),
      }),
    );
  }
  if (secondary) path(secondary, "#a7bab2", true);
  path(key, color);
  pts.forEach((p, i) => {
    if (p[key] === null) return;
    const c = svgEl("circle", {
      cx: x(i),
      cy: y(p[key]),
      r: 5,
      fill: color,
      tabindex: i % Math.max(1, Math.floor(pts.length / 20)) === 0 ? "0" : "-1",
      "aria-label": `${p.date}: ${p[key].toFixed(2)}`,
    });
    const title = svgEl("title", {});
    title.textContent = `${p.date} · ${key}: ${p[key].toFixed(2)}`;
    c.append(title);
    svg.append(c);
  });
  $(id).replaceChildren(svg);
}
function render() {
  const d = current,
    m = d.metrics;
  $("source").textContent = `${d.meta.name} / ${d.meta.mode}`;
  $("range").textContent = `${d.receipt.start} → ${d.receipt.end}`;
  $("close").textContent = money(m.close);
  for (const k of ["period_return", "volatility", "max_drawdown"])
    $(k).textContent = pct(m[k]);
  $("period_return").className = m.period_return >= 0 ? "positive" : "negative";
  $("max_drawdown").className = "negative";
  $("volume_ratio").textContent =
    m.volume_ratio == null ? "—" : m.volume_ratio.toFixed(2) + "×";
  $("volumeChange").textContent =
    `${pct(m.volume_change)} vs previous observation`;
  $("chartStart").textContent = d.receipt.start;
  $("chartEnd").textContent = d.receipt.end;
  chart("priceChart", "close", "#23836c", "ma20");
  chart("drawdownChart", "drawdown", "#bd7161");
  chart("volChart", "volatility", "#698da7");
  $("alerts").replaceChildren(
    ...(d.alerts.length
      ? d.alerts
      : ["No configured threshold crossed. This does not imply low risk."]
    ).map((a) => element("div", a, "alert")),
  );
  $("findings").replaceChildren(
    ...d.observations.map((s, i) => {
      const e = element("article", undefined, "finding");
      e.append(element("span", "0" + (i + 1)), element("p", s));
      return e;
    }),
  );
  const q = d.quality;
  const entries = [
    ["Input rows", q.input_rows],
    ["Invalid rows rejected", q.invalid_rows],
    ["Duplicate dates removed", q.duplicate_rows],
    ["Accepted rows", q.accepted_rows],
    ["Rows retained", q.retained_pct + "%"],
    ["Long date gaps (window)", q.gap_count],
    ["Last observation age", q.age_days + " calendar days"],
  ];
  $("qualityRows").replaceChildren(
    ...entries.map(([k, v]) => {
      const row = element("div");
      row.append(element("dt", k), element("dd", String(v)));
      return row;
    }),
  );
  $("hash").textContent = `SHA-256 · ${d.receipt.sha256}`;
  $("tailRisk").textContent =
    `Historical 95% loss threshold: ${pct(m.var95)}. Tail mean loss: ${pct(m.expected_shortfall)}. Estimated from ${d.receipt.rows - 1} returns; not a loss limit.`;
  $("sqlRows").replaceChildren(
    ...d.sql.map((row) => {
      const tr = element("tr");
      [
        row.date,
        money(row.close),
        Number(row.volume).toLocaleString("en-US"),
        pct(row.return_pct),
        pct(row.volume_change_pct),
      ].forEach((v) => tr.append(element("td", v)));
      return tr;
    }),
  );
}
function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = element("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("export").onclick = () => {
  if (!current) return message("Load an analysis before exporting.", true);
  download(
    "marketlens-evidence.json",
    JSON.stringify(current, null, 2),
    "application/json",
  );
};
$("report").onclick = () => {
  if (!current) return message("Load an analysis before exporting.", true);
  const d = current;
  download(
    "marketlens-research-brief.md",
    `# MarketLens research brief\n\nDataset: ${d.meta.name}\nSource: ${d.meta.source}\nSource URL: ${d.meta.source_url || "Local import"}\nPeriod: ${d.receipt.start} to ${d.receipt.end}\nPrice basis: ${d.meta.price_basis}\n\n## Findings\n\n${d.observations.map((s) => "- " + s).join("\n")}\n\n## Reproducibility\n\nMethod version: ${d.receipt.method_version}\nClean window SHA-256: ${d.receipt.sha256}\n\n## Limits\n\nNo prediction or causal attribution. No dividend-inclusive returns. Gap checks are not exchange-calendar checks. No guarantee of source accuracy. No trading recommendations or Nasdaq affiliation.\n`,
    "text/markdown",
  );
};
$("dataset").onchange = () => {
  const d = catalog.find((d) => d.id === $("dataset").value);
  $("cutoff").min = d.first;
  $("cutoff").max = d.last;
  $("cutoff").value = d.last;
  load();
};
$("window").onchange = load;
$("cutoff").onchange = load;
$("latest").onclick = () => {
  $("cutoff").value =
    catalog.find((d) => d.id === $("dataset").value)?.last || "";
  load();
};
function stress() {
  const exposure = Number($("exposure").value),
    shock = Number($("shock").value);
  $("shockLabel").textContent = shock + "%";
  if (!Number.isFinite(exposure) || exposure < 0 || exposure > 1e9) {
    $("stressResult").textContent = "Enter a valid exposure";
    $("stressAfter").textContent = "";
    return;
  }
  $("stressResult").textContent = money((exposure * shock) / 100);
  $("stressResult").style.color = shock < 0 ? "var(--red)" : "var(--green)";
  $("stressAfter").textContent =
    "Remaining value: " + money(exposure * (1 + shock / 100));
}
$("exposure").oninput = stress;
$("shock").oninput = stress;
stress();
$("csv").onchange = async () => {
  const f = $("csv").files[0];
  if (!f) return;
  try {
    if (f.size > 1_500_000)
      throw Error("CSV must be below 1.5 MB to fit the import request limit.");
    message("Validating CSV…");
    await api("/api/import", {
      csv: await f.text(),
      asset_class: $("assetClass").value,
    });
    await loadCatalog("IMPORT");
  } catch (e) {
    message(e.message, true);
  } finally {
    $("csv").value = "";
  }
};
$("refresh").onclick = async () => {
  const b = $("refresh");
  b.disabled = true;
  try {
    message("Fetching completed daily candles…");
    const symbol = $("refreshSymbol").value;
    await api("/api/refresh", { symbol });
    await loadCatalog(symbol);
  } catch (e) {
    message(e.message, true);
  } finally {
    b.disabled = false;
  }
};
async function quote() {
  if (quoteBusy) return;
  quoteBusy = true;
  const symbol = $("quoteSymbol").value;
  try {
    const d = await api("/api/ticker?symbol=" + encodeURIComponent(symbol));
    if (symbol !== $("quoteSymbol").value || !$("poll").checked) return;
    $("quotePrice").textContent = money(d.price);
    $("quoteTime").textContent =
      `${d.source} · trade ${new Date(d.time).toLocaleString()} · polled, not streaming`;
  } catch (e) {
    $("quotePrice").textContent = "Unavailable";
    $("quoteTime").textContent =
      "Quote fetch failed. No live price is being shown.";
  } finally {
    quoteBusy = false;
  }
}
$("poll").onchange = () => {
  clearInterval(pollTimer);
  if ($("poll").checked) {
    quote();
    pollTimer = setInterval(() => {
      if (!document.hidden) quote();
    }, 30000);
  } else {
    $("quoteTime").textContent =
      "Polling paused · displayed quote may be stale";
  }
};
$("quoteSymbol").onchange = () => {
  $("quotePrice").textContent = "—";
  $("quoteTime").textContent = "Enable polling to fetch a quote";
  if ($("poll").checked) quote();
};
loadCatalog().catch((e) => message(e.message, true));
