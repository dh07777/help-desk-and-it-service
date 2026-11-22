// In-app Notifications System

document.addEventListener('DOMContentLoaded', () => {
  const notifBtn = document.getElementById('notif-btn');
  const notifDropdown = document.getElementById('notif-dropdown');
  const notifList = document.getElementById('notif-list');
  const notifBadge = document.getElementById('notif-badge');
  const markAllBtn = document.getElementById('mark-all-read-btn');

  if (!notifBtn || !notifDropdown) return;

  // Toggle dropdown
  notifBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    notifDropdown.classList.toggle('show');
    if (notifDropdown.classList.contains('show')) {
      fetchNotifications();
    }
  });

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (!notifDropdown.contains(e.target) && e.target !== notifBtn) {
      notifDropdown.classList.remove('show');
    }
  });

  // Fetch notifications list
  function fetchNotifications() {
    fetch('/api/notifications')
      .then(res => res.json())
      .then(data => {
        updateBadge(data.unread_count);
        renderNotifications(data.notifications);
      })
      .catch(err => console.error('Error fetching notifications:', err));
  }

  function updateBadge(count) {
    if (notifBadge) {
      if (count > 0) {
        notifBadge.textContent = count > 99 ? '99+' : count;
        notifBadge.style.display = 'flex';
      } else {
        notifBadge.style.display = 'none';
      }
    }
  }

  function renderNotifications(items) {
    if (!notifList) return;
    if (!items || items.length === 0) {
      notifList.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--gray-400); font-size: 0.85rem;">No notifications</div>';
      return;
    }

    notifList.innerHTML = items.map(n => `
      <div class="notif-item ${!n.is_read ? 'unread' : ''}" data-id="${n.id}">
        <a href="${n.link || '#'}" style="text-decoration: none; color: inherit; display: block;" class="notif-link" data-id="${n.id}">
          <div class="notif-title">${escapeHtml(n.title)}</div>
          <div style="color: var(--gray-600); font-size: 0.8rem; margin-bottom: 0.2rem;">${escapeHtml(n.message)}</div>
          <div class="notif-meta">${timeAgo(new Date(n.created_at))}</div>
        </a>
      </div>
    `).join('');

    // Attach click handler to mark as read
    notifList.querySelectorAll('.notif-link').forEach(link => {
      link.addEventListener('click', (e) => {
        const id = link.getAttribute('data-id');
        markAsRead(id);
      });
    });
  }

  function markAsRead(id) {
    const csrfToken = getCsrfToken();
    fetch(`/api/notifications/${id}/read`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken,
        'Content-Type': 'application/json'
      }
    }).then(() => {
      fetchNotifications();
    });
  }

  if (markAllBtn) {
    markAllBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const csrfToken = getCsrfToken();
      fetch('/api/notifications/mark-all-read', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrfToken,
          'Content-Type': 'application/json'
        }
      }).then(() => {
        fetchNotifications();
      });
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, m => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    })[m]);
  }

  function timeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }
});
