# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging
from datetime import datetime, date
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .scope_master_data import get_default_approval_authority
from .project_scope import robust_parse_date

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:
    openpyxl = None


class ProjectScopeImportWizard(models.TransientModel):
    _name = 'project.scope.import.wizard'
    _description = 'Import Project Scopes & Tasks from Excel/CSV'

    project_id = fields.Many2one(
        'project.manage', string='Target Project', required=True,
        default=lambda self: self.env.context.get('active_id'))
    file = fields.Binary(string='Excel or CSV File', required=True)
    filename = fields.Char(string='Filename')
    import_mode = fields.Selection([
        ('append', 'Append / Update Existing Scopes'),
        ('replace', 'Replace Existing Scopes in Project'),
    ], default='append', string='Import Mode', required=True)

    def _clean_authority(self, auth_raw):
        """Map any authority string to standard Selection key ('TL', 'PM', 'VP', 'CEO')."""
        if not auth_raw:
            return False
        s = str(auth_raw).strip().upper()
        if s in ('TL', 'PM', 'VP', 'CEO'):
            return s
        if 'TEAM' in s or 'LEAD' in s:
            return 'TL'
        if 'MANAGER' in s or 'PM' in s:
            return 'PM'
        if 'VICE' in s or 'VP' in s:
            return 'VP'
        if 'CEO' in s or 'CHIEF' in s or 'DIRECTOR' in s:
            return 'CEO'
        return False

    def _parse_date(self, val):
        """Robust date parsing for Excel dates, serials, and date strings."""
        return robust_parse_date(val)

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_('Please choose a file to import.'))

        data = base64.b64decode(self.file)
        rows = []
        filename = (self.filename or '').lower()
        excel_auth_map = {}
        excel_date_map = {}
        excel_resp_map = {}

        is_excel = filename.endswith(('.xlsx', '.xlsm', '.xltx')) or data[:4] == b'PK\x03\x04'

        if is_excel:
            if not openpyxl:
                raise UserError(_('openpyxl python library is required to read Excel files.'))
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)

            # If workbook contains 'Scope_Task_List', extract exact Authority, Dates, and Responsible mappings
            if 'Scope_Task_List' in wb.sheetnames:
                ws_st = wb['Scope_Task_List']
                for r in ws_st.iter_rows(values_only=True):
                    if len(r) >= 6 and r[0] is not None and str(r[0]).strip().isdigit():
                        s_no = int(str(r[0]).strip())
                        # Documentation (cols 2..9): doc_no, name, type, auth, acc, resp, start, end
                        if len(r) > 2 and r[2] is not None and str(r[2]).strip().isdigit():
                            d_no = int(str(r[2]).strip())
                            d_item_id = f'S{s_no:02d}-D-{d_no:03d}'
                            if len(r) > 5 and r[5]:
                                d_auth = self._clean_authority(r[5])
                                if d_auth:
                                    excel_auth_map[d_item_id] = d_auth
                                    excel_auth_map[(s_no, 'Documentation', d_no)] = d_auth
                            d_acc = str(r[6]).strip() if len(r) > 6 and r[6] else ''
                            d_resp = str(r[7]).strip() if len(r) > 7 and r[7] else ''
                            d_start = r[8] if len(r) > 8 else None
                            d_end = r[9] if len(r) > 9 else None
                            if d_start or d_end:
                                excel_date_map[d_item_id] = (d_start, d_end)
                                excel_date_map[(s_no, 'Documentation', d_no)] = (d_start, d_end)
                            if d_acc or d_resp:
                                excel_resp_map[d_item_id] = (d_acc, d_resp)
                                excel_resp_map[(s_no, 'Documentation', d_no)] = (d_acc, d_resp)

                        # Implementation (cols 11..19): act_no, name, type, proof, auth, acc, resp, start, end
                        if len(r) > 11 and r[11] is not None and str(r[11]).strip().isdigit():
                            a_no = int(str(r[11]).strip())
                            a_item_id = f'S{s_no:02d}-I-{a_no:03d}'
                            if len(r) > 15 and r[15]:
                                a_auth = self._clean_authority(r[15])
                                if a_auth:
                                    excel_auth_map[a_item_id] = a_auth
                                    excel_auth_map[(s_no, 'Implementation', a_no)] = a_auth
                            a_acc = str(r[16]).strip() if len(r) > 16 and r[16] else ''
                            a_resp = str(r[17]).strip() if len(r) > 17 and r[17] else ''
                            a_start = r[18] if len(r) > 18 else None
                            a_end = r[19] if len(r) > 19 else None
                            if a_start or a_end:
                                excel_date_map[a_item_id] = (a_start, a_end)
                                excel_date_map[(s_no, 'Implementation', a_no)] = (a_start, a_end)
                            if a_acc or a_resp:
                                excel_resp_map[a_item_id] = (a_acc, a_resp)
                                excel_resp_map[(s_no, 'Implementation', a_no)] = (a_acc, a_resp)

            # Prefer sheet named 'Upload_Data', otherwise first active sheet
            ws = wb['Upload_Data'] if 'Upload_Data' in wb.sheetnames else wb.active
            for row in ws.iter_rows(values_only=True):
                if any(v is not None and str(v).strip() for v in row):
                    row_vals = []
                    for v in row:
                        if v is None:
                            row_vals.append('')
                        elif isinstance(v, (datetime, date)):
                            row_vals.append(v.strftime('%Y-%m-%d'))
                        else:
                            row_vals.append(str(v).strip())
                    rows.append(row_vals)
        else:
            # CSV parsing
            text = None
            for enc in ('utf-8-sig', 'utf-8', 'latin1', 'cp1252'):
                try:
                    text = data.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if text is None:
                raise UserError(_('Unable to decode the CSV file. Please ensure it is saved in UTF-8 format.'))
            reader = csv.reader(io.StringIO(text))
            for r in reader:
                if any(c.strip() for c in r):
                    rows.append([c.strip() for c in r])

        if not rows:
            raise UserError(_('The uploaded file is empty.'))

        if self.import_mode == 'replace':
            self.project_id.scope_ids.unlink()

        scopes_created, tasks_created = self._process_rows(
            rows,
            excel_auth_map=excel_auth_map,
            excel_date_map=excel_date_map,
            excel_resp_map=excel_resp_map
        )

        # Guarantee all scopes in the target project have approval_authority pre-filled automatically
        missing_scopes = self.project_id.scope_ids.filtered(lambda s: not s.approval_authority)
        if missing_scopes:
            missing_scopes.action_populate_approval_authority()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Successful'),
                'message': _('Successfully imported %s scopes and %s tasks into project "%s" with dates, team members, and approver roles.',
                             scopes_created, tasks_created, self.project_id.name),
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'project.manage',
                    'res_id': self.project_id.id,
                    'views': [(False, 'form')],
                }
            }
        }

    def _process_rows(self, rows, excel_auth_map=None, excel_date_map=None, excel_resp_map=None):
        Scope = self.env['project.manage.scope'].sudo().with_context(import_file=True, bypass_creation_approval=True)
        Employee = self.env['hr.employee'].sudo()
        excel_auth_map = excel_auth_map or {}
        excel_date_map = excel_date_map or {}
        excel_resp_map = excel_resp_map or {}

        # Cache existing scopes for this project to prevent duplicate creation
        existing_by_item_id = {}
        existing_by_key = {}
        for sc in self.project_id.scope_ids:
            if sc.item_id:
                existing_by_item_id[sc.item_id.strip()] = sc
            key = ((sc.scope or '').strip().lower(), (sc.name or '').strip().lower(), sc.category or '')
            existing_by_key[key] = sc

        scopes_count = 0
        tasks_count = 0

        # Try to locate header row for flat format: Item_ID, Scope_No, Scope, Category, ...
        flat_header_idx = -1
        for idx, r in enumerate(rows):
            r_lower = [str(c).lower().strip().replace(' ', '_').replace('/', '_') for c in r]
            if 'item_id' in r_lower:
                flat_header_idx = idx
                break
            if ('scope' in r_lower and 'category' in r_lower) or (('name' in r_lower or 'task' in r_lower) and ('responsible' in r_lower or 'start_date' in r_lower)):
                flat_header_idx = idx
                break

        if flat_header_idx != -1:
            header = [str(c).lower().strip().replace(' ', '_').replace('/', '_') for c in rows[flat_header_idx]]
            h_map = {col: i for i, col in enumerate(header)}

            for r in rows[flat_header_idx + 1:]:
                if not r or len(r) <= max(h_map.get('item_id', 0), h_map.get('item_name', 0), h_map.get('name', 0)):
                    continue

                def val(col_name):
                    i = h_map.get(col_name)
                    return str(r[i]).strip() if i is not None and i < len(r) and r[i] is not None else ''

                item_id = val('item_id')
                scope_str = val('scope') or val('scope_name') or val('scope_(functional_area)')
                scope_no_str = val('scope_no')
                category_str = val('category').lower()
                item_no_str = val('item_no') or val('doc_no') or val('activity_no')
                item_name = val('item_name') or val('name') or val('document_name') or val('implementation_activity') or val('task_deliverable') or val('task')
                item_type = val('item_type') or val('document_type') or val('activity_type')
                evidence = val('evidence___proof') or val('evidence') or val('proof')
                auth_str = (
                    val('final_approval_authority') or
                    val('approval_authority') or
                    val('final_approver') or
                    val('authority') or
                    val('final_approver_authority')
                )
                acc_str = val('accountable')
                resp_str = val('responsible')
                start_d = self._parse_date(val('start_date') or val('start'))
                end_d = self._parse_date(val('end_date') or val('end'))

                if not item_name and not scope_str and not item_id:
                    continue

                try:
                    scope_no = int(scope_no_str) if scope_no_str != '' else 0
                except ValueError:
                    scope_no = 0

                try:
                    item_no = int(item_no_str) if item_no_str != '' else 0
                except ValueError:
                    item_no = 0

                # Deduce scope_no, category, item_no from item_id if missing (e.g. S01-D-001 or S00-I-018)
                if item_id:
                    import re
                    m = re.match(r'S(\d+)-([DI])-(\d+)', item_id.strip().upper())
                    if m:
                        if not scope_no:
                            scope_no = int(m.group(1))
                        if not category_str:
                            category_str = 'implementation' if m.group(2) == 'I' else 'documentation'
                        if not item_no:
                            item_no = int(m.group(3))

                cat_val = 'Implementation' if 'imp' in category_str else 'Documentation'
                cand_name = item_name or item_id

                # Deduce scope_str if missing
                if not scope_str and scope_no is not None:
                    matched_scope = self.project_id.scope_ids.filtered(lambda s: s.scope_no == scope_no and s.scope)
                    if matched_scope:
                        scope_str = matched_scope[0].scope
                    else:
                        scope_str = f"Scope {scope_no}"

                if (scope_no == 0 or scope_no is None) and scope_str:
                    is_init = any(k in scope_str.lower() for k in ('initiation', 'governance'))
                    if not is_init and self.project_id:
                        scope_no = self.project_id._assign_next_scope_no(scope_str)

                cand_key = (scope_str.strip().lower(), cand_name.strip().lower(), cat_val)

                # Check if this item already exists in this project
                existing_scope = None
                if item_id and item_id.strip().upper() in existing_by_item_id:
                    existing_scope = existing_by_item_id[item_id.strip().upper()]
                elif cand_key in existing_by_key:
                    existing_scope = existing_by_key[cand_key]
                elif cand_name:
                    # Match by name in project
                    by_name = self.project_id.scope_ids.filtered(lambda s: (s.name or '').strip().lower() == cand_name.strip().lower())
                    if by_name:
                        existing_scope = by_name[0]

                # Map authority: 1) from file column, 2) from live Excel Scope_Task_List, 3) from Master Mapping
                auth_val = self._clean_authority(auth_str)
                if not auth_val and excel_auth_map:
                    if item_id and item_id.upper() in excel_auth_map:
                        auth_val = excel_auth_map[item_id.upper()]
                    elif (scope_no, cat_val, item_no) in excel_auth_map:
                        auth_val = excel_auth_map[(scope_no, cat_val, item_no)]

                if not auth_val:
                    auth_val = get_default_approval_authority(
                        item_id=item_id,
                        scope_no=scope_no,
                        category=cat_val,
                        item_no=item_no,
                        name=cand_name,
                    )
                auth_val = auth_val or 'TL'

                # Fallback to date_map if not found in Upload_Data
                if (not start_d or not end_d) and excel_date_map:
                    dm = excel_date_map.get(item_id.strip().upper() if item_id else None) or excel_date_map.get((scope_no, cat_val, item_no))
                    if dm:
                        if not start_d and dm[0]:
                            start_d = self._parse_date(dm[0])
                        if not end_d and dm[1]:
                            end_d = self._parse_date(dm[1])

                # Sync if only one date is present
                if start_d and not end_d:
                    end_d = start_d
                elif end_d and not start_d:
                    start_d = end_d

                # Fallback to resp_map if not found in Upload_Data
                if (not acc_str or not resp_str) and excel_resp_map:
                    rm = excel_resp_map.get(item_id.strip().upper() if item_id else None) or excel_resp_map.get((scope_no, cat_val, item_no))
                    if rm:
                        if not acc_str and rm[0]:
                            acc_str = rm[0]
                        if not resp_str and rm[1]:
                            resp_str = rm[1]

                scope_vals = {
                    'item_id': item_id,
                    'scope_no': scope_no,
                    'scope': scope_str,
                    'category': cat_val,
                    'item_no': item_no,
                    'name': cand_name,
                    'item_type': item_type,
                    'evidence_proof': evidence,
                    'approval_authority': auth_val,
                    'start_date': start_d,
                    'end_date': end_d,
                    'project_id': self.project_id.id,
                }

                if acc_str:
                    matched_acc = self.env['hr.employee'].sudo().search([('name', '=ilike', str(acc_str).strip())], limit=1)
                    if not matched_acc:
                        matched_acc = self.env['hr.employee'].sudo().search([('name', 'ilike', str(acc_str).strip())], limit=1)
                    if matched_acc:
                        scope_vals['accountable_id'] = matched_acc.id

                if resp_str:
                    resp_names = [r.strip() for r in str(resp_str).split(',') if r.strip()]
                    emp_list = []
                    for rn in resp_names:
                        me = self.env['hr.employee'].sudo().search([('name', '=ilike', rn)], limit=1)
                        if not me:
                            me = self.env['hr.employee'].sudo().search([('name', 'ilike', rn)], limit=1)
                        if me and me.id not in emp_list:
                            emp_list.append(me.id)
                    if emp_list:
                        scope_vals['responsible_ids'] = [(6, 0, emp_list)]
                        scope_vals['responsible_id'] = emp_list[0]

                if existing_scope:
                    # Update fields on existing record
                    update_vals = {}
                    if 'responsible_ids' in scope_vals and scope_vals['responsible_ids']:
                        update_vals['responsible_ids'] = scope_vals['responsible_ids']
                    if 'responsible_id' in scope_vals and scope_vals['responsible_id']:
                        update_vals['responsible_id'] = scope_vals['responsible_id']
                    if 'accountable_id' in scope_vals and scope_vals['accountable_id']:
                        update_vals['accountable_id'] = scope_vals['accountable_id']
                    if start_d:
                        update_vals['start_date'] = start_d
                    if end_d:
                        update_vals['end_date'] = end_d
                    if auth_val:
                        update_vals['approval_authority'] = auth_val
                    if evidence:
                        update_vals['evidence_proof'] = evidence
                    if item_type:
                        update_vals['item_type'] = item_type
                    if cand_name and not existing_scope.name:
                        update_vals['name'] = cand_name
                    if update_vals:
                        existing_scope.write(update_vals)
                else:
                    new_scope = Scope.create(scope_vals)
                    if item_id:
                        existing_by_item_id[item_id] = new_scope
                    existing_by_key[cand_key] = new_scope
                    tasks_count += 1

        else:
            # Fallback parser for two-column Scope_Task_List format
            current_scope = None
            for r in rows:
                if not r or not any(r):
                    continue
                first_cell = r[0].strip()
                if first_cell.upper().startswith('SCOPE ') and ' - ' in first_cell:
                    parts = first_cell.split('|')[0].strip()
                    scope_title = parts
                    scope_no = 0
                    try:
                        s_num = parts.split('-')[0].replace('SCOPE', '').strip()
                        scope_no = int(s_num)
                        scope_title = parts.split('-', 1)[1].strip()
                    except Exception:
                        pass
                    current_scope = Scope.create({
                        'name': scope_title,
                        'scope_no': scope_no,
                        'project_id': self.project_id.id,
                    })
                    scopes_count += 1
                    continue

                if len(r) >= 10 and r[0].isdigit():
                    scope_no = int(r[0])
                    scope_name = r[1]
                    if not current_scope or current_scope.scope_no != scope_no:
                        current_scope = Scope.create({
                            'name': scope_name,
                            'scope_no': scope_no,
                            'project_id': self.project_id.id,
                        })
                        scopes_count += 1

                    # Check documentation on left (cols 2..9)
                    doc_no_str = r[2] if len(r) > 2 else ''
                    doc_name = r[3] if len(r) > 3 else ''
                    doc_type = r[4] if len(r) > 4 else ''
                    doc_auth = r[5] if len(r) > 5 else ''
                    doc_acc = r[6] if len(r) > 6 else ''
                    doc_resp = r[7] if len(r) > 7 else ''
                    doc_start = self._parse_date(r[8] if len(r) > 8 else '')
                    doc_end = self._parse_date(r[9] if len(r) > 9 else '')
                    if doc_start and not doc_end:
                        doc_end = doc_start
                    elif doc_end and not doc_start:
                        doc_start = doc_end

                    if doc_name:
                        try:
                            d_no = int(doc_no_str)
                        except ValueError:
                            d_no = 0
                        doc_item_id = f"S{scope_no:02d}-D-{d_no:03d}"
                        doc_auth_val = (
                            self._clean_authority(doc_auth) or
                            get_default_approval_authority(
                                item_id=doc_item_id,
                                scope_no=scope_no,
                                category='Documentation',
                                item_no=d_no,
                                name=doc_name,
                            ) or 'TL'
                        )
                        doc_vals = {
                            'name': doc_name,
                            'item_no': d_no,
                            'item_id': doc_item_id,
                            'category': 'Documentation',
                            'item_type': doc_type,
                            'approval_authority': doc_auth_val,
                            'start_date': doc_start,
                            'end_date': doc_end,
                            'scope_no': scope_no,
                            'scope': scope_name,
                            'project_id': self.project_id.id,
                        }
                        if doc_acc:
                            m_acc = Employee.search([('name', '=ilike', str(doc_acc).strip())], limit=1)
                            if not m_acc:
                                m_acc = Employee.search([('name', 'ilike', str(doc_acc).strip())], limit=1)
                            if m_acc:
                                doc_vals['accountable_id'] = m_acc.id
                        if doc_resp:
                            m_emps = []
                            for rn in str(doc_resp).split(','):
                                if rn.strip():
                                    me = Employee.search([('name', '=ilike', rn.strip())], limit=1)
                                    if not me:
                                        me = Employee.search([('name', 'ilike', rn.strip())], limit=1)
                                    if me and me.id not in m_emps:
                                        m_emps.append(me.id)
                            if m_emps:
                                doc_vals['responsible_ids'] = [(6, 0, m_emps)]
                                doc_vals['responsible_id'] = m_emps[0]

                        existing_doc = existing_by_item_id.get(doc_item_id) or existing_by_key.get(
                            (scope_name.strip().lower(), doc_name.strip().lower(), 'Documentation'))
                        if existing_doc:
                            up = {}
                            for fn, fv in doc_vals.items():
                                if fv and (not getattr(existing_doc, fn, None) or fn in ('start_date', 'end_date', 'accountable_id', 'responsible_ids')):
                                    up[fn] = fv
                            if not existing_doc.approval_authority and doc_auth_val:
                                up['approval_authority'] = doc_auth_val
                            if up:
                                existing_doc.write(up)
                        else:
                            new_s = Scope.create(doc_vals)
                            existing_by_item_id[doc_item_id] = new_s
                            existing_by_key[(scope_name.strip().lower(), doc_name.strip().lower(), 'Documentation')] = new_s
                            tasks_count += 1

                    # Check implementation on right (cols 11..19)
                    if len(r) >= 14:
                        act_no_str = r[11] if len(r) > 11 else ''
                        act_name = r[12] if len(r) > 12 else ''
                        act_type = r[13] if len(r) > 13 else ''
                        act_proof = r[14] if len(r) > 14 else ''
                        act_auth = r[15] if len(r) > 15 else ''
                        act_acc = r[16] if len(r) > 16 else ''
                        act_resp = r[17] if len(r) > 17 else ''
                        act_start = self._parse_date(r[18] if len(r) > 18 else '')
                        act_end = self._parse_date(r[19] if len(r) > 19 else '')
                        if act_start and not act_end:
                            act_end = act_start
                        elif act_end and not act_start:
                            act_start = act_end

                        if act_name:
                            try:
                                a_no = int(act_no_str)
                            except ValueError:
                                a_no = 0
                            act_item_id = f"S{scope_no:02d}-I-{a_no:03d}"
                            act_auth_val = (
                                self._clean_authority(act_auth) or
                                get_default_approval_authority(
                                    item_id=act_item_id,
                                    scope_no=scope_no,
                                    category='Implementation',
                                    item_no=a_no,
                                    name=act_name,
                                ) or 'TL'
                            )
                            act_vals = {
                                'name': act_name,
                                'item_no': a_no,
                                'item_id': act_item_id,
                                'category': 'Implementation',
                                'item_type': act_type,
                                'evidence_proof': act_proof,
                                'approval_authority': act_auth_val,
                                'start_date': act_start,
                                'end_date': act_end,
                                'scope_no': scope_no,
                                'scope': scope_name,
                                'project_id': self.project_id.id,
                            }
                            if act_acc:
                                m_acc = Employee.search([('name', '=ilike', str(act_acc).strip())], limit=1)
                                if not m_acc:
                                    m_acc = Employee.search([('name', 'ilike', str(act_acc).strip())], limit=1)
                                if m_acc:
                                    act_vals['accountable_id'] = m_acc.id
                            if act_resp:
                                m_emps = []
                                for rn in str(act_resp).split(','):
                                    if rn.strip():
                                        me = Employee.search([('name', '=ilike', rn.strip())], limit=1)
                                        if not me:
                                            me = Employee.search([('name', 'ilike', rn.strip())], limit=1)
                                        if me and me.id not in m_emps:
                                            m_emps.append(me.id)
                                if m_emps:
                                    act_vals['responsible_ids'] = [(6, 0, m_emps)]
                                    act_vals['responsible_id'] = m_emps[0]

                            existing_act = existing_by_item_id.get(act_item_id) or existing_by_key.get(
                                (scope_name.strip().lower(), act_name.strip().lower(), 'Implementation'))
                            if existing_act:
                                up = {}
                                for fn, fv in act_vals.items():
                                    if fv and (not getattr(existing_act, fn, None) or fn in ('start_date', 'end_date', 'accountable_id', 'responsible_ids')):
                                        up[fn] = fv
                                if not existing_act.approval_authority and act_auth_val:
                                    up['approval_authority'] = act_auth_val
                                if up:
                                    existing_act.write(up)
                            else:
                                new_s = Scope.create(act_vals)
                                existing_by_item_id[act_item_id] = new_s
                                existing_by_key[(scope_name.strip().lower(), act_name.strip().lower(), 'Implementation')] = new_s
                                tasks_count += 1

        return scopes_count, tasks_count

