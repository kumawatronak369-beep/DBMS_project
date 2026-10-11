/* ============================================================
   DEVICE ACTIVITY
   ============================================================ */

const DEVICE_ACTIVITY_API_BASE =
    "/api/v1/dashboard/devices";


async function loadDeviceActivity(deviceId) {

    console.log("Loading activity for device:", deviceId);

    const modal =
        document.getElementById("deviceActivityModal");

    const table =
        document.getElementById("deviceActivityTable");

    const details =
        document.getElementById("deviceDetailsContent");

    if (!modal || !table || !details) {

        console.error(
            "Device activity elements not found."
        );

        return;
    }

    modal.style.display = "block";

    details.textContent =
        "Loading device activity...";

    table.innerHTML = `
        <tr>
            <td colspan="6" style="text-align:center">
                Loading...
            </td>
        </tr>
    `;

    try {

        const response = await fetch(
            `${DEVICE_ACTIVITY_API_BASE}/${deviceId}/activity`,
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
                "Device Activity API HTTP " +
                response.status
            );
        }

        const data = await response.json();

        console.log(
            "Device activity response:",
            data
        );

        if (!data.success) {

            throw new Error(
                data.error ||
                "Unable to load device activity"
            );
        }

        const activity =
            Array.isArray(data.activity)
                ? data.activity
                : Array.isArray(data.events)
                    ? data.events
                    : Array.isArray(data.recent_activity)
                        ? data.recent_activity
                        : [];

        details.textContent =
            `Device ID: ${deviceId} | ` +
            `Activity Records: ${activity.length}`;

        if (activity.length === 0) {

            table.innerHTML = `
                <tr>
                    <td
                        colspan="6"
                        style="text-align:center"
                    >
                        No activity found
                    </td>
                </tr>
            `;

            return;
        }

        table.innerHTML = "";

        activity.forEach(event => {

            const row =
                document.createElement("tr");

            row.innerHTML = `

                <td>
                    ${escapeHtml(
                        event.access_time ??
                        event.timestamp ??
                        "-"
                    )}
                </td>

                <td>
                    ${escapeHtml(
                        event.destination_ip ??
                        "-"
                    )}
                </td>

                <td>
                    ${escapeHtml(
                        event.domain_name ??
                        event.domain ??
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

            table.appendChild(row);

        });

    }
    catch (error) {

        console.error(
            "Device activity error:",
            error
        );

        details.textContent =
            "Unable to load device activity.";

        table.innerHTML = `
            <tr>
                <td
                    colspan="6"
                    style="text-align:center"
                >
                    ${escapeHtml(error.message)}
                </td>
            </tr>
        `;
    }
}


function closeDeviceActivity() {

    const modal =
        document.getElementById(
            "deviceActivityModal"
        );

    if (modal) {

        modal.style.display = "none";

    }
}


window.addEventListener(
    "click",
    function(event) {

        const modal =
            document.getElementById(
                "deviceActivityModal"
            );

        if (
            modal &&
            event.target === modal
        ) {

            closeDeviceActivity();

        }
    }
);


window.addEventListener(
    "keydown",
    function(event) {

        if (event.key === "Escape") {

            closeDeviceActivity();

        }
    }
);


function escapeHtml(value) {

    if (
        value === null ||
        value === undefined
    ) {

        return "-";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}