(function () {
  'use strict';

  // --- Layout- och Vy-rotation ---

  let layoutState = { currentIdx: 0, timer: null };
  let zoneStates = {}; // zoneId -> { currentIdx, timer, paused, activeViews, lastActiveKey }
  let isPaused = false;
  let isOffline = false;

  function _isViewActive(view, now) {
    const s = view.schedule_json;
    if (!s) return true;
    
    const type = s.type || 'always';
    if (type === 'always') return true;

    const currentTime = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
    if (s.time_start && currentTime < s.time_start) return false;
    if (s.time_end && currentTime >= s.time_end) return false;

    if (type === 'weekly') {
      const days = s.weekdays || [];
      const currentDay = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][now.getDay()];
      return days.includes(currentDay);
    }
    
    if (type === 'monthly') {
      return now.getDate() === s.day;
    }
    
    if (type === 'yearly') {
      return now.getDate() === s.day && (now.getMonth() + 1) === s.month;
    }
    
    if (type === 'dates') {
      const currentDate = now.getFullYear() + '-' + (now.getMonth() + 1).toString().padStart(2, '0') + '-' + now.getDate().toString().padStart(2, '0');
      return (s.dates || []).includes(currentDate);
    }

    return true;
  }

  function initRotation() {
    if (KIOSK_LAYOUTS && KIOSK_LAYOUTS.length > 1) {
      scheduleLayoutRotation();
    }
    startActiveLayoutZones();
  }

  function startActiveLayoutZones() {
    if (!KIOSK_LAYOUTS || !KIOSK_LAYOUTS[layoutState.currentIdx]) return;
    const layout = KIOSK_LAYOUTS[layoutState.currentIdx];

    layout.zones.forEach(function(zone) {
      if (zone.role === 'schedulable' && zone.views && zone.views.length > 0) {
        zoneStates[zone.id] = {
          currentIdx: 0,
          timer: null,
          paused: false,
          activeViews: [],
          lastActiveKey: ''
        };
        scheduleZone(zone.id);
      }
    });
  }

  function stopAllZones() {
    Object.keys(zoneStates).forEach(id => {
      clearTimeout(zoneStates[id].timer);
      delete zoneStates[id];
    });
  }

  function scheduleLayoutRotation() {
    clearTimeout(layoutState.timer);
    const layout = KIOSK_LAYOUTS[layoutState.currentIdx];
    if (!layout || !layout.duration_seconds || KIOSK_LAYOUTS.length <= 1) return;

    layoutState.timer = setTimeout(function() {
      if (isPaused) return;
      rotateLayout();
    }, layout.duration_seconds * 1000);
  }

  function rotateLayout() {
    const prevIdx = layoutState.currentIdx;
    const nextIdx = (prevIdx + 1) % KIOSK_LAYOUTS.length;
    
    const prevLayout = KIOSK_LAYOUTS[prevIdx];
    const prevPanel = document.getElementById('layout-panel-' + prevIdx);
    const nextPanel = document.getElementById('layout-panel-' + nextIdx);
    
    if (!prevPanel || !nextPanel) return;

    // Stoppa gamla zon-rotationer
    stopAllZones();
    clearTimeout(layoutState.timer);

    const transition = prevLayout.transition || 'fade';
    const transMs = prevLayout.transition_duration_ms || 700;
    const direction = prevLayout.transition_direction || 'left';

    if (transition === 'fade') {
      nextPanel.style.opacity = '0';
      nextPanel.style.zIndex = '10';
      nextPanel.style.transform = 'translateX(0)';
      nextPanel.classList.add('active');
      
      void nextPanel.offsetWidth; // Force reflow
      nextPanel.style.transition = 'opacity ' + transMs + 'ms ease';
      nextPanel.style.opacity = '1';

      setTimeout(finish, transMs);
    } else if (transition === 'slide') {
      nextPanel.style.transition = 'none';
      prevPanel.style.transition = 'none';

      let startNext = '', endPrev = '';
      if (direction === 'left') {
        startNext = 'translateX(100%)';
        endPrev = 'translateX(-100%)';
      } else if (direction === 'right') {
        startNext = 'translateX(-100%)';
        endPrev = 'translateX(100%)';
      } else if (direction === 'up') {
        startNext = 'translateY(100%)';
        endPrev = 'translateY(-100%)';
      } else if (direction === 'down') {
        startNext = 'translateY(-100%)';
        endPrev = 'translateY(100%)';
      }

      nextPanel.style.transform = startNext;
      nextPanel.style.opacity = '1';
      nextPanel.style.zIndex = '10';
      nextPanel.classList.add('active');
      
      void nextPanel.offsetWidth; // Force reflow
      nextPanel.style.transition = 'transform ' + transMs + 'ms ease';
      prevPanel.style.transition = 'transform ' + transMs + 'ms ease';
      
      nextPanel.style.transform = 'translate(0, 0)';
      prevPanel.style.transform = endPrev;

      setTimeout(finish, transMs);
    } else { // none
      finish();
    }

    function finish() {
      // Frys transitionerna innan klassändringar
      prevPanel.style.transition = 'none';
      nextPanel.style.transition = 'none';
      void prevPanel.offsetHeight; // reflow

      prevPanel.classList.remove('active');

      // Dölj prev — lämna transform orörd så den stannar off-screen
      prevPanel.style.opacity = '0';
      prevPanel.style.zIndex = '';

      // Rensa next-panel inline-styles (CSS .active tar över)
      nextPanel.style.opacity = '';
      nextPanel.style.transform = '';
      nextPanel.style.zIndex = '';

      // Återställ CSS-transitionerna i nästa frame
      requestAnimationFrame(function() {
        prevPanel.style.transition = '';
        nextPanel.style.transition = '';
      });

      layoutState.currentIdx = nextIdx;
      startActiveLayoutZones();
      scheduleLayoutRotation();
    }
  }

  // --- Zon-logik ---

  function showZoneView(zoneId, idx) {
    if (!KIOSK_LAYOUTS || !KIOSK_LAYOUTS[layoutState.currentIdx]) return;
    const layout = KIOSK_LAYOUTS[layoutState.currentIdx];
    const zone = layout.zones.find(z => z.id === zoneId);
    if (!zone || !zoneStates[zoneId]) return;

    const state = zoneStates[zoneId];
    const views = state.activeViews || zone.views;
    if (!views.length) return;

    const prevIdx = state.currentIdx;
    state.currentIdx = idx % views.length;

    const nextView = views[state.currentIdx];
    const nextEl = document.getElementById('z' + zoneId + '-v' + nextView.position);
    if (!nextEl) return;

    const transition = nextView.transition || zone.transition || 'fade';
    const transitionDir = nextView.transition_direction || zone.transition_direction || 'left';
    const transMs = nextView.transition_duration_ms || zone.transition_duration_ms || 700;

    if (transition === 'slide') {
      const leavingEl = document.getElementById('z' + zoneId + '-v' + views[prevIdx].position);
      const zoneEl = document.querySelector('.zone[data-zone-id="' + zoneId + '"]');
      
      // Reset classes
      zone.views.forEach(v => {
        const el = document.getElementById('z' + zoneId + '-v' + v.position);
        if (el) {
          el.classList.remove('active', 'view-entering', 'view-leaving');
          el.style.transitionDuration = '';
        }
      });

      if (zoneEl) {
        zoneEl.setAttribute('data-vt-dir', transitionDir);
        zoneEl.classList.add('zone-sliding');
      }

      if (leavingEl && leavingEl !== nextEl) {
        leavingEl.style.transitionDuration = transMs + 'ms';
        leavingEl.classList.add('view-leaving');
      }
      nextEl.style.transitionDuration = transMs + 'ms';
      nextEl.classList.add('view-entering', 'active');
      nextEl.style.opacity = '1';

      setTimeout(function() {
        if (leavingEl) {
          leavingEl.style.transition = 'none';
          leavingEl.style.opacity = '0';
          leavingEl.style.transitionDuration = '';
          void leavingEl.offsetHeight;
          leavingEl.classList.remove('view-leaving');
          requestAnimationFrame(function() { leavingEl.style.removeProperty('transition'); });
        }
        nextEl.classList.remove('view-entering');
        nextEl.style.transitionDuration = '';
        if (zoneEl) zoneEl.classList.remove('zone-sliding');
      }, transMs);
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
      nextEl.style.opacity = '1';
      zone.views.forEach((v) => {
        if (v.position !== nextView.position) {
          const el = document.getElementById('z' + zoneId + '-v' + v.position);
          if (el) el.style.opacity = '0';
        }
      });
    }
  }

  function scheduleZone(zoneId) {
    if (!KIOSK_LAYOUTS || !KIOSK_LAYOUTS[layoutState.currentIdx]) return;
    const layout = KIOSK_LAYOUTS[layoutState.currentIdx];
    const zone = layout.zones.find(z => z.id === zoneId);
    const state = zoneStates[zoneId];
    if (!zone || !state) return;

    clearTimeout(state.timer);
    if (state.paused) return;

    const now = new Date();
    const activeViews = zone.views.filter(v => _isViewActive(v, now));
    const activeKey = JSON.stringify(activeViews.map(v => v.position));

    if (activeViews.length === 0) {
      state.activeViews = [];
      state.lastActiveKey = '';
      return;
    }

    if (activeKey !== state.lastActiveKey) {
      const isFirst = !state.lastActiveKey;
      state.activeViews = activeViews;
      state.lastActiveKey = activeKey;
      state.currentIdx = 0;
      if (isFirst) {
        zone.views.forEach(v => {
          const el = document.getElementById('z' + zoneId + '-v' + v.position);
          if (el) { el.classList.remove('active'); el.style.opacity = '0'; }
        });
        const firstEl = document.getElementById('z' + zoneId + '-v' + activeViews[0].position);
        if (firstEl) { firstEl.classList.add('active'); firstEl.style.opacity = '1'; }
      } else {
        showZoneView(zoneId, 0);
      }
    }

    const currentView = state.activeViews[state.currentIdx];
    const duration = currentView.duration_seconds || zone.rotation_seconds || 30;
    state.nextAt = Date.now() + duration * 1000;

    state.timer = setTimeout(function() {
      const nextIdx = (state.currentIdx + 1) % state.activeViews.length;
      showZoneView(zoneId, nextIdx);
      scheduleZone(zoneId);
    }, duration * 1000);
  }

  function checkSchedules() {
    if (!KIOSK_LAYOUTS || !KIOSK_LAYOUTS[layoutState.currentIdx]) return;
    const layout = KIOSK_LAYOUTS[layoutState.currentIdx];
    layout.zones.forEach(function(zone) {
      if (zone.role === 'schedulable' && zoneStates[zone.id]) {
        scheduleZone(zone.id);
      }
    });
  }

  setInterval(checkSchedules, 60000);

  function nextZoneView(zoneId) {
    if (!KIOSK_LAYOUTS || !KIOSK_LAYOUTS[layoutState.currentIdx]) return;
    const layout = KIOSK_LAYOUTS[layoutState.currentIdx];
    const zone = layout.zones.find(z => z.id === zoneId);
    const state = zoneStates[zoneId];
    if (!zone || !state || !state.activeViews.length) return;
    const nextIdx = (state.currentIdx + 1) % state.activeViews.length;
    showZoneView(zoneId, nextIdx);
  }

  function prevZoneView(zoneId) {
    if (!KIOSK_LAYOUTS || !KIOSK_LAYOUTS[layoutState.currentIdx]) return;
    const layout = KIOSK_LAYOUTS[layoutState.currentIdx];
    const zone = layout.zones.find(z => z.id === zoneId);
    const state = zoneStates[zoneId];
    if (!zone || !state || !state.activeViews.length) return;
    const prevIdx = (state.currentIdx - 1 + state.activeViews.length) % state.activeViews.length;
    showZoneView(zoneId, prevIdx);
  }

  // --- Gemensamma kontroller ---

  function pauseAll() {
    isPaused = true;
    clearTimeout(layoutState.timer);
    Object.keys(zoneStates).forEach(id => {
      zoneStates[id].paused = true;
      clearTimeout(zoneStates[id].timer);
    });
  }

  function resumeAll() {
    isPaused = false;
    if (KIOSK_LAYOUTS && KIOSK_LAYOUTS.length > 1) scheduleLayoutRotation();
    Object.keys(zoneStates).forEach(id => {
      zoneStates[id].paused = false;
      scheduleZone(parseInt(id));
    });
  }

  function stepAll(direction) {
    Object.keys(zoneStates).forEach(id => {
      if (direction === 'next') nextZoneView(parseInt(id));
      else prevZoneView(parseInt(id));
      if (!zoneStates[id].paused) scheduleZone(parseInt(id));
    });
  }

  // --- Per-zon-navigation (debug=1) ---

  document.querySelectorAll('.zone-nav-prev').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      const zoneId = parseInt(btn.dataset.zoneId);
      prevZoneView(zoneId);
      if (zoneStates[zoneId] && !zoneStates[zoneId].paused) scheduleZone(zoneId);
    });
  });

  document.querySelectorAll('.zone-nav-next').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      const zoneId = parseInt(btn.dataset.zoneId);
      nextZoneView(zoneId);
      if (zoneStates[zoneId] && !zoneStates[zoneId].paused) scheduleZone(zoneId);
    });
  });

  document.querySelectorAll('.zone-nav-pause').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      const zoneId = parseInt(btn.dataset.zoneId);
      const state = zoneStates[zoneId];
      if (!state) return;
      if (state.paused) {
        state.paused = false;
        btn.innerHTML = '&#9646;&#9646;';
        scheduleZone(zoneId);
      } else {
        state.paused = true;
        clearTimeout(state.timer);
        btn.innerHTML = '&#9654;';
      }
      isPaused = state.paused;
    });
  });

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
        if (isPaused || userPaused || el.scrollHeight <= el.clientHeight) return;
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
    if (isPaused) return;
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
      isOffline = false;
      if (offlineBanner) offlineBanner.classList.remove('visible');
      if (pendingReload) {
        pendingReload = false;
        location.reload();
      } else {
        // Vi behöver inte resumeAll() här längre om vi inte pausar vid offline
      }
    };

    eventSource.addEventListener('connected', function (e) {
      lastEventAt = Date.now();
    });

    eventSource.addEventListener('keepalive', function () {
      lastEventAt = Date.now();
    });

    eventSource.addEventListener('reload', function () {
      lastEventAt = Date.now();
      location.reload();
    });

    eventSource.addEventListener('goto_view', function (e) {
      lastEventAt = Date.now();
      var data = JSON.parse(e.data);
      if (data.zone_id && KIOSK_LAYOUTS) {
        const layout = KIOSK_LAYOUTS[layoutState.currentIdx];
        const zone = layout.zones.find(z => z.id === data.zone_id);
        if (zone) {
          const viewIdx = zone.views.findIndex(v => v.position === data.position);
          if (viewIdx !== -1) {
            showZoneView(data.zone_id, viewIdx);
            if (zoneStates[data.zone_id] && !zoneStates[data.zone_id].paused) scheduleZone(data.zone_id);
          }
        }
      } else {
        stepAll('next');
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
      isOffline = true;
      if (offlineBanner && typeof SHOW_OFFLINE_BANNER !== 'undefined' && SHOW_OFFLINE_BANNER) {
        offlineBanner.classList.add('visible');
      }
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

  function updateDebugReconnects() {
    var el = document.getElementById('debug-reconnects');
    if (el) el.textContent = 'Reconnects: ' + reconnectCount;
  }

  if (window.__KIOSK_DEBUG) {
    setInterval(function () {
      var sseEl = document.getElementById('debug-sse');
      if (sseEl) {
        var s = Math.round((Date.now() - lastEventAt) / 1000);
        var color = s < 15 ? '#4ade80' : s < 60 ? '#facc15' : '#f87171';
        sseEl.textContent = 'SSE ' + s + 's sedan';
        sseEl.style.color = color;
      }
    }, 1000);
  }

  // --- Start ---

  const startDelay = (typeof LAYOUT_ROTATION !== 'undefined' && LAYOUT_ROTATION.transition_duration_ms) || 700;
  setTimeout(initRotation, startDelay);
  connectSSE();
})();
