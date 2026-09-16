ALTER TABLE att_data_repair_settings
ADD COLUMN saturday_missing_out_default TEXT NOT NULL DEFAULT '11:00'
    CHECK (saturday_missing_out_default GLOB '[0-2][0-9]:[0-5][0-9]');

ALTER TABLE att_data_repair_settings
ADD COLUMN midnight_time_out_default TEXT NOT NULL DEFAULT '23:59'
    CHECK (midnight_time_out_default GLOB '[0-2][0-9]:[0-5][0-9]');
