"""Synthetic residual opening/archive proof via odoo shell; creates a fresh test company."""
import base64, hashlib, json
from odoo import api, Command
assert env.cr.dbname == 'tcsi_alignment_phase2'
company = env['res.company'].create({'name': 'Synthetic residual cutover company', 'thirdcode_live_history_policy': 'archive_only', 'currency_id': env.company.currency_id.id})
admin = env.ref('base.user_admin')
admin.write({'company_ids': [Command.link(company.id)]})
env = api.Environment(env.cr, admin.id, {'allowed_company_ids': company.ids})
accounts = {}
for code, name, kind in [('100','Assets','asset_fixed'),('110','AR','asset_receivable'),('120','Undeposited','asset_current'),('200','AP','liability_payable'),('300','Equity','equity'),('399','Opening clearing','equity')]:
    accounts[code] = env['account.account'].create({'code': code, 'name': name, 'account_type': kind, 'company_ids': [Command.set(company.ids)], 'reconcile': kind in ('asset_receivable','liability_payable','asset_current')})
journal = env['account.journal'].create({'name': 'Synthetic cutover', 'code': 'CUT', 'type': 'general', 'company_id': company.id})
partner = env['res.partner'].create({'name': 'Synthetic MYOB customer/supplier', 'company_id': company.id, 'property_account_receivable_id': accounts['110'].id, 'property_account_payable_id': accounts['200'].id})
payload = {'policy':'residual_cutover_v1','journal_id':journal.id,'clearing_account_id':accounts['399'].id,'trial_balance':[{'account_id':accounts[c].id,'debit':d,'credit':r} for c,d,r in [('100','100','0'),('110','50','0'),('120','50','0'),('200','0','30'),('300','0','170')]],'open_items':[{'source_id':'INV1','account_id':accounts['110'].id,'partner_id':partner.id,'move_type':'out_invoice','residual':'60','document_date':'2024-12-01'}, {'source_id':'BILL1','account_id':accounts['200'].id,'partner_id':partner.id,'move_type':'in_invoice','residual':'30','document_date':'2024-12-02'}], 'undeposited_receipts':[{'source_id':'REC1','cash_account_id':accounts['120'].id,'partner_id':partner.id,'amount':'40','document_date':'2024-12-03','disposition':'already_allocated','source_allocation_reference':'MYOB invoice already reduced by40'}, {'source_id':'REC2','cash_account_id':accounts['120'].id,'partner_id':partner.id,'amount':'10','document_date':'2024-12-04','disposition':'unallocated','receivable_account_id':accounts['110'].id}]}
archive=b'SYNTHETIC MYOB ORIGINAL SOURCE - retain read only; no real client data'
mapping=json.dumps(payload).encode()
batch=env['thirdcode.migration.batch'].create({'company_id':company.id,'source_system':'csv','cutover_date':'2024-12-31','opening_balance_owner':'Synthetic fixture owner; no real approval','source_file_hash':hashlib.sha256(archive).hexdigest(),'source_archive':base64.b64encode(archive),'source_archive_filename':'synthetic-myob.txt','cutover_mapping_file':base64.b64encode(mapping),'cutover_mapping_filename':'mapping.json'})
batch.action_review_cutover_file()
result=batch.action_apply_cutover()
assert result==batch.action_apply_cutover()
history=[{'source_entry_id':'OLD2015','source_line_id':str(i),'date':'2015-01-01','account_code':c,'debit':d,'credit':r,'description':'Archived synthetic transaction'} for i,c,d,r in [(1,'100','12','0'),(2,'300','0','12')]]
result['archive']=batch.action_archive_source_history(history)
assert result['archive']['created_lines']==2
assert hashlib.sha256(base64.b64decode(batch.source_archive)).hexdigest()==batch.source_file_hash
result.update({'batch_id':batch.id,'company_id':company.id,'source_retrieved':True,'scope':'Synthetic; no real MYOB acceptance'})
print('CUTOVER_RESULT '+json.dumps(result,sort_keys=True))
env.cr.commit()
