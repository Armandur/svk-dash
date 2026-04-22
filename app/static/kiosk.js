(function () {
  'use strict';

  // --- Vy-rotation ---

  let currentPosition = 0;
  let rotationTimer = null;
  let rotationPaused = false;

  function showView(position) {
    document.querySelectorAll('.view').forEach(function (el) {
      el.classList.remove('active');
    });
    var el = document.getElementById('view-' + position);
    if (el) {
      el.classList.add('active');
      currentPosition = position;
    }
    if (window.__KIOSK_DEBUG) updateDebugView();
  }

  function nextView() {
    showView((currentPosition + 1) % VIEW_COUNT);
  }

  function scheduleNext() {
    clearTimeout(rotationTimer);
    if (VIEW_COUNT <= 1 || rotationPaused) return;
    var duration = (VIEWS[currentPosition] && VIEWS[currentPosition].duration) || 30;
    rotationTimer = setTimeout(function () {
      nextView();
      scheduleNext();
    }, duration * 1000);
  }

  function pauseRotation() {
    rotationPaused = true;
    clearTimeout(rotationTimer);
  }

  function resumeRotation() {
    rotationPaused = false;
    scheduleNext();
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
        resumeRotation();
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
      showView(data.position);
      scheduleNext();
    });

    eventSource.addEventListener('config_changed', function () {
      lastEventAt = Date.now();
      // Ladda inte om direkt — vänta tills SSE är uppkopplad (redan är vi det)
      pendingReload = true;
      pauseRotation();
      // Reload sker vid nästa onopen om anslutningen bryts, annars omedelbart
      location.reload();
    });

    eventSource.addEventListener('widget_updated', function (e) {
      lastEventAt = Date.now();
      var data = JSON.parse(e.data);
      fetchWidgetUpdate(data.widget_id);
    });

    // Kommentarer (keepalive) räknas som aktivitet
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

  // Offline-detektion: om ingen SSE-aktivitet på >90s
  setInterval(function () {
    if (Date.now() - lastEventAt > 90000) {
      offlineBanner.classList.add('visible');
      pauseRotation();
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
    if (el) el.textContent = 'Vy ' + (currentPosition + 1) + '/' + VIEW_COUNT;
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

  showView(0);
  scheduleNext();
  connectSSE();
})();
