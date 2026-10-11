from db import get_connection


BURST_WINDOW_SECONDS = 30
BURST_THRESHOLD = 20
REPEATED_DESTINATION_WINDOW_SECONDS = 60
REPEATED_DESTINATION_THRESHOLD = 10
NEW_DESTINATION_MIN_HISTORY = 10
UNUSUAL_PORT_MIN_HISTORY = 10

SENSITIVE_SERVICE_PORTS = {
    21: ("FTP", "LOW"),
    23: ("TELNET", "HIGH"),
    139: ("NETBIOS", "MEDIUM"),
    445: ("SMB", "MEDIUM"),
    3389: ("RDP", "MEDIUM"),
}
RISK_WEIGHTS = {
    "CONNECTION_BURST": 30,
    "REPEATED_DESTINATION": 20,
    "NEW_DESTINATION": 10,
    "UNUSUAL_PORT": 25,
    "SENSITIVE_SERVICE_PORT": 50,
}
RISK_LEVELS = {
    "INFO": 0,
    "LOW": 20,
    "MEDIUM": 40,
    "HIGH": 70,
    "CRITICAL": 100,
}

def check_connection_burst(device_id, history_id):
    """
    Detect unusually high network activity from one device.

    Rule:
        More than 20 events from the same device
        within the previous 30 seconds.

    Returns:
        True  -> alert created
        False -> no alert created
    """

    connection = get_connection()

    if connection is None:
        print("Detection engine: database connection failed")
        return False

    cursor = None

    try:

        cursor = connection.cursor(dictionary=True)

        # -----------------------------------------------------
        # Count recent events for this device
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS event_count
            FROM browsing_history
            WHERE device_id = %s
              AND access_time >= (
                    SELECT access_time
                    FROM browsing_history
                    WHERE history_id = %s
                ) - INTERVAL %s SECOND
              AND access_time <= (
                    SELECT access_time
                    FROM browsing_history
                    WHERE history_id = %s
                )
            """,
            (
                device_id,
                history_id,
                BURST_WINDOW_SECONDS,
                history_id
            )
        )

        result = cursor.fetchone()

        event_count = (
            result["event_count"]
            if result
            else 0
        )

        print(
            f"Detection check | "
            f"device={device_id} | "
            f"events={event_count}"
        )

        # -----------------------------------------------------
        # No burst
        # -----------------------------------------------------

        if event_count <= BURST_THRESHOLD:

            return False

        # -----------------------------------------------------
        # Prevent duplicate burst alerts
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT alert_id
            FROM alerts
            WHERE device_id = %s
              AND alert_type = 'CONNECTION_BURST'
              AND status IN ('OPEN', 'ACKNOWLEDGED')
              AND detected_at >= (
                    SELECT access_time
                    FROM browsing_history
                    WHERE history_id = %s
                ) - INTERVAL %s SECOND
            LIMIT 1
            """,
            (
                device_id,
                history_id,
                BURST_WINDOW_SECONDS
            )
        )

        existing_alert = cursor.fetchone()

        if existing_alert:

            print(
                "Detection check | "
                "existing burst alert found"
            )

            return False

        # -----------------------------------------------------
        # Get destination associated with this event
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT destination_id
            FROM browsing_history
            WHERE history_id = %s
            LIMIT 1
            """,
            (history_id,)
        )

        event = cursor.fetchone()

        destination_id = (
            event["destination_id"]
            if event
            else None
        )

        # -----------------------------------------------------
        # Create alert
        # -----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO alerts
            (
                device_id,
                history_id,
                alert_type,
                severity,
                title,
                description,
                destination_id,
                detected_at
            )
            VALUES
            (
                %s,
                %s,
                'CONNECTION_BURST',
                'HIGH',
                %s,
                %s,
                %s,
                (
                    SELECT access_time
                    FROM browsing_history
                    WHERE history_id = %s
                )
            )
            """,
            (
                device_id,
                history_id,
                "Unusual Connection Burst",
                (
                    f"Device generated {event_count} "
                    f"network events within "
                    f"{BURST_WINDOW_SECONDS} seconds."
                ),
                destination_id,
                history_id
            )
        )

        connection.commit()

        print(
            f"ALERT CREATED | "
            f"type=CONNECTION_BURST | "
            f"device={device_id} | "
            f"events={event_count}"
        )

        return True

    except Exception as error:

        connection.rollback()

        print(
            "Detection engine error:",
            error
        )

        return False

    finally:

        if cursor is not None:
            cursor.close()

        connection.close()


def check_repeated_destination(device_id, history_id):
    """
    Detect repeated connections from the same device
    to the same destination within a short time window.

    Rule:
        More than 10 events from the same device
        to the same destination within 60 seconds.

    Returns:
        True  -> alert created
        False -> no alert created
    """

    connection = get_connection()

    if connection is None:
        print("Repeated destination detection: database connection failed")
        return False

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        # -----------------------------------------------------
        # Get the destination and timestamp of the current event
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT
                destination_id,
                access_time
            FROM browsing_history
            WHERE history_id = %s
            LIMIT 1
            """,
            (history_id,)
        )

        event = cursor.fetchone()

        if event is None:
            return False

        destination_id = event["destination_id"]
        access_time = event["access_time"]

        # -----------------------------------------------------
        # Count events to the same destination
        # within the 60-second window
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS event_count
            FROM browsing_history
            WHERE device_id = %s
              AND destination_id = %s
              AND access_time >= %s - INTERVAL %s SECOND
              AND access_time <= %s
            """,
            (
                device_id,
                destination_id,
                access_time,
                REPEATED_DESTINATION_WINDOW_SECONDS,
                access_time
            )
        )

        result = cursor.fetchone()

        event_count = (
            result["event_count"]
            if result
            else 0
        )

        print(
            f"Repeated destination check | "
            f"device={device_id} | "
            f"destination={destination_id} | "
            f"events={event_count}"
        )

        # -----------------------------------------------------
        # Threshold not reached
        # -----------------------------------------------------

        if event_count <= REPEATED_DESTINATION_THRESHOLD:
            return False

        # -----------------------------------------------------
        # Prevent duplicate alerts
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT alert_id
            FROM alerts
            WHERE device_id = %s
              AND destination_id = %s
              AND alert_type = 'REPEATED_DESTINATION'
              AND status IN ('OPEN', 'ACKNOWLEDGED')
              AND detected_at >= %s - INTERVAL %s SECOND
            LIMIT 1
            """,
            (
                device_id,
                destination_id,
                access_time,
                REPEATED_DESTINATION_WINDOW_SECONDS
            )
        )

        existing_alert = cursor.fetchone()

        if existing_alert:
            print(
                "Repeated destination check | "
                "existing alert found"
            )
            return False

        # -----------------------------------------------------
        # Create alert
        # -----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO alerts
            (
                device_id,
                history_id,
                alert_type,
                severity,
                title,
                description,
                destination_id,
                detected_at
            )
            VALUES
            (
                %s,
                %s,
                'REPEATED_DESTINATION',
                'MEDIUM',
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                device_id,
                history_id,
                "Repeated Destination Activity",
                (
                    f"Device contacted the same destination "
                    f"{event_count} times within "
                    f"{REPEATED_DESTINATION_WINDOW_SECONDS} seconds."
                ),
                destination_id,
                access_time
            )
        )

        connection.commit()

        print(
            f"ALERT CREATED | "
            f"type=REPEATED_DESTINATION | "
            f"device={device_id} | "
            f"destination={destination_id} | "
            f"events={event_count}"
        )

        return True

    except Exception as error:

        connection.rollback()

        print(
            "Repeated destination detection error:",
            error
        )

        return False

    finally:

        if cursor is not None:
            cursor.close()

        connection.close()
def check_new_destination(device_id, history_id):
    """
    Detect when a device contacts a destination
    that it has never contacted before.

    Rule:
        The device must already have at least
        NEW_DESTINATION_MIN_HISTORY previous events.

        The current destination must not have appeared
        previously in that device's browsing history.

    Severity:
        LOW

    Returns:
        True  -> alert created
        False -> no alert created
    """

    connection = get_connection()

    if connection is None:
        print(
            "New destination detection: "
            "database connection failed"
        )
        return False

    cursor = None

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        # -----------------------------------------------------
        # Get the current event
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT
                destination_id,
                access_time
            FROM browsing_history
            WHERE history_id = %s
            LIMIT 1
            """,
            (history_id,)
        )

        current_event = cursor.fetchone()

        if current_event is None:
            return False

        destination_id = current_event["destination_id"]
        access_time = current_event["access_time"]


        # -----------------------------------------------------
        # Check device history size
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS history_count
            FROM browsing_history
            WHERE device_id = %s
              AND history_id <> %s
            """,
            (
                device_id,
                history_id
            )
        )

        history_result = cursor.fetchone()

        history_count = (
            history_result["history_count"]
            if history_result
            else 0
        )


        print(
            f"New destination check | "
            f"device={device_id} | "
            f"destination={destination_id} | "
            f"history={history_count}"
        )


        # -----------------------------------------------------
        # Device has insufficient history
        # -----------------------------------------------------

        if history_count < NEW_DESTINATION_MIN_HISTORY:

            return False


        # -----------------------------------------------------
        # Check whether this device has seen the
        # destination before this event
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT history_id
            FROM browsing_history
            WHERE device_id = %s
              AND destination_id = %s
              AND access_time < %s
            LIMIT 1
            """,
            (
                device_id,
                destination_id,
                access_time
            )
        )

        previous_event = cursor.fetchone()


        # Destination is not new
        if previous_event is not None:

            return False


        # -----------------------------------------------------
        # Prevent duplicate NEW_DESTINATION alerts
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT alert_id
            FROM alerts
            WHERE device_id = %s
              AND destination_id = %s
              AND alert_type = 'NEW_DESTINATION'
              AND status IN ('OPEN', 'ACKNOWLEDGED')
            LIMIT 1
            """,
            (
                device_id,
                destination_id
            )
        )

        existing_alert = cursor.fetchone()


        if existing_alert:

            print(
                "New destination check | "
                "existing alert found"
            )

            return False


        # -----------------------------------------------------
        # Create alert
        # -----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO alerts
            (
                device_id,
                history_id,
                alert_type,
                severity,
                title,
                description,
                destination_id,
                detected_at
            )
            VALUES
            (
                %s,
                %s,
                'NEW_DESTINATION',
                'LOW',
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                device_id,
                history_id,
                "New Destination Detected",
                (
                    f"Device contacted a destination "
                    f"that has not been seen previously "
                    f"in its history."
                ),
                destination_id,
                access_time
            )
        )


        connection.commit()


        print(
            f"ALERT CREATED | "
            f"type=NEW_DESTINATION | "
            f"device={device_id} | "
            f"destination={destination_id}"
        )


        return True


    except Exception as error:

        connection.rollback()

        print(
            "New destination detection error:",
            error
        )

        return False


    finally:

        if cursor is not None:
            cursor.close()

        connection.close()

def check_unusual_port(device_id, history_id):
    """
    Detect a destination port that has never previously
    been observed for the device.

    Rule:
        Device must have at least
        UNUSUAL_PORT_MIN_HISTORY previous events.

        Current destination port must be non-null and
        must not have appeared previously for the device.

    Severity:
        MEDIUM

    Returns:
        True  -> alert created
        False -> no alert created
    """

    connection = get_connection()

    if connection is None:
        print(
            "Unusual port detection: "
            "database connection failed"
        )
        return False

    cursor = None

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        # -----------------------------------------------------
        # Get the current event
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT
                destination_id,
                destination_port,
                access_time
            FROM browsing_history
            WHERE history_id = %s
            LIMIT 1
            """,
            (history_id,)
        )

        current_event = cursor.fetchone()

        if current_event is None:
            return False

        destination_id = current_event["destination_id"]
        destination_port = current_event["destination_port"]
        access_time = current_event["access_time"]


        # -----------------------------------------------------
        # Ignore events without a destination port
        # -----------------------------------------------------

        if destination_port is None:

            return False


        # -----------------------------------------------------
        # Check device history size
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS history_count
            FROM browsing_history
            WHERE device_id = %s
              AND history_id <> %s
            """,
            (
                device_id,
                history_id
            )
        )

        history_result = cursor.fetchone()

        history_count = (
            history_result["history_count"]
            if history_result
            else 0
        )


        print(
            f"Unusual port check | "
            f"device={device_id} | "
            f"port={destination_port} | "
            f"history={history_count}"
        )


        # -----------------------------------------------------
        # Device has insufficient history
        # -----------------------------------------------------

        if history_count < UNUSUAL_PORT_MIN_HISTORY:

            return False


        # -----------------------------------------------------
        # Check whether this port was previously observed
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT history_id
            FROM browsing_history
            WHERE device_id = %s
              AND destination_port = %s
              AND history_id <> %s
            LIMIT 1
            """,
            (
                device_id,
                destination_port,
                history_id
            )
        )

        previous_event = cursor.fetchone()


        # Port is already normal for this device
        if previous_event is not None:

            return False


        # -----------------------------------------------------
        # Prevent duplicate alerts
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT alert_id
            FROM alerts
            WHERE device_id = %s
              AND alert_type = 'UNUSUAL_PORT'
              AND status IN ('OPEN', 'ACKNOWLEDGED')
              AND description LIKE %s
            LIMIT 1
            """,
            (
                device_id,
                f"%port {destination_port}%"
            )
        )

        existing_alert = cursor.fetchone()


        if existing_alert:

            print(
                "Unusual port check | "
                "existing alert found"
            )

            return False


        # -----------------------------------------------------
        # Create alert
        # -----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO alerts
            (
                device_id,
                history_id,
                alert_type,
                severity,
                title,
                description,
                destination_id,
                detected_at
            )
            VALUES
            (
                %s,
                %s,
                'UNUSUAL_PORT',
                'MEDIUM',
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                device_id,
                history_id,
                "Unusual Destination Port",
                (
                    f"Device used destination port "
                    f"{destination_port}, which has not "
                    f"been previously observed for this device."
                ),
                destination_id,
                access_time
            )
        )


        connection.commit()


        print(
            f"ALERT CREATED | "
            f"type=UNUSUAL_PORT | "
            f"device={device_id} | "
            f"port={destination_port}"
        )


        return True


    except Exception as error:

        connection.rollback()

        print(
            "Unusual port detection error:",
            error
        )

        return False


    finally:

        if cursor is not None:
            cursor.close()

        connection.close()
def check_sensitive_service_port(device_id, history_id):
    """
    Detect connections to sensitive service ports.

    Rule:
        If the current destination port is one of the
        configured sensitive service ports, generate an alert.

    Returns:
        True  -> alert created
        False -> no alert created
    """

    connection = get_connection()

    if connection is None:
        print(
            "Sensitive service port detection: "
            "database connection failed"
        )
        return False

    cursor = None

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        # -----------------------------------------------------
        # Get current event
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT
                destination_id,
                destination_port,
                access_time
            FROM browsing_history
            WHERE history_id = %s
            LIMIT 1
            """,
            (history_id,)
        )

        current_event = cursor.fetchone()

        if current_event is None:
            return False


        destination_id = current_event["destination_id"]
        destination_port = current_event["destination_port"]
        access_time = current_event["access_time"]


        # -----------------------------------------------------
        # Ignore events without destination port
        # -----------------------------------------------------

        if destination_port is None:
            return False


        # -----------------------------------------------------
        # Check whether port is sensitive
        # -----------------------------------------------------

        port_info = SENSITIVE_SERVICE_PORTS.get(
            destination_port
        )

        if port_info is None:

            print(
                f"Sensitive port check | "
                f"device={device_id} | "
                f"port={destination_port} | "
                f"not sensitive"
            )

            return False


        service_name, severity = port_info


        print(
            f"Sensitive port check | "
            f"device={device_id} | "
            f"port={destination_port} | "
            f"service={service_name} | "
            f"severity={severity}"
        )


        # -----------------------------------------------------
        # Prevent duplicate open/acknowledged alerts
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT alert_id
            FROM alerts
            WHERE device_id = %s
              AND destination_id = %s
              AND alert_type = 'SENSITIVE_SERVICE_PORT'
              AND status IN ('OPEN', 'ACKNOWLEDGED')
              AND detected_at >= %s - INTERVAL 60 SECOND
            LIMIT 1
            """,
            (
                device_id,
                destination_id,
                access_time
            )
        )

        existing_alert = cursor.fetchone()


        if existing_alert:

            print(
                "Sensitive port check | "
                "existing alert found"
            )

            return False


        # -----------------------------------------------------
        # Create alert
        # -----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO alerts
            (
                device_id,
                history_id,
                alert_type,
                severity,
                title,
                description,
                destination_id,
                detected_at
            )
            VALUES
            (
                %s,
                %s,
                'SENSITIVE_SERVICE_PORT',
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                device_id,
                history_id,
                severity,
                f"Sensitive Service Port Detected",
                (
                    f"Device connected to destination port "
                    f"{destination_port}, associated with "
                    f"{service_name}."
                ),
                destination_id,
                access_time
            )
        )


        connection.commit()


        print(
            f"ALERT CREATED | "
            f"type=SENSITIVE_SERVICE_PORT | "
            f"device={device_id} | "
            f"port={destination_port} | "
            f"service={service_name}"
        )


        return True


    except Exception as error:

        connection.rollback()

        print(
            "Sensitive service port detection error:",
            error
        )

        return False


    finally:

        if cursor is not None:
            cursor.close()

        connection.close()
def calculate_risk_level(risk_score):
    """
    Convert a numerical risk score into a risk level.
    """

    if risk_score >= RISK_LEVELS["CRITICAL"]:
        return "CRITICAL"

    if risk_score >= RISK_LEVELS["HIGH"]:
        return "HIGH"

    if risk_score >= RISK_LEVELS["MEDIUM"]:
        return "MEDIUM"

    if risk_score >= RISK_LEVELS["LOW"]:
        return "LOW"

    return "INFO"


def correlate_alerts(device_id, history_id):
    """
    Correlate all detection alerts generated for one
    network event and create a security incident.

    The individual alerts remain as evidence.
    The security incident represents their combined risk.
    """

    connection = get_connection()

    if connection is None:
        print(
            "Risk correlation: "
            "database connection failed"
        )
        return False

    cursor = None

    try:

        cursor = connection.cursor(
            dictionary=True
        )

        # -----------------------------------------------------
        # Get alerts associated with this event
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT
                alert_id,
                alert_type,
                severity,
                title,
                description
            FROM alerts
            WHERE device_id = %s
              AND history_id = %s
            ORDER BY alert_id
            """,
            (
                device_id,
                history_id
            )
        )

        alerts = cursor.fetchall()


        if not alerts:

            print(
                f"Risk correlation | "
                f"device={device_id} | "
                f"history={history_id} | "
                f"no alerts"
            )

            return False


        # -----------------------------------------------------
        # Calculate combined risk score
        # -----------------------------------------------------

        risk_score = 0

        triggered_rules = []

        for alert in alerts:

            alert_type = alert["alert_type"]

            weight = RISK_WEIGHTS.get(
                alert_type,
                0
            )

            risk_score += weight

            triggered_rules.append(
                alert_type
            )


        risk_level = calculate_risk_level(
            risk_score
        )


        # -----------------------------------------------------
        # Prevent duplicate incident
        # -----------------------------------------------------

        cursor.execute(
            """
            SELECT incident_id
            FROM security_incidents
            WHERE history_id = %s
            LIMIT 1
            """,
            (history_id,)
        )

        existing_incident = cursor.fetchone()


        if existing_incident:

            print(
                f"Risk correlation | "
                f"existing incident found | "
                f"history={history_id}"
            )

            return False


        # -----------------------------------------------------
        # Build incident description
        # -----------------------------------------------------

        rules_text = ", ".join(
            triggered_rules
        )

        title = (
            f"{risk_level} Risk Security Incident"
        )

        description = (
            f"Device {device_id} triggered "
            f"{len(alerts)} detection rule(s): "
            f"{rules_text}. "
            f"Combined risk score: {risk_score}."
        )


        # -----------------------------------------------------
        # Create security incident
        # -----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO security_incidents
            (
                device_id,
                history_id,
                risk_score,
                risk_level,
                title,
                description,
                detected_at
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                (
                    SELECT access_time
                    FROM browsing_history
                    WHERE history_id = %s
                )
            )
            """,
            (
                device_id,
                history_id,
                risk_score,
                risk_level,
                title,
                description,
                history_id
            )
        )


        connection.commit()


        print(
            f"INCIDENT CREATED | "
            f"device={device_id} | "
            f"history={history_id} | "
            f"score={risk_score} | "
            f"level={risk_level}"
        )


        return True


    except Exception as error:

        connection.rollback()

        print(
            "Risk correlation error:",
            error
        )

        return False


    finally:

        if cursor is not None:
            cursor.close()

        connection.close()
def analyze_event(device_id, history_id):
    """
    Run all currently enabled detection rules
    against a newly stored event and correlate
    any generated alerts into a security incident.
    """

    alerts_created = 0

    # Rule 1: Connection burst
    if check_connection_burst(
        device_id,
        history_id
    ):
        alerts_created += 1

    # Rule 2: Repeated destination
    if check_repeated_destination(
        device_id,
        history_id
    ):
        alerts_created += 1

    # Rule 3: New destination
    if check_new_destination(
        device_id,
        history_id
    ):
        alerts_created += 1

    # Rule 4: Unusual destination port
    if check_unusual_port(
        device_id,
        history_id
    ):
        alerts_created += 1

    # Rule 5: Sensitive service port
    if check_sensitive_service_port(
        device_id,
        history_id
    ):
        alerts_created += 1

    # Correlate all alerts generated for this event
    incident_created = correlate_alerts(
        device_id,
        history_id
    )

    return {
        "alerts_created": alerts_created,
        "incident_created": incident_created
    }