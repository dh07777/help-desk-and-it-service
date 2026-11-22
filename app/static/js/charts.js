// Analytics & Chart.js Integration

document.addEventListener('DOMContentLoaded', () => {
  const trendsCanvas = document.getElementById('chart-trends');
  const statusCanvas = document.getElementById('chart-status');
  const priorityCanvas = document.getElementById('chart-priority');
  const categoryCanvas = document.getElementById('chart-category');
  const agentCanvas = document.getElementById('chart-agents');

  // Only run if at least one chart canvas is present on page
  if (!trendsCanvas && !statusCanvas && !priorityCanvas && !categoryCanvas && !agentCanvas) {
    return;
  }

  fetch('/api/stats/dashboard')
    .then(res => res.json())
    .then(data => {
      // Trends Chart (Line)
      if (trendsCanvas && data.volume_trends) {
        new Chart(trendsCanvas, {
          type: 'line',
          data: {
            labels: data.volume_trends.labels,
            datasets: [
              {
                label: 'Created',
                data: data.volume_trends.created,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                tension: 0.3,
                fill: true
              },
              {
                label: 'Resolved',
                data: data.volume_trends.resolved,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                tension: 0.3,
                fill: true
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'top' }
            },
            scales: {
              y: { beginAtZero: true, ticks: { precision: 0 } }
            }
          }
        });
      }

      // Status Chart (Doughnut)
      if (statusCanvas && data.status_breakdown) {
        new Chart(statusCanvas, {
          type: 'doughnut',
          data: {
            labels: data.status_breakdown.labels,
            datasets: [{
              data: data.status_breakdown.data,
              backgroundColor: ['#38bdf8', '#818cf8', '#f59e0b', '#10b981', '#94a3b8']
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'right' }
            }
          }
        });
      }

      // Priority Chart (Bar)
      if (priorityCanvas && data.priority_breakdown) {
        new Chart(priorityCanvas, {
          type: 'bar',
          data: {
            labels: data.priority_breakdown.labels,
            datasets: [{
              label: 'Tickets',
              data: data.priority_breakdown.data,
              backgroundColor: ['#94a3b8', '#6366f1', '#f97316', '#ef4444']
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false }
            },
            scales: {
              y: { beginAtZero: true, ticks: { precision: 0 } }
            }
          }
        });
      }

      // Category Chart (Pie)
      if (categoryCanvas && data.category_breakdown) {
        new Chart(categoryCanvas, {
          type: 'pie',
          data: {
            labels: data.category_breakdown.labels,
            datasets: [{
              data: data.category_breakdown.data,
              backgroundColor: ['#6366f1', '#ec4899', '#14b8a6', '#f59e0b', '#8b5cf6', '#06b6d4']
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'right' }
            }
          }
        });
      }

      // Agent Workload (Grouped Bar)
      if (agentCanvas && data.agent_performance) {
        new Chart(agentCanvas, {
          type: 'bar',
          data: {
            labels: data.agent_performance.labels,
            datasets: [
              {
                label: 'Assigned',
                data: data.agent_performance.assigned,
                backgroundColor: '#818cf8'
              },
              {
                label: 'Resolved',
                data: data.agent_performance.resolved,
                backgroundColor: '#10b981'
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'top' }
            },
            scales: {
              y: { beginAtZero: true, ticks: { precision: 0 } }
            }
          }
        });
      }
    })
    .catch(err => console.error('Error loading analytics chart data:', err));
});
