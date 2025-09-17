// Wrap the entire script in an IIFE to prevent global scope pollution.
(function () {
    /**
     * Waits for the HTML document to be fully loaded before running the script.
     */
    document.addEventListener('DOMContentLoaded', function () {
        // Find the canvas element on the page.
        const canvasElement = document.getElementById('po-price-history-chart');

        // If the canvas or the data from WordPress doesn't exist, stop the script.
        if (!canvasElement || typeof poPriceHistoryData === 'undefined') {
            return;
        }

        // --- Data Preparation ---
        // The 'poPriceHistoryData' object is safely passed from PHP.
        const labels = poPriceHistoryData.dates;
        const dataPoints = poPriceHistoryData.prices;

        // --- Chart Configuration ---
        const data = {
            labels: labels,
            datasets: [{
                label: 'Price History',
                backgroundColor: 'rgba(79, 70, 229, 0.1)', // Light indigo fill
                borderColor: 'rgba(79, 70, 229, 1)',      // Solid indigo line
                data: dataPoints,
                fill: true,
                borderWidth: 2,
                tension: 0.1, // Makes the line slightly curved
                pointRadius: 3,
                pointBackgroundColor: 'rgba(79, 70, 229, 1)',
            }]
        };

        const config = {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false, // Don't force the chart to start at 0
                        ticks: {
                            // Format the Y-axis labels as currency (e.g., "₱5,300.01")
                            callback: function (value, index, values) {
                                return new Intl.NumberFormat('en-PH', {
                                    style: 'currency',
                                    currency: 'PHP'
                                }).format(value);
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false // Hide the legend box
                    },
                    tooltip: {
                        // Customize the tooltip that appears on hover
                        callbacks: {
                            label: function (context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += new Intl.NumberFormat('en-PH', {
                                        style: 'currency',
                                        currency: 'PHP'
                                    }).format(context.parsed.y);
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        };

        // --- Render the Chart ---
        // Use the Chart.js library to create the new chart instance.
        new Chart(canvasElement, config);
    });
})();