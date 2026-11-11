# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .scope_master_data import get_default_approval_authority

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
        if not val:
            return False
        if isinstance(val, datetime):
            return val.date()
        s = str(val).strip()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%d.%m.%Y'):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return False

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_('Please choose a file to import.'))

        data = base64.b64decode(self.file)
        rows = []
        filename = (self.filename or '').lower()
        excel_auth_map = {}

        is_excel = filename.endswith(('.xlsx', '.xlsm', '.xltx')) or data[:4] == b'PK\x03\x04'

        if is_excel:
            if not openpyxl:
                raise UserError(_('openpyxl python library is required to read Excel files.'))
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)

            # If workbook contains 'Scope_Task_List', extract the exact Final Approval Authority mapping
            if 'Scope_Task_List' in wb.sheetnames:
                ws_st = wb['Scope_Task_List']
                for r in ws_st.iter_rows(values_only=True):
                    if len(r) >= 6 and r[0] is not None and str(r[0]).strip().isdigit():
                        s_no = int(str(r[0]).strip())
                        # Documentation approval authority (col index 5)
                        if len(r) > 5 and r[2] is not None and str(r[2]).strip().isdigit() and r[5]:
                            d_no = int(str(r[2]).strip())
                            d_auth = self._clean_authority(r[5])
                            if d_auth:
                                excel_auth_map[f'S{s_no:02d}-D-{d_no:03d}'] = d_auth
                                excel_auth_map[(s_no, 'Documentation', d_no)] = d_auth
                        # Implementation approval authority (col index 15)
                        if len(r) > 15 and r[11] is not None and str(r[11]).strip().isdigit() and r[15]:
                            a_no = int(str(r[11]).strip())
                            a_auth = self._clean_authority(r[15])
                            if a_auth:
                                excel_auth_map[f'S{s_no:02d}-I-{a_no:03d}'] = a_auth
                                excel_auth_map[(s_no, 'Implementation', a_no)] = a_auth

            # Prefer sheet named 'Upload_Data', otherwise first active sheet
            ws = wb['Upload_Data'] if 'Upload_Data' in wb.sheetnames else wb.active
            for row in ws.iter_rows(values_only=True):
                if any(v is not None and str(v).strip() for v in row):
                    rows.append([str(v).strip() if v is not None else '' for v in row])
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

        scopes_created, tasks_created = self._process_rows(rows, excel_auth_map=excel_auth_map)

        # Guarantee all scopes in the target project have approval_authority pre-filled automatically
        missing_scopes = self.project_id.scope_ids.filtered(lambda s: not s.approval_authority)
        if missing_scopes:
            missing_scopes.action_populate_approval_authority()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Successful'),
                'message': _('Successfully imported %s scopes and %s tasks into project "%s" with final approver roles pre-filled.',
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

    def _process_rows(self, rows, excel_auth_map=None):
        Scope = self.env['project.manage.scope'].sudo()
        Employee = self.env['hr.employee'].sudo()
        excel_auth_map = excel_auth_map or {}

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
            r_lower = [c.lower() for c in r]
            if 'item_id' in r_lower and 'scope' in r_lower and 'category' in r_lower:
                flat_header_idx = idx
                break

        if flat_header_idx != -1:
            header = [c.lower().replace(' ', '_').replace('/', '_') for c in rows[flat_header_idx]]
            h_map = {col: i for i, col in enumerate(header)}

            for r in rows[flat_header_idx + 1:]:
                if not r or len(r) <= max(h_map.get('item_id', 0), h_map.get('item_name', 0)):
                    continue

                def val(col_name):
                    i = h_map.get(col_name)
                    return r[i].strip() if i is not None and i < len(r) else ''

                item_id = val('item_id')
                scope_str = val('scope') or val('scope_name') or val('scope_(functional_area)')
                scope_no_str = val('scope_no')
                category_str = val('category').lower()
                item_no_str = val('item_no') or val('doc_no') or val('activity_no')
                item_name = val('item_name') or val('document_name') or val('implementation_activity')
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

                if not item_name and not scope_str:
                    continue

                try:
                    scope_no = int(scope_no_str) if scope_no_str != '' else 0
                except ValueError:
                    scope_no = 0

                try:
                    item_no = int(item_no_str) if item_no_str != '' else 0
                except ValueError:
                    item_no = 0

                cat_val = 'Implementation' if 'imp' in category_str else 'Documentation'
                cand_name = item_name or item_id
                cand_key = (scope_str.strip().lower(), cand_name.strip().lower(), cat_val)

                # Check if this item already exists in this project
                existing_scope = None
                if item_id and item_id in existing_by_item_id:
                    existing_scope = existing_by_item_id[item_id]
                elif cand_key in existing_by_key:
                    existing_scope = existing_by_key[cand_key]

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

                if existing_scope:
                    # Update missing fields on existing record
                    update_vals = {}
                    for field_name, val_to_set in scope_vals.items():
                        if val_to_set and not getattr(existing_scope, field_name, None):
                            update_vals[field_name] = val_to_set
                    # Guarantee approval_authority is filled if missing
                    if auth_val and not existing_scope.approval_authority:
                        update_vals['approval_authority'] = auth_val
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

                        existing_doc = existing_by_item_id.get(doc_item_id) or existing_by_key.get(
                            (scope_name.strip().lower(), doc_name.strip().lower(), 'Documentation'))
                        if existing_doc:
                            up = {}
                            for fn, fv in doc_vals.items():
                                if fv and not getattr(existing_doc, fn, None):
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

                            existing_act = existing_by_item_id.get(act_item_id) or existing_by_key.get(
                                (scope_name.strip().lower(), act_name.strip().lower(), 'Implementation'))
                            if existing_act:
                                up = {}
                                for fn, fv in act_vals.items():
                                    if fv and not getattr(existing_act, fn, None):
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
