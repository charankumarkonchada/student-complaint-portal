/**
 * Analytics Charts Module - Owned by K. Charankumar
 * Enhanced with IntelliHostel Modern SaaS Theme (Peach/Orange Accents)
 * Fully compatible with Light & Dark Themes with live re-theming
 */
const activeCharts = [];

function getChartColors() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
        isDark: isDark,
        textColor: isDark ? '#cbd5e1' : '#475569',
        mutedTextColor: isDark ? '#94a3b8' : '#64748b',
        gridColor: isDark ? 'rgba(51, 65, 85, 0.45)' : 'rgba(226, 232, 240, 0.7)',
        borderColor: isDark ? '#111827' : '#ffffff',
        tooltipBg: isDark ? 'rgba(17, 24, 39, 0.96)' : 'rgba(15, 23, 42, 0.92)'
    };
}

function initChart(canvasId, type, labels, data, datasetLabel) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === 'undefined') {
        return null;
    }

    const themeColors = {
        primary: '#ff6b4a',
        primaryLight: 'rgba(255, 107, 74, 0.15)',
        secondary: '#f97316',
        palette: [
            '#ff6b4a',
            '#fb923c',
            '#f59e0b',
            '#10b981',
            '#3b82f6',
            '#8b5cf6',
            '#ec4899',
            '#64748b'
        ],
        statusColors: [
            '#f59e0b', // Pending (Amber)
            '#3b82f6', // In Progress (Blue)
            '#10b981'  // Resolved (Emerald)
        ]
    };

    const colors = getChartColors();

    let datasetConfig = {
        label: datasetLabel || 'Complaints',
        data: data
    };

    if (type === 'line') {
        datasetConfig.borderColor = themeColors.primary;
        datasetConfig.backgroundColor = themeColors.primaryLight;
        datasetConfig.fill = true;
        datasetConfig.tension = 0.35;
        datasetConfig.pointBackgroundColor = themeColors.primary;
        datasetConfig.pointBorderColor = colors.borderColor;
        datasetConfig.pointBorderWidth = 2;
        datasetConfig.pointRadius = 4;
        datasetConfig.pointHoverRadius = 6;
    } else if (type === 'doughnut') {
        datasetConfig.backgroundColor = themeColors.statusColors;
        datasetConfig.borderWidth = 2;
        datasetConfig.borderColor = colors.borderColor;
    } else if (type === 'bar') {
        datasetConfig.backgroundColor = themeColors.palette.slice(0, data.length);
        datasetConfig.borderRadius = 8;
        datasetConfig.borderWidth = 0;
    }

    const chartInstance = new Chart(canvas, {
        type: type,
        data: {
            labels: labels,
            datasets: [datasetConfig]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: type === 'doughnut' ? 'bottom' : 'top',
                    labels: {
                        color: colors.textColor,
                        font: {
                            family: "'Inter', sans-serif",
                            size: 12
                        },
                        boxWidth: 14,
                        padding: 15
                    }
                },
                tooltip: {
                    backgroundColor: colors.tooltipBg,
                    titleFont: { family: "'Plus Jakarta Sans', sans-serif", weight: 'bold' },
                    bodyFont: { family: "'Inter', sans-serif" },
                    padding: 10,
                    cornerRadius: 8
                }
            },
            scales: type === 'doughnut' ? {} : {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: colors.mutedTextColor,
                        font: { family: "'Inter', sans-serif", size: 11 }
                    }
                },
                y: {
                    grid: { color: colors.gridColor },
                    ticks: {
                        color: colors.mutedTextColor,
                        font: { family: "'Inter', sans-serif", size: 11 },
                        stepSize: 1,
                        precision: 0
                    },
                    beginAtZero: true
                }
            }
        }
    });

    activeCharts.push(chartInstance);
    return chartInstance;
}

// Live Chart Theme Synchronization
window.addEventListener('themeChanged', function () {
    const colors = getChartColors();
    activeCharts.forEach(function (chart) {
        if (!chart || !chart.ctx) return;

        if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
            chart.options.plugins.legend.labels.color = colors.textColor;
        }

        if (chart.options.plugins && chart.options.plugins.tooltip) {
            chart.options.plugins.tooltip.backgroundColor = colors.tooltipBg;
        }

        if (chart.options.scales) {
            if (chart.options.scales.x && chart.options.scales.x.ticks) {
                chart.options.scales.x.ticks.color = colors.mutedTextColor;
            }
            if (chart.options.scales.y) {
                if (chart.options.scales.y.ticks) {
                    chart.options.scales.y.ticks.color = colors.mutedTextColor;
                }
                if (chart.options.scales.y.grid) {
                    chart.options.scales.y.grid.color = colors.gridColor;
                }
            }
        }

        if (chart.data && chart.data.datasets) {
            chart.data.datasets.forEach(function (ds) {
                if (chart.config.type === 'doughnut') {
                    ds.borderColor = colors.borderColor;
                } else if (chart.config.type === 'line') {
                    ds.pointBorderColor = colors.borderColor;
                }
            });
        }

        chart.update();
    });
});
