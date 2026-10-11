/* ============================================================
   SECURITY ALERTS
   ============================================================ */

const ALERTS_API = "/dashboard/alerts";
const ALERTS_SUMMARY_API = "/dashboard/alerts/summary";


/* ============================================================
   LOAD ALERTS
   ============================================================ */

async function loadAlerts() {

    try {

        const [alertsResponse, summaryResponse] =
            await Promise.all([
                fetch(ALERTS_API, {
                    cache: "no-store"
                }),

                fetch(ALERTS_SUMMARY_API, {
                    cache: "no-store"
                })
            ]);


        if (!alertsResponse.ok) {
            throw new Error(
                `Alerts API HTTP ${alertsResponse.status}`
            );
        }


        if (!summaryResponse.ok) {
            throw new Error(
                `Alert Summary API HTTP ${summaryResponse.status}`
            );
        }


        const alertsData =
            await alertsResponse.json();

        const summaryData =
            await summaryResponse.json();


        if (!alertsData.success) {
            throw new Error(
                alertsData.error ||
                "Failed to load alerts"
            );
        }


        if (!summaryData.success) {
            throw new Error(
                summaryData.error ||
                "Failed to load alert summary"
            );
        }


        renderAlertSummary(
            summaryData.summary || {}
        );


        renderAlerts(
            alertsData.alerts || []
        );

    }
    catch (error) {

        console.error(
            "Alerts loading error:",
            error
        );

    }

}


/* ============================================================
   RENDER SUMMARY
   ============================================================ */

function renderAlertSummary(summary) {

    setAlertValue(
        "alertTotal",
        summary.total_alerts ?? 0
    );

    setAlertValue(
        "alertOpen",
        summary.open_alerts ?? 0
    );

    setAlertValue(
        "alertCritical",
        summary.critical_alerts ?? 0
    );

    setAlertValue(
        "alertHigh",
        summary.high_alerts ?? 0
    );

    setAlertValue(
        "alertMedium",
        summary.medium_alerts ?? 0
    );

    setAlertValue(
        "alertLow",
        summary.low_alerts ?? 0
    );

}


function setAlertValue(id, value) {

    const element =
        document.getElementById(id);

    if (element) {

        element.textContent = value;

    }

}


/* ============================================================
   RENDER ALERT TABLE
   ============================================================ */

function renderAlerts(alerts) {

    const tableBody =
        document.getElementById(
            "alertsTableBody"
        );


    if (!tableBody) {

        console.error(
            "alertsTableBody not found"
        );

        return;

    }


    if (
        !Array.isArray(alerts) ||
        alerts.length === 0
    ) {

        tableBody.innerHTML = `
            <tr>
                <td
                    colspan="7"
                    style="text-align:center"
                >
                    No security alerts
                </td>
            </tr>
        `;

        return;

    }


    tableBody.innerHTML = "";


    alerts.forEach(alert => {

        const row =
            document.createElement("tr");


        const severity =
            String(
                alert.severity || "INFO"
            ).toUpperCase();


        const status =
            String(
                alert.status || "OPEN"
            ).toUpperCase();


        let actions = "";


        if (status === "OPEN") {

            actions = `
                <button
                    class="alert-action-btn acknowledge-btn"
                    onclick="acknowledgeAlert(${alert.alert_id})"
                >
                    Acknowledge
                </button>
            `;

        }
        else if (status === "ACKNOWLEDGED") {

            actions = `
                <button
                    class="alert-action-btn resolve-btn"
                    onclick="resolveAlert(${alert.alert_id})"
                >
                    Resolve
                </button>
            `;

        }
        else {

            actions = `
                <span class="alert-resolved-label">
                    Resolved
                </span>
            `;

        }


        row.innerHTML = `

            <td>

                <span
                    class="alert-severity ${severity.toLowerCase()}"
                >
                    ${escapeAlertHtml(severity)}
                </span>

            </td>


            <td>

                <strong>
                    ${escapeAlertHtml(
                        alert.title || "-"
                    )}
                </strong>

                <br>

                <small>
                    ${escapeAlertHtml(
                        alert.description || ""
                    )}
                </small>

            </td>


            <td>

                ${escapeAlertHtml(
                    alert.hostname ||
                    alert.device_ip ||
                    `Device ${alert.device_id}`
                )}

                <br>

                <small>
                    ${escapeAlertHtml(
                        alert.device_ip || "-"
                    )}
                </small>

            </td>


            <td>

                ${escapeAlertHtml(
                    alert.destination_ip || "-"
                )}

                <br>

                <small>
                    ${escapeAlertHtml(
                        alert.domain_name || "-"
                    )}
                </small>

            </td>


            <td>

                <span
                    class="alert-status ${status.toLowerCase()}"
                >
                    ${escapeAlertHtml(status)}
                </span>

            </td>


            <td>

                ${formatAlertDate(
                    alert.detected_at
                )}

            </td>


            <td>

                ${actions}

            </td>

        `;


        tableBody.appendChild(row);

    });

}


/* ============================================================
   ACKNOWLEDGE ALERT
   ============================================================ */

async function acknowledgeAlert(alertId) {

    try {

        const response =
            await fetch(
                `${ALERTS_API}/${alertId}/acknowledge`,
                {
                    method: "PATCH",
                    headers: {
                        "Accept": "application/json"
                    }
                }
            );


        const data =
            await response.json();


        console.log(
            "Acknowledge response:",
            data
        );


        if (!response.ok || !data.success) {

            throw new Error(
                data.error ||
                `HTTP ${response.status}`
            );

        }


        await loadAlerts();

    }
    catch (error) {

        console.error(
            "Acknowledge alert error:",
            error
        );

        alert(
            "Unable to acknowledge alert: " +
            error.message
        );

    }

}


/* ============================================================
   RESOLVE ALERT
   ============================================================ */

async function resolveAlert(alertId) {

    try {

        const response =
            await fetch(
                `${ALERTS_API}/${alertId}/resolve`,
                {
                    method: "PATCH",
                    headers: {
                        "Accept": "application/json"
                    }
                }
            );


        const data =
            await response.json();


        console.log(
            "Resolve response:",
            data
        );


        if (!response.ok || !data.success) {

            throw new Error(
                data.error ||
                `HTTP ${response.status}`
            );

        }


        await loadAlerts();

    }
    catch (error) {

        console.error(
            "Resolve alert error:",
            error
        );

        alert(
            "Unable to resolve alert: " +
            error.message
        );

    }

}


/* ============================================================
   DATE FORMAT
   ============================================================ */

function formatAlertDate(value) {

    if (!value) {
        return "-";
    }


    const date =
        new Date(value);


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return escapeAlertHtml(value);

    }


    return escapeAlertHtml(
        date.toLocaleString()
    );

}


/* ============================================================
   HTML ESCAPING
   ============================================================ */

function escapeAlertHtml(value) {

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
   INITIALIZE
   ============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    function() {

        loadAlerts();

    }
);