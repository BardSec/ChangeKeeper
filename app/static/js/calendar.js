// Calendar view for changes

var currentYear, currentMonth;
var eventsCache = {};

var MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
];

document.addEventListener('DOMContentLoaded', function() {
    var now = new Date();
    currentYear = now.getFullYear();
    currentMonth = now.getMonth() + 1; // 1-indexed

    document.getElementById('prevMonth').addEventListener('click', function() {
        currentMonth--;
        if (currentMonth < 1) { currentMonth = 12; currentYear--; }
        loadMonth();
    });

    document.getElementById('nextMonth').addEventListener('click', function() {
        currentMonth++;
        if (currentMonth > 12) { currentMonth = 1; currentYear++; }
        loadMonth();
    });

    loadMonth();
});

function loadMonth() {
    var key = currentYear + '-' + currentMonth;
    document.getElementById('calendarTitle').textContent =
        MONTH_NAMES[currentMonth - 1] + ' ' + currentYear;

    closeDayDetail();

    if (eventsCache[key]) {
        renderCalendar(eventsCache[key]);
        return;
    }

    fetch('/changes/calendar/events?year=' + currentYear + '&month=' + currentMonth, {
        headers: {'Accept': 'application/json'}
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        eventsCache[key] = data.events;
        renderCalendar(data.events);
    })
    .catch(function() {
        renderCalendar([]);
    });
}

function renderCalendar(events) {
    var body = document.getElementById('calendarBody');
    body.innerHTML = '';

    // Group events by date
    var byDate = {};
    events.forEach(function(ev) {
        if (!byDate[ev.date]) byDate[ev.date] = [];
        byDate[ev.date].push(ev);
    });

    // Calculate grid
    var firstDay = new Date(currentYear, currentMonth - 1, 1).getDay(); // 0=Sun
    var daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
    var today = new Date();
    var todayStr = today.getFullYear() + '-' +
        String(today.getMonth() + 1).padStart(2, '0') + '-' +
        String(today.getDate()).padStart(2, '0');

    // Build rows
    var totalCells = firstDay + daysInMonth;
    var rows = Math.ceil(totalCells / 7);

    for (var row = 0; row < rows; row++) {
        var weekEl = document.createElement('div');
        weekEl.className = 'calendar-week';

        for (var col = 0; col < 7; col++) {
            var cellIndex = row * 7 + col;
            var dayNum = cellIndex - firstDay + 1;
            var cell = document.createElement('div');

            if (dayNum < 1 || dayNum > daysInMonth) {
                cell.className = 'calendar-cell calendar-cell-empty';
            } else {
                var dateStr = currentYear + '-' +
                    String(currentMonth).padStart(2, '0') + '-' +
                    String(dayNum).padStart(2, '0');
                var dayEvents = byDate[dateStr] || [];

                cell.className = 'calendar-cell';
                if (dateStr === todayStr) cell.className += ' calendar-cell-today';
                if (dayEvents.length > 0) cell.className += ' calendar-cell-has-events';

                var numEl = document.createElement('div');
                numEl.className = 'calendar-cell-number';
                numEl.textContent = dayNum;
                cell.appendChild(numEl);

                if (dayEvents.length > 0) {
                    var dotsEl = document.createElement('div');
                    dotsEl.className = 'calendar-cell-dots';

                    // Show up to 3 event dots, color by impact
                    var shown = Math.min(dayEvents.length, 3);
                    for (var i = 0; i < shown; i++) {
                        var dot = document.createElement('span');
                        dot.className = 'event-dot dot-' + dayEvents[i].impact.toLowerCase();
                        dot.title = dayEvents[i].title;
                        dotsEl.appendChild(dot);
                    }
                    if (dayEvents.length > 3) {
                        var more = document.createElement('span');
                        more.className = 'event-dot-more';
                        more.textContent = '+' + (dayEvents.length - 3);
                        dotsEl.appendChild(more);
                    }
                    cell.appendChild(dotsEl);

                    // Show first event title preview
                    var preview = document.createElement('div');
                    preview.className = 'calendar-cell-preview';
                    preview.textContent = dayEvents[0].title;
                    cell.appendChild(preview);

                    if (dayEvents.length > 1) {
                        var countEl = document.createElement('div');
                        countEl.className = 'calendar-cell-count';
                        countEl.textContent = dayEvents.length + ' changes';
                        cell.appendChild(countEl);
                    }

                    cell.addEventListener('click', (function(date, evts) {
                        return function() { showDayDetail(date, evts); };
                    })(dateStr, dayEvents));
                }
            }

            weekEl.appendChild(cell);
        }

        body.appendChild(weekEl);
    }
}

function showDayDetail(dateStr, events) {
    var panel = document.getElementById('dayDetail');
    var parts = dateStr.split('-');
    var d = new Date(parts[0], parts[1] - 1, parts[2]);
    var dayName = d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });

    document.getElementById('dayDetailTitle').textContent = dayName;

    var list = document.getElementById('dayDetailList');
    list.innerHTML = '';

    events.forEach(function(ev) {
        var item = document.createElement('a');
        item.href = '/changes/' + ev.id;
        item.className = 'day-detail-item';

        var badge = ev.change_type === 'quick' ? '<span class="badge badge-type-quick">Quick</span>' : '';
        var impactClass = 'badge-impact-' + ev.impact.toLowerCase();

        item.innerHTML =
            '<div class="day-detail-item-header">' +
                '<span class="day-detail-item-title">' + escapeHtml(ev.title) + '</span>' +
                badge +
            '</div>' +
            '<div class="day-detail-item-meta">' +
                '<span class="badge badge-category">' + escapeHtml(ev.category) + '</span>' +
                '<span class="badge ' + impactClass + '">' + escapeHtml(ev.impact) + '</span>' +
                '<span class="badge badge-status-' + ev.status.toLowerCase().replace(/ /g, '-') + '">' + escapeHtml(ev.status) + '</span>' +
                '<span class="day-detail-implementer">' + escapeHtml(ev.implementer) + '</span>' +
            '</div>';

        list.appendChild(item);
    });

    panel.style.display = 'block';
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function closeDayDetail() {
    document.getElementById('dayDetail').style.display = 'none';
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}
