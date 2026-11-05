(function () {
  "use strict";

  const ICONS = {
    swap: "M7 7h11l-3-3M17 17H6l3 3",
    cross: "M6 6l12 12M18 6L6 18",
    link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    door: "M6 20V4h9v16M4 20h16M12 12h.01",
    arrowR: "M5 12h14l-5-5M19 12l-5 5",
    arrowL: "M19 12H5l5-5M5 12l5 5",
    plus: "M12 5v14M5 12h14",
    calendar: "M5 6h14v14H5zM5 10h14M9 4v4M15 4v4",
    info: "M12 11v6M12 7.5h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z"
  };

  const BADGE_META = {
    SUPLOVANI: { icon: "swap", label: "Suplování" },
    ODPADA: { icon: "cross", label: "Odpadá" },
    SPOJENO: { icon: "link", label: "Spojeno" },
    ZMENA_UCEBNY: { icon: "door", label: "Změna učebny" },
    PRESUN_NA: { icon: "arrowR", label: "Přesun (odkud)" },
    PRESUN_Z: { icon: "arrowL", label: "Přesun (kam)" },
    NAVIC: { icon: "plus", label: "Navíc" },
    VYMENA: { icon: "swap", label: "Výměna" },
    CELODENNI_AKCE: { icon: "calendar", label: "Akce třídy" },
    OSTATNI: { icon: "info", label: "Ostatní" }
  };

  const SHORT = {
    SUPLOVANI: "Supluje",
    ODPADA: "Odpadá",
    SPOJENO: "Spojeno",
    ZMENA_UCEBNY: "Učebna",
    PRESUN_NA: "Přesun >",
    PRESUN_Z: "Přesun <",
    NAVIC: "Navíc",
    VYMENA: "Výměna",
    CELODENNI_AKCE: "Akce",
    OSTATNI: "Změna"
  };

  function svgIcon(name) {
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "15");
    svg.setAttribute("height", "15");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(NS, "path");
    path.setAttribute("d", ICONS[name] || ICONS.info);
    svg.appendChild(path);
    return svg;
  }

  const state = {
    dates: [],
    selectedDate: "",
    dayData: null,
    status: null,
    selectedEntity: "",
    searchQuery: "",
    isStaticExport: Boolean(window.__STATIC_EXPORT__),
    isOffline: false
  };

  const els = {
    mainContainer: document.getElementById("main-container"),
    schoolName: document.getElementById("school-name"),
    exportedAtLabel: document.getElementById("exported-at-label"),
    updatedAtLabel: document.getElementById("updated-at-label"),
    bannerParseError: document.getElementById("banner-parse-error"),
    bannerParseErrorText: document.getElementById("banner-parse-error-text"),
    bannerStale: document.getElementById("banner-stale"),
    bannerStaleText: document.getElementById("banner-stale-text"),
    bannerOffline: document.getElementById("banner-offline"),
    dateTabs: document.getElementById("date-tabs"),
    entitySelect: document.getElementById("entity-select"),
    searchInput: document.getElementById("search-input"),
    btnClearFilter: document.getElementById("btn-clear-filter"),
    dayHeading: document.getElementById("day-heading"),
    gridView: document.getElementById("grid-view")
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function formatHourRange(hFrom, hTo) {
    if (hFrom === hTo) return hFrom + ". hod";
    return hFrom + ".–" + hTo + ". hod";
  }

  function formatShortDate(isoDate, dayName) {
    const parts = isoDate.split("-");
    if (parts.length !== 3) return isoDate;
    const d = parseInt(parts[2], 10);
    const m = parseInt(parts[1], 10);
    return (dayName ? dayName + " " : "") + d + ". " + m + ".";
  }

  function chooseDefaultDate(datesList) {
    if (!datesList || datesList.length === 0) return "";
    const todayIso = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Prague" });
    const exact = datesList.find((d) => d.date === todayIso);
    if (exact) return exact.date;
    const future = datesList.find((d) => d.date >= todayIso);
    if (future) return future.date;
    return datesList[datesList.length - 1].date;
  }

  async function fetchSchedulePayload(targetDate) {
    if (state.isStaticExport) {
      const idxRes = await fetch("./data/index.json", { cache: "no-cache" });
      if (!idxRes.ok) throw new Error("Nelze načíst statický index.");
      const idxData = await idxRes.json();
      const chosen = targetDate || chooseDefaultDate(idxData.dates);
      let dayObj = null;
      if (chosen) {
        const dayRes = await fetch("./data/day-" + chosen + ".json", { cache: "no-cache" });
        if (dayRes.ok) dayObj = await dayRes.json();
      }
      return {
        dates: idxData.dates || [],
        selected_date: chosen,
        day: dayObj,
        status: idxData.status || {}
      };
    }

    const q = targetDate ? "?date=" + encodeURIComponent(targetDate) : "";
    const res = await fetch("/api/schedule" + q, { cache: "no-cache" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return await res.json();
  }

  async function loadData(targetDate, preserveSelection) {
    try {
      const dateToLoad = preserveSelection ? state.selectedDate : targetDate;
      const payload = await fetchSchedulePayload(dateToLoad);
      state.isOffline = false;
      state.dates = payload.dates || [];
      state.selectedDate = payload.selected_date || "";
      state.dayData = payload.day || null;
      state.status = payload.status || null;

      try {
        localStorage.setItem("krizik_supl_last_payload", JSON.stringify(payload));
      } catch (_e) {
        // Ignoruj
      }
      renderAll();
    } catch (_err) {
      state.isOffline = true;
      try {
        const cached = localStorage.getItem("krizik_supl_last_payload");
        if (cached) {
          const payload = JSON.parse(cached);
          state.dates = payload.dates || [];
          state.selectedDate = payload.selected_date || "";
          state.dayData = payload.day || null;
          state.status = payload.status || null;
        }
      } catch (_e) {
        // Ignoruj
      }
      renderAll();
    }
  }

  function renderBannersAndHeader() {
    const day = state.dayData;
    const st = state.status || {};

    if (day && day.school_name) {
      els.schoolName.textContent = day.school_name;
    }

    const expDisp =
      (day && day.exported_at_display) ||
      (st.last_success && st.last_success.exported_at) ||
      "—";
    els.exportedAtLabel.textContent = "Výpis: " + expDisp;

    const nowStr = new Date().toLocaleTimeString("cs-CZ", {
      timeZone: "Europe/Prague",
      hour: "2-digit",
      minute: "2-digit"
    });
    els.updatedAtLabel.textContent = "Kontrola: " + nowStr;

    if (st.has_parse_error) {
      els.bannerParseError.classList.remove("hidden");
      els.bannerParseErrorText.textContent =
        " Zobrazují se poslední platná data.";
    } else {
      els.bannerParseError.classList.add("hidden");
    }

    if (st.is_stale && st.has_data) {
      els.bannerStale.classList.remove("hidden");
      const ageTxt = st.age_hours !== null && st.age_hours !== undefined ? st.age_hours + " h" : "limit";
      els.bannerStaleText.textContent =
        "Upozornění: Data výpisu jsou starší než " +
        (st.stale_threshold_hours || 24) +
        " hodin (stáří: " +
        ageTxt +
        ").";
    } else {
      els.bannerStale.classList.add("hidden");
    }

    if (state.isOffline) {
      els.bannerOffline.classList.remove("hidden");
    } else {
      els.bannerOffline.classList.add("hidden");
    }
  }

  function renderDateTabs() {
    els.dateTabs.replaceChildren();
    state.dates.forEach((d) => {
      const btn = el(
        "button",
        "date-tab" + (d.date === state.selectedDate ? " active" : ""),
        formatShortDate(d.date, d.day_name)
      );
      btn.type = "button";
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", d.date === state.selectedDate ? "true" : "false");
      btn.addEventListener("click", () => {
        state.selectedDate = d.date;
        loadData(d.date, false);
      });
      els.dateTabs.appendChild(btn);
    });
  }

  function populateEntityFilter() {
    const day = state.dayData;
    const prevVal = state.selectedEntity;
    els.entitySelect.replaceChildren();

    const defaultOpt = el("option", "", "Všechny třídy");
    defaultOpt.value = "";
    els.entitySelect.appendChild(defaultOpt);

    if (!day) return;

    const items = new Set();
    (day.class_changes || []).forEach((ch) => {
      if (ch.class_name) items.add(ch.class_name);
    });
    (day.absent_classes || []).forEach((ac) => {
      if (ac.class_name) items.add(ac.class_name);
    });

    Array.from(items)
      .sort((a, b) => a.localeCompare(b, "cs", { numeric: true }))
      .forEach((val) => {
        const opt = el("option", "", "Třída " + val);
        opt.value = val;
        els.entitySelect.appendChild(opt);
      });

    if (items.has(prevVal)) {
      els.entitySelect.value = prevVal;
    } else {
      state.selectedEntity = "";
      els.entitySelect.value = "";
    }

    const hasFilter = Boolean(state.selectedEntity || state.searchQuery);
    els.btnClearFilter.classList.toggle("hidden", !hasFilter);
  }

  function matchesSearch(texts) {
    if (!state.searchQuery) return true;
    const q = state.searchQuery.toLowerCase();
    return texts.some((t) => t && String(t).toLowerCase().includes(q));
  }

  function hoursRangeText(hoursObj) {
    const hs = Object.keys(hoursObj || {})
      .map(Number)
      .sort((a, b) => a - b);
    if (hs.length === 0) return "";
    return hs[0] === hs[hs.length - 1] ? hs[0] + "." : hs[0] + ".–" + hs[hs.length - 1] + ".";
  }

  function gridCellForChange(ch) {
    const box = el("div", "gcell badge-" + ch.change_type);
    const top = el("div", "gcell-top");
    top.appendChild(svgIcon((BADGE_META[ch.change_type] || BADGE_META.OSTATNI).icon));
    top.appendChild(el("strong", "", SHORT[ch.change_type] || "Změna"));
    if (ch.subject) top.appendChild(el("span", "", ch.subject));
    if (ch.group_name) top.appendChild(el("span", "gcell-group", ch.group_name));
    if (ch.room) top.appendChild(el("span", "gcell-room", "(" + ch.room + ")"));
    box.appendChild(top);
    const parts = [];
    if (ch.sub_teacher) parts.push(ch.sub_teacher);
    if (ch.orig_teacher_code && !ch.sub_teacher) parts.push("(" + ch.orig_teacher_code + ")");
    if (ch.note && ch.change_type !== "CELODENNI_AKCE") parts.push(ch.note);
    if (parts.length) box.appendChild(el("div", "gcell-bottom", parts.join(" · ")));
    box.title = [
      formatHourRange(ch.hour_from, ch.hour_to),
      SHORT[ch.change_type],
      ch.subject,
      ch.sub_teacher,
      ch.orig_teacher_code ? "původně (" + ch.orig_teacher_code + ")" : "",
      ch.room ? "učebna " + ch.room : "",
      ch.note
    ]
      .filter(Boolean)
      .join(", ");
    return box;
  }

  function changeMatchesSearch(ch) {
    return matchesSearch([
      ch.class_name,
      ch.subject,
      ch.group_name,
      ch.room,
      ch.sub_teacher,
      ch.orig_teacher_code,
      ch.orig_teacher_resolved,
      ch.note,
      ch.change_type_raw
    ]);
  }

  function renderGrid(day) {
    const root = els.gridView;
    root.replaceChildren();

    const strip = el("div", "grid-strip");
    const absT = day.absent_teachers || [];
    const tBox = el("div", "strip-box strip-teachers");
    tBox.appendChild(el("strong", "", "Nepřítomní učitelé: "));
    tBox.appendChild(
      el(
        "span",
        "",
        absT.length
          ? absT
              .map(
                (a) =>
                  (a.teacher_code && a.teacher_full_name.indexOf(a.teacher_code) < 0
                    ? a.teacher_full_name + " (" + a.teacher_code + ")"
                    : a.teacher_full_name) +
                  " " +
                  hoursRangeText(a.hours)
              )
              .join("  |  ")
          : "nejsou"
      )
    );
    strip.appendChild(tBox);

    const rooms = day.closed_rooms || [];
    const rBox = el("div", "strip-box strip-rooms");
    rBox.appendChild(el("strong", "", "Učebny mimo provoz: "));
    rBox.appendChild(
      el(
        "span",
        "",
        rooms.length ? rooms.map((r) => r.room_name + " (" + hoursRangeText(r.hours) + ")").join(", ") : "nejsou"
      )
    );
    strip.appendChild(rBox);

    if (day.supervisions && day.supervisions.length > 0) {
      const sBox = el("div", "strip-box strip-sup");
      sBox.appendChild(el("strong", "", "Dohledy: "));
      sBox.appendChild(
        el(
          "span",
          "",
          day.supervisions
            .map((s) => s.class_name + " (" + formatHourRange(s.hour_from, s.hour_to) + ": " + s.teachers_text + ")")
            .join(" | ")
        )
      );
      strip.appendChild(sBox);
    }
    root.appendChild(strip);

    const allChanges = (day.class_changes || []).filter(changeMatchesSearch);
    const classes = new Set();
    allChanges.forEach((c) => classes.add(c.class_name));
    if (!state.searchQuery) {
      (day.absent_classes || []).forEach((c) => classes.add(c.class_name));
    }

    const rowsList = Array.from(classes)
      .filter((c) => !state.selectedEntity || c === state.selectedEntity)
      .sort((a, b) => a.localeCompare(b, "cs", { numeric: true }));

    let maxHour = 7;
    (day.class_changes || []).forEach((c) => {
      maxHour = Math.max(maxHour, c.hour_to);
    });
    maxHour = Math.min(maxHour, 10);

    if (rowsList.length === 0) {
      root.appendChild(el("div", "section-block", "Žádné změny v rozvrhu neodpovídají zadanému filtru."));
      return;
    }

    const avail = Math.max(
      window.innerHeight - (document.body.classList.contains("kiosk") ? 110 : 195),
      260
    );
    const fs = Math.max(10.5, Math.min(14, avail / rowsList.length / 2.75));
    root.style.setProperty("--gfs", fs.toFixed(1) + "px");

    const tbl = el("table", "big-grid");
    const thead = el("thead");
    const trh = el("tr");
    trh.appendChild(el("th", "gh-class", "Třída"));
    for (let hr = 1; hr <= maxHour; hr++) trh.appendChild(el("th", "", hr + ". hod"));
    thead.appendChild(trh);
    tbl.appendChild(thead);

    const tbody = el("tbody");
    rowsList.forEach((cls) => {
      const tr = el("tr");
      tr.appendChild(el("th", "gh-class", cls));
      const changes = allChanges.filter(
        (c) => c.class_name === cls && c.change_type !== "CELODENNI_AKCE"
      );
      const actions = allChanges.filter(
        (c) => c.class_name === cls && c.change_type === "CELODENNI_AKCE"
      );
      const absCls = (day.absent_classes || []).find((a) => a.class_name === cls);
      let hr = 1;
      while (hr <= maxHour) {
        const act = actions.find((a) => a.hour_from <= hr && hr <= a.hour_to);
        const inside = act && changes.some((c) => c.hour_from <= act.hour_to && c.hour_to >= act.hour_from);
        if (act && !inside) {
          const span = Math.min(act.hour_to, maxHour) - hr + 1;
          const td = el("td", "gtd gtd-action");
          td.colSpan = span;
          td.appendChild(gridCellForChange(act));
          tr.appendChild(td);
          hr += span;
          continue;
        }
        const td = el("td", "gtd");
        const here = changes.filter((c) => c.hour_from <= hr && hr <= c.hour_to);
        here.forEach((c) => td.appendChild(gridCellForChange(c)));
        if (!here.length && absCls && (absCls.hours[hr] || absCls.hours[String(hr)])) {
          td.appendChild(
            el("div", "gcell badge-CELODENNI_AKCE", "Nepřítomna (" + (absCls.hours[hr] || absCls.hours[String(hr)]) + ")")
          );
        }
        tr.appendChild(td);
        hr += 1;
      }
      tbody.appendChild(tr);
    });
    tbl.appendChild(tbody);
    const scroll = el("div", "table-scroll");
    scroll.appendChild(tbl);
    root.appendChild(scroll);

    const legend = el("div", "grid-legend");
    ["SUPLOVANI", "ODPADA", "SPOJENO", "ZMENA_UCEBNY", "PRESUN_NA", "NAVIC", "CELODENNI_AKCE"].forEach((k) => {
      const b = el("span", "badge badge-" + k);
      b.appendChild(svgIcon(BADGE_META[k].icon));
      b.appendChild(el("span", "", BADGE_META[k].label));
      legend.appendChild(b);
    });
    root.appendChild(legend);
  }

  // Režim celé obrazovky s plynulým automatickým posunem nahoru a dolů
  const kiosk = {
    pos: 0,
    active: false,
    raf: 0,
    dir: 1,
    pauseUntil: 0,
    last: 0,
    speed: 40,
    pauseMs: 2500
  };
  const btnFs = document.getElementById("btn-fullscreen");
  const btnKioskExit = document.getElementById("btn-kiosk-exit");

  function getScrollTop() {
    return (
      window.scrollY ||
      document.documentElement.scrollTop ||
      document.body.scrollTop ||
      0
    );
  }

  function setScrollTop(y) {
    const target = Math.round(y);
    window.scrollTo(0, target);
    if (document.scrollingElement) document.scrollingElement.scrollTop = target;
    document.documentElement.scrollTop = target;
    document.body.scrollTop = target;
  }

  function renderAll() {
    const keepScroll = getScrollTop();
    renderBannersAndHeader();
    renderDateTabs();
    populateEntityFilter();

    const day = state.dayData;
    if (!day) {
      els.dayHeading.textContent = "Žádná data suplování nejsou momentálně k dispozici.";
      els.gridView.replaceChildren();
      return;
    }

    els.dayHeading.replaceChildren();
    els.dayHeading.appendChild(
      el("span", "", formatShortDate(day.date, day.day_name) + " " + day.date.slice(0, 4))
    );
    if (day.week_label) {
      els.dayHeading.appendChild(el("span", "week-badge", day.week_label));
    }

    renderGrid(day);
    if (kiosk.active) setScrollTop(keepScroll);
  }

  window.addEventListener("resize", () => {
    renderAll();
  });

  els.entitySelect.addEventListener("change", (e) => {
    state.selectedEntity = e.target.value;
    renderAll();
  });

  els.searchInput.addEventListener("input", (e) => {
    state.searchQuery = e.target.value.trim();
    renderAll();
  });

  els.btnClearFilter.addEventListener("click", () => {
    state.selectedEntity = "";
    state.searchQuery = "";
    els.entitySelect.value = "";
    els.searchInput.value = "";
    renderAll();
  });

  function kioskStep(ts) {
    if (!kiosk.active) return;
    if (!kiosk.last) kiosk.last = ts;
    const dt = Math.min((ts - kiosk.last) / 1000, 0.1);
    kiosk.last = ts;

    const docH = Math.max(
      document.documentElement.scrollHeight,
      document.body.scrollHeight
    );
    const maxY = docH - window.innerHeight;

    if (ts >= kiosk.pauseUntil) {
      if (maxY > 12) {
        if (els.mainContainer) els.mainContainer.style.transform = "";
        const currentY = getScrollTop();
        if (Math.abs(currentY - kiosk.pos) > 8) kiosk.pos = currentY;
        kiosk.pos += kiosk.dir * kiosk.speed * dt;
        if (kiosk.pos >= maxY) {
          kiosk.pos = maxY;
          kiosk.dir = -1;
          kiosk.pauseUntil = ts + kiosk.pauseMs;
        } else if (kiosk.pos <= 0) {
          kiosk.pos = 0;
          kiosk.dir = 1;
          kiosk.pauseUntil = ts + kiosk.pauseMs;
        }
        setScrollTop(kiosk.pos);
      } else {
        // Obsah se vejde na obrazovku – nic se neposouvá.
        kiosk.pos = 0;
        if (els.mainContainer) els.mainContainer.style.transform = "";
      }
    }
    kiosk.raf = requestAnimationFrame(kioskStep);
  }

  function startKiosk() {
    if (kiosk.active) return;
    kiosk.active = true;
    kiosk.dir = 1;
    kiosk.last = 0;
    kiosk.pos = 0;
    kiosk.pauseUntil = performance.now() + 1200;
    document.body.classList.add("kiosk");
    btnKioskExit.classList.remove("hidden");
    setScrollTop(0);
    renderAll();
    const root = document.documentElement;
    if (root.requestFullscreen) {
      root.requestFullscreen().catch(() => {});
    } else if (root.webkitRequestFullscreen) {
      root.webkitRequestFullscreen();
    }
    kiosk.raf = requestAnimationFrame(kioskStep);
  }

  function stopKiosk() {
    if (!kiosk.active) return;
    kiosk.active = false;
    cancelAnimationFrame(kiosk.raf);
    if (els.mainContainer) els.mainContainer.style.transform = "";
    document.body.classList.remove("kiosk");
    btnKioskExit.classList.add("hidden");
    if (document.fullscreenElement && document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    }
    renderAll();
  }

  btnFs.addEventListener("click", () => (kiosk.active ? stopKiosk() : startKiosk()));
  btnKioskExit.addEventListener("click", stopKiosk);
  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && kiosk.active) stopKiosk();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") stopKiosk();
  });
  ["wheel", "touchstart"].forEach((evt) =>
    window.addEventListener(
      evt,
      () => {
        if (kiosk.active) kiosk.pauseUntil = performance.now() + 6000;
      },
      { passive: true }
    )
  );

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./sw.js").catch(() => {});
    });
  }

  function setupLiveUpdates() {
    if (state.isStaticExport) return;

    if ("EventSource" in window) {
      const es = new EventSource("/api/events");
      es.addEventListener("update", () => {
        loadData(state.selectedDate, true);
      });
      es.onerror = () => {};
    }

    setInterval(() => {
      loadData(state.selectedDate, true);
    }, 25000);
  }

  loadData("", false);
  setupLiveUpdates();
})();
