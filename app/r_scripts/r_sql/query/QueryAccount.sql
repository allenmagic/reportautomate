-- !preview conn=DBI::dbConnect(RSQLite::SQLite())

select distinct
(select param_drpt from base_param bp where bp.id = b.bank_name_id) as BankBrokerName,
(select param_drpt from base_param bp where bp.id = blc.bank_short_name_id) as ShortName,
(select param_drpt from base_param bp where bp.id = blc.location) as Location,
cad.account_number as AccountNumber
from company_account_detail cad
left join company_account ca on ca.id = cad.account_id
left join company_base cb on ca.company_id = cb.id
left join bank b on b.id = ca.bank_id
left join bank_location blc on ca.bank_location = blc.id
where cad.deleted_status = 0