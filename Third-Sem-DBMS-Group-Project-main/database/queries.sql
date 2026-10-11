-- ============================================================
-- PRIVATE NETWORK MONITORING SYSTEM
-- DEMONSTRATION QUERIES (read-only)
-- MySQL 8+
--
-- Every statement here is a SELECT. Nothing modifies data.
-- Queries that need parameters use session variables (@name)
-- so the file can be run as-is in MySQL Workbench.
-- ============================================================

USE network_monitor;


-- ------------------------------------------------------------
-- 1. Recent activity (multi-table JOIN, ORDER BY, LIMIT)
-- ------------------------------------------------------------
SELECT
    h.history_id,
    h.observed_at,
    dv.device_identifier,
    dv.ip_address AS device_ip,
    n.node_name,
    d.ip_address AS destination_ip,
    d.domain
FROM network_history h
JOIN devices dv
    ON h.device_id = dv.device_id
JOIN nodes n
    ON h.node_id = n.node_id
JOIN destinations d
    ON h.destination_id = d.destination_id
ORDER BY h.observed_at DESC
LIMIT 50;


-- ------------------------------------------------------------
-- 2. Most visited destinations (GROUP BY, COUNT)
-- ------------------------------------------------------------
SELECT
    d.domain,
    d.ip_address,
    COUNT(*) AS event_count
FROM network_history h
JOIN destinations d
    ON h.destination_id = d.destination_id
GROUP BY
    d.destination_id,
    d.domain,
    d.ip_address
ORDER BY event_count DESC;


-- ------------------------------------------------------------
-- 3. Most active devices
-- ------------------------------------------------------------
SELECT
    dv.device_identifier,
    dv.ip_address,
    n.node_name,
    COUNT(*) AS event_count
FROM network_history h
JOIN devices dv
    ON h.device_id = dv.device_id
JOIN nodes n
    ON dv.node_id = n.node_id
GROUP BY
    dv.device_id,
    dv.device_identifier,
    dv.ip_address,
    n.node_name
ORDER BY event_count DESC;


-- ------------------------------------------------------------
-- 4. Activity by node
-- ------------------------------------------------------------
SELECT
    n.node_name,
    COUNT(*) AS event_count
FROM network_history h
JOIN nodes n
    ON h.node_id = n.node_id
GROUP BY
    n.node_id,
    n.node_name
ORDER BY event_count DESC;


-- ------------------------------------------------------------
-- 5. Unique devices accessing each destination (COUNT DISTINCT)
-- ------------------------------------------------------------
SELECT
    d.domain,
    COUNT(DISTINCT h.device_id) AS unique_devices
FROM network_history h
JOIN destinations d
    ON h.destination_id = d.destination_id
GROUP BY
    d.destination_id,
    d.domain
ORDER BY unique_devices DESC;


-- ------------------------------------------------------------
-- 6. Activity by day (date aggregation)
-- ------------------------------------------------------------
SELECT
    DATE(observed_at) AS activity_date,
    COUNT(*) AS event_count
FROM network_history
GROUP BY DATE(observed_at)
ORDER BY activity_date;


-- ------------------------------------------------------------
-- 7. Activity within a date range (WHERE ... BETWEEN)
-- ------------------------------------------------------------
SET @range_start = NOW() - INTERVAL 24 HOUR;
SET @range_end   = NOW();

SELECT
    h.history_id,
    h.observed_at,
    dv.device_identifier,
    n.node_name,
    d.domain
FROM network_history h
JOIN devices dv
    ON h.device_id = dv.device_id
JOIN nodes n
    ON h.node_id = n.node_id
JOIN destinations d
    ON h.destination_id = d.destination_id
WHERE h.observed_at BETWEEN @range_start AND @range_end
ORDER BY h.observed_at DESC;


-- ------------------------------------------------------------
-- 8. Busy destinations only (HAVING)
-- ------------------------------------------------------------
SELECT
    d.domain,
    COUNT(*) AS event_count,
    COUNT(DISTINCT h.device_id) AS unique_devices
FROM network_history h
JOIN destinations d
    ON h.destination_id = d.destination_id
GROUP BY
    d.destination_id,
    d.domain
HAVING event_count >= 50
ORDER BY event_count DESC;


-- ------------------------------------------------------------
-- 9. Nodes with their device counts, including nodes that have
--    no devices yet (LEFT JOIN)
-- ------------------------------------------------------------
SELECT
    n.node_code,
    n.node_name,
    n.status,
    COUNT(dv.device_id) AS device_count
FROM nodes n
LEFT JOIN devices dv
    ON dv.node_id = n.node_id
GROUP BY
    n.node_id,
    n.node_code,
    n.node_name,
    n.status
ORDER BY n.node_name;


-- ------------------------------------------------------------
-- 10. Devices that have never generated stored activity
--     (LEFT JOIN + IS NULL anti-join)
-- ------------------------------------------------------------
SELECT
    dv.device_id,
    dv.device_identifier,
    dv.ip_address
FROM devices dv
LEFT JOIN network_history h
    ON h.device_id = dv.device_id
WHERE h.history_id IS NULL;


-- ------------------------------------------------------------
-- 11. Destination investigation: summary for one destination
-- ------------------------------------------------------------
SET @destination_domain = 'github.com';

SELECT
    d.destination_id,
    d.domain,
    d.ip_address,
    d.category,
    d.first_seen,
    d.last_seen,
    COUNT(h.history_id) AS total_events,
    COUNT(DISTINCT h.device_id) AS unique_devices,
    COUNT(DISTINCT h.node_id) AS nodes_involved
FROM destinations d
LEFT JOIN network_history h
    ON h.destination_id = d.destination_id
WHERE d.domain = @destination_domain
GROUP BY
    d.destination_id,
    d.domain,
    d.ip_address,
    d.category,
    d.first_seen,
    d.last_seen;


-- ------------------------------------------------------------
-- 12. Destination investigation: devices accessing it
-- ------------------------------------------------------------
SELECT
    dv.device_identifier,
    dv.ip_address AS device_ip,
    n.node_name,
    COUNT(*) AS access_count,
    MAX(h.observed_at) AS last_access
FROM network_history h
JOIN destinations d
    ON h.destination_id = d.destination_id
JOIN devices dv
    ON h.device_id = dv.device_id
JOIN nodes n
    ON h.node_id = n.node_id
WHERE d.domain = @destination_domain
GROUP BY
    dv.device_id,
    dv.device_identifier,
    dv.ip_address,
    n.node_name
ORDER BY access_count DESC;


-- ------------------------------------------------------------
-- 13. Device investigation: destinations one device visited
-- ------------------------------------------------------------
SET @device_identifier = 'PC-LAB-A-001';

SELECT
    d.domain,
    d.ip_address AS destination_ip,
    d.category,
    COUNT(*) AS visits,
    MAX(h.observed_at) AS last_visit
FROM network_history h
JOIN devices dv
    ON h.device_id = dv.device_id
JOIN destinations d
    ON h.destination_id = d.destination_id
WHERE dv.device_identifier = @device_identifier
GROUP BY
    d.destination_id,
    d.domain,
    d.ip_address,
    d.category
ORDER BY visits DESC;


-- ------------------------------------------------------------
-- 14. Report: activity per node with unique devices
-- ------------------------------------------------------------
SELECT
    n.node_name,
    COUNT(*) AS event_count,
    COUNT(DISTINCT h.device_id) AS unique_devices
FROM network_history h
JOIN nodes n
    ON h.node_id = n.node_id
GROUP BY
    n.node_id,
    n.node_name
ORDER BY event_count DESC;


-- ------------------------------------------------------------
-- 15. Destination category breakdown
-- ------------------------------------------------------------
SELECT
    d.category,
    COUNT(*) AS event_count
FROM network_history h
JOIN destinations d
    ON h.destination_id = d.destination_id
GROUP BY d.category
ORDER BY event_count DESC;


-- ------------------------------------------------------------
-- 16. Search: device / IP / domain text search
-- ------------------------------------------------------------
SET @search = '%lab-a%';

SELECT
    h.history_id,
    h.observed_at,
    dv.device_identifier,
    dv.ip_address AS device_ip,
    n.node_name,
    d.domain
FROM network_history h
JOIN devices dv
    ON h.device_id = dv.device_id
JOIN nodes n
    ON h.node_id = n.node_id
JOIN destinations d
    ON h.destination_id = d.destination_id
WHERE dv.device_identifier LIKE @search
   OR dv.ip_address        LIKE @search
   OR d.domain             LIKE @search
ORDER BY h.observed_at DESC
LIMIT 100;


-- ------------------------------------------------------------
-- 17. 30-SECOND RULE: the duplicate check used by the backend.
--     A row returned means the incoming event is a duplicate
--     and must NOT be inserted.
--     cutoff = incoming_event_time - 30 seconds
-- ------------------------------------------------------------
SET @device_id      = 1;
SET @destination_id = 1;
SET @incoming_time  = NOW();

SELECT
    history_id,
    observed_at
FROM network_history
WHERE device_id = @device_id
  AND destination_id = @destination_id
  AND observed_at >= @incoming_time - INTERVAL 30 SECOND
ORDER BY observed_at DESC
LIMIT 1;


-- ------------------------------------------------------------
-- 18. Audit: verify no stored pair of events breaks the 30-second
--     rule. Returns zero rows when the data is consistent.
-- ------------------------------------------------------------
SELECT
    a.device_id,
    a.destination_id,
    a.observed_at AS first_event,
    b.observed_at AS second_event
FROM network_history a
JOIN network_history b
    ON  a.device_id = b.device_id
    AND a.destination_id = b.destination_id
    AND b.observed_at > a.observed_at
    AND b.observed_at < a.observed_at + INTERVAL 30 SECOND;


-- ------------------------------------------------------------
-- 19. Integrity audit: every event's device must belong to the
--     event's node. Returns zero rows (enforced by the composite
--     foreign key fk_history_device_node).
-- ------------------------------------------------------------
SELECT
    h.history_id,
    h.node_id AS event_node,
    dv.node_id AS device_node
FROM network_history h
JOIN devices dv
    ON h.device_id = dv.device_id
WHERE h.node_id <> dv.node_id;


-- ------------------------------------------------------------
-- 20. Dashboard summary metrics (single-row aggregates)
-- ------------------------------------------------------------
SELECT
    (SELECT COUNT(*) FROM nodes WHERE status = 'ACTIVE') AS active_nodes,
    (SELECT COUNT(*) FROM devices) AS registered_devices,
    (SELECT COUNT(*) FROM network_history
        WHERE observed_at >= CURDATE()) AS todays_events,
    (SELECT COUNT(*) FROM destinations) AS known_destinations;


-- ------------------------------------------------------------
-- 21. Connection metadata: events with a protocol and ports
--     (NULL for simulated / DNS-only events and for events stored before these columns existed)
-- ------------------------------------------------------------
SELECT
    h.history_id,
    h.observed_at,
    dv.device_identifier,
    d.ip_address AS destination_ip,
    d.domain,
    h.protocol,
    h.source_port,
    h.destination_port
FROM network_history h
JOIN devices dv
    ON h.device_id = dv.device_id
JOIN destinations d
    ON h.destination_id = d.destination_id
WHERE h.protocol IS NOT NULL
ORDER BY h.observed_at DESC
LIMIT 50;


-- ------------------------------------------------------------
-- 22. Most used destination ports (only events that recorded one)
-- ------------------------------------------------------------
SELECT
    destination_port,
    protocol,
    COUNT(*) AS event_count
FROM network_history
WHERE destination_port IS NOT NULL
GROUP BY destination_port, protocol
ORDER BY event_count DESC;
