from flask import Blueprint, jsonify
from db import get_connection


dashboard_bp = Blueprint("dashboard", __name__)
@dashboard_bp.get("/devices")
def get_devices():

    connection = get_connection()

    if connection is None:
        return jsonify({
            "success": False,
            "error": "Database connection failed"
        }), 500

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                cd.device_id,
                cd.device_ip,
                cd.hostname,
                cd.device_type,
                cd.status,
                cd.last_seen,
                nn.node_code AS gateway_node
            FROM connected_devices cd
            JOIN network_nodes nn
                ON cd.node_id = nn.node_id
            ORDER BY cd.last_seen DESC
        """)

        devices = cursor.fetchall()

        return jsonify({
            "success": True,
            "devices": devices
        }), 200

    except Exception as error:

        print("Database error:", error)

        return jsonify({
            "success": False,
            "error": "Database operation failed"
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        connection.close()

@dashboard_bp.get("/summary")
def dashboard_summary():

    connection = get_connection()

    if connection is None:
        return jsonify({
            "success": False,
            "error": "Database connection failed"
        }), 500

    cursor = None

    try:

        cursor = connection.cursor(dictionary=True)

        # ---------------------------------------------
        # 1. Total devices
        # ---------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total_devices
            FROM connected_devices
        """)

        total_devices = cursor.fetchone()["total_devices"]

        # ---------------------------------------------
        # 2. Active devices
        # ---------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS active_devices
            FROM connected_devices
            WHERE status = 'ACTIVE'
        """)

        active_devices = cursor.fetchone()["active_devices"]

        # ---------------------------------------------
        # 3. Total network events
        # ---------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total_events
            FROM browsing_history
        """)

        total_events = cursor.fetchone()["total_events"]

        # ---------------------------------------------
        # 4. Unique destinations
        # ---------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS unique_destinations
            FROM destinations
        """)

        unique_destinations = cursor.fetchone()["unique_destinations"]

        # ---------------------------------------------
        # 5. TCP / UDP statistics
        # ---------------------------------------------

        cursor.execute("""
            SELECT
                protocol,
                COUNT(*) AS event_count
            FROM browsing_history
            GROUP BY protocol
            ORDER BY event_count DESC
        """)

        protocol_statistics = cursor.fetchall()

        # ---------------------------------------------
        # 6. Recent activity
        # ---------------------------------------------

        cursor.execute("""
            SELECT
                bh.history_id,
                cd.device_ip,
                d.ip_address AS destination_ip,
                d.domain_name,
                bh.protocol,
                bh.source_port,
                bh.destination_port,
                bh.access_time
            FROM browsing_history bh

            JOIN connected_devices cd
                ON bh.device_id = cd.device_id

            JOIN destinations d
                ON bh.destination_id = d.destination_id

            ORDER BY bh.access_time DESC

            LIMIT 10
        """)

        recent_activity = cursor.fetchall()

        # ---------------------------------------------
        # Response
        # ---------------------------------------------

        return jsonify({
            "success": True,

            "summary": {
                "total_devices": total_devices,
                "active_devices": active_devices,
                "total_events": total_events,
                "unique_destinations": unique_destinations
            },

            "protocol_statistics": protocol_statistics,

            "recent_activity": recent_activity
        })

    except Exception as error:

        print(
            "Dashboard database error:",
            error
        )

        return jsonify({
            "success": False,
            "error": "Dashboard query failed"
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        connection.close()

@dashboard_bp.get("/devices/<int:device_id>/activity")
def device_activity(device_id):

    connection = get_connection()

    if connection is None:
        return jsonify({
            "success": False,
            "error": "Database connection failed"
        }), 500

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        # ------------------------------------------------
        # 1. Get device information
        # ------------------------------------------------

        cursor.execute(
            """
            SELECT
                cd.device_id,
                cd.device_ip,
                cd.hostname,
                cd.device_type,
                cd.status,
                cd.last_seen,
                nn.node_code AS gateway_node
            FROM connected_devices cd
            JOIN network_nodes nn
                ON cd.node_id = nn.node_id
            WHERE cd.device_id = %s
            LIMIT 1
            """,
            (device_id,)
        )

        device = cursor.fetchone()

        if device is None:
            return jsonify({
                "success": False,
                "error": "Device not found"
            }), 404

        # ------------------------------------------------
        # 2. Get protocol statistics
        # ------------------------------------------------

        cursor.execute(
            """
            SELECT
                bh.protocol,
                COUNT(*) AS event_count
            FROM browsing_history bh
            WHERE bh.device_id = %s
            GROUP BY bh.protocol
            ORDER BY event_count DESC
            """,
            (device_id,)
        )

        protocol_statistics = cursor.fetchall()

        # ------------------------------------------------
        # 3. Get unique destination count
        # ------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(DISTINCT destination_id) AS count
            FROM browsing_history
            WHERE device_id = %s
            """,
            (device_id,)
        )

        destination_result = cursor.fetchone()

        unique_destinations = (
            destination_result["count"]
            if destination_result
            else 0
        )

        # ------------------------------------------------
        # 4. Get total event count
        # ------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM browsing_history
            WHERE device_id = %s
            """,
            (device_id,)
        )

        event_result = cursor.fetchone()

        total_events = (
            event_result["count"]
            if event_result
            else 0
        )

        # ------------------------------------------------
        # 5. Get recent activity
        # ------------------------------------------------

        cursor.execute(
            """
            SELECT
                bh.history_id,
                bh.access_time,
                bh.protocol,
                bh.source_ip,
                bh.source_port,
                bh.destination_port,
                d.ip_address AS destination_ip,
                d.domain_name
            FROM browsing_history bh
            JOIN destinations d
                ON bh.destination_id = d.destination_id
            WHERE bh.device_id = %s
            ORDER BY bh.access_time DESC
            LIMIT 50
            """,
            (device_id,)
        )

        recent_activity = cursor.fetchall()

        # ------------------------------------------------
        # 6. Return result
        # ------------------------------------------------

        return jsonify({
            "success": True,

            "device": device,

            "statistics": {
                "total_events": total_events,
                "unique_destinations": unique_destinations
            },

            "protocol_statistics": protocol_statistics,

            "recent_activity": recent_activity
        }), 200

    except Exception as error:

        print(
            "Device activity error:",
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

@dashboard_bp.get("/events-over-time")
def events_over_time():

    connection = get_connection()

    if connection is None:
        return jsonify({
            "success": False,
            "error": "Database connection failed"
        }), 500

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                DATE_FORMAT(access_time, '%Y-%m-%d %H:%i') AS time_bucket,
                COUNT(*) AS event_count
            FROM browsing_history
            WHERE access_time >= NOW() - INTERVAL 24 HOUR
            GROUP BY DATE_FORMAT(access_time, '%Y-%m-%d %H:%i')
            ORDER BY time_bucket ASC
            """
        )

        events = cursor.fetchall()

        return jsonify({
            "success": True,
            "events": events
        }), 200

    except Exception as error:

        print("Events over time error:", error)

        return jsonify({
            "success": False,
            "error": "Database operation failed"
        }), 500

    finally:

        if cursor is not None:
            cursor.close()

        connection.close()
@dashboard_bp.get("/top-destinations")
def top_destinations():

    connection = get_connection()

    if connection is None:
        return jsonify({
            "success": False,
            "error": "Database connection failed"
        }), 500

    cursor = None

    try:

        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                d.ip_address AS destination_ip,
                d.domain_name,
                COUNT(*) AS event_count
            FROM browsing_history bh
            JOIN destinations d
                ON bh.destination_id = d.destination_id
            GROUP BY
                d.destination_id,
                d.ip_address,
                d.domain_name
            ORDER BY event_count DESC
            LIMIT 10
            """
        )

        destinations = cursor.fetchall()

        return jsonify({
            "success": True,
            "destinations": destinations
        }), 200

    except Exception as error:

        print(
            "Top destinations error:",
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