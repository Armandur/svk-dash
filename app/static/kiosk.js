(function () {
  'use strict';

  // --- Vy-rotation (Zon-baserad eller Legacy) ---

  let zoneStates = {}; // zoneId -> { currentIdx, timer, paused }
  let legacyState = { currentPosition: 0, timer: null, paused: false };
  let isLegacy = (typeof KIOSK_ZONES === 'undefined' || KIOSK_ZONES === null);

  function initRotation() {
    if (!isLegacy) {
      KIOSK_ZONES.forEach(function(zone) {
        if (zone.role === 'schedulable' && zone.views && zone.views.length > 1) {
          zoneStates[zone.id] = {
            currentIdx: 0,
            timer: null,
            paused: false
          };
          scheduleZone(zone.id);
        }
      });
    } else {
      if (LEGACY_VIEWS && LEGACY_VIEWS.length > 1) {
        scheduleLegacy();
      }
    }
    if (window.__KIOSK_DEBUG) updateDebugView();
  }

  // --- Zon-logik ---

  function showZoneView(zoneId, idx) {
    const zone = KIOSK_ZONES.find(z => z.id === zoneId);
    if (!zone || !zoneStates[zoneId]) return;

    const state = zoneStates[zoneId];
    const prevIdx = state.currentIdx;
    state.currentIdx = idx;

    const views = zone.views;
    const nextView = views[idx];
    const nextEl = document.getElementById('z' + zoneId + '-v' + nextView.position);
    if (!nextEl) return;

    const transition = zone.transition || 'fade';
    const transitionDir = zone.transition_direction || 'left';

    if (transition === 'slide') {
      const leavingEl = document.getElementById('z' + zoneId + '-v' + views[prevIdx].position);
      
      // Setup classes for slide animation
      // Note: We use the same CSS classes as legacy slide but scoped to the zone
      // Since .view is position absolute inset 0, it works within the zone's div
      
      // Reset classes
      zone.views.forEach(v => {
        const el = document.getElementById('z' + zoneId + '-v' + v.position);
        if (el) el.classList.remove('active', 'view-entering', 'view-leaving');
      });

      // Set direction on body or zone? The CSS expects it on body vt-dir
      // We'll temporarily set it on body or just use the default
      document.body.setAttribute('data-vt-dir', transitionDir);
      document.body.className = 'vt-slide';

      if (leavingEl && leavingEl !== nextEl) leavingEl.classList.add('view-leaving');
      nextEl.classList.add('view-entering', 'active');
      nextEl.style.opacity = '1';

      setTimeout(function() {
        if (leavingEl) {
          leavingEl.classList.remove('view-leaving');
          leavingEl.style.opacity = '0';
        }
        nextEl.classList.remove('view-entering');
      }, 700);
    } else if (transition === 'none') {
      zone.views.forEach(v => {
        const el = document.getElementById('z' + zoneId + '-v' + v.position);
        if (el) {
          el.classList.remove('active');
          el.style.opacity = '0';
        }
      });
      nextEl.classList.add('active');
      nextEl.style.opacity = '1';
    } else { // fade (default)
      zone.views.forEach(v => {
        const el = document.getElementById('z' + zoneId + '-v' + v.position);
        if (el) el.classList.remove('active');
      });
      nextEl.classList.add('active');
      // CSS handles the opacity transition for .view
      // But we need to make sure the inline style from template doesn't override it forever
      nextEl.style.opacity = '1';
      zone.views.forEach((v, i) => {
        if (i !== idx) {
          const el = document.getElementById('z' + zoneId + '-v' + v.position);
          if (el) el.style.opacity = '0';
        }
      });
    }

    if (window.__KIOSK_DEBUG) updateDebugView();
  }

  function scheduleZone(zoneId) {
    const zone = KIOSK_ZONES.find(z => z.id === zoneId);
    const state = zoneStates[zoneId];
    if (!zone || !state) return;

    clearTimeout(state.timer);
    if (state.paused) return;

    const currentView = zone.views[state.currentIdx];
    const duration = currentView.duration_seconds || zone.rotation_seconds || 30;

    state.timer = setTimeout(function() {
      const nextIdx = (state.currentIdx + 1) % zone.views.length;
      showZoneView(zoneId, nextIdx);
      scheduleZone(zoneId);
    }, duration * 1000);
  }

  function nextZoneView(zoneId) {
    const zone = KIOSK_ZONES.find(z => z.id === zoneId);
    const state = zoneStates[zoneId];
    if (!zone || !state) return;
    const nextIdx = (state.currentIdx + 1) % zone.views.length;
    showZoneView(zoneId, nextIdx);
  }

  function prevZoneView(zoneId) {
    const zone = KIOSK_ZONES.find(z => z.id === zoneId);
    const state = zoneStates[zoneId];
    if (!zone || !state) return;
    const prevIdx = (state.currentIdx - 1 + zone.views.length) % zone.views.length;
    showZoneView(zoneId, prevIdx);
  }

  // --- Legacy-logik ---

  function showLegacyView(position) {
    var tr = (typeof SCREEN_TRANSITION !== 'undefined') ? SCREEN_TRANSITION : 'fade';
    var nextEl = document.getElementById('view-' + position);
    if (!nextEl) return;

    if (tr === 'slide') {
      var leavingEl = document.getElementById('view-' + legacyState.currentPosition);
      document.querySelectorAll('.view').forEach(function (el) {
        el.classList.remove('active', 'view-entering', 'view-leaving');
      });
      if (leavingEl && leavingEl !== nextEl) leavingEl.classList.add('view-leaving');
      nextEl.classList.add('view-entering', 'active');
      var _lv = leavingEl;
      setTimeout(function () {
        if (_lv) _lv.classList.remove('view-leaving');
        nextEl.classList.remove('view-entering');
      }, 700);
    } else {
      document.querySelectorAll('.view').forEach(function (el) {
        el.classList.remove('active');
      });
      nextEl.classList.add('active');
    }

    legacyState.currentPosition = position;
    if (window.__KIOSK_DEBUG) updateDebugView();
  }

  function scheduleLegacy() {
    clearTimeout(legacyState.timer);
    if (!LEGACY_VIEWS || LEGACY_VIEWS.length <= 1 || legacyState.paused) return;
    var duration = (LEGACY_VIEWS[legacyState.currentPosition] && LEGACY_VIEWS[legacyState.currentPosition].duration_seconds) || 30;
    legacyState.timer = setTimeout(function () {
      var nextPos = (legacyState.currentPosition + 1) % LEGACY_VIEWS.length;
      showLegacyView(nextPos);
      scheduleLegacy();
    }, duration * 1000);
  }

  // --- Gemensamma kontroller ---

  function pauseAll() {
    if (!isLegacy) {
      Object.keys(zoneStates).forEach(id => {
        zoneStates[id].paused = true;
        clearTimeout(zoneStates[id].timer);
      });
    } else {
      legacyState.paused = true;
      clearTimeout(legacyState.timer);
    }
  }

  function resumeAll() {
    if (!isLegacy) {
      Object.keys(zoneStates).forEach(id => {
        zoneStates[id].paused = false;
        scheduleZone(parseInt(id));
      });
    } else {
      legacyState.paused = false;
      scheduleLegacy();
    }
  }

  function stepAll(direction) {
    if (!isLegacy) {
      Object.keys(zoneStates).forEach(id => {
        if (direction === 'next') nextZoneView(parseInt(id));
        else prevZoneView(parseInt(id));
        if (!zoneStates[id].paused) scheduleZone(parseInt(id));
      });
    } else {
      const count = LEGACY_VIEWS.length;
      if (direction === 'next') {
        showLegacyView((legacyState.currentPosition + 1) % count);
      } else {
        showLegacyView((legacyState.currentPosition - 1 + count) % count);
      }
      if (!legacyState.paused) scheduleLegacy();
    }
  }

  // --- Kiosk-navigation ---

  var navOverlay = document.getElementById('kiosk-nav');
  var navHideTimer = null;
  var navPaused = false;

  function showNav() {
    if (!navOverlay) return;
    navOverlay.classList.add('visible');
    clearTimeout(navHideTimer);
    navHideTimer = setTimeout(hideNav, 3000);
  }

  function hideNav() {
    if (!navOverlay) return;
    navOverlay.classList.remove('visible');
  }

  document.addEventListener('mousemove', showNav);
  document.addEventListener('touchstart', showNav, { passive: true });

  var pauseBtn = document.getElementById('nav-pause');
  if (pauseBtn) {
    pauseBtn.addEventListener('click', function () {
      if (navPaused) {
        navPaused = false;
        pauseBtn.innerHTML = '&#9646;&#9646;';
        resumeAll();
      } else {
        navPaused = true;
        pauseBtn.innerHTML = '&#9654;';
        pauseAll();
      }
    });
  }

  var prevBtn = document.getElementById('nav-prev');
  if (prevBtn) {
    prevBtn.addEventListener('click', function () {
      stepAll('prev');
    });
  }

  var nextBtn = document.getElementById('nav-next');
  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      stepAll('next');
    });
  }

  // --- Klocka ---

  function tickClocks() {
    var now = new Date();
    document.querySelectorAll('[data-clock-format]').forEach(function (el) {
      var fmt      = el.dataset.clockFormat || 'time_date';
      var tz       = el.dataset.clockTimezone || 'Europe/Stockholm';
      var locale   = el.dataset.clockLocale || 'sv-SE';
      var opts     = { timeZone: tz };
      var timeEl   = el.querySelector('.clock-time');
      var dateEl   = el.querySelector('.clock-date');

      if (timeEl && (fmt === 'time_only' || fmt === 'time_date' || fmt === 'day_time')) {
        timeEl.textContent = now.toLocaleTimeString(locale, Object.assign({}, opts,
          { hour: '2-digit', minute: '2-digit', second: fmt === 'day_time' ? undefined : '2-digit' }));
      }
      if (dateEl && (fmt === 'date_only' || fmt === 'time_date')) {
        dateEl.textContent = now.toLocaleDateString(locale, Object.assign({}, opts,
          { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }));
      }
      if (dateEl && fmt === 'day_time') {
        dateEl.textContent = now.toLocaleDateString(locale, Object.assign({}, opts,
          { weekday: 'long', day: 'numeric', month: 'long' }));
      }
    });
  }

  setInterval(tickClocks, 1000);
  tickClocks();

  // --- Auto-scroll (ics_list) ---

  (function () {
    var PAUSE_MS = 3000;

    document.querySelectorAll('[data-autoscroll]').forEach(function (el) {
      var speed = parseFloat(el.dataset.autoscroll) || 30; // px/s
      var userPaused = false;
      var state = 'pause-top'; // 'scrolling' | 'pause-top' | 'pause-bottom'
      var lastTs = null;
      var pauseUntil = performance.now() + PAUSE_MS;

      el.addEventListener('touchstart', function () {
        userPaused = true;
      }, { passive: true });
      el.addEventListener('touchend', function () {
        setTimeout(function () {
          userPaused = false;
          lastTs = null;
          state = 'pause-top';
          el.scrollTop = 0;
          pauseUntil = performance.now() + PAUSE_MS;
        }, 2000);
      }, { passive: true });

      function step(ts) {
        requestAnimationFrame(step);
        if (userPaused || el.scrollHeight <= el.clientHeight) return;
        if (lastTs === null) lastTs = ts;
        var dt = (ts - lastTs) / 1000;
        lastTs = ts;

        if (state === 'pause-top' || state === 'pause-bottom') {
          if (ts >= pauseUntil) state = state === 'pause-top' ? 'scrolling' : 'pause-reset';
          return;
        }
        if (state === 'pause-reset') {
          el.scrollTop = 0;
          state = 'pause-top';
          pauseUntil = ts + PAUSE_MS;
          return;
        }
        el.scrollTop += speed * dt;
        if (el.scrollTop + el.clientHeight >= el.scrollHeight - 1) {
          state = 'pause-bottom';
          pauseUntil = ts + PAUSE_MS;
        }
      }

      requestAnimationFrame(step);
    });
  })();

  // --- Tidslinje (ics_schedule) ---

  function updateNowLines() {
    var now = new Date();
    var nowMin = now.getHours() * 60 + now.getMinutes();
    document.querySelectorAll('[data-now-start]').forEach(function (col) {
      var startH = parseInt(col.dataset.nowStart, 10);
      var endH   = parseInt(col.dataset.nowEnd, 10);
      var totalMin = (endH - startH) * 60;
      var offset   = nowMin - startH * 60;
      var topPct   = (100 * offset / totalMin).toFixed(4) + '%';
      var hidden   = offset < 0 || offset > totalMin;

      var line = col.querySelector('.isch-now-line');
      var dot  = col.querySelector('.isch-now-dot');
      if (line) { line.style.display = hidden ? 'none' : ''; if (!hidden) line.style.top = topPct; }
      if (dot)  { dot.style.display  = hidden ? 'none' : ''; if (!hidden) dot.style.top  = topPct; }
    });
  }

  updateNowLines();
  setInterval(updateNowLines, 60000);

  // --- SSE ---

  var lastEventAt = Date.now();
  var reconnectCount = 0;
  var backoffMs = 1000;
  var pendingReload = false;
  var offlineBanner = document.getElementById('offline-banner');
  var eventSource = null;

  function connectSSE() {
    if (eventSource) { eventSource.close(); eventSource = null; }

    eventSource = new EventSource('/s/' + SCREEN_SLUG + '/events');

    eventSource.onopen = function () {
      lastEventAt = Date.now();
      backoffMs = 1000;
      offlineBanner.classList.remove('visible');
      if (pendingReload) {
        pendingReload = false;
        location.reload();
      } else {
        resumeAll();
      }
    };

    eventSource.addEventListener('connected', function (e) {
      lastEventAt = Date.now();
    });

    eventSource.addEventListener('reload', function () {
      lastEventAt = Date.now();
      location.reload();
    });

    eventSource.addEventListener('goto_view', function (e) {
      lastEventAt = Date.now();
      var data = JSON.parse(e.data);
      if (data.zone_id && !isLegacy) {
        const zone = KIOSK_ZONES.find(z => z.id === data.zone_id);
        if (zone) {
          const viewIdx = zone.views.findIndex(v => v.position === data.position);
          if (viewIdx !== -1) {
            showZoneView(data.zone_id, viewIdx);
            if (!zoneStates[data.zone_id].paused) scheduleZone(data.zone_id);
          }
        }
      } else {
        if (!isLegacy) {
          stepAll('next');
        } else {
          showLegacyView(data.position);
          if (!legacyState.paused) scheduleLegacy();
        }
      }
    });

    eventSource.addEventListener('config_changed', function () {
      lastEventAt = Date.now();
      pendingReload = true;
      pauseAll();
      location.reload();
    });

    eventSource.addEventListener('widget_updated', function (e) {
      lastEventAt = Date.now();
      var data = JSON.parse(e.data);
      fetchWidgetUpdate(data.widget_id);
    });

    eventSource.onmessage = function () {
      lastEventAt = Date.now();
    };

    eventSource.onerror = function () {
      eventSource.close();
      eventSource = null;
      reconnectCount++;
      if (window.__KIOSK_DEBUG) updateDebugReconnects();
      backoffMs = Math.min(backoffMs * 2, 60000);
      setTimeout(connectSSE, backoffMs);
    };
  }

  setInterval(function () {
    if (Date.now() - lastEventAt > 90000) {
      offlineBanner.classList.add('visible');
      pauseAll();
    }
  }, 10000);

  // --- Widget-uppdatering ---

  function fetchWidgetUpdate(widgetId) {
    fetch('/api/widget/' + widgetId + '/data')
      .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
      .then(function (html) {
        document.querySelectorAll('[data-widget-id="' + widgetId + '"]').forEach(function (el) {
          el.innerHTML = html;
        });
      })
      .catch(function () { /* behåll befintlig DOM vid fel */ });
  }

  // --- Debug ---

  function updateDebugView() {
    var el = document.getElementById('debug-view');
    if (!el) return;
    if (isLegacy) {
      el.textContent = 'Vy ' + (legacyState.currentPosition + 1) + '/' + (LEGACY_VIEWS ? LEGACY_VIEWS.length : 0);
    } else {
      let status = Object.keys(zoneStates).map(id => {
        const z = KIOSK_ZONES.find(zone => zone.id == id);
        return 'Z' + id + ':' + (zoneStates[id].currentIdx + 1) + '/' + z.views.length;
      }).join(' ');
      el.textContent = status || 'Zon-läge';
    }
  }

  function updateDebugReconnects() {
    var el = document.getElementById('debug-reconnects');
    if (el) el.textContent = 'Reconnects: ' + reconnectCount;
  }

  if (window.__KIOSK_DEBUG) {
    setInterval(function () {
      var el = document.getElementById('debug-sse-age');
      if (el) {
        var s = Math.round((Date.now() - lastEventAt) / 1000);
        el.textContent = 'SSE: ' + s + 's sedan';
      }
    }, 1000);
  }

  // --- Start ---

  initRotation();
  connectSSE();
})();
