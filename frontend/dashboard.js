/**
 * Sonora Dashboard — dashboard.js
 * Populates all demo data, renders charts, animates feed
 */
(function() {
  'use strict';

  // ==========================================
  // DEMO DATA
  // ==========================================
  const LEADS = [
    { name: 'Marcus Rivera', type: 'Emergency', urgency: 9, phone: '(602) 555-0142', time: '3m ago', col: 'new' },
    { name: 'Jennifer Walsh', type: 'Repair', urgency: 6, phone: '(480) 555-0198', time: '12m ago', col: 'new' },
    { name: 'David Kim', type: 'Install', urgency: 4, phone: '(623) 555-0167', time: '1h ago', col: 'new' },
    { name: 'Amanda Foster', type: 'Repair', urgency: 7, phone: '(602) 555-0234', time: '28m ago', col: 'contacted' },
    { name: 'Robert Gonzalez', type: 'Maintenance', urgency: 3, phone: '(480) 555-0311', time: '2h ago', col: 'contacted' },
    { name: 'Lisa Thompson', type: 'Install', urgency: 5, phone: '(623) 555-0455', time: '45m ago', col: 'contacted' },
    { name: 'Sarah Chen', type: 'Install', urgency: 5, phone: '(480) 555-0789', time: '3h ago', col: 'qualified' },
    { name: 'James Mitchell', type: 'Repair', urgency: 8, phone: '(602) 555-0561', time: '1h ago', col: 'qualified' },
    { name: 'Karen Williams', type: 'Maintenance', urgency: 2, phone: '(623) 555-0678', time: '4h ago', col: 'qualified' },
    { name: 'Michael Patel', type: 'Install', urgency: 4, phone: '(480) 555-0923', time: '5h ago', col: 'booked' },
    { name: 'Rachel Adams', type: 'Repair', urgency: 6, phone: '(602) 555-0845', time: '3h ago', col: 'booked' },
    { name: 'Tom Nguyen', type: 'Emergency', urgency: 9, phone: '(623) 555-0134', time: '6h ago', col: 'booked' },
    { name: 'Diana Lopez', type: 'Maintenance', urgency: 3, phone: '(480) 555-0456', time: '1d ago', col: 'booked' },
    { name: 'Chris Baker', type: 'Repair', urgency: 5, phone: '(602) 555-0567', time: '1d ago', col: 'completed' },
    { name: 'Emily Turner', type: 'Install', urgency: 4, phone: '(623) 555-0789', time: '1d ago', col: 'completed' },
    { name: 'Ryan Scott', type: 'Maintenance', urgency: 2, phone: '(480) 555-0890', time: '2d ago', col: 'completed' },
  ];

  const APPOINTMENTS = [
    { time: '8:00 AM', job: 'AC Repair — Unit not cooling', address: '4521 E Baseline Rd, Mesa', tech: 'Mike Rodriguez' },
    { time: '9:30 AM', job: 'Annual Maintenance', address: '1234 W Camelback Rd, Phoenix', tech: 'Sarah Kim' },
    { time: '11:00 AM', job: 'New Install — 3-ton Carrier', address: '789 N Scottsdale Rd, Scottsdale', tech: 'Mike Rodriguez' },
    { time: '1:00 PM', job: 'Duct Inspection + Repair', address: '3456 S Mill Ave, Tempe', tech: 'James Chen' },
    { time: '2:30 PM', job: 'Emergency — No AC (112°F)', address: '8901 E Indian School Rd, Scottsdale', tech: 'Mike Rodriguez' },
    { time: '4:00 PM', job: 'Thermostat Replacement', address: '2345 W Bethany Home Rd, Glendale', tech: 'Sarah Kim' },
  ];

  const FOLLOWUPS = [
    { lead: 'Jennifer Walsh', type: 'Missed Call SMS', countdown: '1m 42s' },
    { lead: 'David Kim', type: '24hr Nurture', countdown: '3h 15m' },
    { lead: 'Robert Gonzalez', type: 'Review Request', countdown: '12m' },
    { lead: 'Karen Williams', type: 'Missed Call SMS', countdown: '47s' },
    { lead: 'Lisa Thompson', type: 'Quote Follow-Up', countdown: '2h 30m' },
    { lead: 'Amanda Foster', type: '24hr Nurture', countdown: '5h 10m' },
  ];

  const REVIEWS = [
    { name: 'Chris Baker', initials: 'CB', stars: 5, status: '★★★★★ Left review 2h ago' },
    { name: 'Emily Turner', initials: 'ET', stars: 5, status: '★★★★★ Left review 4h ago' },
    { name: 'Ryan Scott', initials: 'RS', stars: 4, status: '★★★★ Left review yesterday' },
    { name: 'Patricia Moore', initials: 'PM', stars: 0, status: 'Sent — awaiting response' },
    { name: 'Daniel White', initials: 'DW', stars: 0, status: 'Sending in 30 min' },
  ];

  const ACTIVITIES = [
    { type: 'emergency', icon: '⚡', text: '<strong>Emergency lead detected</strong> — Marcus Rivera, No AC, Phoenix. Urgency: 9/10.', time: '3 min ago' },
    { type: 'call', icon: '📞', text: 'Recovered missed call from <strong>Jennifer Walsh</strong> — sent SMS follow-up.', time: '12 min ago' },
    { type: 'book', icon: '📅', text: 'Booked install for <strong>Sarah Chen</strong> — $8,200 est. revenue.', time: '28 min ago' },
    { type: 'followup', icon: '💬', text: 'Sent 24hr follow-up to <strong>3 leads</strong> — David Kim, Robert Gonzalez, Karen Williams.', time: '45 min ago' },
    { type: 'review', icon: '⭐', text: '<strong>Chris Baker</strong> left a 5-star review: "Mike was amazing! Fixed our AC in 30 min."', time: '2h ago' },
    { type: 'book', icon: '📅', text: 'Booked emergency repair for <strong>Tom Nguyen</strong> — same day dispatch.', time: '2h ago' },
    { type: 'call', icon: '📞', text: 'Qualified incoming call from <strong>Amanda Foster</strong> — AC making grinding noise, 5yr system.', time: '3h ago' },
    { type: 'review', icon: '⭐', text: '<strong>Emily Turner</strong> left a 5-star review after install completion.', time: '4h ago' },
    { type: 'followup', icon: '💬', text: 'Reactivation campaign sent to <strong>12 dormant customers</strong> — annual maintenance reminders.', time: '5h ago' },
    { type: 'book', icon: '📅', text: 'Booked maintenance for <strong>Diana Lopez</strong> — $189 routine service.', time: '6h ago' },
  ];

  // ==========================================
  // RENDER FUNCTIONS
  // ==========================================

  function renderDate() {
    const el = document.getElementById('dashDate');
    if (!el) return;
    const now = new Date();
    el.textContent = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
  }

  function renderKanban() {
    const kanban = document.getElementById('kanban');
    if (!kanban) return;

    const columns = [
      { id: 'new', name: 'New' },
      { id: 'contacted', name: 'Contacted' },
      { id: 'qualified', name: 'Qualified' },
      { id: 'booked', name: 'Booked' },
      { id: 'completed', name: 'Completed' },
    ];

    kanban.innerHTML = columns.map(col => {
      const cards = LEADS.filter(l => l.col === col.id);
      return `
        <div class="kanban__col">
          <div class="kanban__col-header">
            <span class="kanban__col-name">${col.name}</span>
            <span class="kanban__col-count">${cards.length}</span>
          </div>
          <div class="kanban__cards">
            ${cards.map(card => {
              const typeClass = card.type.toLowerCase();
              const urgClass = card.urgency >= 8 ? 'high' : card.urgency >= 5 ? 'medium' : 'low';
              return `
                <div class="kanban__card">
                  <div class="kanban__card-name">${card.name}</div>
                  <div class="kanban__card-meta">
                    <span class="kanban__badge kanban__badge--${typeClass}">${card.type}</span>
                    <span class="kanban__urgency kanban__urgency--${urgClass}">${card.urgency}/10</span>
                    <span class="kanban__card-time">${card.time}</span>
                  </div>
                  <div class="kanban__card-meta" style="margin-top:4px;">
                    <span class="kanban__card-phone">${card.phone}</span>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      `;
    }).join('');
  }

  function renderTimeline() {
    const el = document.getElementById('timeline');
    if (!el) return;
    el.innerHTML = APPOINTMENTS.map(apt => `
      <div class="timeline__item">
        <span class="timeline__time">${apt.time}</span>
        <div class="timeline__details">
          <span class="timeline__job">${apt.job}</span>
          <span class="timeline__address">${apt.address}</span>
        </div>
        <span class="timeline__tech">${apt.tech}</span>
      </div>
    `).join('');
  }

  function renderFollowups() {
    const el = document.getElementById('followupList');
    if (!el) return;
    el.innerHTML = FOLLOWUPS.map(f => `
      <div class="followup__item">
        <span class="followup__lead">${f.lead}</span>
        <span class="followup__type">${f.type}</span>
        <span class="followup__countdown">${f.countdown}</span>
      </div>
    `).join('');
  }

  function renderReviews() {
    const el = document.getElementById('reviewList');
    if (!el) return;
    el.innerHTML = REVIEWS.map(r => `
      <div class="review__item">
        <div class="review__avatar">${r.initials}</div>
        <div class="review__info">
          <div class="review__name">${r.name}</div>
          <div class="review__status">${r.status}</div>
        </div>
      </div>
    `).join('');
  }

  function renderActivity() {
    const el = document.getElementById('activityFeed');
    if (!el) return;
    el.innerHTML = ACTIVITIES.map(a => `
      <div class="activity__item activity__item--${a.type}">
        <div class="activity__icon">${a.icon}</div>
        <div class="activity__content">
          <div class="activity__text">${a.text}</div>
          <div class="activity__time">${a.time}</div>
        </div>
      </div>
    `).join('');
  }

  // ==========================================
  // CHART
  // ==========================================
  function renderChart() {
    const canvas = document.getElementById('revenueChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // Gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, 240);
    gradient.addColorStop(0, 'rgba(0, 131, 143, 0.3)');
    gradient.addColorStop(1, 'rgba(0, 131, 143, 0.02)');

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        datasets: [{
          label: 'Est. Revenue',
          data: [14200, 18500, 22100, 16800, 24500, 19200, 12100],
          backgroundColor: gradient,
          borderColor: 'rgba(0, 131, 143, 0.6)',
          borderWidth: 1,
          borderRadius: 6,
          borderSkipped: false,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0D1117',
            borderColor: 'rgba(0,131,143,0.3)',
            borderWidth: 1,
            titleColor: '#fff',
            bodyColor: '#94A3B8',
            titleFont: { family: 'Inter', weight: '600' },
            bodyFont: { family: 'Inter' },
            padding: 12,
            cornerRadius: 8,
            callbacks: {
              label: (ctx) => '$' + ctx.parsed.y.toLocaleString(),
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#64748B', font: { family: 'Inter', size: 12 } },
            border: { display: false },
          },
          y: {
            grid: { color: 'rgba(30,41,59,0.5)', drawBorder: false },
            ticks: {
              color: '#64748B',
              font: { family: 'Inter', size: 12 },
              callback: (v) => '$' + (v / 1000) + 'k',
            },
            border: { display: false },
          }
        },
        animation: {
          duration: 800,
          easing: 'easeOutQuart',
        }
      }
    });
  }

  // ==========================================
  // LIVE ACTIVITY SIMULATION
  // ==========================================
  const liveMessages = [
    { type: 'call', icon: '📞', text: 'Incoming call from <strong>(602) 555-0312</strong> — qualifying lead...' },
    { type: 'followup', icon: '💬', text: 'Sent appointment reminder to <strong>Michael Patel</strong> for tomorrow.' },
    { type: 'book', icon: '📅', text: 'Booked AC tune-up for <strong>New Lead</strong> — $149 maintenance package.' },
    { type: 'review', icon: '⭐', text: 'Review request sent to <strong>Rachel Adams</strong> after job completion.' },
    { type: 'call', icon: '📞', text: 'Recovered after-hours call — <strong>New Lead</strong> needs weekend emergency repair.' },
  ];

  function simulateLiveActivity() {
    const el = document.getElementById('activityFeed');
    if (!el) return;

    let idx = 0;
    setInterval(() => {
      const msg = liveMessages[idx % liveMessages.length];
      const div = document.createElement('div');
      div.className = `activity__item activity__item--${msg.type}`;
      div.innerHTML = `
        <div class="activity__icon">${msg.icon}</div>
        <div class="activity__content">
          <div class="activity__text">${msg.text}</div>
          <div class="activity__time">Just now</div>
        </div>
      `;
      el.insertBefore(div, el.firstChild);

      // Remove oldest if too many
      while (el.children.length > 15) {
        el.removeChild(el.lastChild);
      }
      idx++;
    }, 8000);
  }

  // ==========================================
  // COUNTDOWN TIMER SIMULATION
  // ==========================================
  function tickCountdowns() {
    const countdowns = document.querySelectorAll('.followup__countdown');
    setInterval(() => {
      countdowns.forEach(el => {
        const text = el.textContent;
        // Simple simulation: just decrement seconds display
        const match = text.match(/(\d+)s/);
        if (match) {
          let sec = parseInt(match[1]) - 1;
          if (sec < 0) sec = 59;
          el.textContent = text.replace(/\d+s/, sec + 's');
        }
      });
    }, 1000);
  }

  // ==========================================
  // INIT
  // ==========================================
  document.addEventListener('DOMContentLoaded', () => {
    renderDate();
    renderKanban();
    renderTimeline();
    renderFollowups();
    renderReviews();
    renderActivity();
    renderChart();
    simulateLiveActivity();
    tickCountdowns();
  });
})();
