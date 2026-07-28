ALTER TABLE outlook_settings
ADD COLUMN payroll_period TEXT
CHECK (
    payroll_period IS NULL
    OR (
        length(payroll_period) = 7
        AND substr(payroll_period, 3, 1) = '-'
        AND substr(payroll_period, 1, 2) BETWEEN '01' AND '12'
        AND substr(payroll_period, 1, 2) GLOB '[0-9][0-9]'
        AND substr(payroll_period, 4, 4) GLOB '[0-9][0-9][0-9][0-9]'
    )
);
