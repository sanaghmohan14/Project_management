import base64
import datetime
import re
import uuid
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
from .scope_master_data import get_default_approval_authority


class ProjectManageTag(models.Model):
    _name = 'project.manage.tag'
    _description = 'Project Tag'

    name = fields.Char(required=True)
    color = fields.Integer(string='Color Index')

    _name_uniq = models.Constraint(
        'unique(name)',
        'Tag name must be unique!',
    )


class ProjectManage(models.Model):
    _name = 'project.manage'
    _description = 'Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, id desc'

    name = fields.Char(string='Project Name', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', tracking=True,required=True)
    team_id = fields.Many2one('project.manage.team', string='Project Team', tracking=True)
    date_start = fields.Date(string='Start Date', tracking=True,required=True)
    date_end = fields.Date(string='End Date', tracking=True,required=True)
    manager_id = fields.Many2one('hr.employee', string='Project Manager', tracking=True,required=True)
    team_lead_id = fields.Many2one('hr.employee', string='Team Lead', tracking=True,required=True)
    consultant_ids = fields.Many2many(
        'hr.employee', 'project_manage_consultant_rel',
        'project_id', 'employee_id', string='Consultants',required=True)
    client_coordinator_id = fields.Many2one(
        'res.partner', string='Client Implementation Coordinator', tracking=True,required=True)
    project_coordinator_id = fields.Many2one(
        'hr.employee', string='Project Implementation Coordinator', tracking=True)
    tag_ids = fields.Many2many('project.manage.tag', string='Tags')
    access_token = fields.Char(
        string='Review Access Token',
        copy=False,
        default=lambda self: uuid.uuid4().hex
    )

    def _get_review_url(self):
        self.ensure_one()
        if not self.access_token:
            self.access_token = uuid.uuid4().hex
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or 'http://localhost:8069'
        return f"{base_url.rstrip('/')}/project/review/{self.id}?token={self.access_token}"

    @api.onchange('team_id')
    def _onchange_team_id(self):
        if self.team_id:
            if self.team_id.team_lead_id:
                emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.team_id.team_lead_id.id)], limit=1)
                if emp:
                    self.team_lead_id = emp
            if self.team_id.member_ids:
                emps = self.env['hr.employee'].sudo().search([('user_id', 'in', self.team_id.member_ids.ids)])
                if emps:
                    self.consultant_ids = [(6, 0, emps.ids)]
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Very High'),
    ], string='Priority', default='0', tracking=True)
    state = fields.Selection([
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Stage', default='todo', required=True, tracking=True,
        copy=False, group_expand='_group_expand_states')
    color = fields.Integer()
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # ---- Dashboard & Health Metrics ----
    health = fields.Selection([
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], string='Health', compute='_compute_metrics', store=True, readonly=False, tracking=True)
    risk_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Risk Level', compute='_compute_metrics', store=True, readonly=False, tracking=True)
    progress = fields.Float(
        string='Progress (%)', compute='_compute_metrics', store=True, readonly=False, tracking=True)
    planned_progress = fields.Float(
        string='Planned Progress (%)', compute='_compute_metrics', store=True, readonly=False)
    condition = fields.Selection([
        ('ahead', 'Ahead'),
        ('on_plan', 'On plan'),
        ('behind', 'Behind'),
        ('overdue', 'Overdue'),
    ], string='Condition', compute='_compute_metrics', store=True)
    running_status = fields.Selection([
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('on_hold', 'On hold'),
        ('not_started', 'Not started'),
    ], string='Running Status', compute='_compute_metrics', store=True)

    @api.depends(
        'date_start', 'date_end', 'state',
        'scope_ids', 'scope_ids.state', 'scope_ids.approval_state', 'scope_ids.end_date'
    )
    def _compute_metrics(self):
        today = fields.Date.today()
        for rec in self:
            # Silently auto-fill any scopes missing approval authority
            missing_auth_scopes = rec.scope_ids.filtered(lambda s: not s.approval_authority)
            if missing_auth_scopes:
                missing_auth_scopes.action_populate_approval_authority()

            # 1. Scope & Task Completion Metrics
            total_tasks = len(rec.scope_ids)
            done_tasks = len(rec.scope_ids.filtered(lambda s: s.state == 'done'))
            review_tasks = len(rec.scope_ids.filtered(
                lambda s: s.state == 'under_review' or (s.approval_state and s.approval_state.startswith('pending'))
            ))
            in_prog_tasks = len(rec.scope_ids.filtered(lambda s: s.state == 'in_progress'))
            overdue_tasks = len(rec.scope_ids.filtered(
                lambda s: s.end_date and today > s.end_date and s.state != 'done'
            ))
            rejected_tasks = len(rec.scope_ids.filtered(
                lambda s: s.approval_state == 'rejected'
            ))

            # 2. Project Progress (%) derived strictly from Scope/Task Completion
            # Increase progress based on completed scopes (documentation & implementation)
            # E.g. If there are 100 tasks and 10 are completed, progress is 10%
            if rec.state == 'done':
                rec.progress = 100.0
            elif total_tasks > 0:
                rec.progress = min(max(round((done_tasks / total_tasks) * 100, 1), 0.0), 100.0)
            else:
                rec.progress = 0.0

            # 3. Planned Progress (%) based on Closing Date (date_end) & Timeline Duration
            days_remaining = None
            if rec.date_start and rec.date_end:
                total_days = (rec.date_end - rec.date_start).days
                elapsed_days = (today - rec.date_start).days
                days_remaining = (rec.date_end - today).days

                if elapsed_days <= 0:
                    rec.planned_progress = 0.0
                elif total_days > 0:
                    rec.planned_progress = min(max(round((elapsed_days / total_days) * 100, 1), 0.0), 100.0)
                else:
                    rec.planned_progress = 100.0
            else:
                rec.planned_progress = rec.progress

            # 4. Running Status derived from Project Stage
            if rec.state == 'done':
                rec.running_status = 'completed'
            elif rec.state == 'cancelled':
                rec.running_status = 'on_hold'
            elif rec.state == 'in_progress':
                rec.running_status = 'running'
            else:
                rec.running_status = 'not_started'

            # 5. Project Condition: Ahead, On plan, Behind, Overdue
            # Evaluates Closing Date vs Today, Actual Progress vs Planned Progress, and Task Bottlenecks
            variance = rec.progress - rec.planned_progress
            is_past_closing_date = bool(rec.date_end and today > rec.date_end and rec.state != 'done')

            if rec.state == 'done':
                rec.condition = 'ahead' if (rec.date_end and today < rec.date_end) else 'on_plan'
            elif is_past_closing_date:
                rec.condition = 'overdue'
            elif variance >= 5.0 and overdue_tasks == 0:
                rec.condition = 'ahead'
            elif variance >= -5.0 and overdue_tasks == 0:
                rec.condition = 'on_plan'
            else:
                rec.condition = 'behind'

            # 6. Project Health: Good, Fair, Poor
            # Evaluated dynamically from Timeline, Closing Date, Stage, and Scope/Task Quality
            if rec.state == 'done':
                rec.health = 'good'
            elif rec.condition == 'overdue':
                days_late = (today - rec.date_end).days if rec.date_end else 0
                if days_late > 7 or rec.progress < 70.0 or rejected_tasks > 0:
                    rec.health = 'poor'
                else:
                    rec.health = 'fair'
            elif rec.condition == 'behind':
                lag = rec.planned_progress - rec.progress
                if lag > 20.0 or rejected_tasks >= 2 or overdue_tasks >= 3 or (days_remaining is not None and days_remaining <= 7 and rec.progress < 50.0):
                    rec.health = 'poor'
                else:
                    rec.health = 'fair'
            elif rec.condition == 'on_plan':
                if rejected_tasks >= 2 or overdue_tasks >= 2:
                    rec.health = 'fair'
                else:
                    rec.health = 'good'
            else:
                # Ahead of schedule
                if rejected_tasks >= 2:
                    rec.health = 'fair'
                else:
                    rec.health = 'good'

            # 7. Project Risk Level: Low, Medium, High
            # Evaluated dynamically from Deadline Proximity, Lag Variance, and Task Issues
            if rec.state == 'done':
                rec.risk_level = 'low'
            elif (
                (rec.condition == 'overdue' and rec.progress < 80.0) or
                (rec.date_end and today > rec.date_end and (today - rec.date_end).days > 7) or
                (days_remaining is not None and 0 <= days_remaining <= 7 and rec.progress < 60.0) or
                (rec.planned_progress - rec.progress > 20.0) or
                rejected_tasks >= 3 or
                overdue_tasks >= 3 or
                rec.health == 'poor'
            ):
                rec.risk_level = 'high'
            elif (
                rec.condition in ('behind', 'overdue') or
                (days_remaining is not None and 0 <= days_remaining <= 14 and rec.progress < rec.planned_progress) or
                rejected_tasks in (1, 2) or
                overdue_tasks in (1, 2) or
                rec.health == 'fair'
            ):
                rec.risk_level = 'medium'
            else:
                rec.risk_level = 'low'

    # ---- Scopes & Tasks Relationships ----
    scope_ids = fields.One2many(
        'project.manage.scope', 'project_id', string='Scopes')
    doc_scope_ids = fields.One2many(
        'project.manage.scope', 'project_id',
        domain=[('category', '=', 'Documentation')],
        string='Documentation Tasks')
    imp_scope_ids = fields.One2many(
        'project.manage.scope', 'project_id',
        domain=[('category', '=', 'Implementation')],
        string='Implementation Tasks')

    scope_count = fields.Integer(
        string='Scopes Count', compute='_compute_counts')
    doc_count = fields.Integer(
        string='Documentation Tasks Count', compute='_compute_counts')
    imp_count = fields.Integer(
        string='Implementation Tasks Count', compute='_compute_counts')

    review_ids = fields.One2many(
        'project.manage.review', 'project_id', string='Customer Reviews')
    review_count = fields.Integer(
        string='Review Count', compute='_compute_reviews', store=True)
    average_rating = fields.Float(
        string='Average Rating', compute='_compute_reviews', store=True)
    last_client_update_date = fields.Datetime(
        string='Last Client Update Sent', readonly=True)

    @api.depends('review_ids.rating_value', 'review_ids.state')
    def _compute_reviews(self):
        for rec in self:
            rec.review_count = len(rec.review_ids)
            if rec.review_ids:
                total_val = sum(r.rating_value for r in rec.review_ids)
                rec.average_rating = round(total_val / len(rec.review_ids), 1)
            else:
                rec.average_rating = 0.0

    def _compute_counts(self):
        for rec in self:
            rec.scope_count = len(set(rec.scope_ids.mapped('scope_no'))) if rec.scope_ids else 0
            rec.doc_count = len(rec.scope_ids.filtered(lambda s: s.category == 'Documentation'))
            rec.imp_count = len(rec.scope_ids.filtered(lambda s: s.category == 'Implementation'))

    def action_view_scopes(self):
        self.ensure_one()
        return {
            'name': _('Scopes - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.scope',
            'view_mode': 'kanban,list,form',
            'views': [(False, 'kanban'), (False, 'list'), (False, 'form')],
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_docs(self):
        self.ensure_one()
        return {
            'name': _('Documentation Tasks - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.scope',
            'view_mode': 'kanban,list,form',
            'views': [(False, 'kanban'), (False, 'list'), (False, 'form')],
            'domain': [('project_id', '=', self.id), ('category', '=', 'Documentation')],
            'context': {'default_project_id': self.id, 'default_category': 'Documentation'},
        }

    def action_view_imps(self):
        self.ensure_one()
        return {
            'name': _('Implementation Tasks - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.scope',
            'view_mode': 'kanban,list,form',
            'views': [(False, 'kanban'), (False, 'list'), (False, 'form')],
            'domain': [('project_id', '=', self.id), ('category', '=', 'Implementation')],
            'context': {'default_project_id': self.id, 'default_category': 'Implementation'},
        }

    def action_view_reviews(self):
        self.ensure_one()
        return {
            'name': _('Customer Reviews - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.review',
            'view_mode': 'list,kanban,form,pivot,graph',
            'views': [(False, 'list'), (False, 'kanban'), (False, 'form'), (False, 'pivot'), (False, 'graph')],
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_reviewer_name': self.partner_id.name,
                'default_reviewer_email': self.partner_id.email,
            },
        }

    def action_create_review(self):
        self.ensure_one()
        return {
            'name': _('New Customer Review - %s', self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.review',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                'default_project_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_reviewer_name': self.partner_id.name,
                'default_reviewer_email': self.partner_id.email,
                'default_review_type': 'completion' if (self.state == 'done' or self.progress >= 100) else 'milestone',
            },
        }

    def action_open_client_update_wizard(self):
        """Open the wizard to send formatted progress/completion report to the client."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Please assign a client before sending project updates."))
        if not self.partner_id.email and not (self.client_coordinator_id and self.client_coordinator_id.email):
            raise UserError(_("Neither the client '%s' nor coordinator has an email address configured.") % self.partner_id.name)

        recipients = self.partner_id
        if self.client_coordinator_id:
            recipients |= self.client_coordinator_id

        is_completed = bool(self.state == 'done' or self.progress >= 100)
        subject = f"Project Completion Report: {self.name} - 100% Successfully Delivered" if is_completed else f"Project Status & Progress Update: {self.name} ({int(self.progress)}% Completed)"
        custom_note = (
            f"Dear {self.partner_id.name},\n\nWe are pleased to inform you that all deliverables for '{self.name}' have been completed successfully. Please review the final completion summary below."
            if is_completed else
            f"Dear {self.partner_id.name},\n\nPlease find below the latest status, deliverables completion, and progress update for '{self.name}'."
        )

        wizard = self.env['project.manage.client.update.wizard'].create({
            'project_id': self.id,
            'partner_id': self.partner_id.id,
            'client_coordinator_id': self.client_coordinator_id.id if self.client_coordinator_id else False,
            'recipient_partner_ids': [(6, 0, recipients.ids)],
            'is_completed': is_completed,
            'subject': subject,
            'custom_message': custom_note,
        })

        return {
            'name': _('Send Project Update to Client'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.manage.client.update.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }

    def action_open_import_wizard(self):
        self.ensure_one()
        return {
            'name': _('Import Scopes & Tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.scope.import.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_project_id': self.id},
        }


    def action_remove_duplicate_scopes(self):
        """Find and remove duplicate scope records within this project."""
        self.ensure_one()
        seen = set()
        duplicates = self.env['project.manage.scope']
        # Sort by id ascending to keep the earliest record
        for sc in self.scope_ids.sorted('id'):
            # Define uniqueness key: item_id if present, else (scope, name, category)
            if sc.item_id:
                key = ('item_id', sc.item_id.strip())
            else:
                key = (
                    'tuple',
                    (sc.scope or '').strip().lower(),
                    (sc.name or '').strip().lower(),
                    sc.category or '',
                )
            if key in seen:
                duplicates |= sc
            else:
                seen.add(key)

        removed_count = len(duplicates)
        if duplicates:
            duplicates.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Duplicate Cleanup'),
                'message': _('Successfully removed %s duplicate scope record(s).', removed_count) if removed_count else _('No duplicate scopes found in this project.'),
                'type': 'success' if removed_count else 'info',
                'sticky': False,
            }
        }

    def _heal_project_scope_numbers(self):
        """Ensure no duplicate scope numbers exist and non-governance scopes are never 0."""
        for project in self:
            scopes = self.env['project.manage.scope'].sudo().search(
                [('project_id', '=', project.id)],
                order='scope_no asc, id asc'
            )
            if not scopes:
                continue

            # 1. Identify non-governance scopes that erroneously have scope_no == 0 or False
            invalid_zeros = scopes.filtered(
                lambda s: (s.scope_no == 0 or not s.scope_no) and s.scope and not any(
                    k in s.scope.lower() for k in ('initiation', 'governance')
                )
            )
            if invalid_zeros:
                valid_scopes = scopes - invalid_zeros
                curr_max = max([s.scope_no for s in valid_scopes if s.scope_no is not None] or [0])
                reassigned = {}
                for sc in invalid_zeros:
                    clean_name = re.sub(r'^(?:Scope|S)\s*0\s*[-:]?\s*', '', (sc.scope or '').strip(), flags=re.IGNORECASE).strip()
                    if not clean_name:
                        clean_name = sc.scope or 'Custom Scope'
                    clean_key = clean_name.lower()
                    if clean_key not in reassigned:
                        curr_max += 1
                        reassigned[clean_key] = (curr_max, clean_name)
                    new_no, target_name = reassigned[clean_key]
                    new_code = f"S{new_no:02d}"
                    vals_to_write = {
                        'scope': target_name,
                        'scope_no': new_no,
                        'code': new_code,
                    }
                    if sc.item_id and sc.item_id.upper().startswith('S00-'):
                        vals_to_write['item_id'] = f"{new_code}-{sc.item_id[4:]}"
                    elif not sc.item_id:
                        cat_letter = 'I' if 'imp' in (sc.category or '').lower() else 'D'
                        vals_to_write['item_id'] = f"{new_code}-{cat_letter}-{sc.item_no or 1:03d}"
                    sc.sudo().write(vals_to_write)

            # 2. Check for duplicate scope_no assigned to different functional scopes (excluding Scope 0 governance)
            refreshed_scopes = self.env['project.manage.scope'].sudo().search(
                [('project_id', '=', project.id)],
                order='scope_no asc, id asc'
            )
            scope_no_to_name = {}
            max_num = max([s.scope_no for s in refreshed_scopes if s.scope_no is not None] or [0])
            for sc in refreshed_scopes:
                if sc.scope_no is None:
                    continue
                clean_name = (sc.scope or '').strip().lower()
                # Skip checking Scope 0 if it's governance
                if sc.scope_no == 0 and any(k in clean_name for k in ('initiation', 'governance')):
                    scope_no_to_name[0] = clean_name
                    continue
                if sc.scope_no in scope_no_to_name and scope_no_to_name[sc.scope_no] != clean_name:
                    max_num += 1
                    new_no = max_num
                    new_code = f"S{new_no:02d}"
                    conflict_recs = refreshed_scopes.filtered(
                        lambda s: (s.scope or '').strip().lower() == clean_name and s.scope_no == sc.scope_no
                    )
                    for cr in conflict_recs:
                        c_vals = {'scope_no': new_no, 'code': new_code}
                        if cr.item_id and cr.item_id.upper().startswith(f"S{cr.scope_no:02d}-"):
                            c_vals['item_id'] = f"{new_code}-{cr.item_id[4:]}"
                        cr.sudo().write(c_vals)
                    scope_no_to_name[new_no] = clean_name
                else:
                    scope_no_to_name[sc.scope_no] = clean_name

    def _assign_next_scope_no(self, scope_name, preferred_no=None):
        """Allocate next sequential scope number for a new scope in this project,
        ensuring NO duplicates. If scope already exists in this project, reuses its scope_no.
        """
        self.ensure_one()
        clean_name = (scope_name or '').strip()
        if not clean_name:
            clean_name = 'General Scope'

        cand_no = preferred_no
        match = re.match(r'^(?:Scope|S)?\s*(\d+)\s*[-:]?\s*(.*)$', clean_name, re.IGNORECASE)
        if match:
            num_part = int(match.group(1))
            title_part = match.group(2).strip()
            if cand_no is None:
                cand_no = num_part
            if title_part and not any(k in clean_name.lower() for k in ('initiation', 'governance')):
                clean_name = title_part

        # 1. If this exact scope already exists in project, reuse its scope_no
        existing = self.env['project.manage.scope'].sudo().search([
            ('project_id', '=', self.id),
            ('scope', '=ilike', clean_name)
        ], limit=1)
        if existing and existing.scope_no is not None:
            name_lower = clean_name.lower()
            is_init = any(k in name_lower for k in ('initiation', 'governance'))
            if not (existing.scope_no == 0 and not is_init):
                return existing.scope_no

        # 2. Check if clean_name represents standard Scope 0 Initiation & Governance
        name_lower = clean_name.lower()
        if any(k in name_lower for k in ('initiation', 'governance')):
            return 0

        # 3. Check existing scope numbers currently in this project
        project_scopes = self.env['project.manage.scope'].sudo().search([
            ('project_id', '=', self.id)
        ])
        used_numbers = set()
        for s in project_scopes:
            if s.scope_no is not None:
                s_lower = (s.scope or '').lower()
                if s.scope_no == 0 and not any(k in s_lower for k in ('initiation', 'governance')):
                    continue
                used_numbers.add(s.scope_no)

        # 4. If preferred or parsed cand_no is valid and unused (> 0, not in used_numbers)
        if cand_no is not None and cand_no > 0 and cand_no not in used_numbers:
            return cand_no

        # 5. Otherwise allocate next sequential number (max + 1, minimum 1)
        if used_numbers:
            return max(max(used_numbers) + 1, 1)
        return 1

    def action_sync_imported_scopes(self):
        """Sync and merge any unlinked scopes (project_id=False, e.g. from generic Excel import)
        or duplicate scopes into this project, transferring responsible employees, accountable, and dates.
        """
        for project in self:
            project._heal_project_scope_numbers()
            today = fields.Date.context_today(project)

            # 1. Consolidate internal duplicates within this project
            item_groups = {}
            for sc in project.scope_ids:
                key = (sc.item_id or '').strip().upper() if sc.item_id else ((sc.scope or '').strip().lower(), (sc.name or '').strip().lower())
                item_groups.setdefault(key, []).append(sc)

            dups_to_remove = self.env['project.manage.scope']
            for key, sc_list in item_groups.items():
                if len(sc_list) > 1:
                    primary = max(
                        sc_list,
                        key=lambda s: (
                            bool(s.responsible_ids or s.responsible_id),
                            bool(s.start_date and s.start_date != today),
                            bool(s.evidence_proof),
                            s.id,
                        )
                    )
                    for dup in sc_list:
                        if dup.id != primary.id:
                            p_vals = {}
                            if not primary.responsible_ids and dup.responsible_ids:
                                p_vals['responsible_ids'] = [(6, 0, dup.responsible_ids.ids)]
                                p_vals['responsible_id'] = dup.responsible_ids[0].id
                            elif not primary.responsible_id and dup.responsible_id:
                                p_vals['responsible_ids'] = [(4, dup.responsible_id.id)]
                                p_vals['responsible_id'] = dup.responsible_id.id
                            if not primary.accountable_id and dup.accountable_id:
                                p_vals['accountable_id'] = dup.accountable_id.id
                            if (not primary.start_date or primary.start_date == today) and dup.start_date:
                                p_vals['start_date'] = dup.start_date
                            if (not primary.end_date or primary.end_date == today) and dup.end_date:
                                p_vals['end_date'] = dup.end_date
                            if not primary.evidence_proof and dup.evidence_proof:
                                p_vals['evidence_proof'] = dup.evidence_proof
                            if p_vals:
                                primary.write(p_vals)
                            dups_to_remove |= dup
            if dups_to_remove:
                dups_to_remove.unlink()

            # 2. Merge unlinked scopes (project_id = False) into this project
            unlinked_scopes = self.env['project.manage.scope'].sudo().search([('project_id', '=', False)])
            if unlinked_scopes:
                current_project_items = {(s.item_id or '').strip().upper(): s for s in project.scope_ids if s.item_id}
                current_project_names = {(s.name or '').strip().lower(): s for s in project.scope_ids if s.name}
                to_unlink = self.env['project.manage.scope']

                for u in unlinked_scopes:
                    target = None
                    u_item_key = (u.item_id or '').strip().upper()
                    u_name_key = (u.name or '').strip().lower()

                    if u_item_key and u_item_key in current_project_items:
                        target = current_project_items[u_item_key]
                    elif u_name_key and u_name_key in current_project_names:
                        target = current_project_names[u_name_key]

                    if target:
                        update_vals = {}
                        if u.responsible_ids:
                            update_vals['responsible_ids'] = [(6, 0, u.responsible_ids.ids)]
                            update_vals['responsible_id'] = u.responsible_ids[0].id
                        elif u.responsible_id:
                            update_vals['responsible_ids'] = [(4, u.responsible_id.id)]
                            update_vals['responsible_id'] = u.responsible_id.id
                        if u.accountable_id:
                            update_vals['accountable_id'] = u.accountable_id.id
                        if u.start_date:
                            update_vals['start_date'] = u.start_date
                        if u.end_date:
                            update_vals['end_date'] = u.end_date
                        if u.item_type and not target.item_type:
                            update_vals['item_type'] = u.item_type
                        if u.evidence_proof and not target.evidence_proof:
                            update_vals['evidence_proof'] = u.evidence_proof
                        if u.priority and u.priority != '0' and target.priority == '0':
                            update_vals['priority'] = u.priority
                        if update_vals:
                            target.write(update_vals)
                        to_unlink |= u
                    else:
                        u.write({'project_id': project.id})

                if to_unlink:
                    to_unlink.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Scopes Synced'),
                'message': _('Successfully synced and linked imported tasks to project "%s".', self[:1].name if self else ''),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_load_standard_scopes(self):
        self.ensure_one()
        import os
        from odoo import tools
        try:
            csv_path = tools.file_path('project_manage/data/default_scope_data.csv')
        except (FileNotFoundError, AttributeError, ValueError):
            csv_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'data', 'default_scope_data.csv'))

        if not csv_path or not os.path.exists(csv_path):
            raise UserError(_('Default scope data template file not found.'))

        with open(csv_path, 'rb') as f:
            data = f.read()

        wizard = self.env['project.scope.import.wizard'].create({
            'project_id': self.id,
            'file': base64.b64encode(data),
            'filename': 'default_scope_data.csv',
            'import_mode': 'append',
        })
        return wizard.action_import()

    @api.model
    def _group_expand_states(self, states, domain=None, *args, **kwargs):
        return [key for key, _val in self._fields['state'].selection]

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_('End date cannot be before start date.'))

    # ---- Button actions ----
    def action_start(self):
        for rec in self:
            if rec.state != 'todo':
                raise UserError(_('Only projects in "To Do" can be started.'))
            rec.state = 'in_progress'
            if not rec.date_start:
                rec.date_start = fields.Date.context_today(rec)

    def action_done(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('Only projects "In Progress" can be marked as done.'))
            rec.state = 'done'

    def action_cancel(self):
        for rec in self:
            if rec.state in ('done', 'cancelled'):
                raise UserError(_('This project is already closed.'))
            rec.state = 'cancelled'

    def action_reset_todo(self):
        self.write({'state': 'todo'})

    def _register_hook(self):
        super()._register_hook()
        # Automatically ensure all projects calculate progress strictly from scope completion
        try:
            projects = self.search([])
            if projects:
                projects._heal_project_scope_numbers()
                projects._compute_metrics()
        except Exception:
            pass

    @api.model
    def get_dashboard_data(self, team_id=None, project_id=None, view_as_role=None, **kwargs):
        today = fields.Date.today()
        user = self.env.user

        # ---- User Role Identification & Privileges ----
        is_actual_admin = (
            user.has_group('project_manage.group_project_manage_administrator') or
            user.has_group('base.group_system') or
            user.has_group('base.group_erp_manager') or
            (hasattr(user, '_is_admin') and user._is_admin())
        )
        is_actual_ceo = is_actual_admin or user.has_group('project_manage.group_project_manage_ceo')
        is_actual_vp = is_actual_ceo or user.has_group('project_manage.group_project_manage_vp')
        is_actual_manager = is_actual_vp or user.has_group('project_manage.group_project_manage_manager')
        is_actual_tl = is_actual_manager or user.has_group('project_manage.group_project_manage_team_lead')

        # Allow Administrators / Executives to preview specific role views
        if (is_actual_admin or is_actual_ceo) and view_as_role:
            target_role = str(view_as_role).strip().lower()
        elif is_actual_admin:
            target_role = 'admin'
        elif is_actual_ceo:
            target_role = 'ceo'
        elif user.has_group('project_manage.group_project_manage_vp'):
            target_role = 'vp'
        elif user.has_group('project_manage.group_project_manage_manager'):
            target_role = 'manager'
        elif user.has_group('project_manage.group_project_manage_team_lead'):
            target_role = 'team_lead'
        elif user.has_group('project_manage.group_project_manage_consultant'):
            target_role = 'consultant'
        else:
            raise AccessError(_("You do not have access rights to the Project Management module."))

        # Only Project Manager, CEO, VP, and Admin can see all teams' data and create projects
        can_see_all_teams = target_role in ('admin', 'ceo', 'vp', 'manager')
        can_create_project = target_role in ('admin', 'ceo', 'vp', 'manager')

        if target_role == 'ceo':
            role_code = 'ceo'
            role_name = 'Chief Executive Officer'
            role_badge = '💼 CEO'
            role_badge_class = 'pm-role-ceo'
        elif target_role == 'admin':
            role_code = 'admin'
            role_name = 'Administrator'
            role_badge = '👑 Administrator'
            role_badge_class = 'pm-role-admin'
        elif target_role == 'vp':
            role_code = 'vp'
            role_name = 'Vice President (VP)'
            role_badge = '⭐ Vice President'
            role_badge_class = 'pm-role-vp'
        elif target_role == 'manager':
            role_code = 'manager'
            role_name = 'Project Manager'
            role_badge = '📋 Project Manager'
            role_badge_class = 'pm-role-manager'
        elif target_role == 'team_lead':
            role_code = 'team_lead'
            role_name = 'Team Lead'
            role_badge = '👥 Team Lead'
            role_badge_class = 'pm-role-lead'
        else:
            role_code = 'consultant'
            role_name = 'Consultant'
            role_badge = '💻 Consultant'
            role_badge_class = 'pm-role-consultant'

        emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        emp_ids = emp.ids if emp else []

        # Team Scope: Executives & Managers see all teams; Team Leads see only their team; Consultants see their team
        if can_see_all_teams:
            all_teams = self.env['project.manage.team'].search([])
            user_teams = all_teams
        elif role_code == 'consultant':
            user_teams = self.env['project.manage.team'].search([('member_ids', 'in', [user.id])])
            all_teams = user_teams
        else:
            user_teams = self.env['project.manage.team'].search([
                '|',
                ('team_lead_id', '=', user.id),
                ('member_ids', 'in', [user.id])
            ])
            if not user_teams and emp:
                assigned_projects = self.search([
                    '|',
                    ('team_lead_id', '=', emp.id),
                    ('consultant_ids', 'in', [emp.id])
                ])
                user_teams = assigned_projects.mapped('team_id')
            all_teams = user_teams

        if user_teams:
            user_team_name = user_teams[0].name
        elif emp:
            user_team_name = f"Team {emp.name}"
        else:
            user_team_name = f"Team {user.name}"

        # Project Search Domain: Consultants see all projects where they have assigned tasks or are assigned members
        if role_code == 'consultant':
            cons_task_domain = ['|', '|', '|',
                ('responsible_ids.user_id', '=', user.id),
                ('responsible_ids', 'in', emp_ids),
                ('responsible_id.user_id', '=', user.id),
                ('responsible_id', 'in', emp_ids)] if emp_ids else ['|', ('responsible_ids.user_id', '=', user.id), ('responsible_id.user_id', '=', user.id)]
            assigned_project_ids = self.env['project.manage.scope'].sudo().search(cons_task_domain).mapped('project_id').ids
            proj_domain = ['|', '|',
                ('id', 'in', assigned_project_ids),
                ('consultant_ids', 'in', emp_ids) if emp_ids else ('id', 'in', assigned_project_ids),
                ('team_id.member_ids', 'in', [user.id])
            ]
            all_base_projects = self.sudo().search(proj_domain)
        elif can_see_all_teams:
            domain = []
            if team_id:
                if str(team_id).startswith('lead_'):
                    try:
                        lead_emp_id = int(str(team_id).replace('lead_', ''))
                        domain.append(('team_lead_id', '=', lead_emp_id))
                    except (ValueError, TypeError):
                        pass
                elif str(team_id).isdigit():
                    domain.append(('team_id', '=', int(team_id)))
            all_base_projects = self.search(domain)
        else:
            domain = []
            if all_teams:
                if team_id and str(team_id).isdigit() and int(team_id) in all_teams.ids:
                    domain.append(('team_id', '=', int(team_id)))
                elif team_id and str(team_id).startswith('lead_'):
                    try:
                        lead_emp_id = int(str(team_id).replace('lead_', ''))
                        domain.append(('team_lead_id', '=', lead_emp_id))
                    except (ValueError, TypeError):
                        pass
                else:
                    domain.append(('team_id', 'in', all_teams.ids))
            elif team_id and str(team_id).startswith('lead_'):
                try:
                    lead_emp_id = int(str(team_id).replace('lead_', ''))
                    domain.append(('team_lead_id', '=', lead_emp_id))
                except (ValueError, TypeError):
                    pass
            elif emp:
                domain.append(('team_lead_id', '=', emp.id))
            else:
                domain.append(('team_lead_id.user_id', '=', user.id))
            all_base_projects = self.search(domain)

        # Build real project filter options for the project dropdown
        filter_projects = []
        for p in all_base_projects:
            filter_projects.append({
                'id': p.id,
                'name': p.name,
                'team_id': p.team_id.id if p.team_id else False,
                'team_name': p.team_id.name if p.team_id else '',
                'health': p.health or 'good',
                'risk_level': p.risk_level or 'low',
                'condition': p.condition or 'on_plan',
                'progress': int(round(p.progress or 0)),
                'running_status': p.running_status or 'running',
            })

        # Apply project filter
        selected_project_id = int(project_id) if project_id and str(project_id).isdigit() else None
        selected_proj = None
        if selected_project_id:
            projects = all_base_projects.filtered(lambda p: p.id == selected_project_id)
            if not projects:
                single_p = self.sudo().browse(selected_project_id)
                if single_p.exists():
                    projects = single_p
            if projects:
                selected_proj = projects[0]
        else:
            projects = all_base_projects

        total_projects = len(projects)
        running_projects = projects.filtered(lambda p: p.running_status == 'running')
        completed_projects = projects.filtered(lambda p: p.running_status == 'completed')
        on_hold_projects = projects.filtered(lambda p: p.running_status == 'on_hold')
        not_started_projects = projects.filtered(lambda p: p.running_status == 'not_started')

        health_good = projects.filtered(lambda p: p.health == 'good')
        health_fair = projects.filtered(lambda p: p.health == 'fair')
        health_poor = projects.filtered(lambda p: p.health == 'poor')

        risk_low = projects.filtered(lambda p: p.risk_level == 'low')
        risk_med = projects.filtered(lambda p: p.risk_level == 'medium')
        risk_high = projects.filtered(lambda p: p.risk_level == 'high')

        cond_ahead = projects.filtered(lambda p: p.condition == 'ahead')
        cond_on_plan = projects.filtered(lambda p: p.condition == 'on_plan')
        cond_behind = projects.filtered(lambda p: p.condition == 'behind')
        cond_overdue = projects.filtered(lambda p: p.condition == 'overdue')
        cond_max_count = 1 if (selected_project_id and selected_proj) else max(len(cond_ahead), len(cond_on_plan), len(cond_behind), len(cond_overdue), 1)

        circ = 238.8
        if selected_project_id and selected_proj:
            p_health = selected_proj.health or 'good'
            if p_health == 'good':
                overall_health_score = 100
                good_arc = circ
                fair_arc = 0.0
                poor_arc = 0.0
            elif p_health == 'fair':
                overall_health_score = 60
                good_arc = 0.0
                fair_arc = circ
                poor_arc = 0.0
            else:
                overall_health_score = 20
                good_arc = 0.0
                fair_arc = 0.0
                poor_arc = circ

            p_risk = selected_proj.risk_level or 'low'
            if p_risk == 'high':
                risk_needle_angle = 50
            elif p_risk == 'medium':
                risk_needle_angle = 0
            else:
                risk_needle_angle = -50

            on_time_pct = 100 if selected_proj.condition in ('ahead', 'on_plan') else 0
            avg_progress = int(round(selected_proj.progress or 0))
        else:
            overall_health_score = round(
                ((len(health_good) * 100) + (len(health_fair) * 60) + (len(health_poor) * 20)) / total_projects
            ) if total_projects else 100

            good_c = len(health_good)
            fair_c = len(health_fair)
            poor_c = len(health_poor)
            if total_projects:
                good_arc = round((good_c / total_projects) * circ, 1)
                fair_arc = round((fair_c / total_projects) * circ, 1)
                poor_arc = round((poor_c / total_projects) * circ, 1)
            else:
                good_arc = circ
                fair_arc = 0.0
                poor_arc = 0.0

            if len(risk_high) >= 2:
                risk_needle_angle = 50
            elif len(risk_high) == 1:
                risk_needle_angle = 30
            elif len(risk_med) > 0:
                risk_needle_angle = 0
            else:
                risk_needle_angle = -50

            on_time_count = len(cond_ahead) + len(cond_on_plan)
            on_time_pct = round((on_time_count / total_projects) * 100) if total_projects else 100
            avg_progress = round(sum(projects.mapped('progress')) / total_projects) if total_projects else 0

        donut_good_dash = f"{good_arc} {circ}"
        donut_good_offset = "0"
        donut_fair_dash = f"{fair_arc} {circ}"
        donut_fair_offset = f"-{good_arc}"
        donut_poor_dash = f"{poor_arc} {circ}"
        donut_poor_offset = f"-{round(good_arc + fair_arc, 1)}"

        # Build real teams data from database
        teams_data = []
        filter_teams = []

        if all_teams:
            for tm in all_teams:
                filter_teams.append({
                    'id': tm.id,
                    'name': tm.name,
                    'lead_name': tm.team_lead_id.name if tm.team_lead_id else '',
                })
                if can_see_all_teams and team_id:
                    if str(team_id).isdigit() and tm.id != int(team_id):
                        continue
                    elif str(team_id).startswith('lead_'):
                        continue

                tm_projects = tm.project_ids
                if not can_see_all_teams:
                    tm_projects = tm_projects.filtered(lambda p: p in projects)
                tm_tot = len(tm_projects)
                tm_healthy = len(tm_projects.filtered(lambda p: p.health == 'good'))
                tm_progress = round(sum(tm_projects.mapped('progress')) / tm_tot) if tm_tot else 0
                tm_on_time = round((len(tm_projects.filtered(lambda p: p.condition in ('ahead', 'on_plan'))) / tm_tot) * 100) if tm_tot else 0

                # Real Quality Score: percentage of completed/reviewed tasks in this team's projects
                tm_scopes = tm_projects.mapped('scope_ids')
                if tm_scopes:
                    done_scopes = len(tm_scopes.filtered(lambda s: s.state in ('done', 'under_review')))
                    tm_quality = round((done_scopes / len(tm_scopes)) * 100)
                elif tm_tot:
                    tm_quality = tm_progress
                else:
                    tm_quality = 0

                # Real Utilisation: ratio of active projects to team members
                if tm.member_ids:
                    active_p = len(tm_projects.filtered(lambda p: p.running_status == 'running'))
                    tm_util = min(round((active_p / len(tm.member_ids)) * 100), 100)
                elif tm_tot:
                    tm_util = 100
                else:
                    tm_util = 0

                if not tm_tot:
                    rating = 'No Projects'
                    rating_class = 'text-bg-secondary'
                    trend_text = '0 projects'
                    trend_color = 'info'
                elif tm_progress >= 85:
                    rating = 'Excellent'
                    rating_class = 'text-bg-success'
                    var = round(sum((p.progress - p.planned_progress) for p in tm_projects) / tm_tot)
                    trend_text = f"+{var} pts vs plan" if var > 0 else (f"{var} pts vs plan" if var < 0 else "On plan")
                    trend_color = 'success'
                elif tm_progress >= 60:
                    rating = 'Good'
                    rating_class = 'text-bg-primary'
                    var = round(sum((p.progress - p.planned_progress) for p in tm_projects) / tm_tot)
                    trend_text = f"+{var} pts vs plan" if var > 0 else (f"{var} pts vs plan" if var < 0 else "On plan")
                    trend_color = 'info' if var >= 0 else 'warning'
                else:
                    rating = 'Needs support'
                    rating_class = 'text-bg-warning'
                    var = round(sum((p.progress - p.planned_progress) for p in tm_projects) / tm_tot)
                    trend_text = f"{var} pts vs plan"
                    trend_color = 'danger'

                teams_data.append({
                    'id': tm.id,
                    'name': tm.name,
                    'lead_name': tm.team_lead_id.name if tm.team_lead_id else 'Unassigned',
                    'members_count': len(tm.member_ids),
                    'projects_count': tm_tot,
                    'healthy_count': tm_healthy,
                    'productivity': tm_progress,
                    'quality': tm_quality,
                    'on_time': tm_on_time,
                    'utilisation': tm_util,
                    'rating': rating,
                    'rating_class': rating_class,
                    'trend_text': trend_text,
                    'trend_color': trend_color,
                })
        else:
            # If no Project Teams have been created in project.manage.team yet,
            # derive actual teams dynamically from assigned Team Leads on projects
            leads = projects.mapped('team_lead_id')
            for idx, lead in enumerate(leads, 1):
                lead_projects = projects.filtered(lambda p: p.team_lead_id == lead)
                if can_see_all_teams and team_id:
                    if str(team_id).startswith('lead_') and str(team_id) != f"lead_{lead.id}":
                        continue
                    elif str(team_id).isdigit():
                        continue
                tm_tot = len(lead_projects)
                tm_healthy = len(lead_projects.filtered(lambda p: p.health == 'good'))
                tm_progress = round(sum(lead_projects.mapped('progress')) / tm_tot) if tm_tot else 0
                tm_on_time = round((len(lead_projects.filtered(lambda p: p.condition in ('ahead', 'on_plan'))) / tm_tot) * 100) if tm_tot else 0

                tm_scopes = lead_projects.mapped('scope_ids')
                if tm_scopes:
                    done_scopes = len(tm_scopes.filtered(lambda s: s.state in ('done', 'under_review')))
                    tm_quality = round((done_scopes / len(tm_scopes)) * 100)
                else:
                    tm_quality = tm_progress

                consultants = lead_projects.mapped('consultant_ids')
                tm_util = min(round((len(lead_projects.filtered(lambda p: p.running_status == 'running')) / (len(consultants) or 1)) * 100), 100) if consultants else 100

                var = round(sum((p.progress - p.planned_progress) for p in lead_projects) / tm_tot) if tm_tot else 0
                trend_text = f"+{var} pts vs plan" if var > 0 else (f"{var} pts vs plan" if var < 0 else "On plan")
                rating = 'Excellent' if tm_progress >= 85 else ('Good' if tm_progress >= 60 else 'Needs support')

                # Check if there is an existing team assigned to any of these projects
                proj_teams = lead_projects.mapped('team_id').filtered(lambda t: t)
                real_team = proj_teams[0] if proj_teams else False
                team_card_id = real_team.id if real_team else f"lead_{lead.id}"

                teams_data.append({
                    'id': team_card_id,
                    'name': real_team.name if real_team else f"Team {lead.name}",
                    'lead_name': lead.name,
                    'members_count': len(consultants),
                    'projects_count': tm_tot,
                    'healthy_count': tm_healthy,
                    'productivity': tm_progress,
                    'quality': tm_quality,
                    'on_time': tm_on_time,
                    'utilisation': tm_util,
                    'rating': rating,
                    'rating_class': 'text-bg-success' if rating == 'Excellent' else ('text-bg-primary' if rating == 'Good' else 'text-bg-warning'),
                    'trend_text': trend_text,
                    'trend_color': 'success' if var >= 0 else 'danger',
                })

                filter_teams.append({
                    'id': team_card_id,
                    'name': real_team.name if real_team else f"Team {lead.name}",
                    'lead_name': lead.name,
                })

        # Build real project rows
        projects_list = []
        for p in projects:
            days_late = (today - p.date_end).days if p.date_end and today > p.date_end and p.state != 'done' else 0
            variance = round(p.progress - p.planned_progress)
            var_str = f"+{variance} pts" if variance > 0 else (f"{variance} pts" if variance < 0 else "on plan")
            late_str = f" · {days_late}d late" if days_late > 0 else ""
            due_date_formatted = p.date_end.strftime('%d %b') if p.date_end else 'No due date'
            projects_list.append({
                'id': p.id,
                'name': p.name,
                'client_name': p.partner_id.name or 'No Client',
                'client_city': p.partner_id.city or (p.partner_id.country_id.name if p.partner_id.country_id else ''),
                'team_id': p.team_id.id if p.team_id else False,
                'team_name': p.team_id.name or (f"Team {p.team_lead_id.name}" if p.team_lead_id else 'No Team'),
                'running_status': p.running_status or 'running',
                'running_status_label': dict(p._fields['running_status'].selection).get(p.running_status, 'Running'),
                'health': p.health or 'good',
                'health_label': dict(p._fields['health'].selection).get(p.health, 'Good'),
                'risk_level': p.risk_level or 'low',
                'risk_level_label': dict(p._fields['risk_level'].selection).get(p.risk_level, 'Low'),
                'progress': int(round(p.progress or 0)),
                'planned_progress': int(round(p.planned_progress or 0)),
                'due_date_str': f"{due_date_formatted}{late_str}",
                'variance_str': var_str,
                'condition': p.condition or 'on_plan',
                'condition_label': dict(p._fields['condition'].selection).get(p.condition, 'On plan'),
                'scope_count': p.scope_count,
                'doc_count': p.doc_count,
                'imp_count': p.imp_count,
                'total_tasks': len(p.scope_ids),
                'done_tasks': len(p.scope_ids.filtered(lambda s: s.state == 'done')),
                'review_count': p.review_count,
                'average_rating': p.average_rating,
            })

        # Consultant count: If project selected, consultants on that project; else Executive/Team Lead count
        team_members = all_teams.mapped('member_ids') if all_teams else self.env['res.users']
        team_member_emps = self.env['hr.employee'].sudo().search([('user_id', 'in', team_members.ids)]) if team_members else self.env['hr.employee']
        proj_consultants = projects.mapped('consultant_ids')

        if selected_project_id and selected_proj:
            assigned_emps = selected_proj.consultant_ids
            task_emps = (selected_proj.scope_ids.mapped('responsible_ids') | selected_proj.scope_ids.mapped('responsible_id'))
            all_consultants = len(assigned_emps | task_emps)
        elif can_see_all_teams:
            all_consultants = self.env['hr.employee'].sudo().search_count([])
        else:
            all_consultants = len(team_member_emps | proj_consultants)

        Scope = self.env['project.manage.scope']
        # Active pending scopes in database across approval stages
        if selected_project_id:
            all_pending_scopes = Scope.search([
                ('approval_state', 'in', ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo')),
                ('project_id', '=', selected_project_id)
            ])
        elif can_see_all_teams:
            all_pending_scopes = Scope.search([('approval_state', 'in', ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'))])
        else:
            all_pending_scopes = Scope.search([
                ('approval_state', 'in', ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo')),
                ('project_id', 'in', projects.ids)
            ])
        all_pending_count = len(all_pending_scopes)

        # Pending items targeted to current user based on their specific approval tier:
        # User requirement: Only show approval requests waiting for THEIR action (do not show other roles' approvals)
        if role_code in ('admin', 'ceo'):
            # Only items awaiting CEO approval (or if personally assigned as manager/TL of that project)
            my_pending_scopes = all_pending_scopes.filtered(
                lambda s: s.approval_state == 'pending_ceo' or
                (s.approval_state == 'pending_pm' and (
                    (s.project_id.manager_id.user_id == user) or
                    (emp and s.project_id.manager_id == emp)
                )) or
                (s.approval_state == 'pending_tl' and (
                    (s.project_id.team_lead_id.user_id == user) or
                    (emp and s.project_id.team_lead_id == emp) or
                    (s.project_id.team_id.team_lead_id == user)
                ))
            )
        elif role_code == 'vp':
            # Only items awaiting Vice President approval (or if personally assigned as manager/TL of that project)
            my_pending_scopes = all_pending_scopes.filtered(
                lambda s: s.approval_state == 'pending_vp' or
                (s.approval_state == 'pending_pm' and (
                    (s.project_id.manager_id.user_id == user) or
                    (emp and s.project_id.manager_id == emp)
                )) or
                (s.approval_state == 'pending_tl' and (
                    (s.project_id.team_lead_id.user_id == user) or
                    (emp and s.project_id.team_lead_id == emp) or
                    (s.project_id.team_id.team_lead_id == user)
                ))
            )
        elif role_code == 'manager':
            # Only items awaiting Project Manager approval for their projects
            my_pending_scopes = all_pending_scopes.filtered(
                lambda s: (
                    s.approval_state == 'pending_pm' and (
                        (s.project_id.manager_id.user_id == user) or
                        (emp and s.project_id.manager_id == emp) or
                        (not s.project_id.manager_id)
                    )
                ) or (
                    # Fallback: if project has no Team Lead assigned at all, PM acts as first reviewer
                    s.approval_state == 'pending_tl' and (
                        (s.project_id.manager_id.user_id == user or (emp and s.project_id.manager_id == emp)) and
                        not s.project_id.team_lead_id and
                        not s.project_id.team_id.team_lead_id
                    )
                )
            )
        elif role_code == 'team_lead':
            # Only items awaiting Team Lead approval for their team / projects
            my_pending_scopes = all_pending_scopes.filtered(
                lambda s: s.approval_state == 'pending_tl' and (
                    (s.project_id.team_lead_id.user_id == user) or
                    (emp and s.project_id.team_lead_id == emp) or
                    (s.project_id.team_id.team_lead_id == user) or
                    (s.project_id in projects) or
                    (s.project_id.team_id in all_teams)
                )
            )
        else:
            my_pending_scopes = Scope.browse()

        pending_items = []
        for s in my_pending_scopes[:20]:
            pending_items.append({
                'id': s.id,
                'name': s.name,
                'code': s.code or (f"S{s.scope_no:02d}" if s.scope_no is not None else '') or s.item_id or '',
                'scope': s.scope or '',
                'project_id': s.project_id.id if s.project_id else False,
                'project_name': s.project_id.name if s.project_id else 'General Project',
                'responsible_name': ', '.join(s.responsible_ids.sudo().mapped('name')) if s.responsible_ids else (s.responsible_id.sudo().name if s.responsible_id else (s.responsible or 'Unassigned')),
                'submitted_by': s.submitted_by_id.sudo().name if s.submitted_by_id else (s.responsible_ids[:1].sudo().name if s.responsible_ids else (s.responsible_id.sudo().name if s.responsible_id else 'Team Member')),
                'submitted_date': s.submitted_date.strftime('%d %b %H:%M') if s.submitted_date else '',
                'approval_state': s.approval_state,
                'approval_stage_label': dict(s._fields['approval_state'].selection).get(s.approval_state, ''),
                'can_approve': bool(s.can_user_approve),
            })

        # ---- Universal Role-Based Tasks Hub (Pending & Completed Tasks) ----
        # Requirement:
        # - Pending tasks = all active tasks assigned to employee not completed (state != 'done' and state != 'cancelled')
        # - Completed tasks = state == 'done'
        # - Consultant: only their assigned tasks (completed and pending)
        # - Team Lead: all consultants in his team / projects (pending and completed)
        # - Project Manager: all tasks under his projects (pending and completed)
        # - Executive (VP, CEO, Admin): all tasks across portfolio / selected team
        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not current_emp and user.email:
            current_emp = self.env['hr.employee'].sudo().search([('work_email', '=ilike', user.email.strip())], limit=1)
        if not current_emp and user.name:
            current_emp = self.env['hr.employee'].sudo().search([('name', '=ilike', user.name.strip())], limit=1)
        emp_ids = current_emp.ids if current_emp else []

        tl_projects = self.search([
            '|', '|', '|',
            ('team_lead_id', 'in', emp_ids),
            ('team_lead_id.user_id', '=', user.id),
            ('team_id.team_lead_id', '=', user.id),
            ('team_id', 'in', user_teams.ids if user_teams else [])
        ]) if role_code == 'team_lead' else self.env['project.manage']
        if role_code == 'team_lead' and not tl_projects and projects:
            tl_projects = projects

        pm_projects = self.search([
            '|', ('manager_id', 'in', emp_ids),
            ('manager_id.user_id', '=', user.id)
        ]) if role_code == 'manager' else self.env['project.manage']
        if role_code == 'manager' and not pm_projects and projects:
            pm_projects = projects

        if role_code == 'consultant':
            cons_filter = ['|', '|', '|',
                ('responsible_ids.user_id', '=', user.id),
                ('responsible_ids', 'in', emp_ids),
                ('responsible_id.user_id', '=', user.id),
                ('responsible_id', 'in', emp_ids)] if emp_ids else ['|', ('responsible_ids.user_id', '=', user.id), ('responsible_id.user_id', '=', user.id)]
            if selected_project_id:
                hub_domain = [('project_id', '=', selected_project_id)] + cons_filter
            else:
                hub_domain = cons_filter
        elif selected_project_id:
            # When specific project selected, Tasks Hub strictly focuses on this chosen project
            hub_domain = [('project_id', '=', selected_project_id)]
        elif role_code == 'team_lead':
            # Team Lead sees tasks for all consultants in his team / projects
            hub_domain = ['|', ('project_id', 'in', tl_projects.ids), '|', '|', '|',
                ('responsible_ids.user_id', '=', user.id),
                ('responsible_ids', 'in', emp_ids),
                ('responsible_id.user_id', '=', user.id),
                ('responsible_id', 'in', emp_ids)]
        elif role_code == 'manager':
            # Project Manager sees all tasks under his projects
            hub_domain = ['|', ('project_id', 'in', pm_projects.ids), '|', '|', '|',
                ('responsible_ids.user_id', '=', user.id),
                ('responsible_ids', 'in', emp_ids),
                ('responsible_id.user_id', '=', user.id),
                ('responsible_id', 'in', emp_ids)]
        else:
            # Executive (VP, CEO, Admin)
            if team_id:
                if str(team_id).startswith('lead_'):
                    try:
                        lead_emp_id = int(str(team_id).replace('lead_', ''))
                        team_projects = self.search([('team_lead_id', '=', lead_emp_id)])
                    except (ValueError, TypeError):
                        team_projects = self.env['project.manage']
                elif str(team_id).isdigit():
                    team_projects = self.search([('team_id', '=', int(team_id))])
                else:
                    team_projects = self.env['project.manage']
                hub_domain = [('project_id', 'in', team_projects.ids)]
            else:
                hub_domain = []

        # Auto-sync any unlinked scopes (project_id = False) to the active project so Tasks Hub displays actual project name
        unlinked_count = Scope.sudo().search_count([('project_id', '=', False)])
        if unlinked_count:
            target_proj = None
            if selected_project_id:
                target_proj = self.browse(selected_project_id)
            if not target_proj or not target_proj.exists():
                active_projs = self.sudo().search([('state', 'in', ('todo', 'in_progress'))], order='write_date desc')
                if active_projs:
                    target_proj = active_projs[0]
            if target_proj and target_proj.exists():
                target_proj.action_sync_imported_scopes()

        all_hub_scopes = Scope.search(hub_domain, order='end_date asc, id desc')

        # Filter strictly by definition:
        # Pending: active tasks not completed (state != 'done' and state != 'cancelled' and approval_state != 'approved')
        # All assigned tasks appear in pending tasks regardless of whether dates have been issued yet.
        completed_scopes = all_hub_scopes.filtered(lambda s: s.state == 'done' or s.approval_state == 'approved')
        pending_scopes = all_hub_scopes.filtered(
            lambda s: s.state not in ('done', 'cancelled') and s.approval_state != 'approved'
        )
        overdue_scopes = pending_scopes.filtered(lambda s: s.end_date and today > s.end_date)
        waiting_approval_scopes = all_hub_scopes.filtered(
            lambda s: s.approval_state in ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo')
        )

        # Collect unique consultants and projects for filtering
        consultants_map = {}
        projects_map = {}
        for s in all_hub_scopes:
            for remp in (s.responsible_ids | s.responsible_id):
                consultants_map[remp.id] = remp.name
            if s.project_id:
                projects_map[s.project_id.id] = s.project_id.name

        available_consultants = [{'id': cid, 'name': cname} for cid, cname in sorted(consultants_map.items(), key=lambda x: x[1])]
        available_projects = [{'id': pid, 'name': pname} for pid, pname in sorted(projects_map.items(), key=lambda x: x[1])]

        def _serialize_task(s):
            is_completed = bool(s.state == 'done' or s.approval_state == 'approved')
            is_late = bool(s.end_date and today > s.end_date and not is_completed)
            is_pending = bool(s.state not in ('done', 'cancelled') and not is_completed)
            is_assigned_to_user = bool(
                (user in s.responsible_ids.mapped('user_id')) or
                (current_emp and current_emp in s.responsible_ids) or
                (s.responsible_id and (
                    (s.responsible_id.user_id == user) or
                    (current_emp and s.responsible_id == current_emp)
                )) or
                (user.name and any(r.name and r.name.lower() == user.name.lower() for r in (s.responsible_ids | s.responsible_id)))
            )
            is_eligible_to_complete = bool(is_assigned_to_user or is_actual_admin)
            can_submit = bool(
                is_eligible_to_complete and
                s.approval_state not in ('approved', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo') and
                s.state != 'done'
            )
            resp_name = ', '.join(s.responsible_ids.mapped('name')) if s.responsible_ids else (s.responsible_id.name if s.responsible_id else (s.responsible or 'Unassigned'))
            return {
                'id': s.id,
                'name': s.name,
                'code': s.code or (f"S{s.scope_no:02d}" if s.scope_no is not None else '') or s.item_id or '',
                'scope': s.scope or '',
                'project_id': s.project_id.id if s.project_id else False,
                'project_name': s.project_id.name if s.project_id else 'General Project',
                'team_name': s.project_id.team_id.name if s.project_id and s.project_id.team_id else '',
                'category': s.category or 'Documentation',
                'priority': s.priority or '0',
                'priority_int': int(s.priority or 0),
                'responsible_id': s.responsible_id.id if s.responsible_id else (s.responsible_ids[:1].id if s.responsible_ids else False),
                'responsible_ids': s.responsible_ids.ids if s.responsible_ids else ([s.responsible_id.id] if s.responsible_id else []),
                'responsible_names': s.responsible_ids.mapped('name') if s.responsible_ids else ([s.responsible_id.name] if s.responsible_id else []),
                'responsible_name': resp_name,
                'start_date': s.start_date.strftime('%Y-%m-%d') if s.start_date else '',
                'start_date_str': s.start_date.strftime('%d %b %Y') if s.start_date else '-',
                'end_date': s.end_date.strftime('%Y-%m-%d') if s.end_date else '',
                'end_date_str': s.end_date.strftime('%d %b %Y') if s.end_date else 'No deadline',
                'is_late': is_late,
                'is_overdue': is_late,
                'is_pending': is_pending,
                'is_completed': is_completed,
                'state': s.state or 'todo',
                'state_label': dict(s._fields['state'].selection).get(s.state, 'To Do'),
                'approval_state': s.approval_state or 'draft',
                'approval_stage_label': dict(s._fields['approval_state'].selection).get(s.approval_state, 'Draft'),
                'can_submit': can_submit,
                'can_approve': bool(s.can_user_approve),
                'rejection_reason': s.rejection_reason or '',
            }

        def _task_sort_key(s):
            pri_weight = -(int(s.priority or 0))
            is_late = bool(s.end_date and today > s.end_date and s.state != 'done')
            is_pend = bool(s.state not in ('done', 'cancelled') and s.approval_state != 'approved')
            if is_pend and is_late:
                return (pri_weight, 0, s.end_date or fields.Date.today())
            if is_pend:
                return (pri_weight, 1, s.end_date or fields.Date.from_string('2099-12-31'))
            if s.approval_state in ('pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'):
                return (pri_weight, 2, s.end_date or fields.Date.from_string('2099-12-31'))
            if s.state == 'done' or s.approval_state == 'approved':
                return (pri_weight, 3, s.end_date or fields.Date.from_string('2000-01-01'))
            return (pri_weight, 4, s.end_date or fields.Date.from_string('2099-12-31'))

        # Ensure completed, waiting approval, and overdue tasks are NEVER truncated,
        # plus serialize all hub scopes up to 5000 to easily cover large enterprise projects.
        critical_scopes = completed_scopes | waiting_approval_scopes | overdue_scopes
        other_scopes = all_hub_scopes - critical_scopes
        combined_scopes = list(critical_scopes) + list(other_scopes[:max(0, 5000 - len(critical_scopes))])
        sorted_scopes = sorted(combined_scopes, key=_task_sort_key)
        tasks_list = [_serialize_task(s) for s in sorted_scopes]

        if selected_project_id and selected_proj:
            if role_code == 'consultant':
                hub_title = f"{selected_proj.name} Tasks"
                hub_subtitle = f"Your assigned deliverables and tasks in {selected_proj.name}"
                hub_role_label = "My Tasks"
            else:
                hub_title = f"{selected_proj.name} Tasks Hub"
                hub_subtitle = f"All consultant tasks for project '{selected_proj.name}'"
                hub_role_label = "Project Tasks"
        elif role_code == 'consultant':
            hub_title = "My Tasks Workspace"
            hub_subtitle = "Track your assigned pending tasks and completed deliverables"
            hub_role_label = "My Tasks"
        elif role_code == 'team_lead':
            hub_title = "Team Lead Tasks Hub"
            hub_subtitle = f"All consultant tasks across {len(tl_projects)} team project(s)"
            hub_role_label = "Team Tasks"
        elif role_code == 'manager':
            hub_title = "Project Manager Tasks Hub"
            hub_subtitle = f"All tasks across {len(pm_projects)} project(s) under your management"
            hub_role_label = "Project Tasks"
        else:
            hub_title = "Enterprise Tasks Hub"
            hub_subtitle = "Executive tracking of pending deliverables and completed tasks across all projects"
            hub_role_label = "All Tasks"

        tasks_hub_data = {
            'role_code': role_code,
            'title': hub_title,
            'subtitle': hub_subtitle,
            'role_label': hub_role_label,
            'total_count': len(all_hub_scopes),
            'pending_count': len(pending_scopes),
            'completed_count': len(completed_scopes),
            'overdue_count': len(overdue_scopes),
            'waiting_approval_count': len(waiting_approval_scopes),
            'available_consultants': available_consultants,
            'available_projects': available_projects,
            'tasks': tasks_list,
        }

        # ---- Consultant Top Performers Leaderboard (Actual Database Calculations) ----
        if selected_project_id:
            all_emp_scopes = Scope.sudo().search([
                '|', ('responsible_ids', '!=', False), ('responsible_id', '!=', False),
                ('project_id', '=', selected_project_id)
            ])
        elif can_see_all_teams:
            all_emp_scopes = Scope.sudo().search(['|', ('responsible_ids', '!=', False), ('responsible_id', '!=', False)])
        else:
            all_emp_scopes = Scope.sudo().search([
                '|', ('responsible_ids', '!=', False), ('responsible_id', '!=', False),
                ('project_id', 'in', projects.ids)
            ])
        emp_stats = {}
        for sc in all_emp_scopes:
            emps = sc.sudo().responsible_ids or sc.sudo().responsible_id
            for emp in emps:
                if not emp or not emp.id:
                    continue
                if emp.id not in emp_stats:
                    emp_stats[emp.id] = {
                        'id': emp.id,
                        'name': emp.sudo().name or 'Consultant',
                        'job': emp.sudo().job_title or 'Consultant',
                        'total': 0,
                        'completed': 0,
                        'on_time': 0,
                        'in_review': 0,
                    }
                st = emp_stats[emp.id]
                st['total'] += 1
                if sc.state == 'done':
                    st['completed'] += 1
                    if not sc.end_date or not sc.last_approval_date or sc.last_approval_date.date() <= sc.end_date:
                        st['on_time'] += 1
                elif sc.state == 'under_review':
                    st['in_review'] += 1

        top_performers = []
        for emp_id, st in emp_stats.items():
            tot = st['total']
            comp = st['completed']
            comp_rate = round((comp / tot) * 100) if tot else 0
            on_time_rate = round((st['on_time'] / comp) * 100) if comp else 100
            score = round((comp_rate * 0.6) + (on_time_rate * 0.4))
            badge = '🏆 Top Performer' if score >= 85 else ('⭐ High Achiever' if score >= 65 else '🚀 Rising Star')
            badge_class = 'pm-badge-gold' if score >= 85 else ('pm-badge-silver' if score >= 65 else 'pm-badge-bronze')
            top_performers.append({
                'id': emp_id,
                'name': st['name'],
                'role': st['job'],
                'total_tasks': tot,
                'completed_tasks': comp,
                'in_review_tasks': st['in_review'],
                'completion_rate': comp_rate,
                'on_time_rate': on_time_rate,
                'score': score,
                'badge': badge,
                'badge_class': badge_class,
            })

        # Fallback to database employees if scopes are not yet assigned to responsible_id
        if not top_performers:
            if selected_project_id and selected_proj:
                fallback_emps = (selected_proj.consultant_ids | selected_proj.scope_ids.mapped('responsible_ids') | selected_proj.scope_ids.mapped('responsible_id'))[:10]
            elif can_see_all_teams:
                fallback_emps = self.env['hr.employee'].sudo().search([], limit=10)
            else:
                fallback_emps = (team_member_emps | proj_consultants)[:10]
            for emp in fallback_emps:
                top_performers.append({
                    'id': emp.id,
                    'name': emp.sudo().name or 'Consultant',
                    'role': emp.sudo().job_title or 'Consultant',
                    'total_tasks': 0,
                    'completed_tasks': 0,
                    'in_review_tasks': 0,
                    'completion_rate': 0,
                    'on_time_rate': 100,
                    'score': 0,
                    'badge': '🚀 Ready to Perform',
                    'badge_class': 'pm-badge-bronze',
                })

        top_performers.sort(key=lambda x: (x['score'], x['completed_tasks']), reverse=True)
        for idx, tp in enumerate(top_performers, 1):
            tp['rank'] = idx
        if role_code == 'consultant':
            top_performers = []

        # ---- Consultant Task Stats for Bar Charts & Condition Breakdown ----
        total_cons_tasks = len(all_hub_scopes)
        completed_cons_tasks = len(completed_scopes)
        not_completed_cons_tasks = total_cons_tasks - completed_cons_tasks
        cons_completion_pct = round((completed_cons_tasks / total_cons_tasks) * 100) if total_cons_tasks else 0
        cons_not_completed_pct = 100 - cons_completion_pct if total_cons_tasks else 0

        consultant_projects_breakdown = []
        target_projects_for_breakdown = projects if selected_project_id else all_base_projects
        for p in target_projects_for_breakdown:
            p_scopes = all_hub_scopes.filtered(lambda s: s.project_id.id == p.id)
            if not p_scopes and role_code != 'consultant' and p.scope_ids:
                p_scopes = p.scope_ids
            if not p_scopes:
                continue
            p_completed = len(p_scopes.filtered(lambda s: s.state == 'done'))
            p_not_completed = len(p_scopes.filtered(lambda s: s.state != 'done'))
            p_total = len(p_scopes)
            p_overdue = len(p_scopes.filtered(lambda s: s.state != 'done' and s.end_date and today > s.end_date))
            p_pct = round((p_completed / p_total) * 100) if p_total else 0
            consultant_projects_breakdown.append({
                'project_id': p.id,
                'project_name': p.name,
                'total': p_total,
                'completed': p_completed,
                'not_completed': p_not_completed,
                'overdue': p_overdue,
                'completed_pct': p_pct,
                'not_completed_pct': 100 - p_pct if p_total else 0,
            })
        consultant_projects_breakdown.sort(key=lambda x: x['total'], reverse=True)

        consultant_task_stats = {
            'total': total_cons_tasks,
            'completed': completed_cons_tasks,
            'not_completed': not_completed_cons_tasks,
            'overdue': len(overdue_scopes),
            'pending': len(pending_scopes),
            'waiting_approval': len(waiting_approval_scopes),
            'completion_pct': cons_completion_pct,
            'not_completed_pct': cons_not_completed_pct,
            'projects_breakdown': consultant_projects_breakdown,
        }

        # ---- Build Rich Calendar Events (Tasks Only) ----
        # NOTE: The calendar is strictly a Task Schedule / Deadline Calendar. Projects are excluded per user requirement.
        calendar_events = []
        for p in projects:
            for s in p.scope_ids:
                task_date = s.end_date
                if task_date:
                    is_task_late = bool(s.end_date and today > s.end_date and s.state != 'done')
                    days_rem_task = (task_date - today).days
                    calendar_events.append({
                        'id': f"task_{s.id}",
                        'record_id': s.id,
                        'project_id': p.id,
                        'project_name': p.name,
                        'team_id': p.team_id.id if p.team_id else (f"lead_{p.team_lead_id.id}" if p.team_lead_id else False),
                        'team_name': p.team_id.name if p.team_id else (f"Team {p.team_lead_id.name}" if p.team_lead_id else ''),
                        'model': 'project.manage.scope',
                        'type': 'task',
                        'title': s.name,
                        'code': s.code or (f"S{s.scope_no:02d}" if s.scope_no is not None else '') or s.item_id or '',
                        'category': s.category or 'Documentation',
                        'item_type': s.item_type or '',
                        'responsible_name': ', '.join(s.responsible_ids.sudo().mapped('name')) if s.responsible_ids else (s.responsible_id.sudo().name if s.responsible_id else (s.responsible or 'Unassigned')),
                        'start_date': s.start_date.strftime('%Y-%m-%d') if s.start_date else '',
                        'end_date': task_date.strftime('%Y-%m-%d'),
                        'date': task_date.strftime('%Y-%m-%d'),
                        'date_str': task_date.strftime('%d %b %Y'),
                        'status': s.state or 'todo',
                        'status_label': dict(s._fields['state'].selection).get(s.state, 'To Do'),
                        'approval_state': s.approval_state or 'draft',
                        'approval_label': dict(s._fields['approval_state'].selection).get(s.approval_state, 'Draft'),
                        'is_overdue': is_task_late,
                        'days_remaining': days_rem_task,
                    })

        return {
            'company_name': self.env.company.name,
            'current_date_str': today.strftime('%d %B %Y'),
            'user_info': {
                'id': user.id,
                'name': user.name,
                'role_code': role_code,
                'role_name': role_name,
                'role_badge': role_badge,
                'role_badge_class': role_badge_class,
                'is_admin': is_actual_admin,
                'is_ceo': is_actual_ceo or role_code in ('admin', 'ceo'),
                'is_vp': is_actual_admin or is_actual_ceo or role_code in ('admin', 'ceo', 'vp'),
                'is_manager': is_actual_admin or role_code in ('admin', 'ceo', 'vp', 'manager'),
                'is_team_lead': is_actual_admin or role_code in ('admin', 'ceo', 'vp', 'manager', 'team_lead'),
                'is_consultant': role_code == 'consultant' and not is_actual_admin,
                'is_executive': is_actual_admin or is_actual_ceo or role_code in ('admin', 'ceo', 'vp'),
                'can_approve': True if (is_actual_admin or is_actual_ceo) else role_code in ('vp', 'manager', 'team_lead'),
                'can_create_project': can_create_project,
                'can_see_all_teams': can_see_all_teams,
                'can_switch_roles': False,
                'active_view_mode': role_code,
            },
            'user_team_name': user_team_name,
            'approvals_summary': {
                'pending_my_approval_count': len(pending_items),
                'all_pending_count': all_pending_count,
                'pending_items': pending_items,
            },
            'consultant_workspace': {
                'my_total_tasks': len(pending_scopes) if role_code == 'consultant' else len(all_hub_scopes),
                'my_todo_count': len(all_hub_scopes.filtered(lambda s: s.state == 'todo')),
                'my_inprogress_count': len(all_hub_scopes.filtered(lambda s: s.state == 'in_progress')),
                'my_waiting_approval_count': len(waiting_approval_scopes),
                'my_done_count': len(completed_scopes),
                'my_rejected_count': len(all_hub_scopes.filtered(lambda s: s.approval_state == 'rejected')),
                'my_tasks': tasks_list,
            },
            'tasks_hub': tasks_hub_data,
            'top_performers': top_performers,
            'total_projects': total_projects,
            'total_teams': len(teams_data),
            'total_consultants': all_consultants,
            'running_count': len(running_projects),
            'completed_count': len(completed_projects),
            'on_hold_count': len(on_hold_projects),
            'not_started_count': len(not_started_projects),
            'health_good_count': len(health_good),
            'health_fair_count': len(health_fair),
            'health_poor_count': len(health_poor),
            'overall_health_score': overall_health_score,
            'overall_health_label': 'Good' if overall_health_score >= 70 else ('Fair' if overall_health_score >= 50 else 'Poor'),
            'risk_low_count': len(risk_low),
            'risk_med_count': len(risk_med),
            'risk_high_count': len(risk_high),
            'risk_status_label': 'High risk' if len(risk_high) >= 2 else ('Low to medium risk' if len(risk_high) > 0 or len(risk_med) > 0 else 'Low risk'),
            'on_time_pct': on_time_pct,
            'avg_progress': avg_progress,
            'condition_ahead_count': len(cond_ahead),
            'condition_on_plan_count': len(cond_on_plan),
            'condition_behind_count': len(cond_behind),
            'condition_overdue_count': len(cond_overdue),
            'cond_max_count': cond_max_count,
            'donut_good_dash': donut_good_dash,
            'donut_good_offset': donut_good_offset,
            'donut_fair_dash': donut_fair_dash,
            'donut_fair_offset': donut_fair_offset,
            'donut_poor_dash': donut_poor_dash,
            'donut_poor_offset': donut_poor_offset,
            'risk_needle_angle': risk_needle_angle,
            'teams': teams_data,
            'all_teams_filter': filter_teams,
            'projects': projects_list,
            'all_projects_filter': filter_projects,
            'selected_project_id': selected_project_id,
            'selected_project_name': selected_proj.name if selected_proj else '',
            'calendar_events': calendar_events,
            'consultant_task_stats': consultant_task_stats,
        }

    # ---- Dashboard Quick Actions ----
    @api.model
    def action_dashboard_start_scope(self, scope_id):
        scope = self.env['project.manage.scope'].browse(scope_id)
        if scope.exists():
            scope.action_start()
            return True
        return False

    @api.model
    def action_dashboard_approve_scope(self, scope_id, note=None):
        scope = self.env['project.manage.scope'].browse(scope_id)
        if scope.exists():
            scope.action_approve_level(note=note)
            return True
        return False

    @api.model
    def action_dashboard_reject_scope(self, scope_id, reason=None):
        scope = self.env['project.manage.scope'].browse(scope_id)
        if scope.exists():
            scope.action_reject_level(reason=reason)
            return True
        return False

    @api.model
    def action_dashboard_submit_scope(self, scope_id):
        scope = self.env['project.manage.scope'].browse(scope_id)
        if scope.exists():
            scope.action_submit_for_approval()
            return True
        return False

    @api.model
    def get_project_scopes_dashboard(self, project_id):
        """Return all Scopes, Documentation, and Implementation tasks under a project

        with color codes, category filters, and summary stats for dashboard management.
        """
        project = self.browse(project_id)
        if not project.exists():
            return {'project': {}, 'scopes': [], 'unique_scopes': [], 'stats': {}}
        try:
            project.check_access('read')
        except Exception:
            return {'project': {}, 'scopes': [], 'unique_scopes': [], 'stats': {}}

        today = fields.Date.context_today(self)
        user = self.env.user
        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        is_admin = (
            user.has_group('project_manage.group_project_manage_administrator') or
            user.has_group('base.group_system') or
            user.id in (1, 2)
        )

        # Auto-sync and consolidate any imported or unlinked scopes into this project
        project._heal_project_scope_numbers()
        project.action_sync_imported_scopes()

        scopes_data = []
        scopes = self.env['project.manage.scope'].sudo().search(
            [('project_id', '=', project.id)],
            order='scope_no asc, category asc, item_no asc, id asc'
        )

        unique_scopes = []
        scope_map = {}

        for s in scopes:
            is_overdue = s.end_date and today > s.end_date and s.state != 'done'

            # Status color mapping:
            # - Green: Completed / Done
            # - Blue: In Progress
            # - Yellow: Pending / Waiting Review / Approval
            # - Red: Overdue / Cancelled / Rejected
            # - Slate: To Do / Draft
            status_full_label = ''
            if s.state == 'done':
                status_color = 'green'
                status_label = 'Completed'
                status_full_label = 'Completed'
            elif s.state == 'in_progress':
                status_color = 'blue'
                status_label = 'In Progress'
                status_full_label = 'In Progress'
            elif s.state in ('under_review', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo') or (s.approval_state and s.approval_state.startswith('pending')):
                status_color = 'yellow'
                status_full_label = dict(s._fields['approval_state'].selection).get(s.approval_state, 'Under Review')
                approval_short_map = {
                    'pending_tl': 'Waiting TL',
                    'pending_pm': 'Waiting PM',
                    'pending_vp': 'Waiting VP',
                    'pending_ceo': 'Waiting CEO',
                    'under_review': 'Under Review',
                }
                status_label = approval_short_map.get(s.approval_state, 'Waiting TL')
            elif is_overdue or s.state == 'cancelled':
                status_color = 'red'
                status_label = 'Overdue' if is_overdue else 'Cancelled'
                status_full_label = 'Overdue' if is_overdue else 'Cancelled'
            elif s.approval_state == 'rejected':
                status_color = 'red'
                status_label = 'Re-Work'
                status_full_label = 'Rejected / Re-Work Needed'
            else:
                status_color = 'slate'
                status_label = 'To Do'
                status_full_label = 'To Do'

            # Category color mapping:
            # - Documentation: Blue pill
            # - Implementation: Purple pill
            # - Scope: Teal pill
            cat_str = str(s.category or 'Documentation').strip()
            cat_lower = cat_str.lower()
            if 'doc' in cat_lower:
                category_color = 'blue'
                category_label = 'Documentation'
                cat_badge_class = 'pm-cat-doc'
                cat_icon = 'fa-file-text-o'
            elif 'imp' in cat_lower:
                category_color = 'purple'
                category_label = 'Implementation'
                cat_badge_class = 'pm-cat-imp'
                cat_icon = 'fa-cogs'
            else:
                category_color = 'teal'
                category_label = cat_str or 'Scope'
                cat_badge_class = 'pm-cat-scope'
                cat_icon = 'fa-folder-o'

            scope_name = s.scope or f"Scope {s.scope_no if s.scope_no is not None else 0}"
            if scope_name not in scope_map:
                scope_map[scope_name] = {
                    'name': scope_name,
                    'scope_no': s.scope_no if s.scope_no is not None else 0,
                    'total': 0,
                    'done': 0,
                }
                unique_scopes.append(scope_map[scope_name])
            scope_map[scope_name]['total'] += 1
            if s.state == 'done':
                scope_map[scope_name]['done'] += 1

            scopes_data.append({
                'id': s.id,
                'priority': s.priority or '0',
                'priority_int': int(s.priority or 0),
                'item_id': s.item_id or f"ITEM-{s.id}",
                'code': s.code or (f"S{s.scope_no:02d}" if s.scope_no is not None else '') or s.item_id or '',
                'scope_no': s.scope_no if s.scope_no is not None else 0,
                'scope': s.scope or '',
                'scope_name': scope_name,
                'name': s.name or s.item_id or 'Untitled Task',
                'category': cat_str,
                'category_color': category_color,
                'category_label': category_label,
                'cat_badge_class': cat_badge_class,
                'cat_icon': cat_icon,
                'item_type': s.item_type or '',
                'evidence_proof': s.evidence_proof or '',
                'state': s.state or 'todo',
                'status_color': status_color,
                'status_label': status_label,
                'status_full_label': status_full_label,
                'approval_state': s.approval_state or 'draft',
                'responsible_id': s.responsible_id.id if s.responsible_id else (s.responsible_ids[:1].id if s.responsible_ids else False),
                'responsible_ids': s.responsible_ids.ids if s.responsible_ids else ([s.responsible_id.id] if s.responsible_id else []),
                'responsible_names': s.responsible_ids.mapped('name') if s.responsible_ids else ([s.responsible_id.name] if s.responsible_id else []),
                'responsible_name': ', '.join(s.responsible_ids.mapped('name')) if s.responsible_ids else (s.responsible_id.name if s.responsible_id else (s.responsible or 'Unassigned')),
                'start_date': s.start_date.strftime('%Y-%m-%d') if s.start_date else '',
                'start_date_str': s.start_date.strftime('%d %b %Y') if s.start_date else '',
                'end_date': s.end_date.strftime('%Y-%m-%d') if s.end_date else '',
                'end_date_str': s.end_date.strftime('%d %b %Y') if s.end_date else 'No deadline',
                'is_overdue': bool(is_overdue),
                'rejection_reason': s.rejection_reason or '',
                'can_start': s.state == 'todo' and bool(
                    is_admin or (
                        (user in s.responsible_ids.mapped('user_id')) or
                        (current_emp and current_emp in s.responsible_ids) or
                        (s.responsible_id and (
                            (s.responsible_id.user_id == user) or (current_emp and s.responsible_id == current_emp)
                        ))
                    )
                ),
                'can_submit': s.state in ('todo', 'in_progress') and bool(
                    is_admin or (
                        (user in s.responsible_ids.mapped('user_id')) or
                        (current_emp and current_emp in s.responsible_ids) or
                        (s.responsible_id and (
                            (s.responsible_id.user_id == user) or (current_emp and s.responsible_id == current_emp)
                        ))
                    )
                ) and s.approval_state not in ('approved', 'pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'),
                'can_approve': bool(s.can_user_approve),
            })

        total_count = len(scopes_data)
        doc_items = [s for s in scopes_data if 'doc' in s['category'].lower()]
        imp_items = [s for s in scopes_data if 'imp' in s['category'].lower()]
        done_items = [s for s in scopes_data if s['status_color'] == 'green']
        prog_items = [s for s in scopes_data if s['status_color'] == 'blue']
        pend_items = [s for s in scopes_data if s['status_color'] == 'yellow']
        over_items = [s for s in scopes_data if s['status_color'] == 'red']

        # Available employees & consultants for dropdown selection
        proj_emps = project.consultant_ids
        if project.team_lead_id:
            proj_emps |= project.team_lead_id
        if project.manager_id:
            proj_emps |= project.manager_id
        if project.team_id and project.team_id.member_ids:
            team_emps = self.env['hr.employee'].sudo().search([('user_id', 'in', project.team_id.member_ids.ids)])
            proj_emps |= team_emps

        all_active_emps = self.env['hr.employee'].sudo().search([('active', '=', True)], order='name asc')
        combo_emps = proj_emps | all_active_emps
        available_employees = [{'id': e.id, 'name': e.name} for e in combo_emps]

        # Sort unique scopes strictly by scope_no ascending
        unique_scopes.sort(key=lambda x: (
            0 if x.get('scope_no') == 0 else (x.get('scope_no') or 99999),
            x.get('name', '')
        ))

        return {
            'project': {
                'id': project.id,
                'name': project.name,
                'client_name': project.partner_id.name or 'No Client',
                'team_name': project.team_id.name or (f"Team {project.team_lead_id.name}" if project.team_lead_id else 'No Team'),
                'progress': int(round(project.progress or 0)),
                'planned_progress': int(round(project.planned_progress or 0)),
                'running_status': project.running_status or 'running',
                'running_status_label': dict(project._fields['running_status'].selection).get(project.running_status, 'Running'),
                'health': project.health or 'good',
                'health_label': dict(project._fields['health'].selection).get(project.health, 'Good'),
                'risk_level': project.risk_level or 'low',
                'risk_level_label': dict(project._fields['risk_level'].selection).get(project.risk_level, 'Low'),
                'due_date_str': project.date_end.strftime('%d %b %Y') if project.date_end else 'No due date',
                'review_count': project.review_count,
                'average_rating': project.average_rating,
            },
            'scopes': scopes_data,
            'unique_scopes': unique_scopes,
            'available_employees': available_employees,
            'available_scopes': [s['name'] for s in unique_scopes],
            'stats': {
                'total_items': total_count,
                'total_scopes': len(unique_scopes),
                'total_docs': len(doc_items),
                'done_docs': len([d for d in doc_items if d['status_color'] == 'green']),
                'total_imps': len(imp_items),
                'done_imps': len([i for i in imp_items if i['status_color'] == 'green']),
                'completed_count': len(done_items),
                'in_progress_count': len(prog_items),
                'pending_count': len(pend_items),
                'overdue_count': len(over_items),
                'completion_pct': round((len(done_items) / total_count * 100)) if total_count else 0,
            }
        }

    @api.model
    def save_scope_inline(self, scope_id, vals):
        """Update a scope record inline from the dashboard and return refreshed scopes data."""
        scope = self.env['project.manage.scope'].browse(scope_id)
        if not scope.exists():
            return {'error': _("Scope item not found")}

        write_vals = {}
        if 'scope' in vals:
            raw_new = (vals['scope'] or '').strip()
            match = re.match(r'^(?:Scope|S)?\s*(\d+)\s*[-:]?\s*(.+)$', raw_new, re.IGNORECASE)
            new_scope = raw_new
            if match and not any(k in raw_new.lower() for k in ('initiation', 'governance')):
                new_scope = match.group(2).strip() or raw_new
            write_vals['scope'] = new_scope
            if new_scope and scope.project_id:
                new_no = scope.project_id._assign_next_scope_no(new_scope)
                write_vals['scope_no'] = new_no
                write_vals['code'] = f"S{new_no:02d}"
        if 'category' in vals and vals['category'] in ('Documentation', 'Implementation'):
            write_vals['category'] = vals['category']
        if 'name' in vals and vals['name']:
            write_vals['name'] = vals['name']
        if 'item_type' in vals:
            write_vals['item_type'] = vals['item_type']
        if 'priority' in vals and str(vals['priority']) in ('0', '1', '2', '3'):
            write_vals['priority'] = str(vals['priority'])
        if 'responsible_ids' in vals:
            raw_ids = vals['responsible_ids'] or []
            emp_ids = [int(i) for i in raw_ids if str(i).isdigit()]
            write_vals['responsible_ids'] = [(6, 0, emp_ids)]
            if emp_ids:
                write_vals['responsible_id'] = emp_ids[0]
                emps = self.env['hr.employee'].sudo().browse(emp_ids)
                write_vals['responsible'] = ', '.join(emps.mapped('name'))
            else:
                write_vals['responsible_id'] = False
                write_vals['responsible'] = ''
        elif 'responsible_id' in vals:
            raw_emp = vals['responsible_id']
            emp_id = int(raw_emp) if raw_emp and str(raw_emp).isdigit() else False
            write_vals['responsible_id'] = emp_id
            if emp_id:
                write_vals['responsible_ids'] = [(6, 0, [emp_id])]
                emp = self.env['hr.employee'].sudo().browse(emp_id)
                write_vals['responsible'] = emp.name if emp.exists() else ''
            else:
                write_vals['responsible_ids'] = [(5, 0, 0)]
                write_vals['responsible'] = ''
        if 'start_date' in vals:
            write_vals['start_date'] = vals['start_date'] or False
        if 'end_date' in vals:
            write_vals['end_date'] = vals['end_date'] or False
        if 'state' in vals and vals['state'] in ('todo', 'in_progress', 'under_review', 'done', 'cancelled'):
            new_st = vals['state']
            write_vals['state'] = new_st
            if new_st == 'done':
                write_vals['approval_state'] = 'approved'
            elif new_st == 'under_review':
                write_vals['approval_state'] = 'pending_tl'
                write_vals['submitted_by_id'] = self.env.user.id
                write_vals['submitted_date'] = fields.Datetime.now()
            elif new_st == 'in_progress' and scope.approval_state == 'draft':
                write_vals['approval_state'] = 'in_progress'
            elif new_st == 'todo':
                write_vals['approval_state'] = 'draft'

        scope.write(write_vals)
        if scope.project_id:
            scope.project_id._compute_metrics()

        return self.get_project_scopes_dashboard(scope.project_id.id)

    @api.model
    def create_scope_from_dashboard(self, project_id, vals):
        """Create a new scope record directly from the dashboard wizard and return refreshed data."""
        project = self.browse(project_id)
        if not project.exists():
            return {'error': _("Project not found")}

        # Heal existing numbers first to prevent anomalies
        project._heal_project_scope_numbers()

        raw_scope = (vals.get('scope') or '').strip()
        scope_str = raw_scope
        match = re.match(r'^(?:Scope|S)?\s*(\d+)\s*[-:]?\s*(.+)$', raw_scope, re.IGNORECASE)
        if match:
            cand_title = match.group(2).strip()
            if not any(k in raw_scope.lower() for k in ('initiation', 'governance')):
                scope_str = cand_title or raw_scope

        if not scope_str:
            scope_str = 'General Scope'

        scope_no = project._assign_next_scope_no(scope_str)

        cat_val = vals.get('category') or 'Documentation'
        cat_letter = 'I' if 'imp' in str(cat_val).lower() else 'D'

        existing_in_cat = self.env['project.manage.scope'].sudo().search([
            ('project_id', '=', project.id),
            ('scope_no', '=', scope_no),
            ('category', '=', cat_val),
        ])
        max_item = max([s.item_no for s in existing_in_cat if s.item_no] or [0])
        item_no = max_item + 1

        item_id = vals.get('item_id') or f"S{scope_no:02d}-{cat_letter}-{item_no:03d}"
        code = f"S{scope_no:02d}"

        raw_ids = vals.get('responsible_ids') or []
        emp_ids = [int(i) for i in raw_ids if str(i).isdigit()]
        if not emp_ids and vals.get('responsible_id'):
            raw_emp = vals.get('responsible_id')
            if raw_emp and str(raw_emp).isdigit():
                emp_ids = [int(raw_emp)]

        emp_name = ''
        if emp_ids:
            emps = self.env['hr.employee'].sudo().browse(emp_ids)
            emp_name = ', '.join(emps.mapped('name'))

        state_val = vals.get('state') or 'todo'
        appr_state = 'approved' if state_val == 'done' else ('in_progress' if state_val == 'in_progress' else 'draft')

        auth_val = vals.get('approval_authority') or get_default_approval_authority(
            item_id=item_id,
            scope_no=scope_no,
            category=cat_val,
            item_no=item_no,
            name=vals.get('name'),
        ) or 'TL'

        create_vals = {
            'project_id': project.id,
            'scope': scope_str,
            'scope_no': scope_no,
            'code': code,
            'item_id': item_id,
            'item_no': item_no,
            'category': cat_val,
            'name': vals.get('name') or 'Untitled Task',
            'item_type': vals.get('item_type') or '',
            'approval_authority': auth_val,
            'responsible_id': emp_ids[0] if emp_ids else False,
            'responsible_ids': [(6, 0, emp_ids)] if emp_ids else False,
            'responsible': emp_name,
            'start_date': vals.get('start_date') or False,
            'end_date': vals.get('end_date') or False,
            'state': state_val,
            'approval_state': appr_state,
            'priority': str(vals.get('priority') or '0'),
        }
        self.env['project.manage.scope'].create(create_vals)
        project._compute_metrics()
        return self.get_project_scopes_dashboard(project.id)

    @api.model
    def bulk_fill_scopes(self, project_id, scope_ids, vals):
        """Bulk update multiple scopes by IDs or by scope name from the dashboard bulk fill wizard."""
        project = self.browse(project_id)
        if not project.exists():
            return {'error': _("Project not found")}

        domain = [('project_id', '=', project.id)]
        if scope_ids and isinstance(scope_ids, list):
            domain.append(('id', 'in', scope_ids))
        elif vals.get('scope_name_filter'):
            domain.append(('scope', '=', vals['scope_name_filter']))

        scopes = self.env['project.manage.scope'].search(domain)
        write_vals = {}
        if vals.get('responsible_ids') and isinstance(vals['responsible_ids'], list):
            emp_ids = [int(eid) for eid in vals['responsible_ids'] if str(eid).isdigit()]
            emps = self.env['hr.employee'].sudo().browse(emp_ids)
            write_vals['responsible_ids'] = [(6, 0, emp_ids)]
            write_vals['responsible_id'] = emp_ids[0] if emp_ids else False
            write_vals['responsible'] = ', '.join(emps.mapped('name')) if emps else ''
        elif vals.get('responsible_id'):
            raw_emp = vals['responsible_id']
            emp_id = int(raw_emp) if raw_emp and str(raw_emp).isdigit() else False
            emp = self.env['hr.employee'].sudo().browse(emp_id)
            write_vals['responsible_id'] = emp_id
            write_vals['responsible_ids'] = [(6, 0, [emp_id])] if emp_id else [(5, 0, 0)]
            write_vals['responsible'] = emp.name if emp.exists() else ''
        elif vals.get('clear_responsible'):
            write_vals['responsible_id'] = False
            write_vals['responsible_ids'] = [(5, 0, 0)]
            write_vals['responsible'] = ''

        if vals.get('start_date'):
            write_vals['start_date'] = vals['start_date']

        if vals.get('end_date'):
            write_vals['end_date'] = vals['end_date']

        if vals.get('category') and vals['category'] in ('Documentation', 'Implementation'):
            write_vals['category'] = vals['category']

        if vals.get('priority') and str(vals['priority']) in ('0', '1', '2', '3'):
            write_vals['priority'] = str(vals['priority'])

        if vals.get('state') and vals['state'] in ('todo', 'in_progress', 'under_review', 'done', 'cancelled'):
            new_st = vals['state']
            write_vals['state'] = new_st
            if new_st == 'done':
                write_vals['approval_state'] = 'approved'
            elif new_st == 'under_review':
                write_vals['approval_state'] = 'pending_tl'
                write_vals['submitted_by_id'] = self.env.user.id
                write_vals['submitted_date'] = fields.Datetime.now()
            elif new_st == 'in_progress':
                write_vals['approval_state'] = 'in_progress'
            elif new_st == 'todo':
                write_vals['approval_state'] = 'draft'

        if write_vals:
            scopes.write(write_vals)
            project._compute_metrics()

        return self.get_project_scopes_dashboard(project.id)

    @api.model
    def get_new_project_form_data(self):
        """Return lists of Partners, Teams, Employees, and Tags for in-dashboard project creation."""
        user = self.env.user
        today = fields.Date.context_today(self)
        current_emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)

        # Clients & Coordinators (all active res.partner records sorted A-Z)
        partners = self.env['res.partner'].sudo().search_read(
            [('active', '=', True)],
            ['id', 'name', 'is_company'],
            order='name asc'
        )
        partners_list = [{
            'id': p['id'],
            'name': p['name'],
            'is_company': bool(p.get('is_company')),
        } for p in partners if p.get('name')]

        clients_list = partners_list
        coordinators_list = partners_list

        # Teams
        teams_data = []
        all_teams = self.env['project.manage.team'].sudo().search([('active', '=', True)], order='name asc')
        for tm in all_teams:
            lead_emp_id = False
            if tm.team_lead_id:
                emp = self.env['hr.employee'].sudo().search([('user_id', '=', tm.team_lead_id.id)], limit=1)
                if emp:
                    lead_emp_id = emp.id
            member_emp_ids = []
            if tm.member_ids:
                m_emps = self.env['hr.employee'].sudo().search([('user_id', 'in', tm.member_ids.ids)])
                member_emp_ids = m_emps.ids
            teams_data.append({
                'id': tm.id,
                'name': tm.name,
                'team_lead_emp_id': lead_emp_id,
                'member_emp_ids': member_emp_ids,
            })

        # Active Employees
        all_emps = self.env['hr.employee'].sudo().search_read(
            [('active', '=', True)],
            ['id', 'name', 'job_title', 'work_email', 'user_id'],
            order='name asc'
        )
        employees_list = [{
            'id': e['id'],
            'name': e['name'],
            'job_title': e.get('job_title') or '',
            'user_id': e['user_id'][0] if e.get('user_id') else False,
        } for e in all_emps]

        # Tags
        tags = self.env['project.manage.tag'].sudo().search_read([], ['id', 'name', 'color'], order='name asc')
        tags_list = [{'id': t['id'], 'name': t['name'], 'color': t.get('color', 0)} for t in tags]

        end_date = today + datetime.timedelta(days=90)

        return {
            'clients': clients_list,
            'coordinators': coordinators_list,
            'teams': teams_data,
            'employees': employees_list,
            'tags': tags_list,
            'default_manager_id': current_emp.id if current_emp else (employees_list[0]['id'] if employees_list else False),
            'default_date_start': today.strftime('%Y-%m-%d'),
            'default_date_end': end_date.strftime('%Y-%m-%d'),
        }

    @api.model
    def create_project_from_dashboard(self, vals):
        """Create a new project directly from the dashboard modal without navigating to backend."""
        user = self.env.user
        is_admin = (
            user.has_group('project_manage.group_project_manage_administrator') or
            user.has_group('base.group_system') or
            user.id in (1, 2)
        )
        can_create = (
            is_admin or
            user.has_group('project_manage.group_project_manage_ceo') or
            user.has_group('project_manage.group_project_manage_vp') or
            user.has_group('project_manage.group_project_manage_manager')
        )
        if not can_create:
            raise AccessError(_("You do not have permission to create projects. Only Project Managers, VP, CEO, and Administrators have project creation access."))

        name = (vals.get('name') or '').strip()
        if not name:
            raise UserError(_("Project Name is required."))

        partner_id = vals.get('partner_id')
        if not partner_id or not str(partner_id).isdigit():
            raise UserError(_("Client is required."))
        partner_id = int(partner_id)

        date_start = vals.get('date_start')
        date_end = vals.get('date_end')
        if not date_start or not date_end:
            raise UserError(_("Start Date and End Date are required."))

        manager_id = vals.get('manager_id')
        if not manager_id or not str(manager_id).isdigit():
            raise UserError(_("Project Manager is required."))
        manager_id = int(manager_id)

        team_lead_id = vals.get('team_lead_id')
        if not team_lead_id or not str(team_lead_id).isdigit():
            raise UserError(_("Team Lead is required."))
        team_lead_id = int(team_lead_id)

        raw_consultants = vals.get('consultant_ids') or []
        consultant_ids = [int(cid) for cid in raw_consultants if str(cid).isdigit()]
        if not consultant_ids:
            consultant_ids = [team_lead_id]

        client_coordinator_id = vals.get('client_coordinator_id')
        if client_coordinator_id and str(client_coordinator_id).isdigit():
            client_coordinator_id = int(client_coordinator_id)
        else:
            client_coordinator_id = partner_id

        project_coordinator_id = vals.get('project_coordinator_id')
        if project_coordinator_id and str(project_coordinator_id).isdigit():
            project_coordinator_id = int(project_coordinator_id)
        else:
            project_coordinator_id = False

        team_id = vals.get('team_id')
        if team_id and str(team_id).isdigit():
            team_id = int(team_id)
        else:
            team_id = False

        raw_tags = vals.get('tag_ids') or []
        tag_ids = [int(tid) for tid in raw_tags if str(tid).isdigit()]

        priority = str(vals.get('priority') or '0')

        project_vals = {
            'name': name,
            'partner_id': partner_id,
            'client_coordinator_id': client_coordinator_id,
            'date_start': date_start,
            'date_end': date_end,
            'manager_id': manager_id,
            'team_lead_id': team_lead_id,
            'project_coordinator_id': project_coordinator_id,
            'team_id': team_id,
            'consultant_ids': [(6, 0, consultant_ids)],
            'priority': priority,
            'state': 'todo',
        }
        if tag_ids:
            project_vals['tag_ids'] = [(6, 0, tag_ids)]

        new_project = self.create(project_vals)

        # Scope Import / Setup Options:
        import_file_b64 = vals.get('import_file')
        import_filename = vals.get('import_filename') or 'scopes_import.xlsx'
        import_mode = vals.get('import_mode') or 'append'
        load_standard_scopes = vals.get('load_standard_scopes', True)

        if import_file_b64:
            try:
                if ',' in import_file_b64:
                    import_file_b64 = import_file_b64.split(',', 1)[1]
                wizard = self.env['project.scope.import.wizard'].create({
                    'project_id': new_project.id,
                    'file': import_file_b64,
                    'filename': import_filename,
                    'import_mode': import_mode,
                })
                wizard.action_import()
            except Exception as e:
                raise UserError(_("Project created, but scope file import failed: %s") % str(e))
        elif load_standard_scopes:
            try:
                new_project.action_load_standard_scopes()
            except Exception:
                pass

        return {
            'success': True,
            'project_id': new_project.id,
            'project_name': new_project.name,
        }

    @api.model
    def get_default_scope_csv_template(self):
        """Return base64 encoded default scope CSV template for download."""
        import os
        from odoo import tools
        try:
            csv_path = tools.file_path('project_manage/data/default_scope_data.csv')
        except Exception:
            csv_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'data', 'default_scope_data.csv'))

        if not csv_path or not os.path.exists(csv_path):
            raise UserError(_('Default scope template file not found.'))

        with open(csv_path, 'rb') as f:
            data = f.read()

        return {
            'filename': 'project_scope_template.csv',
            'file_content': base64.b64encode(data).decode('utf-8'),
        }
