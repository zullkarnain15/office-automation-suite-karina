CREATE TABLE att_data_repair_settings (
    att_data_repair_settings_id INTEGER PRIMARY KEY
        CHECK (att_data_repair_settings_id = 1),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    minimum_duration_minutes INTEGER NOT NULL DEFAULT 61
        CHECK (minimum_duration_minutes BETWEEN 1 AND 1440),
    weekday_default_in TEXT NOT NULL DEFAULT '09:30'
        CHECK (weekday_default_in GLOB '[0-2][0-9]:[0-5][0-9]'),
    weekday_default_out TEXT NOT NULL DEFAULT '17:00'
        CHECK (weekday_default_out GLOB '[0-2][0-9]:[0-5][0-9]'),
    saturday_default_in TEXT NOT NULL DEFAULT '09:30'
        CHECK (saturday_default_in GLOB '[0-2][0-9]:[0-5][0-9]'),
    saturday_default_out TEXT NOT NULL DEFAULT '12:05'
        CHECK (saturday_default_out GLOB '[0-2][0-9]:[0-5][0-9]'),
    sunday_invalid_default_in TEXT NOT NULL DEFAULT '09:30'
        CHECK (sunday_invalid_default_in GLOB '[0-2][0-9]:[0-5][0-9]'),
    sunday_invalid_default_out TEXT NOT NULL DEFAULT '12:05'
        CHECK (sunday_invalid_default_out GLOB '[0-2][0-9]:[0-5][0-9]'),
    txt_max_rows INTEGER NOT NULL DEFAULT 10000 CHECK (txt_max_rows > 0),
    generate_txt INTEGER NOT NULL DEFAULT 1 CHECK (generate_txt IN (0, 1)),
    generate_excel_report INTEGER NOT NULL DEFAULT 1
        CHECK (generate_excel_report IN (0, 1)),
    use_global_period INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_period IN (0, 1)),
    use_global_output INTEGER NOT NULL DEFAULT 1
        CHECK (use_global_output IN (0, 1)),
    updated_at TEXT NOT NULL,
    updated_by TEXT,
    CHECK (weekday_default_out > weekday_default_in),
    CHECK (saturday_default_out > saturday_default_in),
    CHECK (sunday_invalid_default_out > sunday_invalid_default_in),
    CHECK (generate_txt = 1 OR generate_excel_report = 1)
);

INSERT INTO att_data_repair_settings (
    att_data_repair_settings_id,
    enabled,
    minimum_duration_minutes,
    weekday_default_in,
    weekday_default_out,
    saturday_default_in,
    saturday_default_out,
    sunday_invalid_default_in,
    sunday_invalid_default_out,
    txt_max_rows,
    generate_txt,
    generate_excel_report,
    use_global_period,
    use_global_output,
    updated_at,
    updated_by
) VALUES (
    1,
    1,
    61,
    '09:30',
    '17:00',
    '09:30',
    '12:05',
    '09:30',
    '12:05',
    10000,
    1,
    1,
    1,
    1,
    datetime('now'),
    'Migration'
);
