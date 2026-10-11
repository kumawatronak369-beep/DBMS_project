from flask import Blueprint, request, jsonify
from datetime import datetime, timezone

from db import get_connection
from detection.detection_engine import analyze_event

events_bp = Blueprint("events", __name__)


DEDUPLICATION_SECONDS = 30


def parse_timestamp(timestamp):

    return datetime.fromisoformat(
        timestamp.replace("Z", "+00:00")
    )


# =========================================================
# RECEIVE NETWORK EVENT
# =========================================================

@events_bp.post("/network-events")
def receive_network_event():

    data = request.get_json(silent=True)


    if not data:

        return jsonify({
            "success": False,
            "error": "Invalid JSON"
        }), 400


    required_fields = {
        "gateway_node",
        "device_ip",
        "destination_ip",
        "timestamp"
    }


    missing = required_fields - data.keys()


    if missing:

        return jsonify({
            "success": False,
            "error": "Missing fields",
            "fields": sorted(missing)
        }), 400


    # -----------------------------------------------------
    # Parse timestamp
    # -----------------------------------------------------

    try:

        event_time = parse_timestamp(
            data["timestamp"]
        )

    except (ValueError, TypeError):

        return jsonify({
            "success": False,
            "error": "Invalid timestamp"
        }), 400


    # -----------------------------------------------------
    # Database connection
    # -----------------------------------------------------

    connection = get_connection()


    if connection is None:

        return jsonify({
            "success": False,
            "error": "Database connection failed"
        }), 500


    cursor = None


    try:

        cursor = connection.cursor(
            dictionary=True
        )


        connection.start_transaction()


        # =================================================
        # 1. Find network node
        # =================================================

        cursor.execute(
            """
            SELECT node_id
            FROM network_nodes
            WHERE node_code = %s
            """,
            (
                data["gateway_node"],
            )
        )


        node = cursor.fetchone()


        if node is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "error": "Gateway node not found"
            }), 404


        node_id = node["node_id"]


        # =================================================
        # 2. Find connected device
        # =================================================

        cursor.execute(
            """
            SELECT device_id
            FROM connected_devices
            WHERE node_id = %s
              AND device_ip = %s
            LIMIT 1
            FOR UPDATE
            """,
            (
                node_id,
                data["device_ip"]
            )
        )


        device = cursor.fetchone()


        if device is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "error": "Connected device not found"
            }), 404


        device_id = device["device_id"]


        # -------------------------------------------------
        # Update device activity
        # -------------------------------------------------

        cursor.execute(
            """
            UPDATE connected_devices
            SET last_seen = %s,
                status = 'ACTIVE'
            WHERE device_id = %s
            """,
            (
                event_time,
                device_id
            )
        )


        # =================================================
        # 3. Find or create destination
        # =================================================

        domain = data.get("domain")


        cursor.execute(
            """
            SELECT destination_id
            FROM destinations
            WHERE ip_address = %s
              AND (
                    domain_name = %s
                    OR (
                        domain_name IS NULL
                        AND %s IS NULL
                    )
                  )
            LIMIT 1
            FOR UPDATE
            """,
            (
                data["destination_ip"],
                domain,
                domain
            )
        )


        destination = cursor.fetchone()


        # -------------------------------------------------
        # Destination doesn't exist
        # -------------------------------------------------

        if destination is None:

            cursor.execute(
                """
                INSERT INTO destinations
                (
                    ip_address,
                    domain_name,
                    first_seen,
                    last_seen
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    data["destination_ip"],
                    domain,
                    event_time,
                    event_time
                )
            )


            destination_id = cursor.lastrowid


        # -------------------------------------------------
        # Destination already exists
        # -------------------------------------------------

        else:

            destination_id = destination[
                "destination_id"
            ]


            cursor.execute(
                """
                UPDATE destinations
                SET last_seen = %s
                WHERE destination_id = %s
                """,
                (
                    event_time,
                    destination_id
                )
            )


        # =================================================
        # 4. Check duplicate event
        # =================================================

        cursor.execute(
            """
            SELECT
                history_id,
                access_time,
                protocol,
                destination_port
            FROM browsing_history
            WHERE device_id = %s
              AND destination_id = %s
              AND protocol = %s
              AND (
                    destination_port = %s
                    OR (
                        destination_port IS NULL
                        AND %s IS NULL
                    )
                  )
            ORDER BY access_time DESC
            LIMIT 1
            FOR UPDATE
            """,
            (
                device_id,
                destination_id,
                data.get("protocol"),
                data.get("destination_port"),
                data.get("destination_port")
            )
        )


        previous = cursor.fetchone()


        if previous is not None:

            previous_time = previous[
                "access_time"
            ]


            if previous_time.tzinfo is None:

                previous_time = previous_time.replace(
                    tzinfo=timezone.utc
                )


            time_difference = (
                event_time - previous_time
            ).total_seconds()


            if (
                0 <= time_difference
                < DEDUPLICATION_SECONDS
            ):

                connection.commit()


                return jsonify({
                    "success": True,
                    "stored": False,
                    "reason":
                        "Duplicate within 30 seconds",
                    "device_id": device_id,
                    "destination_id":
                        destination_id
                }), 200


        # =================================================
        # 5. Store new browsing history
        # =================================================

        cursor.execute(
            """
            INSERT INTO browsing_history
            (
                device_id,
                destination_id,
                access_time,
                protocol,
                source_ip,
                source_port,
                destination_port
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                device_id,
                destination_id,
                event_time,
                data.get("protocol"),
                data.get("device_ip"),
                data.get("source_port"),
                data.get("destination_port")
            )
        )

        history_id = cursor.lastrowid

        connection.commit()


        # =========================================================
        # 6. Run detection engine
        # =========================================================

        detection_result = analyze_event(
            device_id,
            history_id
        )

        alerts_created = detection_result["alerts_created"]
        incident_created = detection_result["incident_created"]


        return jsonify({
            "success": True,
            "stored": True,
            "history_id": history_id,
            "device_id": device_id,
            "destination_id": destination_id,
            "alerts_created": alerts_created,
            "incident_created": incident_created,
            "message": "Network event stored"
        }), 200


    except Exception as error:

        connection.rollback()


        print(
            "Database error:",
            error
        )


        return jsonify({
            "success": False,
            "error": "Database operation failed"
        }), 500


    finally:

        if cursor is not None:

            cursor.close()


        connection.close()


# =========================================================
# DNS CORRELATION
# =========================================================

@events_bp.post("/network-events/dns-correlation")
def correlate_dns():

    data = request.get_json(silent=True)


    if not data:

        return jsonify({
            "success": False,
            "error": "Invalid JSON"
        }), 400


    required_fields = {
        "device_ip",
        "destination_ip",
        "domain"
    }


    missing = required_fields - data.keys()


    if missing:

        return jsonify({
            "success": False,
            "error": "Missing fields",
            "fields": sorted(missing)
        }), 400


    device_ip = data["device_ip"]
    destination_ip = data["destination_ip"]
    domain = data["domain"]


    if not domain:

        return jsonify({
            "success": False,
            "error": "Domain cannot be empty"
        }), 400


    # -----------------------------------------------------
    # Database connection
    # -----------------------------------------------------

    connection = get_connection()


    if connection is None:

        return jsonify({
            "success": False,
            "error": "Database connection failed"
        }), 500


    cursor = None


    try:

        cursor = connection.cursor(
            dictionary=True
        )


        connection.start_transaction()


        # =================================================
        # 1. Find device
        # =================================================

        cursor.execute(
            """
            SELECT device_id
            FROM connected_devices
            WHERE device_ip = %s
            LIMIT 1
            """,
            (
                device_ip,
            )
        )


        device = cursor.fetchone()


        if device is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "error": "Connected device not found"
            }), 404


        device_id = device[
            "device_id"
        ]


        # =================================================
        # 2. Find destination
        # =================================================

        cursor.execute(
            """
            SELECT destination_id
            FROM destinations
            WHERE ip_address = %s
            ORDER BY destination_id DESC
            LIMIT 1
            """,
            (
                destination_ip,
            )
        )


        destination = cursor.fetchone()


        if destination is None:

            connection.rollback()

            return jsonify({
                "success": False,
                "error": "Destination not found"
            }), 404


        destination_id = destination[
            "destination_id"
        ]


        # =================================================
        # 3. Update destination domain
        # =================================================

        cursor.execute(
            """
            UPDATE destinations
            SET domain_name = %s
            WHERE destination_id = %s
            """,
            (
                domain,
                destination_id
            )
        )


        # =================================================
        # 4. Find recent NULL-domain traffic
        #
        # The domain is stored in destinations, so updating
        # the destination automatically makes it visible
        # to browsing_history queries using that destination.
        # =================================================

        cursor.execute(
            """
            SELECT COUNT(*) AS event_count
            FROM browsing_history
            WHERE device_id = %s
              AND destination_id = %s
              AND access_time >=
                    NOW() - INTERVAL 30 SECOND
            """,
            (
                device_id,
                destination_id
            )
        )


        result = cursor.fetchone()


        updated_history = (
            result["event_count"]
            if result
            else 0
        )


        connection.commit()


        return jsonify({
            "success": True,
            "domain": domain,
            "destination_ip":
                destination_ip,
            "updated_history":
                updated_history,
            "message":
                "DNS correlation completed"
        }), 200


    except Exception as error:

        connection.rollback()


        print(
            "DNS correlation error:",
            error
        )


        return jsonify({
            "success": False,
            "error": "DNS correlation failed"
        }), 500


    finally:

        if cursor is not None:

            cursor.close()


        connection.close()