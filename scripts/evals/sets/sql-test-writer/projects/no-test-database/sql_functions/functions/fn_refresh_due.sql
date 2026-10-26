create or replace function fn_refresh_due(refresh_due boolean, retry_due boolean) returns boolean as $$ select refresh_due and retry_due $$ language sql;
