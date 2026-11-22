// Ticket Creation & Interactions Script

document.addEventListener('DOMContentLoaded', () => {
  // Live KB Suggestions on Ticket Creation
  const titleInput = document.getElementById('ticket-title-input');
  const suggestionsBox = document.getElementById('kb-suggestions-box');
  const suggestionsList = document.getElementById('kb-suggestions-list');

  let debounceTimer;
  if (titleInput && suggestionsBox && suggestionsList) {
    titleInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      const query = titleInput.value.trim();
      if (query.length < 3) {
        suggestionsBox.style.display = 'none';
        return;
      }

      debounceTimer = setTimeout(() => {
        fetch(`/api/kb/search?q=${encodeURIComponent(query)}`)
          .then(res => res.json())
          .then(articles => {
            if (articles && articles.length > 0) {
              suggestionsList.innerHTML = articles.map(a => `
                <li style="padding: 0.5rem 0; border-bottom: 1px solid var(--gray-100); display: flex; justify-content: space-between; align-items: center;">
                  <div>
                    <a href="/kb/${a.slug}" target="_blank" style="font-weight: 500; text-decoration: underline;">${escapeHtml(a.title)}</a>
                    <span style="font-size: 0.75rem; color: var(--gray-400); margin-left: 0.5rem;">[${a.category}]</span>
                  </div>
                  <span style="font-size: 0.75rem; color: var(--success);">👍 ${a.helpful_count} helpful</span>
                </li>
              `).join('');
              suggestionsBox.style.display = 'block';
            } else {
              suggestionsBox.style.display = 'none';
            }
          })
          .catch(() => {
            suggestionsBox.style.display = 'none';
          });
      }, 350);
    });
  }

  // KB Article Vote Buttons
  document.querySelectorAll('.kb-vote-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const articleId = btn.getAttribute('data-article-id');
      const voteType = btn.getAttribute('data-vote');
      const csrfToken = getCsrfToken();

      fetch(`/api/kb/${articleId}/vote`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ vote: voteType })
      })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          const helpfulEl = document.getElementById(`helpful-count-${articleId}`);
          const notHelpfulEl = document.getElementById(`not-helpful-count-${articleId}`);
          if (helpfulEl) helpfulEl.textContent = data.helpful_count;
          if (notHelpfulEl) notHelpfulEl.textContent = data.not_helpful_count;

          const voteContainer = btn.closest('.kb-feedback-container');
          if (voteContainer) {
            voteContainer.innerHTML = '<div style="color: var(--success); font-weight: 600; padding: 0.5rem 0;">Thank you for your feedback!</div>';
          }
        }
      });
    });
  });

  // Client-side file size checker
  const fileInput = document.getElementById('ticket-attachment');
  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length > 0) {
        const file = fileInput.files[0];
        const maxBytes = 16 * 1024 * 1024;
        if (file.size > maxBytes) {
          alert('Warning: Selected file exceeds 16MB limit and will be rejected.');
          fileInput.value = '';
        }
      }
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
});
