/**
 * Analytics Charts Module
 */

function initChart(canvasId, type, labels, data, datasetLabel) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === 'undefined') {
        return null;
    }

    return new Chart(canvas, {
        type: type,
        data: {
            labels: labels,
            datasets: [{
                label: datasetLabel || 'Complaints',
                data: data
            }]
        },
        options: {
            responsive: true
        }
    });
}
