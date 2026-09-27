-- Read-only user for the AI agent: it can read data, but never change it.
CREATE ROLE copilot_reader WITH LOGIN PASSWORD 'reader_pw';
GRANT CONNECT ON DATABASE pagila TO copilot_reader;
GRANT USAGE ON SCHEMA public TO copilot_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO copilot_reader;

-- Kill any query that runs longer than 5 seconds
ALTER ROLE copilot_reader SET statement_timeout = '5s';

-- Hide sensitive columns: staff logins and passwords are off-limits to the AI
REVOKE SELECT ON staff FROM copilot_reader;
GRANT SELECT (staff_id, first_name, last_name, address_id, email, store_id, active, last_update) ON staff TO copilot_reader;
