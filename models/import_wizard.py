import base64
import csv
import io
import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError

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

        is_excel = filename.endswith(('.xlsx', '.xlsm', '.xltx')) or data[:4] == b'PK\x03\x04'

        if is_excel:
            if not openpyxl:
                raise UserError(_('openpyxl python library is required to read Excel files.'))
            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
            # Prefer sheet named 'Upload_Data', otherwise first sheet
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

        scopes_created, tasks_created = self._process_rows(rows)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Successful'),
                'message': _('Successfully imported %s scopes and %s tasks into project "%s".',
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

    def _process_rows(self, rows):
        Scope = self.env['project.manage.scope'].sudo()
        Employee = self.env['hr.employee'].sudo()

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
                auth = val('final_approval_authority') or val('approval_authority')
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

                scope_vals = {
                    'item_id': item_id,
                    'scope_no': scope_no,
                    'scope': scope_str,
                    'category': cat_val,
                    'item_no': item_no,
                    'name': cand_name,
                    'item_type': item_type,
                    'evidence_proof': evidence,
                    'approval_authority': auth if auth in ('TL', 'PM', 'VP', 'CEO') else False,
                    'accountable': acc_str,
                    'responsible': resp_str,
                    'start_date': start_d,
                    'end_date': end_d,
                    'project_id': self.project_id.id,
                }

                if existing_scope:
                    # Don't create duplicates! Update missing fields if needed
                    update_vals = {}
                    for field_name, val_to_set in scope_vals.items():
                        if val_to_set and not getattr(existing_scope, field_name, None):
                            update_vals[field_name] = val_to_set
                    if update_vals:
                        existing_scope.write(update_vals)
                else:
                    new_scope = Scope.create(scope_vals)
                    if item_id:
                        existing_by_item_id[item_id] = new_scope
                    existing_by_key[cand_key] = new_scope
                    tasks_count += 1

        else:
            # Fallback parser for two-column format or general CSV rows
            current_scope = None
            for r in rows:
                if not r or not any(r):
                    continue
                first_cell = r[0].strip()
                if first_cell.upper().startswith('SCOPE ') and ' - ' in first_cell:
                    # Scope header row, e.g. "SCOPE 0  -  PROJECT INITIATION & GOVERNANCE"
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

                    # Check documentation on left (cols 2..8)
                    doc_no_str = r[2] if len(r) > 2 else ''
                    doc_name = r[3] if len(r) > 3 else ''
                    doc_type = r[4] if len(r) > 4 else ''
                    doc_auth = r[5] if len(r) > 5 else ''
                    if doc_name:
                        try:
                            d_no = int(doc_no_str)
                        except ValueError:
                            d_no = 0
                        Scope.create({
                            'name': doc_name,
                            'item_no': d_no,
                            'item_id': f"S{scope_no:02d}-D-{d_no:03d}",
                            'category': 'Documentation',
                            'item_type': doc_type,
                            'scope_no': scope_no,
                            'scope': scope_name,
                            'project_id': self.project_id.id,
                            'approval_authority': doc_auth if doc_auth in ('TL', 'PM', 'VP', 'CEO') else False,
                        })
                        tasks_count += 1

                    # Check implementation on right (cols 11..18)
                    if len(r) >= 14:
                        act_no_str = r[11] if len(r) > 11 else ''
                        act_name = r[12] if len(r) > 12 else ''
                        act_type = r[13] if len(r) > 13 else ''
                        act_proof = r[14] if len(r) > 14 else ''
                        act_auth = r[15] if len(r) > 15 else ''
                        if act_name:
                            try:
                                a_no = int(act_no_str)
                            except ValueError:
                                a_no = 0
                            Scope.create({
                                'name': act_name,
                                'item_no': a_no,
                                'item_id': f"S{scope_no:02d}-I-{a_no:03d}",
                                'category': 'Implementation',
                                'item_type': act_type,
                                'evidence_proof': act_proof,
                                'scope_no': scope_no,
                                'scope': scope_name,
                                'project_id': self.project_id.id,
                                'approval_authority': act_auth if act_auth in ('TL', 'PM', 'VP', 'CEO') else False,
                            })
                            tasks_count += 1

        return scopes_count, tasks_count
