async function loadEventsOverTime() {

    const statusElement =
        document.getElementById("eventsChartStatus");

    try {

        const response = await fetch(
            EVENTS_OVER_TIME_API,
            {
                method: "GET",
                cache: "no-store",
                headers: {
                    "Accept": "application/json"
                }
            }
        );

        if (!response.ok) {
            throw new Error(
                "Events Over Time API HTTP " +
                response.status
            );
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(
                data.error ||
                "Events Over Time API failed"
            );
        }

        const events = data.events || [];

        renderEventsOverTimeChart(events);

        statusElement.textContent =
            events.length === 0
                ? "No event data available."
                : "Showing event activity by minute.";

    } catch (error) {

        console.error(
            "Events over time error:",
            error
        );

        statusElement.textContent =
            "Unable to load event history: " +
            error.message;
    }
}


/* ============================================================
   RENDER EVENTS OVER TIME
   ============================================================ */

function renderEventsOverTimeChart(events) {

    const canvas =
        document.getElementById(
            "eventsOverTimeChart"
        );

    if (!canvas || typeof Chart === "undefined") {
        return;
    }

    const labels = events.map(
        event => event.time_bucket
    );

    const values = events.map(
        event => Number(event.event_count)
    );

    if (eventsOverTimeChart) {
        eventsOverTimeChart.destroy();
    }

    eventsOverTimeChart = new Chart(
        canvas.getContext("2d"),
        {
            type: "line",

            data: {
                labels: labels,

                datasets: [
                    {
                        label: "Network Events",
                        data: values,
                        borderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        tension: 0.25,
                        fill: false
                    }
                ]
            },

            options: {
                responsive: true,
                maintainAspectRatio: false,

                interaction: {
                    mode: "index",
                    intersect: false
                },

                plugins: {
                    legend: {
                        display: true
                    }
                },

                scales: {
                    x: {
                        title: {
                            display: true,
                            text: "Time"
                        },

                        ticks: {
                            maxRotation: 45
                        }
                    },

                    y: {
                        beginAtZero: true,

                        title: {
                            display: true,
                            text: "Events"
                        },

                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        }
    );
}



/* ============================================================
   LOAD TOP DESTINATIONS
   ============================================================ */

async function loadTopDestinations() {

    const statusElement =
        document.getElementById(
            "topDestinationsStatus"
        );

    try {

        const response =
            await fetch(
                TOP_DESTINATIONS_API,
                {
                    method: "GET",
                    cache: "no-store",
                    headers: {
                        "Accept": "application/json"
                    }
                }
            );

        if (!response.ok) {

            throw new Error(
                "Top Destinations API HTTP " +
                response.status
            );
        }

        const data =
            await response.json();

        if (!data.success) {

            throw new Error(
                data.error ||
                "Top Destinations API failed"
            );
        }

        const destinations =
            data.destinations || [];

        renderTopDestinationsChart(
            destinations
        );

        statusElement.textContent =
            destinations.length === 0
                ? "No destination data available."
                : "Showing the 10 most frequently contacted destinations.";

    } catch (error) {

        console.error(
            "Top destinations error:",
            error
        );

        statusElement.textContent =
            "Unable to load destination statistics: " +
            error.message;
    }
}


/* ============================================================
   RENDER TOP DESTINATIONS
   ============================================================ */

function renderTopDestinationsChart(
    destinations
) {

    const canvas =
        document.getElementById(
            "topDestinationsChart"
        );

    if (
        !canvas ||
        typeof Chart === "undefined"
    ) {
        return;
    }

    const labels =
        destinations.map(
            item => {

                if (
                    item.domain_name &&
                    item.domain_name !== "NULL"
                ) {

                    return (
                        item.ip_address +
                        " (" +
                        item.domain_name +
                        ")"
                    );
                }

                return item.ip_address;
            }
        );

    const values =
        destinations.map(
            item =>
                Number(item.event_count)
        );

    if (topDestinationsChart) {

        topDestinationsChart.destroy();
    }

    topDestinationsChart =
        new Chart(
            canvas.getContext("2d"),
            {
                type: "bar",

                data: {

                    labels: labels,

                    datasets: [
                        {
                            label: "Events",

                            data: values,

                            borderWidth: 1
                        }
                    ]
                },

                options: {

                    indexAxis: "y",

                    responsive: true,

                    maintainAspectRatio: false,

                    plugins: {

                        legend: {
                            display: true
                        }
                    },

                    scales: {

                        x: {

                            beginAtZero: true,

                            title: {

                                display: true,

                                text: "Network Events"
                            },

                            ticks: {

                                precision: 0
                            }
                        },

                        y: {

                            title: {

                                display: true,

                                text: "Destination"
                            }
                        }
                    }
                }
            }
        );
}


/* ============================================================
   LOAD DEVICES
   ============================================================ */

/* ============================================================
   TCP VS UDP CHART
   ============================================================ */

let protocolChart = null;


function renderProtocolChart(protocolStatistics) {

    const canvas =
        document.getElementById("protocolChart");

    const statusElement =
        document.getElementById("protocolChartStatus");

    if (!canvas || typeof Chart === "undefined") {
        return;
    }


    const tcp =
        getProtocolEventCount(
            protocolStatistics,
            "TCP"
        );

    const udp =
        getProtocolEventCount(
            protocolStatistics,
            "UDP"
        );


    if (protocolChart) {
        protocolChart.destroy();
    }


    if (statusElement) {
        statusElement.textContent =
            "TCP: " + tcp + " events | UDP: " + udp + " events";
    }

    protocolChart = new Chart(
        canvas.getContext("2d"),
        {
            type: "doughnut",

            data: {

                labels: [
                    "TCP",
                    "UDP"
                ],

                datasets: [
                    {
                        data: [
                            tcp,
                            udp
                        ],

                        borderWidth: 1
                    }
                ]
            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                plugins: {

                    legend: {
                        position: "bottom"
                    },

                    tooltip: {

                        callbacks: {

                            label: function(context) {

                                return (
                                    context.label +
                                    ": " +
                                    context.raw +
                                    " events"
                                );
                            }
                        }
                    }
                }
            }
        }
    );
}


function getProtocolEventCount(
    protocolStatistics,
    protocol
) {

    if (!Array.isArray(protocolStatistics)) {
        return 0;
    }


    const item =
        protocolStatistics.find(
            entry =>
                String(
                    entry.protocol || ""
                ).toUpperCase() === protocol
        );


    return item
        ? Number(item.event_count)
        : 0;
}