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

  const OFFICIAL_TEACHER_CODES = {};

  const NAME_TO_CODE = {};
  Object.keys(OFFICIAL_TEACHER_CODES).forEach((code) => {
    const fullName = OFFICIAL_TEACHER_CODES[code];
    NAME_TO_CODE[fullName] = code;
    NAME_TO_CODE[fullName.toLowerCase()] = code;
    const parts = fullName.split(/\s+/);
    if (parts.length === 2) {
      const reversed = parts[1] + " " + parts[0];
      NAME_TO_CODE[reversed] = code;
      NAME_TO_CODE[reversed.toLowerCase()] = code;
    }
  });

  function formatTeacherWithCode(fullName, code) {
    const name = (fullName || "").trim();
    const c = (code || "").trim();
    if (!name) return c ? "(" + c + ")" : "";
    if (!c) return name;
    if (name.includes("(" + c + ")")) return name;
    if (name === c) return name; // V anonymizovaném režimu, kde je jméno shodné se zkratkou
    return name + " (" + c + ")";
  }

  function lookupTeacherCode(name, dayOrMap) {
    const trimmed = (name || "").trim();
    if (!trimmed) return "";

    if (OFFICIAL_TEACHER_CODES[trimmed]) return trimmed;

    const m = trimmed.match(/\(([^)]+)\)/);
    if (m) return m[1].trim();

    if (dayOrMap && typeof dayOrMap === "object") {
      if (typeof dayOrMap.get === "function" && dayOrMap.has(trimmed)) {
        return dayOrMap.get(trimmed);
      }
      if (dayOrMap[trimmed]) {
        return dayOrMap[trimmed];
      }
      if (Array.isArray(dayOrMap.derived_teachers)) {
        for (const dt of dayOrMap.derived_teachers) {
          if (
            dt.teacher_code &&
            (dt.teacher_key === trimmed ||
              dt.teacher_display === trimmed ||
              dt.teacher_full_name === trimmed)
          ) {
            return dt.teacher_code;
          }
        }
      }
      if (Array.isArray(dayOrMap.absent_teachers)) {
        for (const at of dayOrMap.absent_teachers) {
          if (
            at.teacher_code &&
            (at.teacher_full_name === trimmed || at.teacher_normalized_name === trimmed)
          ) {
            return at.teacher_code;
          }
        }
      }
    }

    if (NAME_TO_CODE[trimmed]) return NAME_TO_CODE[trimmed];
    if (NAME_TO_CODE[trimmed.toLowerCase()]) return NAME_TO_CODE[trimmed.toLowerCase()];

    const cleaned = trimmed.replace(/^(?:Mgr\.|Ing\.|Bc\.|PaedDr\.|RNDr\.|PhDr\.|DiS\.)\s+/i, "").trim();
    if (NAME_TO_CODE[cleaned]) return NAME_TO_CODE[cleaned];
    if (NAME_TO_CODE[cleaned.toLowerCase()]) return NAME_TO_CODE[cleaned.toLowerCase()];

    return "";
  }

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

  const hasDom = typeof document !== "undefined" && typeof window !== "undefined";

  const state = {
    dates: [],
    selectedDate: "",
    dayData: null,
    status: null,
    selectedEntity: "",
    searchQuery: "",
    activeView: "grid",
    isStaticExport: typeof window !== "undefined" ? Boolean(window.__STATIC_EXPORT__) : false,
    isOffline: false
  };

  const els = hasDom
    ? {
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
        viewTabs: document.getElementById("view-tabs"),
        btnViewGrid: document.getElementById("btn-view-grid"),
        btnViewCards: document.getElementById("btn-view-cards"),
        entitySelect: document.getElementById("entity-select"),
        searchInput: document.getElementById("search-input"),
        btnClearFilter: document.getElementById("btn-clear-filter"),
        dayHeading: document.getElementById("day-heading"),
        sourceBadge: document.getElementById("source-badge"),
        sourceBadgeText: document.getElementById("source-badge-text"),
        gridView: document.getElementById("grid-view"),
        cardsView: document.getElementById("cards-view")
      }
    : {};

  function el(tag, className, text) {
    if (typeof document !== "undefined") {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined && text !== null) node.textContent = String(text);
      return node;
    }
    return {
      tagName: tag.toUpperCase(),
      className: className || "",
      textContent: text !== undefined && text !== null ? String(text) : "",
      children: [],
      appendChild(child) {
        this.children.push(child);
        return child;
      }
    };
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

  function formatDateTimeCzech(isoString, fallbackDisplay) {
    if (isoString && typeof isoString === "string") {
      const mIso = isoString.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{1,2}):(\d{2})/);
      if (mIso) {
        const y = mIso[1];
        const mo = parseInt(mIso[2], 10);
        const d = parseInt(mIso[3], 10);
        const h = mIso[4];
        const min = mIso[5];
        return d + ". " + mo + ". " + y + " v " + h + ":" + min;
      }
    }
    if (fallbackDisplay && typeof fallbackDisplay === "string") {
      const trimmed = fallbackDisplay.trim();
      const mFb = trimmed.match(/^(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})(?:\s+(?:v\s+)?(\d{1,2}:\d{2}))?$/);
      if (mFb) {
        const d = parseInt(mFb[1], 10);
        const mo = parseInt(mFb[2], 10);
        const y = mFb[3];
        const time = mFb[4];
        if (time) {
          return d + ". " + mo + ". " + y + " v " + time;
        }
        return d + ". " + mo + ". " + y;
      }
      if (trimmed && trimmed !== "—") {
        return trimmed;
      }
    }
    return "";
  }

  function formatSourceBadgeText(day) {
    if (!day) return "";
    const isWeb =
      day.data_source === "web" ||
      (day.source_label && day.source_label.toLowerCase().includes("web"));
    if (isWeb) {
      const srcLabel = day.source_label || "Web (klasifikace.skolakrizik.cz)";
      const timeStr = formatDateTimeCzech(day.fetched_at || day.exported_at, day.exported_at_display);
      return "Zdroj: " + srcLabel + (timeStr ? " · Načteno " + timeStr : "");
    } else {
      const srcLabel = day.source_label || "Soubor (Bakaláři export)";
      const timeStr = formatDateTimeCzech(day.exported_at, day.exported_at_display);
      return "Zdroj: " + srcLabel + (timeStr ? " · Export " + timeStr : "");
    }
  }

  function updateSourceBadge(day) {
    if (!els.sourceBadge) return;
    if (!day) {
      els.sourceBadge.classList.add("hidden");
      if (els.sourceBadgeText) els.sourceBadgeText.textContent = "";
      return;
    }
    els.sourceBadge.classList.remove("hidden");
    const isWeb =
      day.data_source === "web" ||
      (day.source_label && day.source_label.toLowerCase().includes("web"));
    els.sourceBadge.className = "source-badge " + (isWeb ? "source-web" : "source-file");
    const text = formatSourceBadgeText(day);
    if (els.sourceBadgeText) {
      els.sourceBadgeText.textContent = text;
    } else {
      els.sourceBadge.textContent = text;
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
      "";

    const isWeb =
      day &&
      (day.data_source === "web" ||
        (day.source_label && day.source_label.toLowerCase().includes("web")));
    const timeStr = formatDateTimeCzech(
      isWeb ? (day && (day.fetched_at || day.exported_at)) : (day && day.exported_at),
      expDisp
    );
    if (els.exportedAtLabel) {
      if (day || expDisp) {
        els.exportedAtLabel.textContent = (isWeb ? "Načteno z webu: " : "Výpis: ") + (timeStr || expDisp);
      } else {
        els.exportedAtLabel.textContent = "";
      }
    }

    const nowStr = new Date().toLocaleTimeString("cs-CZ", {
      timeZone: "Europe/Prague",
      hour: "2-digit",
      minute: "2-digit"
    });
    if (els.updatedAtLabel) {
      if (day || state.status) {
        els.updatedAtLabel.textContent = "Kontrola: " + nowStr;
      } else {
        els.updatedAtLabel.textContent = "";
      }
    }

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

    updateSourceBadge(day);
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
        // Okamžitá aktivace záložky bez prodlevy
        const allTabs = els.dateTabs.querySelectorAll
          ? els.dateTabs.querySelectorAll(".date-tab")
          : (els.dateTabs.children || []);
        for (let i = 0; i < allTabs.length; i++) {
          if (allTabs[i].classList && allTabs[i].classList.remove) {
            allTabs[i].classList.remove("active");
          }
          if (allTabs[i].setAttribute) {
            allTabs[i].setAttribute("aria-selected", "false");
          }
        }
        if (btn.classList && btn.classList.add) {
          btn.classList.add("active");
        }
        btn.setAttribute("aria-selected", "true");

        // Okamžitá změna třídy i textu štítku s časem (0 ms prodleva)
        updateSourceBadge(d);

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

  function formatHoursList(hours) {
    if (!Array.isArray(hours) || hours.length === 0) return "";
    const hs = Array.from(new Set(hours.map(Number).filter((n) => !isNaN(n)))).sort(
      (a, b) => a - b
    );
    if (hs.length === 0) return "";

    const ranges = [];
    let start = hs[0];
    let prev = hs[0];
    for (let i = 1; i < hs.length; i++) {
      const curr = hs[i];
      if (curr === prev + 1) {
        prev = curr;
      } else {
        ranges.push({ start, end: prev });
        start = curr;
        prev = curr;
      }
    }
    ranges.push({ start, end: prev });

    const parts = ranges.map((r) => {
      if (r.start === r.end) {
        return r.start + ".";
      }
      return r.start + ".–" + r.end + ".";
    });
    return parts.join(", ") + " hod";
  }

  function extractSubstitutingTeachers(changes, dayOrMap) {
    if (!Array.isArray(changes) || changes.length === 0) return [];
    const teacherHoursMap = new Map();
    changes.forEach((ch) => {
      if (!ch || !ch.sub_teacher) return;
      const name = String(ch.sub_teacher).trim();
      if (!name) return;
      const isActive =
        ch.change_type === "SUPLOVANI" ||
        ch.change_type === "SPOJENO" ||
        (Boolean(ch.sub_teacher_changed) && ch.change_type !== "ZMENA_UCEBNY");
      if (!isActive) return;

      if (!teacherHoursMap.has(name)) {
        teacherHoursMap.set(name, new Set());
      }
      const set = teacherHoursMap.get(name);
      const from = typeof ch.hour_from === "number" ? ch.hour_from : 1;
      const to = typeof ch.hour_to === "number" ? ch.hour_to : from;
      for (let h = from; h <= to; h++) {
        set.add(h);
      }
    });

    const sortedTeachers = Array.from(teacherHoursMap.keys()).sort((a, b) =>
      a.localeCompare(b, "cs")
    );

    return sortedTeachers.map((teacher) => {
      const hours = Array.from(teacherHoursMap.get(teacher));
      const code = lookupTeacherCode(teacher, dayOrMap);
      return {
        teacher: teacher,
        teacherCode: code,
        displayName: formatTeacherWithCode(teacher, code),
        hoursText: formatHoursList(hours)
      };
    });
  }

  function createTeacherPill(name, hoursText, variant) {
    const pill = el("div", "teacher-pill pill-" + variant);
    pill.appendChild(el("span", "pill-name", name));
    if (hoursText) {
      pill.appendChild(el("span", "pill-hours", hoursText));
    }
    return pill;
  }

  function renderGridStrip(day) {
    const strip = el("div", "grid-strip");

    // Blok 1: Nepřítomní učitelé
    const tBox = el("div", "strip-box strip-teachers");
    tBox.appendChild(el("div", "strip-header", "Nepřítomní učitelé:"));
    const tPills = el("div", "strip-pills");
    const absT = (day && day.absent_teachers ? day.absent_teachers : []).slice().sort((a, b) =>
      (a.teacher_full_name || "").localeCompare(b.teacher_full_name || "", "cs")
    );
    if (absT.length === 0) {
      tPills.appendChild(el("span", "strip-empty", "žádní"));
    } else {
      absT.forEach((a) => {
        const rawName = a.teacher_full_name || a.teacher_normalized_name || a.teacher_code || "";
        const code = a.teacher_code || lookupTeacherCode(rawName, day);
        const name = formatTeacherWithCode(rawName, code);
        const hours = Object.keys(a.hours || {}).map(Number);
        tPills.appendChild(createTeacherPill(name, formatHoursList(hours), "absent"));
      });
    }
    tBox.appendChild(tPills);
    strip.appendChild(tBox);

    // Blok 2: Suplující učitelé (nahrazuje strip-rooms a strip-sup)
    const sBox = el("div", "strip-box strip-sub-teachers");
    sBox.appendChild(el("div", "strip-header", "Suplující učitelé:"));
    const sPills = el("div", "strip-pills");
    const subTeachers = extractSubstitutingTeachers((day && day.class_changes) || [], day);
    if (subTeachers.length === 0) {
      sPills.appendChild(el("span", "strip-empty", "žádní"));
    } else {
      subTeachers.forEach((st) => {
        sPills.appendChild(createTeacherPill(st.displayName || st.teacher, st.hoursText, "sub"));
      });
    }
    sBox.appendChild(sPills);
    strip.appendChild(sBox);

    return strip;
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
    if (ch.sub_teacher) {
      const code = lookupTeacherCode(ch.sub_teacher, state.dayData);
      parts.push(formatTeacherWithCode(ch.sub_teacher, code));
    }
    if (ch.orig_teacher_code && !ch.sub_teacher) parts.push("(" + ch.orig_teacher_code + ")");
    if (ch.note && ch.change_type !== "CELODENNI_AKCE") parts.push(ch.note);
    if (parts.length) box.appendChild(el("div", "gcell-bottom", parts.join(" · ")));
    box.title = [
      formatHourRange(ch.hour_from, ch.hour_to),
      SHORT[ch.change_type],
      ch.subject,
      ch.sub_teacher
        ? formatTeacherWithCode(ch.sub_teacher, lookupTeacherCode(ch.sub_teacher, state.dayData))
        : "",
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

    const strip = renderGridStrip(day);
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
    if (root && root.style && typeof root.style.setProperty === "function") {
      root.style.setProperty("--gfs", fs.toFixed(1) + "px");
    }

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

  function renderCards(day) {
    if (!els.cardsView) return;
    const root = els.cardsView;
    root.replaceChildren();

    const strip = renderGridStrip(day);
    root.appendChild(strip);

    if (!day) {
      root.appendChild(el("div", "section-block", "Žádná data suplování nejsou momentálně k dispozici."));
      return;
    }

    const allChanges = (day.class_changes || []).filter(changeMatchesSearch);
    const classes = new Set();
    allChanges.forEach((c) => classes.add(c.class_name));
    if (!state.searchQuery) {
      (day.absent_classes || []).forEach((c) => classes.add(c.class_name));
    }

    const rowsList = Array.from(classes)
      .filter((c) => !state.selectedEntity || c === state.selectedEntity)
      .sort((a, b) => a.localeCompare(b, "cs", { numeric: true }));

    if (rowsList.length === 0) {
      root.appendChild(el("div", "section-block", "Žádné změny v rozvrhu neodpovídají zadanému filtru."));
      return;
    }

    const container = el("div", "cards-container");

    rowsList.forEach((cls) => {
      const card = el("article", "group-card");

      const clsChanges = allChanges
        .filter((c) => c.class_name === cls)
        .sort((a, b) => a.hour_from - b.hour_from || a.hour_to - b.hour_to);
      const absCls = (day.absent_classes || []).find((a) => a.class_name === cls);

      const header = el("div", "group-card-header");
      const title = el("h3", "group-card-title", "Třída " + cls);
      header.appendChild(title);

      const count = clsChanges.length;
      let countText = count + " ";
      if (count === 1) countText += "změna";
      else if (count >= 2 && count <= 4) countText += "změny";
      else countText += "změn";
      if (absCls && count === 0) countText = "akce";
      header.appendChild(el("span", "group-card-badge", countText));
      card.appendChild(header);

      const itemsList = el("div", "group-card-items");

      if (absCls && (!clsChanges.length || Object.keys(absCls.hours || {}).length > 0)) {
        const hKeys = Object.keys(absCls.hours || {});
        if (hKeys.length > 0 && !clsChanges.some((c) => c.change_type === "CELODENNI_AKCE")) {
          const item = el("div", "group-card-item badge-CELODENNI_AKCE");
          const iHeader = el("div", "item-header");
          const b = el("span", "badge badge-CELODENNI_AKCE");
          b.appendChild(svgIcon("calendar"));
          b.appendChild(el("span", "", "Akce"));
          iHeader.appendChild(b);
          iHeader.appendChild(el("span", "item-hour", formatHoursList(hKeys.map(Number))));
          item.appendChild(iHeader);
          const iDetail = el("div", "item-detail");
          const firstVal = absCls.hours[hKeys[0]];
          iDetail.appendChild(el("span", "item-desc", "Nepřítomna (" + firstVal + ")"));
          item.appendChild(iDetail);
          itemsList.appendChild(item);
        }
      }

      clsChanges.forEach((ch) => {
        const item = el("div", "group-card-item badge-" + ch.change_type);
        const iHeader = el("div", "item-header");

        const meta = BADGE_META[ch.change_type] || BADGE_META.OSTATNI;
        const b = el("span", "badge badge-" + ch.change_type);
        b.appendChild(svgIcon(meta.icon));
        b.appendChild(el("span", "", SHORT[ch.change_type] || "Změna"));
        iHeader.appendChild(b);

        iHeader.appendChild(el("span", "item-hour", formatHourRange(ch.hour_from, ch.hour_to)));
        if (ch.subject) iHeader.appendChild(el("span", "item-subject", ch.subject));
        if (ch.group_name) iHeader.appendChild(el("span", "item-group", ch.group_name));
        if (ch.room) iHeader.appendChild(el("span", "item-room", "(" + ch.room + ")"));
        item.appendChild(iHeader);

        const details = [];
        if (ch.sub_teacher) {
          const code = lookupTeacherCode(ch.sub_teacher, day);
          details.push("Supluje: " + formatTeacherWithCode(ch.sub_teacher, code));
        } else if (ch.orig_teacher_code) {
          details.push("Původně: (" + ch.orig_teacher_code + ")");
        }
        if (ch.note) {
          details.push(ch.note);
        }

        if (details.length > 0) {
          const iDetail = el("div", "item-detail");
          details.forEach((dText) => {
            iDetail.appendChild(el("span", "item-desc", dText));
          });
          item.appendChild(iDetail);
        }

        itemsList.appendChild(item);
      });

      card.appendChild(itemsList);
      container.appendChild(card);
    });

    root.appendChild(container);
  }

  function switchView(viewName) {
    if (viewName !== "grid" && viewName !== "cards") return;
    state.activeView = viewName;
    kiosk.pos = 0;
    setScrollTop(0);
    renderAll();
  }

  function renderViewTabs() {
    if (els.btnViewGrid) {
      const isGrid = state.activeView === "grid";
      if (els.btnViewGrid.classList) {
        if (typeof els.btnViewGrid.classList.toggle === "function") {
          els.btnViewGrid.classList.toggle("active", isGrid);
        } else if (isGrid) {
          els.btnViewGrid.classList.add("active");
        } else {
          els.btnViewGrid.classList.remove("active");
        }
      }
      if (typeof els.btnViewGrid.setAttribute === "function") {
        els.btnViewGrid.setAttribute("aria-selected", isGrid ? "true" : "false");
      }
    }
    if (els.btnViewCards) {
      const isCards = state.activeView === "cards";
      if (els.btnViewCards.classList) {
        if (typeof els.btnViewCards.classList.toggle === "function") {
          els.btnViewCards.classList.toggle("active", isCards);
        } else if (isCards) {
          els.btnViewCards.classList.add("active");
        } else {
          els.btnViewCards.classList.remove("active");
        }
      }
      if (typeof els.btnViewCards.setAttribute === "function") {
        els.btnViewCards.setAttribute("aria-selected", isCards ? "true" : "false");
      }
    }
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
  const btnFs = hasDom ? document.getElementById("btn-fullscreen") : null;
  const btnKioskExit = hasDom ? document.getElementById("btn-kiosk-exit") : null;

  function getScrollTop() {
    return (
      (typeof window !== "undefined" && window.scrollY) ||
      (typeof document !== "undefined" && document.documentElement && document.documentElement.scrollTop) ||
      (typeof document !== "undefined" && document.body && document.body.scrollTop) ||
      0
    );
  }

  function setScrollTop(y) {
    const target = Math.round(y);
    if (typeof window !== "undefined" && window.scrollTo) window.scrollTo(0, target);
    if (typeof document !== "undefined") {
      if (document.scrollingElement) document.scrollingElement.scrollTop = target;
      if (document.documentElement) document.documentElement.scrollTop = target;
      if (document.body) document.body.scrollTop = target;
    }
  }

  function renderAll() {
    const keepScroll = getScrollTop();
    renderBannersAndHeader();
    renderDateTabs();
    renderViewTabs();
    populateEntityFilter();

    const day = state.dayData;
    if (!day) {
      if (state.status) {
        els.dayHeading.textContent = "Žádná data suplování nejsou momentálně k dispozici.";
      } else {
        els.dayHeading.textContent = "";
      }
      if (els.gridView) els.gridView.replaceChildren();
      if (els.cardsView) els.cardsView.replaceChildren();
      return;
    }

    els.dayHeading.replaceChildren();
    els.dayHeading.appendChild(
      el("span", "", formatShortDate(day.date, day.day_name) + " " + day.date.slice(0, 4))
    );
    if (day.week_label) {
      els.dayHeading.appendChild(el("span", "week-badge", day.week_label));
    }

    if (state.activeView === "cards") {
      if (els.gridView) els.gridView.classList.add("hidden");
      if (els.cardsView) {
        els.cardsView.classList.remove("hidden");
        renderCards(day);
      }
    } else {
      if (els.cardsView) els.cardsView.classList.add("hidden");
      if (els.gridView) {
        els.gridView.classList.remove("hidden");
        renderGrid(day);
      }
    }

    if (kiosk.active) setScrollTop(keepScroll);
  }

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

  if (hasDom) {
    window.addEventListener("online", () => {
      state.isOffline = false;
      renderBannersAndHeader();
      loadData(state.selectedDate, true);
    });

    window.addEventListener("offline", () => {
      state.isOffline = true;
      renderBannersAndHeader();
    });

    window.addEventListener("resize", () => {
      renderAll();
    });

    if (els.entitySelect) {
      els.entitySelect.addEventListener("change", (e) => {
        state.selectedEntity = e.target.value;
        renderAll();
      });
    }

    if (els.searchInput) {
      els.searchInput.addEventListener("input", (e) => {
        state.searchQuery = e.target.value.trim();
        renderAll();
      });
    }

    if (els.btnClearFilter) {
      els.btnClearFilter.addEventListener("click", () => {
        state.selectedEntity = "";
        state.searchQuery = "";
        els.entitySelect.value = "";
        els.searchInput.value = "";
        renderAll();
      });
    }

    if (els.btnViewGrid) {
      els.btnViewGrid.addEventListener("click", () => switchView("grid"));
    }

    if (els.btnViewCards) {
      els.btnViewCards.addEventListener("click", () => switchView("cards"));
    }

    if (btnFs) btnFs.addEventListener("click", () => (kiosk.active ? stopKiosk() : startKiosk()));
    if (btnKioskExit) btnKioskExit.addEventListener("click", stopKiosk);
    if (document.addEventListener) {
      document.addEventListener("fullscreenchange", () => {
        if (!document.fullscreenElement && kiosk.active) stopKiosk();
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") stopKiosk();
      });
    }
    if (typeof window !== "undefined" && window.addEventListener) {
      ["wheel", "touchstart"].forEach((evt) =>
        window.addEventListener(
          evt,
          () => {
            if (kiosk.active) kiosk.pauseUntil = performance.now() + 6000;
          },
          { passive: true }
        )
      );
    }

    if ("serviceWorker" in navigator) {
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("./sw.js").catch(() => {});
      });
    }

    loadData("", false);
    setupLiveUpdates();
  }

  if (typeof window !== "undefined") {
    window.formatHoursList = formatHoursList;
    window.extractSubstitutingTeachers = extractSubstitutingTeachers;
    window.createTeacherPill = createTeacherPill;
    window.renderGridStrip = renderGridStrip;
    window.formatTeacherWithCode = formatTeacherWithCode;
    window.lookupTeacherCode = lookupTeacherCode;
    window.OFFICIAL_TEACHER_CODES = OFFICIAL_TEACHER_CODES;
    window.formatDateTimeCzech = formatDateTimeCzech;
    window.formatSourceBadgeText = formatSourceBadgeText;
    window.updateSourceBadge = updateSourceBadge;
    window.switchView = switchView;
    window.renderCards = renderCards;
    window.renderViewTabs = renderViewTabs;
    window.renderAll = renderAll;
    window.state = state;
    window.els = els;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      formatHoursList,
      extractSubstitutingTeachers,
      createTeacherPill,
      renderGridStrip,
      formatTeacherWithCode,
      lookupTeacherCode,
      OFFICIAL_TEACHER_CODES,
      formatDateTimeCzech,
      formatSourceBadgeText,
      updateSourceBadge,
      switchView,
      renderCards,
      renderViewTabs,
      renderAll,
      state,
      els
    };
  }
})();
