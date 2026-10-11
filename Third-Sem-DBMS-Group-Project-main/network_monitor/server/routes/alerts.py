from flask import Blueprint, jsonify, request

from db import get_connection


alerts_bp = Blueprint(
    "alerts",
    __name__,
    url_prefix="/dashboard"
)


# =========================================================
# GET ALERTS
# =========================================================

@alerts_bp.get("/alerts")
def get_alerts():

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


        # -------------------------------------------------
        # Optional limit
        # -------------------------------------------------

        try:

            limit = int(
                request.args.get(
                    "limit",
                    20
                )
            )

        except (ValueError, TypeError):

            limit = 20


        # Keep the API within a reasonable range.

        limit = max(
            1,
            min(limit, 100)
        )


        # -------------------------------------------------
        # Get recent alerts
        # -------------------------------------------------

        query = f"""
            SELECT
                a.alert_id,
                a.device_id,
                a.history_id,
                a.alert_type,
                a.severity,
                a.title,
                a.description,
                a.destination_id,
                a.detected_at,
                a.status,
                a.created_at,

                cd.device_ip,
                cd.mac_address,
                cd.hostname,

                d.ip_address AS destination_ip,
                d.domain_name

            FROM alerts a

            LEFT JOIN connected_devices cd
                ON a.device_id = cd.device_id

            LEFT JOIN destinations d
                ON a.destination_id = d.destination_id

            ORDER BY a.detected_at DESC,
                     a.alert_id DESC

            LIMIT {limit}
        """


        cursor.execute(query)

        alerts = cursor.fetchall()


        return jsonify({
            "success": True,
            "alerts": alerts,
            "count": len(alerts)
        }), 200


    except Exception as error:

        print(
            "Alerts API error:",
            error
        )


        return jsonify({
            "success": False,
            "error": "Failed to retrieve alerts"
        }), 500


    finally:

        if cursor is not None:
            cursor.close()

        connection.close()


# =========================================================
# GET ALERT SUMMARY
# =========================================================

@alerts_bp.get("/alerts/summary")
def get_alert_summary():

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


        cursor.execute(
            """
            SELECT

                COUNT(*) AS total_alerts,

                SUM(
                    CASE
                        WHEN status = 'OPEN'
                        THEN 1
                        ELSE 0
                    END
                ) AS open_alerts,

                SUM(
                    CASE
                        WHEN severity = 'CRITICAL'
                        THEN 1
                        ELSE 0
                    END
                ) AS critical_alerts,

                SUM(
                    CASE
                        WHEN severity = 'HIGH'
                        THEN 1
                        ELSE 0
                    END
                ) AS high_alerts,

                SUM(
                    CASE
                        WHEN severity = 'MEDIUM'
                        THEN 1
                        ELSE 0
                    END
                ) AS medium_alerts,

                SUM(
                    CASE
                        WHEN severity = 'LOW'
                        THEN 1
                        ELSE 0
                    END
                ) AS low_alerts

            FROM alerts
            """
        )


        summary = cursor.fetchone()


        return jsonify({
            "success": True,
            "summary": summary
        }), 200


    except Exception as error:

        print(
            "Alert summary API error:",
            error
        )


        return jsonify({
            "success": False,
            "error": "Failed to retrieve alert summary"
        }), 500


    finally:

        if cursor is not None:
            cursor.close()

        connection.close()

# =========================================================
# ACKNOWLEDGE ALERT
# =========================================================

@alerts_bp.patch("/alerts/<int:alert_id>/acknowledge")
def acknowledge_alert(alert_id):

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

        # -------------------------------------------------
        # Check alert
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                alert_id,
                status
            FROM alerts
            WHERE alert_id = %s
            LIMIT 1
            """,
            (alert_id,)
        )

        alert = cursor.fetchone()

        if alert is None:

            return jsonify({
                "success": False,
                "error": "Alert not found"
            }), 404


        # -------------------------------------------------
        # Validate status
        # -------------------------------------------------

        if alert["status"] == "RESOLVED":

            return jsonify({
                "success": False,
                "error": "Resolved alert cannot be acknowledged"
            }), 409


        if alert["status"] == "ACKNOWLEDGED":

            return jsonify({
                "success": True,
                "message": "Alert already acknowledged",
                "alert_id": alert_id,
                "status": "ACKNOWLEDGED"
            }), 200


        # -------------------------------------------------
        # Update alert
        # -------------------------------------------------

        cursor.execute(
            """
            UPDATE alerts
            SET status = 'ACKNOWLEDGED'
            WHERE alert_id = %s
            """,
            (alert_id,)
        )

        connection.commit()


        return jsonify({
            "success": True,
            "message": "Alert acknowledged",
            "alert_id": alert_id,
            "status": "ACKNOWLEDGED"
        }), 200


    except Exception as error:

        connection.rollback()

        print(
            "Acknowledge alert error:",
            error
        )

        return jsonify({
            "success": False,
            "error": "Failed to acknowledge alert"
        }), 500


    finally:

        if cursor is not None:
            cursor.close()

        connection.close()

# =========================================================
# RESOLVE ALERT
# =========================================================

@alerts_bp.patch("/alerts/<int:alert_id>/resolve")
def resolve_alert(alert_id):

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

        # -------------------------------------------------
        # Check alert
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                alert_id,
                status
            FROM alerts
            WHERE alert_id = %s
            LIMIT 1
            """,
            (alert_id,)
        )

        alert = cursor.fetchone()

        if alert is None:

            return jsonify({
                "success": False,
                "error": "Alert not found"
            }), 404


        # -------------------------------------------------
        # Already resolved
        # -------------------------------------------------

        if alert["status"] == "RESOLVED":

            return jsonify({
                "success": True,
                "message": "Alert already resolved",
                "alert_id": alert_id,
                "status": "RESOLVED"
            }), 200


        # -------------------------------------------------
        # Resolve
        # -------------------------------------------------

        cursor.execute(
            """
            UPDATE alerts
            SET status = 'RESOLVED'
            WHERE alert_id = %s
            """,
            (alert_id,)
        )

        connection.commit()


        return jsonify({
            "success": True,
            "message": "Alert resolved",
            "alert_id": alert_id,
            "status": "RESOLVED"
        }), 200


    except Exception as error:

        connection.rollback()

        print(
            "Resolve alert error:",
            error
        )

        return jsonify({
            "success": False,
            "error": "Failed to resolve alert"
        }), 500


    finally:

        if cursor is not None:
            cursor.close()

        connection.close()