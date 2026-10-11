/* ============================================================
   CONFIGURATION
   ============================================================ */

const DASHBOARD_API =
    "/api/v1/dashboard/summary";


const DEVICES_API =
    "/api/v1/dashboard/devices";

const EVENTS_OVER_TIME_API =
    "/api/v1/dashboard/events-over-time";

const TOP_DESTINATIONS_API =
    "/api/v1/dashboard/top-destinations";

let eventsOverTimeChart = null;
let topDestinationsChart = null;


const REFRESH_INTERVAL =
    5000;


let isRefreshing = false;



/* ============================================================
   ERROR HANDLING
   ============================================================ */

function showError(message) {

    const errorBox =
        document.getElementById(
            "errorMessage"
        );


    errorBox.textContent =
        message;


    errorBox.style.display =
        "block";
}

function hideError() {

    const errorBox =
        document.getElementById(
            "errorMessage"
        );


    errorBox.textContent =
        "";


    errorBox.style.display =
        "none";
}



/* ============================================================
   LOAD DASHBOARD
   ============================================================ */

async function loadDashboard() {


    if (isRefreshing) {

        return;
    }


    isRefreshing = true;


    const refreshButton =
        document.getElementById(
            "refreshButton"
        );


    try {


        refreshButton.disabled =
            true;


        console.log(
            "Loading dashboard..."
        );


        /* ==================================================
           LOAD SUMMARY
           ================================================== */

        const dashboardResponse =
            await fetch(
                DASHBOARD_API,
                {
                    method: "GET",

                    cache: "no-store",

                    headers: {
                        "Accept":
                            "application/json"
                    }
                }
            );


        if (!dashboardResponse.ok) {

            throw new Error(
                "Dashboard API HTTP " +
                dashboardResponse.status
            );
        }


        const data =
            await dashboardResponse.json();


        console.log(
            "Dashboard:",
            data
        );


        if (!data.success) {

            throw new Error(
                data.error ||
                "Dashboard API failed"
            );
        }


        /* ==================================================
           SUMMARY
           ================================================== */

        document.getElementById(
            "totalDevices"
        ).textContent =
            data.summary.total_devices;


        document.getElementById(
            "activeDevices"
        ).textContent =
            data.summary.active_devices;


        document.getElementById(
            "totalEvents"
        ).textContent =
            data.summary.total_events;


        document.getElementById(
            "uniqueDestinations"
        ).textContent =
            data.summary.unique_destinations;



        /* ==================================================
           PROTOCOL STATISTICS
           ================================================== */

        const protocolContainer =
            document.getElementById(
                "protocolStats"
            );


        protocolContainer.innerHTML =
            "";


        if (
            !data.protocol_statistics ||
            data.protocol_statistics.length === 0
        ) {

            protocolContainer.innerHTML =
                "<p>No protocol data available.</p>";

        }
        else {

            data.protocol_statistics.forEach(
                item => {

                    const row =
                        document.createElement(
                            "div"
                        );


                    row.className =
                        "protocol";


                    row.innerHTML = `

                        <span>
                            ${escapeHtml(
                                item.protocol
                            )}
                        </span>

                        <strong>
                            ${item.event_count}
                        </strong>

                    `;


                    protocolContainer.appendChild(
                        row
                    );

                }
            );

        }



        renderProtocolChart(
            data.protocol_statistics
        );


        /* ==================================================
           RECENT ACTIVITY
           ================================================== */

        const table =
            document.getElementById(
                "activityTable"
            );


        table.innerHTML =
            "";


        if (
            !data.recent_activity ||
            data.recent_activity.length === 0
        ) {

            const row =
                document.createElement(
                    "tr"
                );


            row.innerHTML = `

                <td
                    colspan="7"
                    style="text-align:center"
                >
                    No recent activity
                </td>

            `;


            table.appendChild(
                row
            );

        }
        else {

            data.recent_activity.forEach(
                event => {

                    const row =
                        document.createElement(
                            "tr"
                        );


                    row.innerHTML = `

                        <td>
                            ${escapeHtml(
                                event.access_time
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                event.device_ip
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                event.destination_ip
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                event.domain_name ??
                                "-"
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                event.protocol ??
                                "-"
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                event.source_port ??
                                "-"
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                event.destination_port ??
                                "-"
                            )}
                        </td>

                    `;


                    table.appendChild(
                        row
                    );

                }
            );

        }



        /* ==================================================
           LOAD DEVICES
           ================================================== */

        await loadDevices();

        await loadEventsOverTime();

        await loadTopDestinations();



        /* ==================================================
           UPDATED TIME
           ================================================== */

        document.getElementById(
            "lastUpdated"
        ).textContent =
            "Last updated: " +
            new Date().toLocaleTimeString();


        hideError();


        console.log(
            "Dashboard successfully refreshed."
        );


    }
    catch (error) {


        console.error(
            "Dashboard error:",
            error
        );


        showError(
            "Unable to load dashboard: " +
            error.message
        );


        document.getElementById(
            "lastUpdated"
        ).textContent =
            "Update failed: " +
            new Date().toLocaleTimeString();

    }
    finally {


        refreshButton.disabled =
            false;


        isRefreshing =
            false;

    }

}




/* ============================================================
   LOAD EVENTS OVER TIME
   ============================================================ */

async function loadDevices() {


    const container =
        document.getElementById(
            "devicesContainer"
        );


    try {


        const response =
            await fetch(
                DEVICES_API,
                {
                    method: "GET",

                    cache: "no-store",

                    headers: {
                        "Accept":
                            "application/json"
                    }
                }
            );


        if (!response.ok) {

            throw new Error(
                "Devices API HTTP " +
                response.status
            );
        }


        const data =
            await response.json();


        console.log(
            "Devices:",
            data
        );


        if (!data.success) {

            throw new Error(
                data.error ||
                "Devices API failed"
            );
        }


        container.innerHTML =
            "";


        if (
            !data.devices ||
            data.devices.length === 0
        ) {

            container.innerHTML = `

                <p>
                    No connected devices found.
                </p>

            `;

            return;
        }


        data.devices.forEach(
            device => {


                const card =
                    document.createElement(
                        "div"
                    );


                card.className =
                    "device-card";


                const status =
                    String(
                        device.status ||
                        "UNKNOWN"
                    ).toUpperCase();


                let statusClass =
                    "status-unknown";


                if (
                    status === "ACTIVE"
                ) {

                    statusClass =
                        "status-active";

                }
                else if (
                    status === "INACTIVE"
                ) {

                    statusClass =
                        "status-inactive";

                }


                card.innerHTML = `

                    <div class="device-header">

                        <div class="device-name">

                            ${escapeHtml(
                                device.hostname ||
                                "Unknown Device"
                            )}

                        </div>

                        <span
                            class="status ${statusClass}"
                        >
                            ${escapeHtml(status)}
                        </span>

                    </div>


                    <div class="device-info">

                        <div>
                            <strong>
                                IP:
                            </strong>

                            ${escapeHtml(
                                device.device_ip
                            )}
                        </div>


                        <div>
                            <strong>
                                Type:
                            </strong>

                            ${escapeHtml(
                                device.device_type ||
                                "-"
                            )}
                        </div>


                        <div>
                            <strong>
                                Gateway:
                            </strong>

                            ${escapeHtml(
                                device.gateway_node ||
                                "-"
                            )}
                        </div>


                        <div>
                            <strong>
                                Last Seen:
                            </strong>

                            ${escapeHtml(
                                device.last_seen ||
                                "-"
                            )}
                        </div>


                        <div>
                            <strong>
                                Device ID:
                            </strong>

                            ${escapeHtml(
                                device.device_id
                            )}
                        </div>

                    </div>

                    <div class="device-actions">
                        <button
                            type="button"
                            class="view-activity-button"
                            onclick="loadDeviceActivity(${device.device_id})"
                        >
                            View Activity
                        </button>
                    </div>

                `;


                container.appendChild(
                    card
                );

            }
        );


    }
    catch (error) {


        console.error(
            "Devices error:",
            error
        );


        container.innerHTML = `

            <p>
                Unable to load devices:
                ${escapeHtml(
                    error.message
                )}
            </p>

        `;


        throw error;
    }

}




/* ============================================================
   DEVICE ACTIVITY
   ============================================================ */

function manualRefresh() {

    loadDashboard();

}



/* ============================================================
   HTML ESCAPING
   ============================================================ */

function escapeHtml(value) {


    if (
        value === null ||
        value === undefined
    ) {

        return "-";
    }


    return String(value)

        .replace(
            /&/g,
            "&amp;"
        )

        .replace(
            /</g,
            "&lt;"
        )

        .replace(
            />/g,
            "&gt;"
        )

        .replace(
            /"/g,
            "&quot;"
        )

        .replace(
            /'/g,
            "&#039;"
        );

}



/* ============================================================
   INITIAL LOAD
   ============================================================ */

loadDashboard();



/* ============================================================
   AUTOMATIC REFRESH
   ============================================================ */

setInterval(
    loadDashboard,
    REFRESH_INTERVAL
);


console.log(
    "Dashboard auto-refresh enabled."
);


console.log(
    "Refresh interval:",
    REFRESH_INTERVAL,
    "ms"
);

