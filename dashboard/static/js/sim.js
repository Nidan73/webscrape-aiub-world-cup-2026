// Team page simulator: mode tabs, what-if preview, Monte Carlo runs, history drawer.
// Preview/hydration races: AbortController + monotonic seq for stale preview drops;
// hydrating gate + dirty flag so /api/sim/current cannot overwrite in-flight edits.
(function () {
  const root = document.getElementById("sim-root");
  if (!root) return;

  const teamId = root.dataset.teamId;
  let standingsSignal = root.dataset.standingsSignal === "1";

  const dataEl = document.getElementById("sim-data");
  const simData = dataEl ? JSON.parse(dataEl.textContent || "{}") : {};
  const groupTeams = simData.groupTeams || {};
  const koSlots = simData.koSlots || [];

  const state = {
    whatif: { groups: {}, ko: {} },
    mc: { n: 1000, bias: 0, use_current_picks: true },
  };

  let hydrating = true;
  let dirty = false;
  let previewAbort = null;
  let previewSeq = 0;

  function qs(sel, el) { return (el || root).querySelector(sel); }
  function qsa(sel, el) { return Array.from((el || root).querySelectorAll(sel)); }

  function debounce(fn, ms) {
    let timer = null;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function postJSON(url, body, options) {
    const opts = options || {};
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
      signal: opts.signal,
    }).then((r) => r.json().then((data) => ({ status: r.status, data })));
  }

  function markDirty() {
    if (!dirty) dirty = true;
  }

  function putJSON(url, body) {
    return fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then((r) => r.json().then((data) => ({ status: r.status, data })));
  }

  function showError(el, msg) {
    if (!el) return;
    if (msg) {
      el.textContent = msg;
      el.hidden = false;
    } else {
      el.textContent = "";
      el.hidden = true;
    }
  }

  // ---- Mode tabs -----------------------------------------------------
  const tabs = qsa(".sim-tab");
  const panels = { possible: qs("#panel-possible"), whatif: qs("#panel-whatif"), montecarlo: qs("#panel-montecarlo") };

  function switchMode(mode) {
    tabs.forEach((t) => {
      const active = t.dataset.mode === mode;
      t.classList.toggle("is-active", active);
      t.setAttribute("aria-selected", active ? "true" : "false");
    });
    Object.entries(panels).forEach(([key, panel]) => {
      if (!panel) return;
      const active = key === mode;
      panel.hidden = !active;
      panel.classList.toggle("is-active", active);
    });
  }

  tabs.forEach((t) => t.addEventListener("click", () => switchMode(t.dataset.mode)));

  const openWhatifCta = qs("#open-whatif-cta");
  if (openWhatifCta) openWhatifCta.addEventListener("click", () => switchMode("whatif"));

  // ---- History drawer --------------------------------------------------
  const historyDrawer = qs("#history-drawer");
  const historyOpenBtn = qs("#history-open");
  const historyCloseBtn = qs("#history-close");
  const historyList = qs("#history-list");
  const historyErrorEl = qs("#history-error");

  function renderHistory(entries) {
    if (!historyList) return;
    historyList.innerHTML = "";
    const mine = entries.filter((h) => !h.team_id || h.team_id === teamId);
    if (mine.length === 0) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "No saved scenarios yet.";
      historyList.appendChild(li);
      return;
    }
    mine.forEach((h) => {
      const li = document.createElement("li");
      li.className = "history-item";
      const top = document.createElement("div");
      top.className = "history-item-top";
      const title = document.createElement("span");
      title.textContent = h.title || h.id;
      const type = document.createElement("span");
      type.className = "pill";
      type.textContent = h.type;
      top.appendChild(title);
      top.appendChild(type);
      const meta = document.createElement("div");
      meta.className = "history-item-meta";
      meta.textContent = h.created_at || "";
      const actions = document.createElement("div");
      actions.className = "history-item-actions";

      const restoreBtn = document.createElement("button");
      restoreBtn.type = "button";
      restoreBtn.textContent = "Restore";
      restoreBtn.addEventListener("click", () => restoreHistory(h.id));

      const renameBtn = document.createElement("button");
      renameBtn.type = "button";
      renameBtn.textContent = "Rename";
      renameBtn.addEventListener("click", () => renameHistory(h.id));

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.textContent = "Delete";
      deleteBtn.addEventListener("click", () => deleteHistory(h.id));

      actions.appendChild(restoreBtn);
      actions.appendChild(renameBtn);
      actions.appendChild(deleteBtn);

      li.appendChild(top);
      li.appendChild(meta);
      li.appendChild(actions);
      historyList.appendChild(li);
    });
  }

  function loadHistory() {
    showError(historyErrorEl, null);
    fetch("/api/sim/history")
      .then((r) => r.json())
      .then((data) => {
        if (!data.ok) throw new Error(data.error || "Failed to load history");
        renderHistory(data.history || []);
      })
      .catch((e) => showError(historyErrorEl, e.message));
  }

  function restoreHistory(id) {
    postJSON(`/api/sim/history/${encodeURIComponent(id)}/restore`, {}).then(({ status, data }) => {
      if (status !== 200 || !data.ok) {
        showError(historyErrorEl, (data && data.error) || "Restore failed");
        return;
      }
      hydrateFromCurrent(data.current, { force: true });
      switchMode("whatif");
      closeDrawer();
    });
  }

  function renameHistory(id) {
    const title = window.prompt("New name:");
    if (!title) return;
    fetch(`/api/sim/history/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.ok) throw new Error(data.error || "Rename failed");
        loadHistory();
      })
      .catch((e) => showError(historyErrorEl, e.message));
  }

  function deleteHistory(id) {
    if (!window.confirm("Delete this saved scenario?")) return;
    fetch(`/api/sim/history/${encodeURIComponent(id)}`, { method: "DELETE" })
      .then((r) => r.json())
      .then((data) => {
        if (!data.ok) throw new Error(data.error || "Delete failed");
        loadHistory();
      })
      .catch((e) => showError(historyErrorEl, e.message));
  }

  function openDrawer() {
    if (!historyDrawer) return;
    historyDrawer.hidden = false;
    loadHistory();
  }
  function closeDrawer() {
    if (!historyDrawer) return;
    historyDrawer.hidden = true;
  }

  if (historyOpenBtn) historyOpenBtn.addEventListener("click", openDrawer);
  if (historyCloseBtn) historyCloseBtn.addEventListener("click", closeDrawer);

  // ---- What-if panel -----------------------------------------------------
  const whatifGroupsEl = qs("#whatif-groups");
  const whatifKoEl = qs("#whatif-ko");
  const whatifPreviewEl = qs("#whatif-preview");
  const whatifErrorEl = qs("#whatif-error");
  const whatifResetBtn = qs("#whatif-reset");
  const whatifSaveBtn = qs("#whatif-save");

  function setSimControlsDisabled(disabled) {
    qsa("select", whatifGroupsEl).forEach((el) => { el.disabled = disabled; });
    qsa("select", whatifKoEl).forEach((el) => { el.disabled = disabled; });
    if (whatifResetBtn) whatifResetBtn.disabled = disabled;
    if (whatifSaveBtn) whatifSaveBtn.disabled = disabled;
    if (mcNInput) mcNInput.disabled = disabled;
    if (mcBiasInput) mcBiasInput.disabled = disabled;
    if (mcUsePicksInput) mcUsePicksInput.disabled = disabled;
    if (mcRunBtn && mcRunBtn.textContent === "Run") mcRunBtn.disabled = disabled;
  }

  function buildSelect(id, options, selected, placeholder) {
    const select = document.createElement("select");
    select.id = id;
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = placeholder;
    select.appendChild(blank);
    options.forEach((o) => {
      const opt = document.createElement("option");
      opt.value = o.id;
      opt.textContent = o.team_name ? `${o.country} (${o.team_name})` : o.country;
      if (o.id === selected) opt.selected = true;
      select.appendChild(opt);
    });
    return select;
  }

  function renderWhatifControls() {
    if (whatifGroupsEl) {
      whatifGroupsEl.innerHTML = "";
      Object.entries(groupTeams).forEach(([group, teams]) => {
        const wrap = document.createElement("div");
        wrap.className = "whatif-group";
        const heading = document.createElement("label");
        heading.textContent = `Group ${group} — 1st`;
        const firstSelect = buildSelect(`whatif-${group}-first`, teams, null, "Undecided");
        const secondLabel = document.createElement("label");
        secondLabel.textContent = `Group ${group} — 2nd`;
        const secondSelect = buildSelect(`whatif-${group}-second`, teams, null, "Undecided");

        firstSelect.addEventListener("change", () => onGroupPickChange(group, firstSelect, secondSelect));
        secondSelect.addEventListener("change", () => onGroupPickChange(group, firstSelect, secondSelect));

        wrap.appendChild(heading);
        wrap.appendChild(firstSelect);
        wrap.appendChild(secondLabel);
        wrap.appendChild(secondSelect);
        whatifGroupsEl.appendChild(wrap);
      });
    }

    if (whatifKoEl) {
      whatifKoEl.innerHTML = "";
      koSlots.forEach((slot) => {
        const wrap = document.createElement("div");
        wrap.className = "whatif-ko-slot";
        const label = document.createElement("label");
        label.textContent = `M${slot.match_no} (${slot.stage}) winner`;
        const select = buildSelect(`whatif-ko-${slot.match_no}`, slot.candidates, null, "Undecided");
        select.addEventListener("change", () => {
          markDirty();
          if (select.value) {
            state.whatif.ko[slot.match_no] = select.value;
          } else {
            delete state.whatif.ko[slot.match_no];
          }
          schedulePreview();
        });
        wrap.appendChild(label);
        wrap.appendChild(select);
        whatifKoEl.appendChild(wrap);
      });
    }
  }

  function onGroupPickChange(group, firstSelect, secondSelect) {
    markDirty();
    const first = firstSelect.value;
    const second = secondSelect.value;
    if (first && second && first !== second) {
      state.whatif.groups[group] = { first, second };
    } else {
      delete state.whatif.groups[group];
    }
    schedulePreview();
  }

  function applyWhatifStateToControls() {
    Object.entries(groupTeams).forEach(([group]) => {
      const pick = state.whatif.groups[group];
      const firstSelect = qs(`#whatif-${group}-first`);
      const secondSelect = qs(`#whatif-${group}-second`);
      if (firstSelect) firstSelect.value = pick ? pick.first : "";
      if (secondSelect) secondSelect.value = pick ? pick.second : "";
    });
    koSlots.forEach((slot) => {
      const select = qs(`#whatif-ko-${slot.match_no}`);
      if (select) select.value = state.whatif.ko[slot.match_no] || "";
    });
  }

  function runWhatifPreview() {
    if (!whatifPreviewEl) return;
    if (previewAbort) previewAbort.abort();
    previewAbort = new AbortController();
    const seq = ++previewSeq;
    const signal = previewAbort.signal;

    showError(whatifErrorEl, null);
    whatifPreviewEl.classList.add("sim-skeleton");
    postJSON("/api/sim/whatif/preview", { team_id: teamId, picks: state.whatif }, { signal })
      .then(({ status, data }) => {
        if (seq !== previewSeq) return;
        whatifPreviewEl.classList.remove("sim-skeleton");
        if (status !== 200 || !data.ok) {
          showError(whatifErrorEl, (data && data.error) || "Preview failed");
          return;
        }
        renderWhatifPreview(data.projection);
      })
      .catch((e) => {
        if (seq !== previewSeq || e.name === "AbortError") return;
        whatifPreviewEl.classList.remove("sim-skeleton");
        showError(whatifErrorEl, e.message);
      });
  }

  const schedulePreview = debounce(runWhatifPreview, 300);

  function renderWhatifPreview(projection) {
    whatifPreviewEl.innerHTML = "";
    const scenarios = (projection && projection.scenarios) || {};
    const entries = Object.entries(scenarios);
    if (entries.length === 0) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = "No projection available for these picks.";
      whatifPreviewEl.appendChild(p);
      return;
    }
    entries.forEach(([scen, rounds]) => {
      const h3 = document.createElement("h3");
      h3.style.fontSize = ".95rem";
      h3.textContent = scen === "group_winner" ? "As group winner" : "As runner-up";
      whatifPreviewEl.appendChild(h3);
      (rounds || []).forEach((r) => {
        const row = document.createElement("div");
        row.className = "round-row";
        const tag = document.createElement("span");
        tag.className = "round-tag";
        tag.textContent = r.round;
        const list = document.createElement("div");
        list.className = "opp-list";
        (r.possible_opponents || []).forEach((o) => {
          const span = document.createElement("span");
          span.className = "opp";
          span.textContent = o.team_name ? `${o.country} ${o.team_name}` : o.country;
          list.appendChild(span);
        });
        if (!r.possible_opponents || r.possible_opponents.length === 0) {
          const span = document.createElement("span");
          span.className = "muted";
          span.textContent = "(none)";
          list.appendChild(span);
        }
        row.appendChild(tag);
        row.appendChild(list);
        whatifPreviewEl.appendChild(row);
      });
    });
  }

  if (whatifResetBtn) {
    whatifResetBtn.addEventListener("click", () => {
      markDirty();
      state.whatif = { groups: {}, ko: {} };
      applyWhatifStateToControls();
      runWhatifPreview();
    });
  }

  if (whatifSaveBtn) {
    whatifSaveBtn.addEventListener("click", () => {
      const title = window.prompt("Name this scenario:");
      if (!title) return;
      showError(whatifErrorEl, null);
      putJSON("/api/sim/current", { whatif: state.whatif, mc: state.mc, autosave: false, team_id: teamId })
        .then(({ status, data }) => {
          if (status !== 200 || !data.ok) throw new Error((data && data.error) || "Save failed");
          return postJSON("/api/sim/history", { type: "named", title, team_id: teamId });
        })
        .then(({ status, data } = {}) => {
          if (status && (status < 200 || status >= 300 || !data.ok)) {
            throw new Error((data && data.error) || "Save failed");
          }
        })
        .catch((e) => showError(whatifErrorEl, e.message));
    });
  }

  // ---- Monte Carlo panel --------------------------------------------------
  const mcNInput = qs("#mc-n");
  const mcBiasInput = qs("#mc-bias");
  const mcUsePicksInput = qs("#mc-use-picks");
  const mcRunBtn = qs("#mc-run");
  const mcResultsEl = qs("#mc-results");
  const mcErrorEl = qs("#mc-error");
  const strengthBanner = qs("#strength-banner");

  [mcNInput, mcBiasInput, mcUsePicksInput].forEach((el) => {
    if (el) el.addEventListener("change", markDirty);
  });
  if (mcBiasInput) mcBiasInput.addEventListener("input", markDirty);

  function setStrengthBanner(signal) {
    standingsSignal = signal;
    if (strengthBanner) strengthBanner.hidden = !!signal;
  }

  function renderMcResults(result) {
    mcResultsEl.innerHTML = "";
    setStrengthBanner(result.standings_signal);

    const reachEntries = Object.entries(result.reach || {});
    if (reachEntries.length === 0) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = "This team does not reach the knockout stage in these trials.";
      mcResultsEl.appendChild(p);
      return;
    }

    const table = document.createElement("table");
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th>Round</th><th class=\"num\">Reach %</th><th>Top opponents</th></tr>";
    const tbody = document.createElement("tbody");
    reachEntries.forEach(([stage, pct]) => {
      const tr = document.createElement("tr");
      const tdStage = document.createElement("td");
      tdStage.textContent = stage;
      const tdPct = document.createElement("td");
      tdPct.className = "num";
      tdPct.textContent = `${(pct * 100).toFixed(1)}%`;
      const tdOpp = document.createElement("td");
      const opponents = (result.opponents && result.opponents[stage]) || [];
      tdOpp.textContent = opponents
        .map((o) => `${o.country} ${(o.pct * 100).toFixed(0)}%`)
        .join(", ") || "—";
      tr.appendChild(tdStage);
      tr.appendChild(tdPct);
      tr.appendChild(tdOpp);
      tbody.appendChild(tr);
    });
    table.appendChild(thead);
    table.appendChild(tbody);
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    wrap.appendChild(table);
    mcResultsEl.appendChild(wrap);
  }

  if (mcRunBtn) {
    mcRunBtn.addEventListener("click", () => {
      showError(mcErrorEl, null);
      const n = parseInt((mcNInput && mcNInput.value) || "1000", 10);
      const bias = parseFloat((mcBiasInput && mcBiasInput.value) || "0");
      const useCurrentPicks = !!(mcUsePicksInput && mcUsePicksInput.checked);
      state.mc = { n, bias, use_current_picks: useCurrentPicks };

      mcRunBtn.disabled = true;
      mcRunBtn.textContent = "Running…";
      mcResultsEl.classList.add("sim-skeleton");
      postJSON("/api/sim/montecarlo/run", {
        team_id: teamId,
        n,
        bias,
        use_current_picks: useCurrentPicks,
        picks: useCurrentPicks ? state.whatif : undefined,
      })
        .then(({ status, data }) => {
          if (status !== 200 || !data.ok) {
            showError(mcErrorEl, (data && data.error) || "Monte Carlo run failed");
            return;
          }
          renderMcResults(data);
        })
        .catch((e) => showError(mcErrorEl, e.message))
        .finally(() => {
          mcRunBtn.disabled = false;
          mcRunBtn.textContent = "Run";
          mcResultsEl.classList.remove("sim-skeleton");
        });
    });
  }

  // ---- Hydrate from server-side current state --------------------------
  function hydrateFromCurrent(current, options) {
    const force = options && options.force;
    if (!current) return;
    if (!force && dirty) return;
    state.whatif = current.whatif || { groups: {}, ko: {} };
    state.mc = current.mc || state.mc;
    applyWhatifStateToControls();
    if (mcNInput) mcNInput.value = state.mc.n;
    if (mcBiasInput) mcBiasInput.value = state.mc.bias;
    if (mcUsePicksInput) mcUsePicksInput.checked = !!state.mc.use_current_picks;
    if (force) dirty = false;
    runWhatifPreview();
  }

  renderWhatifControls();
  setSimControlsDisabled(true);
  fetch("/api/sim/current")
    .then((r) => r.json())
    .then((data) => {
      if (data.ok) hydrateFromCurrent(data.current);
      else runWhatifPreview();
    })
    .catch(() => runWhatifPreview())
    .finally(() => {
      hydrating = false;
      setSimControlsDisabled(false);
    });
})();
