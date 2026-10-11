-- ============================================================
-- PRIVATE NETWORK MONITORING SYSTEM
-- SAFE DATABASE SCHEMA
-- MySQL 8+
-- ============================================================

CREATE DATABASE IF NOT EXISTS network_monitor
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE network_monitor;

-- ============================================================
-- 1. USERS
-- ============================================================

CREATE TABLE users (
    user_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    name VARCHAR(100) NOT NULL,

    email VARCHAR(255) NOT NULL,

    password_hash VARCHAR(255) NOT NULL,

    role ENUM('ADMIN', 'ANALYST')
        NOT NULL DEFAULT 'ANALYST',

    status ENUM('ACTIVE', 'DISABLED')
        NOT NULL DEFAULT 'ACTIVE',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    last_login DATETIME NULL,

    PRIMARY KEY (user_id),

    CONSTRAINT uq_users_email
        UNIQUE (email)
)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- ============================================================
-- 2. NODES
-- ============================================================

CREATE TABLE nodes (
    node_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    node_code VARCHAR(50) NOT NULL,

    node_name VARCHAR(100) NOT NULL,

    ip_address VARCHAR(45) NOT NULL,

    location VARCHAR(150) NOT NULL,

    description VARCHAR(500) NULL,

    status ENUM('ACTIVE', 'INACTIVE', 'OFFLINE')
        NOT NULL DEFAULT 'ACTIVE',

    registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    last_seen DATETIME NULL,

    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (node_id),

    CONSTRAINT uq_nodes_node_code
        UNIQUE (node_code),

    INDEX idx_nodes_status (status),

    INDEX idx_nodes_last_seen (last_seen)
)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- ============================================================
-- 3. DEVICES
-- ============================================================

CREATE TABLE devices (
    device_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    node_id BIGINT UNSIGNED NOT NULL,

    device_identifier VARCHAR(100) NOT NULL,

    device_name VARCHAR(100) NULL,

    ip_address VARCHAR(45) NOT NULL,

    mac_address VARCHAR(17) NULL,

    hostname VARCHAR(255) NULL,

    status ENUM('ACTIVE', 'INACTIVE', 'UNKNOWN')
        NOT NULL DEFAULT 'UNKNOWN',

    first_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (device_id),

    /*
     * Required so network_history can enforce that a device
     * belongs to the node recorded in the event.
     */
    CONSTRAINT uq_devices_node_device
        UNIQUE (node_id, device_id),

    /*
     * Device identifiers are unique within a node.
     */
    CONSTRAINT uq_devices_node_identifier
        UNIQUE (node_id, device_identifier),

    CONSTRAINT fk_devices_node
        FOREIGN KEY (node_id)
        REFERENCES nodes(node_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    INDEX idx_devices_ip
        (ip_address),

    INDEX idx_devices_status
        (status),

    INDEX idx_devices_last_seen
        (last_seen)
)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- ============================================================
-- 4. DESTINATIONS
-- ============================================================

CREATE TABLE destinations (
    destination_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    ip_address VARCHAR(45) NOT NULL,

    domain VARCHAR(255) NULL,

    /*
     * Used only for reliable uniqueness when domain is NULL.
     * The actual domain column remains NULL when DNS information
     * was not observable.
     */
    domain_key VARCHAR(255)
        GENERATED ALWAYS AS (COALESCE(domain, '')) STORED,

    category ENUM(
        'SEARCH',
        'SOCIAL',
        'DEVELOPMENT',
        'EDUCATION',
        'VIDEO',
        'CLOUD',
        'OTHER',
        'UNKNOWN'
    )
    NOT NULL DEFAULT 'UNKNOWN',

    first_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (destination_id),

    /*
     * Prevent duplicate destination records for the same
     * IP + domain combination, including NULL domains.
     */
    CONSTRAINT uq_destinations_ip_domain
        UNIQUE (ip_address, domain_key),

    INDEX idx_destinations_domain
        (domain),

    INDEX idx_destinations_category
        (category),

    INDEX idx_destinations_last_seen
        (last_seen)
)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- ============================================================
-- 5. COLLECTOR API KEYS
-- ============================================================

CREATE TABLE collector_api_keys (
    api_key_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    node_id BIGINT UNSIGNED NOT NULL,

    key_name VARCHAR(100) NOT NULL,

    key_hash VARCHAR(255) NOT NULL,

    status ENUM('ACTIVE', 'REVOKED')
        NOT NULL DEFAULT 'ACTIVE',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    last_used_at DATETIME NULL,

    revoked_at DATETIME NULL,

    PRIMARY KEY (api_key_id),

    CONSTRAINT uq_collector_api_key_hash
        UNIQUE (key_hash),

    CONSTRAINT fk_collector_api_keys_node
        FOREIGN KEY (node_id)
        REFERENCES nodes(node_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    INDEX idx_collector_api_keys_node_status
        (node_id, status)
)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;


-- ============================================================
-- 6. NETWORK HISTORY
-- ============================================================

CREATE TABLE network_history (
    history_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    device_id BIGINT UNSIGNED NOT NULL,

    node_id BIGINT UNSIGNED NOT NULL,

    destination_id BIGINT UNSIGNED NOT NULL,

    observed_at DATETIME NOT NULL,

    /*
     * Connection metadata, when the collector could observe it (NULL otherwise, e.g. for
     * simulated or DNS-only events). These describe THIS event only, so they live here and
     * not in devices/destinations. They are NOT part of the 30-second duplicate rule.
     */
    protocol ENUM('TCP', 'UDP') NULL,

    source_port SMALLINT UNSIGNED NULL,

    destination_port SMALLINT UNSIGNED NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (history_id),

    /*
     * Ensures the referenced device exists.
     */
    CONSTRAINT fk_history_device
        FOREIGN KEY (device_id)
        REFERENCES devices(device_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    /*
     * Ensures the referenced node exists.
     */
    CONSTRAINT fk_history_node
        FOREIGN KEY (node_id)
        REFERENCES nodes(node_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    /*
     * IMPORTANT:
     * Guarantees that the device actually belongs to the
     * node recorded in this history event.
     */
    CONSTRAINT fk_history_device_node
        FOREIGN KEY (node_id, device_id)
        REFERENCES devices(node_id, device_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    /*
     * Ensures the destination exists.
     */
    CONSTRAINT fk_history_destination
        FOREIGN KEY (destination_id)
        REFERENCES destinations(destination_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    INDEX idx_history_device_time
        (device_id, observed_at),

    INDEX idx_history_node_time
        (node_id, observed_at),

    INDEX idx_history_destination_time
        (destination_id, observed_at),

    INDEX idx_history_time
        (observed_at)
)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;
